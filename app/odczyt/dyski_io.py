"""Odczyt i zapis każdego dysku z /proc/diskstats hosta (sektory po 512 B)."""
from __future__ import annotations

import time
from pathlib import Path


def parsuj_diskstats(tekst: str) -> dict[str, tuple[int, int]]:
    """{urządzenie: (sektory_odczytane, sektory_zapisane)}."""
    wynik = {}
    for linia in tekst.splitlines():
        pola = linia.split()
        if len(pola) >= 10:
            wynik[pola[2]] = (int(pola[5]), int(pola[9]))
    return wynik


class CzytnikRuchuDyskow:
    def __init__(self, katalog_proc: str = "/host/proc"):
        self.plik = Path(katalog_proc) / "diskstats"
        self._poprzedni: tuple[float, dict] | None = None

    def odczytaj(self) -> dict[str, tuple[float, float]]:
        """{urządzenie: (odczyt MB/s, zapis MB/s)} od poprzedniego odczytu."""
        try:
            teraz, stan = time.monotonic(), parsuj_diskstats(self.plik.read_text())
        except OSError:
            return {}
        wynik = {}
        if self._poprzedni:
            dt = teraz - self._poprzedni[0]
            if dt > 0:
                for dev, (r, w) in stan.items():
                    pr, pw = self._poprzedni[1].get(dev, (r, w))
                    wynik[dev] = (max(0, r - pr) * 512 / dt / 1e6, max(0, w - pw) * 512 / dt / 1e6)
        self._poprzedni = (teraz, stan)
        return wynik
