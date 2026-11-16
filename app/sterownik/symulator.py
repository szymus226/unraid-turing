"""Ekran w pamięci: pozwala pracować bez fizycznego urządzenia."""
from __future__ import annotations

from PIL import Image

from .baza import Ekran, Orientacja


class EkranSymulowany(Ekran):
    def __init__(self, szerokosc: int = 320, wysokosc: int = 480):
        super().__init__(szerokosc, wysokosc)
        self.jasnosc = 100
        self.wlaczony = True
        self.klatka = Image.new("RGB", self.rozmiar, (0, 0, 0))
        self.wyslane_bajty = 0

    def ustaw_jasnosc(self, procent: int) -> None:
        self.jasnosc = max(0, min(100, int(procent)))

    def wlacz(self, wlaczony: bool) -> None:
        self.wlaczony = wlaczony

    def ustaw_orientacje(self, orientacja: Orientacja) -> None:
        super().ustaw_orientacje(orientacja)
        self.klatka = Image.new("RGB", self.rozmiar, (0, 0, 0))

    def wyslij_obszar(self, obraz: Image.Image, x: int, y: int) -> None:
        self.klatka.paste(obraz, (x, y))
        self.wyslane_bajty += obraz.width * obraz.height * 2
