"""Sterownik ekranów Turing Smart Screen 3,5" (rewizja A) i UsbMonitor.

Protokół opisany na podstawie projektu turing-smart-screen-python
(https://github.com/mathoudebine/turing-smart-screen-python, GPLv3, autor: Matthieu Houdebine
i współautorzy). Ten plik jest własną, uproszczoną implementacją tego samego protokołu
i podlega tej samej licencji GPLv3.

Ekran to port szeregowy USB (CDC ACM, układ CH552T, VID:PID 1a86:5722). Każde polecenie
to 6 bajtów: współrzędne x, y, ex, ey upakowane bitowo i kod polecenia. Po poleceniu
DISPLAY_BITMAP idą piksele w formacie RGB565 little-endian.
"""
from __future__ import annotations

import logging
from enum import IntEnum

import numpy as np
from PIL import Image

from .baza import BladEkranu, Ekran, Orientacja

log = logging.getLogger(__name__)

VID = 0x1A86
PID = 0x5722
NUMER_SERYJNY_TURING = "USB35INCHIPSV2"
PREDKOSC = 115200


class Polecenie(IntEnum):
    RESET = 101
    CZYSC = 102
    EKRAN_WYL = 108
    EKRAN_WL = 109
    JASNOSC = 110
    ORIENTACJA = 121
    OBRAZ = 197
    HELLO = 69


# Kod orientacji w protokole (wartość + 100 w bajcie 6 polecenia ORIENTACJA).
KOD_ORIENTACJI = {
    Orientacja.PIONOWO: 0,
    Orientacja.PIONOWO_ODWROCONY: 1,
    Orientacja.POZIOMO: 2,
    Orientacja.POZIOMO_ODWROCONY: 3,
}


def naglowek(polecenie: int, x: int, y: int, ex: int, ey: int) -> bytes:
    """Pakuje polecenie z czterema współrzędnymi do 6 bajtów."""
    return bytes((
        (x >> 2) & 0xFF,
        (((x & 3) << 6) + (y >> 4)) & 0xFF,
        (((y & 15) << 4) + (ex >> 6)) & 0xFF,
        (((ex & 63) << 2) + (ey >> 8)) & 0xFF,
        ey & 0xFF,
        polecenie,
    ))


def do_rgb565(obraz: Image.Image) -> bytes:
    """Zamienia obraz na piksele RGB565 little-endian."""
    rgb = np.asarray(obraz.convert("RGB"), dtype=np.uint16)
    r, g, b = rgb[..., 0] >> 3, rgb[..., 1] >> 2, rgb[..., 2] >> 3
    return ((r << 11) | (g << 5) | b).astype("<u2").tobytes()


class EkranRevA(Ekran):
    """Ekran podłączony przez port szeregowy. `port` to np. /dev/ttyACM0."""

    def __init__(self, port: str, szerokosc: int = 320, wysokosc: int = 480, otworz_port=None):
        super().__init__(szerokosc, wysokosc)
        self.port = port
        self._otworz_port = otworz_port or _otworz_serial
        self._polaczenie = None

    # --- połączenie ---
    def polacz(self) -> None:
        try:
            self._polaczenie = self._otworz_port(self.port)
        except Exception as blad:  # pyserial zgłasza różne wyjątki zależnie od systemu
            raise BladEkranu(f"nie można otworzyć {self.port}: {blad}") from blad

    def rozlacz(self) -> None:
        if self._polaczenie is not None:
            try:
                self._polaczenie.close()
            except Exception:
                pass
        self._polaczenie = None

    @property
    def polaczony(self) -> bool:
        return self._polaczenie is not None

    def _zapisz(self, dane: bytes) -> None:
        if self._polaczenie is None:
            raise BladEkranu("ekran nie jest połączony")
        try:
            self._polaczenie.write(dane)
        except Exception as blad:
            self.rozlacz()
            raise BladEkranu(f"błąd zapisu do {self.port}: {blad}") from blad

    # --- polecenia ---
    def ustaw_jasnosc(self, procent: int) -> None:
        procent = max(0, min(100, int(procent)))
        # Ekran: 0 = najjaśniej, 255 = najciemniej.
        self._zapisz(naglowek(Polecenie.JASNOSC, int(255 - procent * 255 / 100), 0, 0, 0))

    def wlacz(self, wlaczony: bool) -> None:
        self._zapisz(naglowek(Polecenie.EKRAN_WL if wlaczony else Polecenie.EKRAN_WYL, 0, 0, 0, 0))

    def ustaw_orientacje(self, orientacja: Orientacja) -> None:
        self.orientacja = orientacja
        szer, wys = self.rozmiar
        dane = bytearray(16)
        dane[0:6] = naglowek(Polecenie.ORIENTACJA, 0, 0, 0, 0)
        dane[6] = KOD_ORIENTACJI[orientacja] + 100
        dane[7], dane[8] = szer >> 8, szer & 0xFF
        dane[9], dane[10] = wys >> 8, wys & 0xFF
        self._zapisz(bytes(dane))

    def wyslij_obszar(self, obraz: Image.Image, x: int, y: int) -> None:
        szer, wys = self.rozmiar
        w = min(obraz.width, szer - x)
        h = min(obraz.height, wys - y)
        if w <= 0 or h <= 0:
            return
        if (w, h) != obraz.size:
            obraz = obraz.crop((0, 0, w, h))
        self._zapisz(naglowek(Polecenie.OBRAZ, x, y, x + w - 1, y + h - 1))
        piksele = do_rgb565(obraz)
        krok = szer * 8  # porcje po 4 linie ekranu, jak w oryginalnym sterowniku
        for i in range(0, len(piksele), krok):
            self._zapisz(piksele[i:i + krok])


def _otworz_serial(port: str):
    import serial  # import tutaj, żeby testy i symulacja działały bez pyserial

    return serial.Serial(port, PREDKOSC, timeout=1, write_timeout=5, rtscts=True)
