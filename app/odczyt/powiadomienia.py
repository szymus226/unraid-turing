"""Nieprzeczytane powiadomienia Unraida i dostępne aktualizacje wtyczek.

Powiadomienia: /tmp/notifications/unread/*.notify (pola event, subject, description, importance).
Wtyczki: Unraid przy sprawdzaniu aktualizacji pobiera nowsze pliki .plg do /tmp/plugins;
porównujemy ich wersje z zainstalowanymi w /boot/config/plugins. Oba katalogi są opcjonalne.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

WERSJA = re.compile(r'<!ENTITY\s+version\s+"([^"]+)"|<PLUGIN[^>]*\sversion="([^"]+)"', re.S)


@dataclass
class Powiadomienie:
    poziom: str        # alarm, uwaga, info
    tytul: str
    opis: str
    czas: int
    plik: str


def czytaj_powiadomienia(katalog: str = "/host/notifications/unread") -> list[Powiadomienie]:
    wynik = []
    try:
        pliki = sorted(Path(katalog).glob("*.notify"))
    except OSError:
        return wynik
    for plik in pliki:
        pola = {}
        try:
            for linia in plik.read_text(encoding="utf-8", errors="replace").splitlines():
                klucz, _, wartosc = linia.partition("=")
                pola[klucz.strip()] = wartosc.strip().strip('"')
        except OSError:
            continue
        poziom = {"alert": "alarm", "warning": "uwaga"}.get(pola.get("importance", ""), "info")
        tytul = pola.get("event") or pola.get("subject") or plik.stem
        opis = pola.get("subject") if pola.get("event") else pola.get("description", "")
        try:
            czas = int(pola.get("timestamp", "0"))
        except ValueError:
            czas = 0
        wynik.append(Powiadomienie(poziom, tytul[:60], (opis or "")[:80], czas, plik.name))
    return wynik


def wersja_wtyczki(tekst: str) -> str | None:
    m = WERSJA.search(tekst or "")
    return (m.group(1) or m.group(2)) if m else None


def aktualizacje_wtyczek(katalog_nowych: str = "/host/plugins-nowe", katalog_zainstalowanych: str = "/host/plugins") -> tuple[int | None, str | None]:
    """(liczba wtyczek z nowszą wersją, nowa wersja Unraida albo None). (None, None) gdy brak dostępu."""
    nowe, zainst = Path(katalog_nowych), Path(katalog_zainstalowanych)
    if not nowe.is_dir():
        return None, None
    licznik, nowy_unraid = 0, None
    for plik in nowe.glob("*.plg"):
        try:
            nowa = wersja_wtyczki(plik.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if plik.stem == "unRAIDServer":
            nowy_unraid = nowa
            continue
        try:
            obecna = wersja_wtyczki((zainst / plik.name).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if nowa and obecna and nowa != obecna:
            licznik += 1
    return (licznik if zainst.is_dir() else None), nowy_unraid
