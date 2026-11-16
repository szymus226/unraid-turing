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
        # Wszystkie ikony pogody (dzień i noc) z opisami, do oceny wyglądu.
        from PIL import ImageDraw
        from app.ekrany.pogoda import OPISY, ikona
        from app.ekrany.rysuj import KOLORY, font
        rodzaje = list(OPISY[jezyk])
        arkusz = Image.new("RGB", (len(rodzaje) * 160 + 20, 260), KOLORY["tlo"])
        d = ImageDraw.Draw(arkusz)
        for i, rodzaj in enumerate(rodzaje):
            x = 20 + i * 160
            arkusz.paste(ikona(rodzaj, True, 64, KOLORY["tlo"]), (x + 38, 20))
            arkusz.paste(ikona(rodzaj, False, 64, KOLORY["tlo"]), (x + 38, 110))
            d.text((x + 70, 210), OPISY[jezyk][rodzaj], font=font(13), fill=KOLORY["szary"], anchor="ma")
        arkusz.save(WYJSCIE / f"lcd-{jezyk}-pogoda-ikony.png")
        # Układ poziomy 480×320 (ekran położony bokiem).
        from app.ekrany import poziome
        pozi = poziome.wszystkie(jezyk)
        for nazwa, obraz in pozi.items():
            obraz.save(WYJSCIE / f"lcd-{jezyk}-poziomo-{nazwa}.png")
        kolumny = 4
        wiersze = -(-len(pozi) // kolumny)
        zestawienie = Image.new("RGB", (kolumny * (poziome.PW + 20) + 20, wiersze * (poziome.PH + 20) + 20), (60, 64, 72))
        for i, obraz in enumerate(pozi.values()):
            zestawienie.paste(obraz, (20 + (i % kolumny) * (poziome.PW + 20), 20 + (i // kolumny) * (poziome.PH + 20)))
        zestawienie.save(WYJSCIE / f"lcd-{jezyk}-zestawienie-poziome.png")
