"""Kontenery i maszyny VM bez gniazda Dockera i bez libvirt API.

Gniazdo /var/run/docker.sock dawałoby pełną kontrolę nad serwerem, nawet zamontowane
„tylko do odczytu”. Zamiast tego czytamy pliki, które Docker i libvirt i tak zapisują:
- /var/lib/docker/containers/<id>/config.v2.json: nazwa, obraz i stan kontenera,
- cgroup kontenera (/sys/fs/cgroup): zużycie CPU i pamięci,
- /var/run/libvirt/qemu/*.pid i /etc/libvirt/qemu/*.xml: działające i zdefiniowane VM.
Wszystko montowane tylko do odczytu.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Kontener:
    id: str
    nazwa: str
    obraz: str
    dziala: bool
    stan: str            # ok (działa), uwaga (zatrzymany z błędem lub restartuje), szary (zatrzymany)
    cpu: float | None = None      # % jednego rdzenia, jak w docker stats
    ram_b: int | None = None


def _czytaj(sciezka: Path) -> str | None:
    try:
        return sciezka.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


class CzytnikDockera:
    def __init__(self, katalog_kontenerow: str = "/host/docker/containers", katalog_cgroup: str = "/host/cgroup"):
        self.kontenery = Path(katalog_kontenerow)
        self.cgroup = Path(katalog_cgroup)
        self._poprzednie_cpu: dict[str, tuple[float, int]] = {}
        self._cache: dict[str, tuple[float, dict]] = {}   # id -> (mtime, konfiguracja)

    @property
    def dostepny(self) -> bool:
        return self.kontenery.is_dir()

    def _konfiguracja(self, katalog: Path) -> dict | None:
        plik = katalog / "config.v2.json"
        try:
            mtime = plik.stat().st_mtime
        except OSError:
            return None
        zapis = self._cache.get(katalog.name)
        if zapis and zapis[0] == mtime:
            return zapis[1]
        tekst = _czytaj(plik)
        try:
            surowe = json.loads(tekst) if tekst else None
        except ValueError:
            return None
        if not isinstance(surowe, dict):
            return None
        # Zapamiętujemy tylko potrzebne pola (bez zmiennych środowiskowych z hasłami).
        stan = surowe.get("State") or {}
        konf = {"nazwa": str(surowe.get("Name", "")).lstrip("/"), "obraz": str((surowe.get("Config") or {}).get("Image", "")),
                "dziala": bool(stan.get("Running")), "restart": bool(stan.get("Restarting")),
                "kod": int(stan.get("ExitCode") or 0)}
        self._cache[katalog.name] = (mtime, konf)
        return konf

    def odczytaj(self) -> list[Kontener]:
        wynik = []
        try:
            katalogi = [k for k in self.kontenery.iterdir() if k.is_dir()]
        except OSError:
            return wynik
        for katalog in katalogi:
            konf = self._konfiguracja(katalog)
            if not konf or not konf["nazwa"]:
                continue
            if konf["restart"]:
                stan = "uwaga"
            elif konf["dziala"]:
                stan = "ok"
            else:
                stan = "uwaga" if konf["kod"] not in (0, 137, 143) else "szary"
            k = Kontener(id=katalog.name, nazwa=konf["nazwa"], obraz=konf["obraz"], dziala=konf["dziala"], stan=stan)
            if k.dziala:
                k.cpu, k.ram_b = self._zuzycie(k.id)
            wynik.append(k)
        wynik.sort(key=lambda k: k.nazwa.lower())
        aktualne = {k.id for k in wynik}
        self._poprzednie_cpu = {i: v for i, v in self._poprzednie_cpu.items() if i in aktualne}
        return wynik

    def _katalog_cgroup(self, id_: str) -> tuple[Path, str] | None:
        for sciezka in (self.cgroup / "docker" / id_, self.cgroup / "system.slice" / f"docker-{id_}.scope"):
            if (sciezka / "cpu.stat").exists():
                return sciezka, "v2"
        if (self.cgroup / "cpuacct" / "docker" / id_).exists():
            return self.cgroup, "v1"
        return None

    def _zuzycie(self, id_: str) -> tuple[float | None, int | None]:
        miejsce = self._katalog_cgroup(id_)
        if not miejsce:
            return None, None
        katalog, wersja = miejsce
        if wersja == "v2":
            m = re.search(r"usage_usec (\d+)", _czytaj(katalog / "cpu.stat") or "")
            cpu_ns = int(m.group(1)) * 1000 if m else None
            ram = _czytaj(katalog / "memory.current")
            # Jak docker stats: bez pamięci podręcznej plików (inactive_file).
            m_stat = re.search(r"inactive_file (\d+)", _czytaj(katalog / "memory.stat") or "")
        else:
            uzycie = _czytaj(katalog / "cpuacct" / "docker" / id_ / "cpuacct.usage")
            cpu_ns = int(uzycie) if uzycie and uzycie.strip().isdigit() else None
            ram = _czytaj(katalog / "memory" / "docker" / id_ / "memory.usage_in_bytes")
            m_stat = re.search(r"total_inactive_file (\d+)", _czytaj(katalog / "memory" / "docker" / id_ / "memory.stat") or "")
        ram_b = int(ram) - (int(m_stat.group(1)) if m_stat else 0) if ram and ram.strip().isdigit() else None
        cpu = None
        if cpu_ns is not None:
            teraz = time.monotonic_ns()
            poprzedni = self._poprzednie_cpu.get(id_)
            self._poprzednie_cpu[id_] = (cpu_ns, teraz)
            if poprzedni and teraz > poprzedni[1]:
                cpu = max(0.0, 100.0 * (cpu_ns - poprzedni[0]) / (teraz - poprzedni[1]))
        return cpu, max(0, ram_b) if ram_b is not None else None


@dataclass
class MaszynaVM:
    nazwa: str
    dziala: bool


def czytaj_vm(katalog_konfiguracji: str = "/host/libvirt-etc/qemu", katalog_stanu: str = "/host/libvirt-run/qemu") -> list[MaszynaVM]:
    """Zdefiniowane VM z plików XML, działające z plików .pid w katalogu stanu libvirt."""
    nazwy = set()
    try:
        for plik in Path(katalog_konfiguracji).glob("*.xml"):
            m = re.search(r"<name>([^<]+)</name>", _czytaj(plik) or "")
            nazwy.add(m.group(1) if m else plik.stem)
    except OSError:
        pass
    dzialajace = set()
    try:
        dzialajace = {p.stem for p in Path(katalog_stanu).glob("*.pid")}
    except OSError:
        pass
    return [MaszynaVM(n, n in dzialajace) for n in sorted(nazwy | dzialajace, key=str.lower)]


def aktualizacje_kontenerow(plik: str = "/host/docker-update-status.json") -> int | None:
    """Liczba obrazów z nowszą wersją wg sprawdzenia Unraida; None, gdy plik niedostępny."""
    tekst = _czytaj(Path(plik)) if os.path.isfile(plik) else None
    if not tekst:
        return None
    try:
        dane = json.loads(tekst)
    except ValueError:
        return None
    return sum(1 for v in dane.values() if isinstance(v, dict) and str(v.get("status")) == "false")
