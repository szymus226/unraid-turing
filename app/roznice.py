"""Wyszukiwanie zmienionych fragmentów obrazu.

Pełna klatka 320x480 przez USB trwa około 0,5–1 s, więc wysyłamy tylko pasy,
w których coś się zmieniło, przycięte do zmienionych kolumn.
"""
from __future__ import annotations

from PIL import Image, ImageChops

WYSOKOSC_PASA = 16


def zmienione_obszary(stary: Image.Image | None, nowy: Image.Image,
                      wysokosc_pasa: int = WYSOKOSC_PASA) -> list[tuple[int, int, int, int]]:
    """Zwraca listę prostokątów (x0, y0, x1, y1) do wysłania; x1 i y1 bez włączenia."""
    if stary is None or stary.size != nowy.size:
        return [(0, 0, nowy.width, nowy.height)]
    roznica = ImageChops.difference(stary.convert("RGB"), nowy.convert("RGB"))
    if roznica.getbbox() is None:
        return []
    obszary: list[tuple[int, int, int, int]] = []
    for y in range(0, nowy.height, wysokosc_pasa):
        y1 = min(y + wysokosc_pasa, nowy.height)
        ramka = roznica.crop((0, y, nowy.width, y1)).getbbox()
        if ramka is None:
            continue
        x0, _, x1, _ = ramka
        # Sąsiednie pasy łączymy, jeśli zakresy kolumn się pokrywają (mniej poleceń USB).
        if obszary and obszary[-1][3] == y:
            px0, py0, px1, _ = obszary[-1]
            if x0 <= px1 and x1 >= px0:
                obszary[-1] = (min(px0, x0), py0, max(px1, x1), y1)
                continue
        obszary.append((x0, y, x1, y1))
    return obszary
