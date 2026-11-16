"""Parametry systemu z /proc i /sys (CPU, rdzenie, RAM, SWAP, uptime, load, sieć, temperatura).

Odczyt jest tani: kilka małych plików tekstowych na cykl. Obciążenie CPU liczymy
z różnicy liczników /proc/stat między dwoma odczytami.
Ruch sieciowy bierzemy z /proc/1/net/dev hosta (proces 1 hosta widzi sieć serwera,
a nie sieć kontenera), dlatego kontener montuje /proc hosta tylko do odczytu.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

# Interfejsy pomijane przy liczeniu ruchu LAN (wirtualne, mostki kontenerów).
POMIJANE_PREFIKSY = ("lo", "docker", "veth", "virbr", "br-", "vnet", "tun", "tailscale", "wg")


@dataclass
class StanSystemu:
    cpu: float = 0.0
    rdzenie: list[float] = field(default_factory=list)
    cpu_temp: float | None = None
    ram_procent: float = 0.0
    ram_uzyte: int = 0
    ram_calkowite: int = 0
    swap_procent: float | None = None
    uptime_s: float = 0.0
    load: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rx_bps: float = 0.0
    tx_bps: float = 0.0


def _czytaj(sciezka: Path) -> str:
    return sciezka.read_text(encoding="ascii", errors="replace")


def parsuj_stat(tekst: str) -> dict[str, tuple[int, int]]:
    """Zwraca {nazwa_cpu: (bezczynny, razem)} z /proc/stat."""
    wynik = {}
    for linia in tekst.splitlines():
        if not linia.startswith("cpu"):
            continue
        czesci = linia.split()
        liczby = [int(x) for x in czesci[1:]]
        bezczynny = liczby[3] + (liczby[4] if len(liczby) > 4 else 0)  # idle + iowait
        # guest i guest_nice są już wliczone w user i nice
        razem = sum(liczby[:8])
        wynik[czesci[0]] = (bezczynny, razem)
    return wynik


def procent_cpu(poprzedni: tuple[int, int], obecny: tuple[int, int]) -> float:
    d_bezczynny = obecny[0] - poprzedni[0]
    d_razem = obecny[1] - poprzedni[1]
    if d_razem <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (1 - d_bezczynny / d_razem)))


def parsuj_meminfo(tekst: str) -> dict[str, int]:
    wynik = {}
    for linia in tekst.splitlines():
        klucz, _, reszta = linia.partition(":")
        czesci = reszta.split()
        if czesci:
            wynik[klucz] = int(czesci[0]) * 1024
    return wynik


def parsuj_net_dev(tekst: str) -> tuple[int, int]:
    """Suma bajtów odebranych i wysłanych przez fizyczne interfejsy."""
    rx = tx = 0
    for linia in tekst.splitlines()[2:]:
        nazwa, _, reszta = linia.partition(":")
        nazwa = nazwa.strip()
        if not reszta or nazwa.startswith(POMIJANE_PREFIKSY):
            continue
        pola = reszta.split()
        rx += int(pola[0])
        tx += int(pola[8])
    return rx, tx


def temperatura_cpu(katalog_sys: Path) -> float | None:
    """Szuka czujnika procesora (coretemp, k10temp, zenpower) w /sys/class/hwmon."""
    hwmon = katalog_sys / "class" / "hwmon"
    if not hwmon.is_dir():
        return None
    for czujnik in sorted(hwmon.iterdir()):
        try:
            nazwa = _czytaj(czujnik / "name").strip()
        except OSError:
            continue
        if nazwa not in ("coretemp", "k10temp", "zenpower", "cpu_thermal"):
            continue
        # Preferujemy "Package id 0" (Intel) albo "Tctl"/"Tdie" (AMD), inaczej pierwszy odczyt.
        odczyty = []
        for plik in sorted(czujnik.glob("temp*_input")):
            etykieta_plik = czujnik / plik.name.replace("_input", "_label")
            etykieta = _czytaj(etykieta_plik).strip() if etykieta_plik.exists() else ""
            try:
                wartosc = int(_czytaj(plik).strip()) / 1000
            except (OSError, ValueError):
                continue
            odczyty.append((etykieta, wartosc))
        for preferowana in ("Package id 0", "Tdie", "Tctl"):
            for etykieta, wartosc in odczyty:
                if etykieta == preferowana:
                    return wartosc
        if odczyty:
            return odczyty[0][1]
    return None


class CzytnikSystemu:
    def __init__(self, katalog_proc: str = "/proc", katalog_sys: str = "/sys", proc_sieci: str | None = None):
        self.proc = Path(katalog_proc)
        self.sys = Path(katalog_sys)
        # Plik z ruchem sieciowym hosta; domyślnie /proc/1/net/dev zamontowanego /proc hosta.
        self.plik_sieci = Path(proc_sieci) if proc_sieci else self.proc / "1" / "net" / "dev"
        self._poprzedni_stat: dict[str, tuple[int, int]] | None = None
        self._poprzednia_siec: tuple[float, int, int] | None = None

    def odczytaj(self) -> StanSystemu:
        stan = StanSystemu()

        stat = parsuj_stat(_czytaj(self.proc / "stat"))
        if self._poprzedni_stat:
            stan.cpu = procent_cpu(self._poprzedni_stat["cpu"], stat["cpu"])
            rdzenie = sorted((k for k in stat if k != "cpu"), key=lambda k: int(k[3:]))
            stan.rdzenie = [procent_cpu(self._poprzedni_stat.get(k, stat[k]), stat[k]) for k in rdzenie]
        self._poprzedni_stat = stat

        pamiec = parsuj_meminfo(_czytaj(self.proc / "meminfo"))
        stan.ram_calkowite = pamiec.get("MemTotal", 0)
        dostepne = pamiec.get("MemAvailable", pamiec.get("MemFree", 0))
        stan.ram_uzyte = max(0, stan.ram_calkowite - dostepne)
        if stan.ram_calkowite:
            stan.ram_procent = 100.0 * stan.ram_uzyte / stan.ram_calkowite
        swap = pamiec.get("SwapTotal", 0)
        if swap:
            stan.swap_procent = 100.0 * (swap - pamiec.get("SwapFree", 0)) / swap

        stan.uptime_s = float(_czytaj(self.proc / "uptime").split()[0])
        l1, l5, l15 = _czytaj(self.proc / "loadavg").split()[:3]
        stan.load = (float(l1), float(l5), float(l15))

        try:
            rx, tx = parsuj_net_dev(_czytaj(self.plik_sieci))
            teraz = time.monotonic()
            if self._poprzednia_siec:
                t0, rx0, tx0 = self._poprzednia_siec
                dt = teraz - t0
                if dt > 0:
                    stan.rx_bps = max(0.0, (rx - rx0) / dt)
                    stan.tx_bps = max(0.0, (tx - tx0) / dt)
            self._poprzednia_siec = (teraz, rx, tx)
        except OSError:
            pass

        stan.cpu_temp = temperatura_cpu(self.sys)
        return stan
