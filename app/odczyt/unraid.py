"""Stan array, dysków i parity z plików emhttp Unraida (/var/local/emhttp, tylko do odczytu).

emhttp (serwer WWW Unraida) co kilka sekund zapisuje stan w plikach ini:
- var.ini: stan array, wersja systemu, postęp i wynik kontroli parity,
- disks.ini: każdy dysk z nazwą, rolą, stanem, temperaturą, zajętością i uśpieniem,
- smart/<dysk>: wynik ostatniego odczytu SMART (smartctl).
Nie potrzeba klucza API ani dostępu do zapisu.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

LINIA_INI = re.compile(r'^\s*([A-Za-z0-9_.\-]+)\s*=\s*"?(.*?)"?\s*$')
SEKCJA_INI = re.compile(r'^\s*\[\s*"?([^"\]]+)"?\s*\]\s*$')

# Stany dysku, które oznaczają awarię (dysk wyłączony, emulowany albo brakujący w array).
AWARIA = ("DISK_DSBL", "DISK_INVALID", "DISK_NP_DSBL", "DISK_DSBL_NEW", "DISK_NP_MISSING", "DISK_WRONG")


def parsuj_ini(tekst: str) -> dict:
    """Plik bez sekcji daje płaski słownik; z sekcjami daje {sekcja: {klucz: wartość}}."""
    wynik: dict = {}
    sekcja = None
    for linia in tekst.splitlines():
        m = SEKCJA_INI.match(linia)
        if m:
            sekcja = wynik.setdefault(m.group(1), {})
            continue
        m = LINIA_INI.match(linia)
        if m:
            (sekcja if sekcja is not None else wynik)[m.group(1)] = m.group(2)
    return wynik


def _int(v, domyslna=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return domyslna


def nazwa_wyswietlana(nazwa: str) -> str:
    """parity → Parity, parity2 → Parity 2, disk3 → Disk 3, cache → Cache."""
    m = re.match(r"^(parity|disk|cache)(\d*)$", nazwa)
    if m:
        return f"{m.group(1).capitalize()}{' ' + m.group(2) if m.group(2) else ''}"
    return nazwa[:1].upper() + nazwa[1:]


@dataclass
class Dysk:
    nazwa: str             # nazwa w Unraid, np. disk1
    etykieta: str          # do wyświetlenia, np. Disk 1
    rola: str              # parity, array, pool
    urzadzenie: str        # np. sdb (do /proc/diskstats)
    stan: str              # ok, uwaga, alarm
    aktywny: bool          # False = uśpiony
    temp: int | None
    ssd: bool
    smart: str             # ok, uwaga, alarm, brak
    rozmiar_kb: int = 0
    zajete_kb: int = 0
    bledy: int = 0
    opis_stanu: str = ""   # surowy stan z emhttp (np. DISK_DSBL)


@dataclass
class StanUnraid:
    dostepny: bool = False
    array: str = "nieznany"          # STARTED, STOPPED...
    wersja: str = ""
    dyski: list[Dysk] = field(default_factory=list)
    array_rozmiar_kb: int = 0
    array_zajete_kb: int = 0
    cache_rozmiar_kb: int = 0
    cache_zajete_kb: int = 0
    parity_trwa: bool = False
    parity_postep: float = 0.0
    parity_predkosc_kbs: float = 0.0
    parity_eta_s: float | None = None
    parity_bledy: int = 0
    parity_ostatnia: int | None = None     # znacznik czasu ostatniej kontroli
    parity_ostatnia_bledy: int = 0
    parity_ostatnia_wynik: int = 0         # 0 = zakończona poprawnie


def ocena_smart(tekst: str) -> str:
    """Wynik ze smartctl: alarm przy FAILED, uwaga przy realokowanych lub oczekujących sektorach."""
    if not tekst:
        return "brak"
    if re.search(r"self-assessment test result:\s*FAILED|SMART Health Status:\s*(?!OK)\S", tekst, re.I):
        return "alarm"
    for atrybut in ("Reallocated_Sector_Ct", "Current_Pending_Sector", "Offline_Uncorrectable"):
        m = re.search(rf"^\s*\d+\s+{atrybut}\s+.*?(\d+)\s*$", tekst, re.M)
        if m and int(m.group(1)) > 0:
            return "uwaga"
    if re.search(r"Media and Data Integrity Errors:\s*[1-9]", tekst):
        return "uwaga"
    return "ok"


class CzytnikUnraid:
    def __init__(self, katalog: str = "/host/emhttp"):
        self.katalog = Path(katalog)

    def _plik(self, nazwa: str) -> str:
        try:
            return (self.katalog / nazwa).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def nazwa_serwera(self) -> str | None:
        return parsuj_ini(self._plik("var.ini")).get("NAME") or None

    def odczytaj(self) -> StanUnraid:
        var = parsuj_ini(self._plik("var.ini"))
        dyski_ini = parsuj_ini(self._plik("disks.ini"))
        stan = StanUnraid(dostepny=bool(var or dyski_ini))
        if not stan.dostepny:
            return stan
        stan.array = var.get("mdState", "nieznany")
        stan.wersja = var.get("version", "")
        for nazwa, d in dyski_ini.items():
            if not isinstance(d, dict):
                continue
            dysk = self._dysk(nazwa, d)
            if dysk is not None:
                stan.dyski.append(dysk)
        for d in stan.dyski:
            if d.rola == "array":
                stan.array_rozmiar_kb += d.rozmiar_kb
                stan.array_zajete_kb += d.zajete_kb
        pule = [d for d in stan.dyski if d.rola == "pool" and d.rozmiar_kb]
        cache = next((d for d in pule if d.nazwa == "cache"), pule[0] if pule else None)
        if cache:
            stan.cache_rozmiar_kb, stan.cache_zajete_kb = cache.rozmiar_kb, cache.zajete_kb
        self._parity(stan, var)
        return stan

    def _dysk(self, nazwa: str, d: dict) -> Dysk | None:
        typ = d.get("type", "")
        status = d.get("status", "")
        urzadzenie = d.get("device", "")
        if typ == "Flash" or nazwa == "flash":
            return None
        if status == "DISK_NP" and not urzadzenie:   # pusty slot
            return None
        rola = "parity" if typ == "Parity" else "array" if typ == "Data" else "pool"
        kolor = d.get("color", "")
        uspiony = d.get("spundown", "0") == "1" or kolor.endswith("blink")
        temp_txt = d.get("temp", "*")
        temp = _int(temp_txt, None) if temp_txt not in ("*", "") else None
        smart = ocena_smart(self._plik(f"smart/{nazwa}")) if urzadzenie else "brak"
        bledy = _int(d.get("numErrors"))
        if status in AWARIA or kolor.startswith("red"):
            ocena = "alarm"
        elif smart == "alarm":
            ocena = "alarm"
        elif smart == "uwaga" or bledy > 0 or kolor.startswith("yellow"):
            ocena = "uwaga"
        else:
            ocena = "ok"
        rozmiar = _int(d.get("fsSize"))
        zajete = _int(d.get("fsUsed")) or max(0, rozmiar - _int(d.get("fsFree")))
        return Dysk(nazwa=nazwa, etykieta=nazwa_wyswietlana(nazwa), rola=rola, urzadzenie=urzadzenie,
                    stan=ocena, aktywny=not uspiony and temp is not None, temp=temp,
                    ssd=d.get("rotational", "1") == "0", smart=smart, rozmiar_kb=rozmiar,
                    zajete_kb=zajete if rozmiar else 0, bledy=bledy, opis_stanu=status)

    @staticmethod
    def _parity(stan: StanUnraid, var: dict) -> None:
        rozmiar = _int(var.get("mdResyncSize")) or _int(var.get("mdResync"))
        pozycja = _int(var.get("mdResyncPos"))
        stan.parity_trwa = _int(var.get("mdResync")) > 0 and rozmiar > 0
        if stan.parity_trwa:
            stan.parity_postep = min(100.0, 100.0 * pozycja / rozmiar)
            dt, db = _int(var.get("mdResyncDt")), _int(var.get("mdResyncDb"))
            stan.parity_predkosc_kbs = db / dt if dt else 0.0
            if stan.parity_predkosc_kbs > 0:
                stan.parity_eta_s = (rozmiar - pozycja) / stan.parity_predkosc_kbs
            stan.parity_bledy = _int(var.get("sbSyncErrs"))
        ostatnia = _int(var.get("sbSynced2")) or _int(var.get("sbSynced"))
        stan.parity_ostatnia = ostatnia or None
        stan.parity_ostatnia_bledy = _int(var.get("sbSyncErrs"))
        stan.parity_ostatnia_wynik = _int(var.get("sbSyncExit"))
