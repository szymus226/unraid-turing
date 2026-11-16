"""Wspólny interfejs ekranów, żeby można było dodać inne modele LCD."""
from __future__ import annotations

from enum import Enum

from PIL import Image


class BladEkranu(Exception):
    """Ekran odłączony albo nie odpowiada."""


class Orientacja(str, Enum):
    PIONOWO = "pionowo"
    PIONOWO_ODWROCONY = "pionowo_odwrocony"
    POZIOMO = "poziomo"
    POZIOMO_ODWROCONY = "poziomo_odwrocony"


class Ekran:
    def __init__(self, szerokosc: int, wysokosc: int):
        self.szerokosc_natywna = szerokosc
        self.wysokosc_natywna = wysokosc
        self.orientacja = Orientacja.PIONOWO

    @property
    def rozmiar(self) -> tuple[int, int]:
        """Rozmiar obrazu w bieżącej orientacji."""
        if self.orientacja in (Orientacja.POZIOMO, Orientacja.POZIOMO_ODWROCONY):
            return self.wysokosc_natywna, self.szerokosc_natywna
        return self.szerokosc_natywna, self.wysokosc_natywna

    def polacz(self) -> None: ...
    def rozlacz(self) -> None: ...

    @property
    def polaczony(self) -> bool:
        return True

    def ustaw_jasnosc(self, procent: int) -> None: ...
    def wlacz(self, wlaczony: bool) -> None: ...
    def ustaw_orientacje(self, orientacja: Orientacja) -> None:
        self.orientacja = orientacja

    def wyslij_obszar(self, obraz: Image.Image, x: int, y: int) -> None:
        raise NotImplementedError
