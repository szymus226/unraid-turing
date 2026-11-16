"""Rysowanie ekranów LCD 320x480 (Pillow).

Ten sam kod generuje makiety (docs/makiety), więc ekran wygląda dokładnie jak makieta.
Każda funkcja ekran_* dostaje słownik tekstów `t` i słownik danych `dane`.
"""
import os
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 320, 480
# Margines od krawędzi ekranu (ramka obudowy zasłania skrajne piksele).
M = 18
# Czcionka Inter (licencja OFL) z pakietu fonts-inter instalowanego w obrazie Dockera.
FONT_DIR = os.environ.get("LCD_CZCIONKI", "/usr/share/fonts/opentype/inter/").rstrip("/") + "/"

KOLORY = {
    "tlo": (11, 15, 25), "karta": (22, 28, 42), "linia": (40, 48, 66),
    "tekst": (232, 236, 244), "szary": (140, 150, 170),
    "ok": (52, 199, 120), "uwaga": (245, 180, 40), "alarm": (240, 70, 70),
    "akcent": (70, 150, 255), "akcent2": (160, 110, 255),
}

TEKSTY = {
    "pl": {"system": "SYSTEM", "dyski": "DYSKI", "docker": "DOCKER", "parity": "PARITY",
           "alerty": "ALERTY", "cpu": "CPU", "ram": "RAM", "swap": "SWAP", "temp": "Temp.",
           "uptime": "Czas pracy", "load": "Obciążenie", "siec": "Sieć LAN",
           "array": "Array", "uruchomiony": "uruchomiony", "cache": "Cache",
           "aktywne": "aktywne", "uspione": "uśpione", "kontenery": "Kontenery",
           "dzialaja": "działa", "zatrzymane": "zatrzymane", "maszyny": "Maszyny VM",
           "postep": "Postęp", "predkosc": "Prędkość", "koniec": "Koniec za",
           "bledy": "Błędy", "brak_alertow": "Wszystko w porządku", "dni": "d",
           "wolne": "wolne", "z": "z"},
    "en": {"system": "SYSTEM", "dyski": "DISKS", "docker": "DOCKER", "parity": "PARITY",
           "alerty": "ALERTS", "cpu": "CPU", "ram": "RAM", "swap": "SWAP", "temp": "Temp.",
           "uptime": "Uptime", "load": "Load", "siec": "LAN",
           "array": "Array", "uruchomiony": "started", "cache": "Cache",
           "aktywne": "active", "uspione": "spun down", "kontenery": "Containers",
           "dzialaja": "running", "zatrzymane": "stopped", "maszyny": "VMs",
           "postep": "Progress", "predkosc": "Speed", "koniec": "Finishes in",
           "bledy": "Errors", "brak_alertow": "All good", "dni": "d",
           "wolne": "free", "z": "of"},
}

PRZYKLADOWE_DANE = {
    "host": "serwer", "godzina": "17:42",
    "cpu": 23, "rdzenie": [12, 35, 8, 41, 19, 27, 5, 33, 22, 14, 9, 30],
    "cpu_temp": 52, "ram": 61, "ram_txt": "9,8 / 16 GB", "swap": None,
    "uptime": "12d 4h", "load": (1.42, 1.18, 0.97),
    "rx": "4,2 MB/s", "tx": "0,8 MB/s",
    "historia_cpu": [18, 22, 25, 20, 31, 45, 38, 26, 22, 19, 24, 28, 23, 21, 26, 30, 27, 23, 25, 23],
    "array_uzycie": 68, "array_txt": "27,1 / 40 TB", "cache_uzycie": 41, "cache_txt": "410 / 1000 GB",
    "dyski": [("Parity", 34, "ok", True), ("Disk 1", 36, "ok", True), ("Disk 2", 0, "ok", False),
              ("Disk 3", 47, "uwaga", True), ("Disk 4", 0, "ok", False), ("Cache", 41, "ok", True)],
    "kontenery_dzialaja": 38, "kontenery_wszystkie": 41,
    "kontenery": [("plex", "ok", 6.1, "1,2 GB"), ("immich", "ok", 3.4, "2,1 GB"),
                  ("nextcloud", "ok", 1.2, "640 MB"), ("adguard", "ok", 0.3, "120 MB"),
                  ("paperless", "uwaga", 0.0, "—"), ("homelabber", "ok", 0.8, "310 MB")],
    "vm": [("Home Assistant", "ok"), ("Windows 11", "szary")],
    "parity_postep": 63.4, "parity_predkosc": "182 MB/s", "parity_eta": "3h 12m", "parity_bledy": 0,
    "alerty": [("uwaga", "Disk 3: 47°C", "próg 45°C"), ("uwaga", "paperless", "zatrzymany 14:05"),
               ("uwaga", "SMART Disk 3", "realokowane sektory: 8")],
}


@lru_cache(maxsize=64)
def font(rozmiar, waga="Regular"):
    return ImageFont.truetype(f"{FONT_DIR}Inter-{waga}.otf", rozmiar)


def liczba(v, jezyk, miejsca=1):
    tekst = f"{v:.{miejsca}f}"
    return tekst.replace(".", ",") if jezyk == "pl" else tekst


def kolor_progu(wartosc, uwaga, alarm):
    return KOLORY["alarm"] if wartosc >= alarm else KOLORY["uwaga"] if wartosc >= uwaga else KOLORY["ok"]


def naglowek(d, tytul, indeks, dane):
    d.rectangle((0, 0, W, 40), fill=KOLORY["karta"])
    d.text((M, 20), tytul, font=font(18, "Bold"), fill=KOLORY["tekst"], anchor="lm")
    d.text((W - M, 20), dane["godzina"], font=font(16, "SemiBold"), fill=KOLORY["szary"], anchor="rm")
    # kropki widoków (który ekran z pięciu)
    for i in range(5):
        x = W // 2 + 18 + i * 12
        d.ellipse((x - 3, 17, x + 3, 23), fill=KOLORY["akcent"] if i == indeks else KOLORY["linia"])


def pasek(d, x, y, szer, wys, procent, kolor):
    d.rounded_rectangle((x, y, x + szer, y + wys), radius=wys // 2, fill=KOLORY["linia"])
    if procent > 0:
        d.rounded_rectangle((x, y, x + max(wys, int(szer * procent / 100)), y + wys), radius=wys // 2, fill=kolor)


def luk(d, cx, cy, r, procent, kolor, grubosc=14):
    d.arc((cx - r, cy - r, cx + r, cy + r), 135, 405, fill=KOLORY["linia"], width=grubosc)
    if procent > 0:
        d.arc((cx - r, cy - r, cx + r, cy + r), 135, 135 + 270 * procent / 100, fill=kolor, width=grubosc)


def karta(d, x, y, szer, wys):
    d.rounded_rectangle((x, y, x + szer, y + wys), radius=10, fill=KOLORY["karta"])


def ekran_system(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["system"], 0, dane)
    # duży wskaźnik CPU
    luk(d, M + 74, 120, 60, dane["cpu"], kolor_progu(dane["cpu"], 70, 90))
    d.text((M + 74, 114), f"{dane['cpu']:.0f}%", font=font(32, "Bold"), fill=KOLORY["tekst"], anchor="mm")
    d.text((M + 74, 146), t["cpu"], font=font(14, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    # temperatura CPU i czas pracy
    temp = dane["cpu_temp"]
    kt = kolor_progu(temp, 70, 85) if temp is not None else KOLORY["szary"]
    x0 = W - M - 126
    karta(d, x0, 54, 126, 62)
    d.text((x0 + 12, 66), t["temp"] + " CPU", font=font(13), fill=KOLORY["szary"])
    d.text((x0 + 12, 84), f"{temp:.0f}°C" if temp is not None else "—", font=font(26, "Bold"), fill=kt)
    karta(d, x0, 124, 126, 56)
    d.text((x0 + 12, 133), t["uptime"], font=font(13), fill=KOLORY["szary"])
    d.text((x0 + 12, 151), dane["uptime"], font=font(21, "Bold"), fill=KOLORY["tekst"])
    # rdzenie
    y0, wys = 194, 36
    n = len(dane["rdzenie"]); szer = (W - 2 * M - (n - 1) * 4) / n
    for i, v in enumerate(dane["rdzenie"]):
        x = M + i * (szer + 4)
        d.rectangle((x, y0, x + szer, y0 + wys), fill=KOLORY["linia"])
        h = int(wys * v / 100)
        d.rectangle((x, y0 + wys - h, x + szer, y0 + wys), fill=kolor_progu(v, 70, 90))
    # wykres historii CPU
    karta(d, M, 242, W - 2 * M, 58)
    hist = dane["historia_cpu"]; krok = (W - 2 * M - 20) / (len(hist) - 1)
    pkt = [(M + 10 + i * krok, 292 - v * 0.42) for i, v in enumerate(hist)]
    d.line(pkt, fill=KOLORY["akcent"], width=2)
    # RAM i SWAP
    y = 314
    d.text((M, y), t["ram"], font=font(15, "SemiBold"), fill=KOLORY["tekst"])
    d.text((W - M, y), f"{dane['ram_txt']}  {dane['ram']:.0f}%", font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
    pasek(d, M, y + 24, W - 2 * M, 12, dane["ram"], kolor_progu(dane["ram"], 80, 92))
    y = 364
    d.text((M, y), t["swap"], font=font(15, "SemiBold"), fill=KOLORY["szary"])
    if dane.get("swap") is None:
        d.text((W - M, y), "—", font=font(15, "SemiBold"), fill=KOLORY["szary"], anchor="ra")
    else:
        d.text((W - M, y), f"{dane['swap']:.0f}%", font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
    # load i sieć
    szer = (W - 2 * M - 12) // 2
    y = 400
    karta(d, M, y, szer, 58); karta(d, W - M - szer, y, szer, 58)
    d.text((M + 10, y + 8), t["load"], font=font(12), fill=KOLORY["szary"])
    d.text((M + 10, y + 28), "  ".join(liczba(v, t["_j"], 2) for v in dane["load"]), font=font(15, "SemiBold"), fill=KOLORY["tekst"])
    x = W - M - szer + 10
    d.text((x, y + 8), t["siec"], font=font(12), fill=KOLORY["szary"])
    d.text((x, y + 24), f"↓ {dane['rx']}", font=font(13, "SemiBold"), fill=KOLORY["ok"])
    d.text((x, y + 40), f"↑ {dane['tx']}", font=font(13, "SemiBold"), fill=KOLORY["akcent"])
    return img


def ekran_dyski(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["dyski"], 1, dane)
    d.ellipse((M, 58, M + 14, 72), fill=KOLORY["ok"])
    d.text((M + 22, 65), f"{t['array']}: {t['uruchomiony']}", font=font(16, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    for i, (nazwa, proc, txt) in enumerate([(t["array"], dane["array_uzycie"], dane["array_txt"]),
                                             (t["cache"], dane["cache_uzycie"], dane["cache_txt"])]):
        y = 88 + i * 62
        karta(d, M, y, W - 2 * M, 54)
        d.text((M + 12, y + 10), nazwa, font=font(14, "SemiBold"), fill=KOLORY["tekst"])
        d.text((W - M - 12, y + 10), f"{txt}  {proc}%", font=font(14, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
        pasek(d, M + 12, y + 34, W - 2 * M - 24, 10, proc, kolor_progu(proc, 85, 95))
    aktywne = sum(1 for x in dane["dyski"] if x[3])
    d.text((M, 222), f"{aktywne} {t['aktywne']} · {len(dane['dyski']) - aktywne} {t['uspione']}",
           font=font(13), fill=KOLORY["szary"])
    for i, (nazwa, temp, smart, aktywny) in enumerate(dane["dyski"]):
        y = 240 + i * 36
        d.line((M, y + 34, W - M, y + 34), fill=KOLORY["linia"])
        d.ellipse((M + 2, y + 11, M + 14, y + 23), fill=KOLORY[smart] if aktywny else KOLORY["linia"])
        d.text((M + 24, y + 17), nazwa, font=font(16, "SemiBold"), fill=KOLORY["tekst"] if aktywny else KOLORY["szary"], anchor="lm")
        tekst = f"{temp}°C" if aktywny else "—"
        kolor = kolor_progu(temp, 45, 50) if aktywny else KOLORY["szary"]
        d.text((W - M - 2, y + 17), tekst, font=font(20, "Bold"), fill=kolor, anchor="rm")
        if aktywny:
            d.text((W - M - 78, y + 17), "SMART", font=font(11, "SemiBold"),
               fill=KOLORY[smart] if smart != "ok" else KOLORY["szary"], anchor="rm")
    return img


def ekran_docker(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["docker"], 2, dane)
    dz, wsz = dane["kontenery_dzialaja"], dane["kontenery_wszystkie"]
    karta(d, M, 54, W - 2 * M, 84)
    d.text((M + 14, 64), t["kontenery"], font=font(14), fill=KOLORY["szary"])
    d.text((M + 14, 84), str(dz), font=font(44, "Bold"), fill=KOLORY["ok"])
    d.text((M + 86, 106), f"/ {wsz} {t['dzialaja']}", font=font(16, "SemiBold"), fill=KOLORY["szary"])
    d.text((W - 2 * M, 106), f"{wsz - dz} {t['zatrzymane']}", font=font(14, "SemiBold"), fill=KOLORY["uwaga"], anchor="ra")
    for i, (nazwa, stan, cpu, ram) in enumerate(dane["kontenery"]):
        y = 150 + i * 40
        d.line((M, y + 37, W - M, y + 37), fill=KOLORY["linia"])
        d.ellipse((M + 2, y + 12, M + 14, y + 24), fill=KOLORY[stan])
        d.text((M + 24, y + 18), nazwa, font=font(16, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
        d.text((W - M - 2, y + 18), ram, font=font(13), fill=KOLORY["szary"], anchor="rm")
        d.text((W - M - 76, y + 18), f"{liczba(cpu, t['_j'])}%", font=font(14, "SemiBold"), fill=KOLORY["tekst"], anchor="rm")
    y = 392
    d.text((M, y), t["maszyny"], font=font(14), fill=KOLORY["szary"])
    for i, (nazwa, stan) in enumerate(dane["vm"]):
        yy = y + 24 + i * 26
        d.ellipse((M + 2, yy + 4, M + 12, yy + 14), fill=KOLORY[stan])
        d.text((M + 22, yy + 9), nazwa, font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    return img


def ekran_parity(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["parity"], 3, dane)
    p = dane["parity_postep"]
    luk(d, W // 2, 180, 100, p, KOLORY["akcent2"], grubosc=18)
    d.text((W // 2, 170), f"{liczba(p, t['_j'])}%", font=font(46, "Bold"), fill=KOLORY["tekst"], anchor="mm")
    d.text((W // 2, 214), t["postep"], font=font(15, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    for i, (etyk, wart, kol) in enumerate([(t["predkosc"], dane["parity_predkosc"], KOLORY["tekst"]),
                                            (t["koniec"], dane["parity_eta"], KOLORY["tekst"]),
                                            (t["bledy"], str(dane["parity_bledy"]), KOLORY["ok"])]):
        y = 306 + i * 52
        karta(d, M, y, W - 2 * M, 44)
        d.text((M + 14, y + 22), etyk, font=font(15), fill=KOLORY["szary"], anchor="lm")
        d.text((W - M - 14, y + 22), wart, font=font(22, "Bold"), fill=kol, anchor="rm")
    return img


def ekran_alerty(t, dane, puste=False):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["alerty"], 4, dane)
    if puste:
        d.ellipse((W // 2 - 50, 170, W // 2 + 50, 270), outline=KOLORY["ok"], width=8)
        d.line([(W // 2 - 24, 222), (W // 2 - 6, 240), (W // 2 + 26, 204)], fill=KOLORY["ok"], width=9)
        d.text((W // 2, 300), t["brak_alertow"], font=font(20, "SemiBold"), fill=KOLORY["tekst"], anchor="mm")
        return img
    for i, (poziom, tytul, opis) in enumerate(dane["alerty"]):
        y = 56 + i * 82
        karta(d, M, y, W - 2 * M, 72)
        d.rounded_rectangle((M, y, M + 8, y + 72), radius=4, fill=KOLORY[poziom])
        d.text((M + 20, y + 14), tytul, font=font(19, "Bold"), fill=KOLORY[poziom])
        d.text((M + 20, y + 44), opis, font=font(14), fill=KOLORY["szary"])
    return img


def wszystkie(jezyk="pl", dane=None):
    """Wszystkie ekrany z danymi (domyślnie przykładowymi). Używane do makiet i testów."""
    dane = dane or PRZYKLADOWE_DANE
    t = dict(TEKSTY[jezyk], _j=jezyk)
    return {"1-system": ekran_system(t, dane), "2-dyski": ekran_dyski(t, dane), "3-docker": ekran_docker(t, dane),
            "4-parity": ekran_parity(t, dane), "5-alerty": ekran_alerty(t, dane),
            "5b-alerty-puste": ekran_alerty(t, dane, True)}
