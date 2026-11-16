"""Generuje zrzuty ekranów LCD z przykładowymi danymi do docs/makiety/png.

Uruchom: python3 -m tools.makiety
"""
from pathlib import Path

from PIL import Image

from app.ekrany import dodatkowe
from app.ekrany.rysuj import H, W, wszystkie

WYJSCIE = Path(__file__).resolve().parent.parent / "docs" / "makiety" / "png"

if __name__ == "__main__":
    WYJSCIE.mkdir(parents=True, exist_ok=True)
    for jezyk in ("pl", "en"):
        ekrany = wszystkie(jezyk)
        for nazwa, obraz in ekrany.items():
            obraz.save(WYJSCIE / f"lcd-{jezyk}-{nazwa}.png")
        zestawienie = Image.new("RGB", (len(ekrany) * (W + 20) + 20, H + 40), (60, 64, 72))
        for i, obraz in enumerate(ekrany.values()):
            zestawienie.paste(obraz, (20 + i * (W + 20), 20))
        zestawienie.save(WYJSCIE / f"lcd-{jezyk}-zestawienie.png")
        nowe = dodatkowe.wszystkie(jezyk)
        for nazwa, obraz in nowe.items():
            obraz.save(WYJSCIE / f"lcd-{jezyk}-{nazwa}.png")
        zestawienie = Image.new("RGB", (len(nowe) * (W + 20) + 20, H + 40), (60, 64, 72))
        for i, obraz in enumerate(nowe.values()):
            zestawienie.paste(obraz, (20 + i * (W + 20), 20))
        zestawienie.save(WYJSCIE / f"lcd-{jezyk}-zestawienie-dodatkowe.png")
