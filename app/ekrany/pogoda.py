"""Ikony pogody rysowane w Pillow (bez plików graficznych) i opis według kodu WMO z Open-Meteo."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

SLONCE, KSIEZYC = (255, 200, 60), (225, 230, 245)
CHMURA, CHMURA_CIEMNA = (200, 208, 222), (120, 130, 150)
DESZCZ, SNIEG, BLYSK = (90, 160, 255), (235, 240, 255), (255, 210, 60)

OPISY = {
    "pl": {"bezchmurnie": "bezchmurnie", "czesciowo": "częściowe zachmurzenie", "pochmurno": "pochmurno",
           "mgla": "mgła", "mzawka": "mżawka", "deszcz": "deszcz", "snieg": "śnieg", "burza": "burza"},
    "en": {"bezchmurnie": "clear", "czesciowo": "partly cloudy", "pochmurno": "cloudy",
           "mgla": "fog", "mzawka": "drizzle", "deszcz": "rain", "snieg": "snow", "burza": "thunderstorm"},
}


def rodzaj_pogody(kod: int) -> str:
    """Kod WMO (pole weather_code w Open-Meteo) na jeden z rodzajów z OPISY."""
    if kod == 0:
        return "bezchmurnie"
    if kod in (1, 2):
        return "czesciowo"
    if kod == 3:
        return "pochmurno"
    if kod in (45, 48):
        return "mgla"
    if 51 <= kod <= 57:
        return "mzawka"
    if 61 <= kod <= 67 or 80 <= kod <= 82:
        return "deszcz"
    if 71 <= kod <= 77 or kod in (85, 86):
        return "snieg"
    if 95 <= kod <= 99:
        return "burza"
    return "pochmurno"


def _slonce(d, cx, cy, r):
    import math
    for i in range(8):
        a = i * math.pi / 4
        d.line((cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35,
                cx + math.cos(a) * r * 1.75, cy + math.sin(a) * r * 1.75), fill=SLONCE, width=max(2, int(r // 4)))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=SLONCE)


def _ksiezyc(d, cx, cy, r, tlo):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=KSIEZYC)
    d.ellipse((cx - r * 0.35, cy - r * 1.15, cx + r * 1.45, cy + r * 0.65), fill=tlo)


def _chmura(d, x, y, s, kolor):
    """Chmura o szerokości ok. 2*s, dolna krawędź na y."""
    d.ellipse((x, y - s * 0.9, x + s * 0.9, y), fill=kolor)
    d.ellipse((x + s * 0.45, y - s * 1.45, x + s * 1.45, y - s * 0.3), fill=kolor)
    d.ellipse((x + s * 1.05, y - s * 1.05, x + s * 2.0, y), fill=kolor)
    d.rectangle((x + s * 0.45, y - s * 0.6, x + s * 1.55, y), fill=kolor)


@lru_cache(maxsize=32)
def ikona(rodzaj: str, dzien: bool, rozmiar: int, tlo: tuple) -> Image.Image:
    """Ikona rysowana w 4x większej skali i zmniejszana (gładkie krawędzie)."""
    k = 4
    n = rozmiar * k
    img = Image.new("RGB", (n, n), tlo)
    d = ImageDraw.Draw(img)
    s = n * 0.36
    if rodzaj == "bezchmurnie":
        if dzien:
            _slonce(d, n / 2, n / 2, n * 0.24)
        else:
            _ksiezyc(d, n / 2, n / 2, n * 0.32, tlo)
    elif rodzaj == "czesciowo":
        if dzien:
            _slonce(d, n * 0.62, n * 0.36, n * 0.17)
        else:
            _ksiezyc(d, n * 0.64, n * 0.34, n * 0.22, tlo)
        _chmura(d, n * 0.08, n * 0.86, s, CHMURA)
    elif rodzaj == "mgla":
        _chmura(d, n * 0.14, n * 0.6, s, CHMURA_CIEMNA)
        for i, (a, b) in enumerate(((0.12, 0.88), (0.2, 0.8), (0.12, 0.72))):
            y = n * (0.7 + i * 0.11)
            d.line((n * a, y, n * b, y), fill=CHMURA, width=int(n // 18))
    else:
        burzowa = rodzaj == "burza"
        gora = rodzaj != "pochmurno"
        y_chm = n * (0.62 if gora else 0.78)
        if not gora:
            _chmura(d, n * 0.3, y_chm - n * 0.12, s * 0.8, CHMURA_CIEMNA)
        _chmura(d, n * 0.14, y_chm, s, CHMURA_CIEMNA if burzowa else CHMURA)
        if rodzaj in ("deszcz", "mzawka"):
            ile, dl = (3, 0.2) if rodzaj == "deszcz" else (3, 0.09)
            for i in range(ile):
                x = n * (0.32 + i * 0.18)
                d.line((x, n * 0.72, x - n * 0.06, n * (0.72 + dl)), fill=DESZCZ, width=int(n // 16))
        elif rodzaj == "snieg":
            for i in range(3):
                x, y = n * (0.3 + i * 0.2), n * (0.8 if i % 2 else 0.75)
                r = n * 0.045
                d.ellipse((x - r, y - r, x + r, y + r), fill=SNIEG)
        elif burzowa:
            p = [(0.52, 0.64), (0.4, 0.82), (0.5, 0.82), (0.42, 0.98), (0.64, 0.76), (0.53, 0.76), (0.6, 0.64)]
            d.polygon([(x * n, y * n) for x, y in p], fill=BLYSK)
    return img.resize((rozmiar, rozmiar), Image.LANCZOS)
