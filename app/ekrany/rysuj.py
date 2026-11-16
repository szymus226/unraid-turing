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

# Motywy kolorów. KOLORY to słownik bieżącego motywu, zmieniany w miejscu przez ustaw_motyw().
MOTYWY = {
    "granatowy": {
        "tlo": (11, 15, 25), "karta": (22, 28, 42), "linia": (40, 48, 66),
        "tekst": (232, 236, 244), "szary": (140, 150, 170),
        "alarm_tlo": (64, 18, 22), "alarm_opis": (230, 180, 180), "alarm_kropka": (200, 90, 90),
    },
    "czarny": {
        "tlo": (0, 0, 0), "karta": (17, 17, 19), "linia": (40, 40, 46),
        "tekst": (236, 236, 240), "szary": (140, 140, 150),
        "alarm_tlo": (60, 12, 14), "alarm_opis": (230, 180, 180), "alarm_kropka": (200, 90, 90),
    },
    "jasny": {
        "tlo": (238, 241, 246), "karta": (255, 255, 255), "linia": (210, 216, 226),
        "tekst": (20, 24, 34), "szary": (96, 106, 124),
        "alarm_tlo": (253, 228, 228), "alarm_opis": (150, 40, 40), "alarm_kropka": (255, 190, 190),
    },
}
STALE = {"ok": (52, 199, 120), "uwaga": (245, 180, 40), "alarm": (240, 70, 70),
         "akcent": (70, 150, 255), "akcent2": (160, 110, 255), "na_alarmie": (255, 255, 255)}
KOLORY = dict(MOTYWY["granatowy"], **STALE)


def ustaw_motyw(nazwa: str) -> None:
    KOLORY.update(MOTYWY.get(nazwa, MOTYWY["granatowy"]))

TEKSTY = {
    "pl": {"system": "SYSTEM", "dyski": "DYSKI", "docker": "DOCKER", "parity": "PARITY",
           "alerty": "ALERTY", "cpu": "CPU", "ram": "RAM", "swap": "SWAP", "temp": "Temp.",
           "uptime": "Czas pracy", "load": "Obciążenie", "siec": "Sieć LAN",
           "array": "Array", "uruchomiony": "uruchomiony", "cache": "Cache",
           "aktywne": "aktywne", "uspione": "uśpione", "kontenery": "Kontenery",
           "dzialaja": "działa", "zatrzymane": "zatrzymane", "maszyny": "Maszyny VM",
           "postep": "Postęp", "predkosc": "Prędkość", "koniec": "Koniec za",
           "bledy": "Błędy", "brak_alertow": "Wszystko w porządku", "dni": "d",
           "krytyczne": "KRYTYCZNY", "przypiety": "Ekran zostaje do usunięcia problemu",
           "wolne": "wolne", "z": "z"},
    "en": {"system": "SYSTEM", "dyski": "DISKS", "docker": "DOCKER", "parity": "PARITY",
           "alerty": "ALERTS", "cpu": "CPU", "ram": "RAM", "swap": "SWAP", "temp": "Temp.",
           "uptime": "Uptime", "load": "Load", "siec": "LAN",
           "array": "Array", "uruchomiony": "started", "cache": "Cache",
           "aktywne": "active", "uspione": "spun down", "kontenery": "Containers",
           "dzialaja": "running", "zatrzymane": "stopped", "maszyny": "VMs",
           "postep": "Progress", "predkosc": "Speed", "koniec": "Finishes in",
           "bledy": "Errors", "brak_alertow": "All good", "dni": "d",
           "krytyczne": "CRITICAL", "przypiety": "Stays on until the problem is fixed",
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

# Wariant z alertem krytycznym (makieta zachowania priorytetowego).
PRZYKLADOWE_DANE_KRYTYCZNE = dict(PRZYKLADOWE_DANE, alerty=[
    ("alarm", "Disk 2: wyłączony", "usunięty z array · 19:28"),
    ("uwaga", "Disk 3: 47°C", "próg 45°C"),
    ("uwaga", "paperless", "zatrzymany 14:05"),
    ("uwaga", "SMART Disk 3", "realokowane sektory: 8"),
])


@lru_cache(maxsize=64)
def font(rozmiar, waga="Regular"):
    return ImageFont.truetype(f"{FONT_DIR}Inter-{waga}.otf", rozmiar)


def liczba(v, jezyk, miejsca=1):
    tekst = f"{v:.{miejsca}f}"
    return tekst.replace(".", ",") if jezyk == "pl" else tekst


def kolor_progu(wartosc, uwaga, alarm):
    return KOLORY["alarm"] if wartosc >= alarm else KOLORY["uwaga"] if wartosc >= uwaga else KOLORY["ok"]


DOMYSLNE_PROGI = {"cpu": (70, 90), "cpu_temp": (70, 85), "ram": (80, 92), "swap": (50, 80),
                  "array": (85, 95), "hdd_temp": (45, 50), "ssd_temp": (60, 70)}


def progi(dane, klucz):
    """(ostrzeżenie, alarm) z ustawień użytkownika albo domyślne."""
    p = (dane.get("_progi") or {}).get(klucz)
    return (p[0], p[1]) if p and p[0] is not None else DOMYSLNE_PROGI[klucz]


WAGA_STANU = {"alarm": 0, "uwaga": 1}


def pokaz(dane, n):
    """Czy element n bieżącego ekranu jest widoczny (użytkownik może ukryć elementy w panelu)."""
    return n not in dane.get("_ukryte", ())


def problemy_na_gorze(lista, indeks_stanu, dane):
    """Gdy włączone (domyślnie), elementy z awarią idą na górę: najpierw alarm, potem uwaga.
    Sortowanie stabilne, więc reszta zostaje w kolejności z ustawień."""
    if not dane.get("sortuj_awarie", True):
        return list(lista)
    return sorted(lista, key=lambda e: WAGA_STANU.get(e[indeks_stanu], 2))


def licznik_alertow(dane):
    alerty = dane.get("alerty") or []
    return (sum(1 for a in alerty if a[0] == "alarm"), sum(1 for a in alerty if a[0] == "uwaga"))


def obramowanie(img, dane):
    """Przy alercie krytycznym czerwona ramka dookoła całego ekranu (6 px, mieści się w marginesie)."""
    if licznik_alertow(dane)[0] and dane.get("_ramka", True):
        ImageDraw.Draw(img).rectangle((0, 0, img.width - 1, img.height - 1), outline=KOLORY["alarm"], width=6)
    return img


def naglowek(d, tytul, indeks, dane, w=W):
    """Pasek tytułu; w to szerokość ekranu (480 w układzie poziomym)."""
    krytyczne, ostrzezenia = licznik_alertow(dane)
    indeks = dane.get("_indeks", indeks)          # pozycja w bieżącej kolejce ekranów
    czerwony = bool(krytyczne) and dane.get("_ramka", True)
    # Alert krytyczny barwi nagłówek każdego ekranu na czerwono.
    tlo = KOLORY["alarm"] if czerwony else KOLORY["karta"]
    d.rectangle((0, 0, w, 40), fill=tlo)
    f = font(18, "Bold")
    d.text((M, 20), tytul, font=f, fill=KOLORY["na_alarmie"] if czerwony else KOLORY["tekst"], anchor="lm")
    d.text((w - M, 20), dane["godzina"], font=font(16, "SemiBold"),
           fill=KOLORY["na_alarmie"] if czerwony else KOLORY["szary"], anchor="rm")
    # Który to ekran: kropki przy maks. 6 ekranach, przy większej liczbie tekst „7/11”.
    razem = dane.get("ekrany_razem", 5)
    if razem <= 6:
        for i in range(razem):
            x = w // 2 + 18 + i * 12
            if czerwony:
                kolor = KOLORY["na_alarmie"] if i == indeks else KOLORY["alarm_kropka"]
            else:
                kolor = KOLORY["akcent"] if i == indeks else KOLORY["linia"]
            d.ellipse((x - 3, 17, x + 3, 23), fill=kolor)
    else:
        d.text((w - M - 62, 20), f"{indeks + 1}/{razem}", font=font(13, "SemiBold"),
               fill=KOLORY["na_alarmie"] if czerwony else KOLORY["szary"], anchor="rm")
    # Licznik: biały z liczbą krytycznych albo żółty z liczbą ostrzeżeń.
    if krytyczne or ostrzezenia:
        x0 = M + d.textlength(tytul, font=f) + 10
        tekst = f"! {krytyczne or ostrzezenia}"
        szer = d.textlength(tekst, font=font(13, "Bold")) + 14
        d.rounded_rectangle((x0, 11, x0 + szer, 29), radius=9, fill=(KOLORY["na_alarmie"] if czerwony else KOLORY["alarm"]) if krytyczne else KOLORY["uwaga"])
        d.text((x0 + szer / 2, 20), tekst, font=font(13, "Bold"), fill=(KOLORY["alarm"] if czerwony else KOLORY["na_alarmie"]) if krytyczne else KOLORY["tlo"], anchor="mm")


def pasek(d, x, y, szer, wys, procent, kolor):
    d.rounded_rectangle((x, y, x + szer, y + wys), radius=wys // 2, fill=KOLORY["linia"])
    if procent > 0:
        d.rounded_rectangle((x, y, x + max(wys, int(szer * procent / 100)), y + wys), radius=wys // 2, fill=kolor)


def luk(d, cx, cy, r, procent, kolor, grubosc=14):
    d.arc((cx - r, cy - r, cx + r, cy + r), 135, 405, fill=KOLORY["linia"], width=grubosc)
    if procent > 0:
        d.arc((cx - r, cy - r, cx + r, cy + r), 135, 135 + 270 * procent / 100, fill=kolor, width=grubosc)


def tekst_w_kole(d, cx, cy, tekst, max_szer, rozmiar, kolor):
    """Rysuje liczbę wyśrodkowaną optycznie (po obrysie znaków) i zmniejsza czcionkę, gdy się nie mieści."""
    while rozmiar > 12:
        f = font(rozmiar, "Bold")
        x0, y0, x1, y1 = d.textbbox((0, 0), tekst, font=f, anchor="ls")
        if x1 - x0 <= max_szer:
            break
        rozmiar -= 2
    d.text((cx - (x0 + x1) / 2, cy - (y0 + y1) / 2), tekst, font=f, fill=kolor, anchor="ls")


def karta(d, x, y, szer, wys):
    d.rounded_rectangle((x, y, x + szer, y + wys), radius=10, fill=KOLORY["karta"])


def ekran_system(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["system"], 0, dane)
    if pokaz(dane, 0):
        # duży wskaźnik CPU
        luk(d, M + 74, 120, 60, dane["cpu"], kolor_progu(dane["cpu"], *progi(dane, "cpu")))
        # wnętrze łuku: promień 60 minus grubość 14 daje 92 px średnicy; zostawiamy odstęp od łuku
        tekst_w_kole(d, M + 74, 114, f"{dane['cpu']:.0f}%", 70, 30, KOLORY["tekst"])
        d.text((M + 74, 146), t["cpu"], font=font(14, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    # temperatura CPU i czas pracy
    temp = dane["cpu_temp"]
    kt = kolor_progu(temp, *progi(dane, "cpu_temp")) if temp is not None else KOLORY["szary"]
    x0 = W - M - 126
    if pokaz(dane, 1):
        karta(d, x0, 54, 126, 62)
        d.text((x0 + 12, 66), t["temp"] + " CPU", font=font(13), fill=KOLORY["szary"])
        d.text((W - M - 12, 84), f"{temp:.0f}°C" if temp is not None else "—", font=font(26, "Bold"), fill=kt, anchor="ra")
    if pokaz(dane, 2):
        karta(d, x0, 124, 126, 56)
        d.text((x0 + 12, 133), t["uptime"], font=font(13), fill=KOLORY["szary"])
        d.text((W - M - 12, 151), dane["uptime"], font=font(21, "Bold"), fill=KOLORY["tekst"], anchor="ra")
    if pokaz(dane, 3):
        # rdzenie
        y0, wys = 194, 36
        n = len(dane["rdzenie"]); szer = (W - 2 * M - (n - 1) * 4) / n
        for i, v in enumerate(dane["rdzenie"]):
            x = M + i * (szer + 4)
            d.rectangle((x, y0, x + szer, y0 + wys), fill=KOLORY["linia"])
            h = int(wys * v / 100)
            d.rectangle((x, y0 + wys - h, x + szer, y0 + wys), fill=kolor_progu(v, *progi(dane, "cpu")))
    if pokaz(dane, 4):
        # wykres historii CPU
        karta(d, M, 242, W - 2 * M, 58)
        hist = dane["historia_cpu"]; krok = (W - 2 * M - 20) / (len(hist) - 1)
        pkt = [(M + 10 + i * krok, 292 - v * 0.42) for i, v in enumerate(hist)]
        d.line(pkt, fill=KOLORY["akcent"], width=2)
    if pokaz(dane, 5):
        # RAM i SWAP
        y = 314
        d.text((M, y), t["ram"], font=font(15, "SemiBold"), fill=KOLORY["tekst"])
        d.text((W - M, y), f"{dane['ram_txt']}  {dane['ram']:.0f}%", font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
        pasek(d, M, y + 24, W - 2 * M, 12, dane["ram"], kolor_progu(dane["ram"], *progi(dane, "ram")))
        y = 364
        d.text((M, y), t["swap"], font=font(15, "SemiBold"), fill=KOLORY["szary"])
        if dane.get("swap") is None:
            d.text((W - M, y), "—", font=font(15, "SemiBold"), fill=KOLORY["szary"], anchor="ra")
        else:
            d.text((W - M, y), f"{dane['swap']:.0f}%", font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
    if pokaz(dane, 6):
        # load i sieć
        szer = (W - 2 * M - 12) // 2
        y = 400
        karta(d, M, y, szer, 58); karta(d, W - M - szer, y, szer, 58)
        d.text((M + 10, y + 8), t["load"], font=font(12), fill=KOLORY["szary"])
        d.text((M + szer - 10, y + 28), "  ".join(liczba(v, t["_j"], 2) for v in dane["load"]), font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
        x = W - M - szer + 10
        d.text((x, y + 8), t["siec"], font=font(12), fill=KOLORY["szary"])
        # strzałka przy lewej krawędzi, liczba wyrównana do prawej
        for dy, znak, wartosc, kolor in ((24, "↓", dane["rx"], KOLORY["ok"]), (40, "↑", dane["tx"], KOLORY["akcent"])):
            d.text((x, y + dy), znak, font=font(13, "SemiBold"), fill=kolor)
            d.text((W - M - 10, y + dy), wartosc, font=font(13, "SemiBold"), fill=kolor, anchor="ra")
    return obramowanie(img, dane)


def ekran_dyski(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["dyski"], 1, dane)
    if pokaz(dane, 0):
        d.ellipse((M, 58, M + 14, 72), fill=KOLORY[dane.get("array_stan", "ok")])
        d.text((M + 22, 65), f"{t['array']}: {dane.get('array_opis', t['uruchomiony'])}", font=font(16, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    if pokaz(dane, 1):
        for i, (nazwa, proc, txt) in enumerate([(t["array"], dane["array_uzycie"], dane["array_txt"]),
                                                 (t["cache"], dane["cache_uzycie"], dane["cache_txt"])]):
            y = 88 + i * 62
            karta(d, M, y, W - 2 * M, 54)
            d.text((M + 12, y + 10), nazwa, font=font(14, "SemiBold"), fill=KOLORY["tekst"])
            d.text((W - M - 12, y + 10), f"{txt}  {proc}%", font=font(14, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
            pasek(d, M + 12, y + 34, W - 2 * M - 24, 10, proc, kolor_progu(proc, *progi(dane, "array")))
    if pokaz(dane, 2):
        aktywne = sum(1 for x in dane["dyski"] if x[3])
        d.text((M, 222), f"{aktywne} {t['aktywne']} · {len(dane['dyski']) - aktywne} {t['uspione']}",
               font=font(13), fill=KOLORY["szary"])
        for i, (nazwa, temp, smart, aktywny) in enumerate(problemy_na_gorze(dane["dyski"], 2, dane)):
            y = 240 + i * 36
            d.line((M, y + 34, W - M, y + 34), fill=KOLORY["linia"])
            d.ellipse((M + 2, y + 11, M + 14, y + 23), fill=KOLORY[smart] if aktywny or smart != "ok" else KOLORY["linia"])
            d.text((M + 24, y + 17), nazwa, font=font(16, "SemiBold"), fill=KOLORY["tekst"] if aktywny else KOLORY["szary"], anchor="lm")
            tekst = f"{temp}°C" if aktywny else "—"
            kolor = kolor_progu(temp, *progi(dane, "hdd_temp")) if aktywny else KOLORY["szary"]
            d.text((W - M - 2, y + 17), tekst, font=font(20, "Bold"), fill=kolor, anchor="rm")
            if aktywny:
                d.text((W - M - 78, y + 17), "SMART", font=font(11, "SemiBold"),
                   fill=KOLORY[smart] if smart != "ok" else KOLORY["szary"], anchor="rm")
    return obramowanie(img, dane)


def ekran_docker(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["docker"], 2, dane)
    dz, wsz = dane["kontenery_dzialaja"], dane["kontenery_wszystkie"]
    if pokaz(dane, 0):
        karta(d, M, 54, W - 2 * M, 84)
        d.text((M + 14, 64), t["kontenery"], font=font(14), fill=KOLORY["szary"])
        d.text((M + 14, 84), str(dz), font=font(44, "Bold"), fill=KOLORY["ok"])
        d.text((M + 86, 106), f"/ {wsz} {t['dzialaja']}", font=font(16, "SemiBold"), fill=KOLORY["szary"])
        d.text((W - 2 * M, 106), f"{wsz - dz} {t['zatrzymane']}", font=font(14, "SemiBold"), fill=KOLORY["uwaga"], anchor="ra")
    if pokaz(dane, 1):
        for i, (nazwa, stan, cpu, ram) in enumerate(problemy_na_gorze(dane["kontenery"], 1, dane)):
            y = 150 + i * 40
            d.line((M, y + 37, W - M, y + 37), fill=KOLORY["linia"])
            d.ellipse((M + 2, y + 12, M + 14, y + 24), fill=KOLORY[stan])
            d.text((M + 24, y + 18), nazwa, font=font(16, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
            d.text((W - M - 2, y + 18), ram, font=font(13), fill=KOLORY["szary"], anchor="rm")
            d.text((W - M - 76, y + 18), f"{liczba(cpu, t['_j'])}%", font=font(14, "SemiBold"), fill=KOLORY["tekst"], anchor="rm")
    if pokaz(dane, 2):
        y = 392
        d.text((M, y), t["maszyny"], font=font(14), fill=KOLORY["szary"])
        for i, (nazwa, stan) in enumerate(problemy_na_gorze(dane["vm"], 1, dane)):
            yy = y + 24 + i * 26
            d.ellipse((M + 2, yy + 4, M + 12, yy + 14), fill=KOLORY[stan])
            d.text((M + 22, yy + 9), nazwa, font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    return obramowanie(img, dane)


def ekran_parity(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["parity"], 3, dane)
    p = dane["parity_postep"]
    if pokaz(dane, 0):
        luk(d, W // 2, 180, 100, p, KOLORY["akcent2"], grubosc=18)
        tekst_w_kole(d, W // 2, 172, f"{liczba(p, t['_j'])}%", 140, 44, KOLORY["tekst"])
        d.text((W // 2, 214), t["postep"], font=font(15, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    if pokaz(dane, 1):
        for i, (etyk, wart, kol) in enumerate([(t["predkosc"], dane["parity_predkosc"], KOLORY["tekst"]),
                                                (t["koniec"], dane["parity_eta"], KOLORY["tekst"]),
                                                (t["bledy"], str(dane["parity_bledy"]), KOLORY["alarm"] if dane["parity_bledy"] else KOLORY["ok"])]):
            y = 306 + i * 52
            karta(d, M, y, W - 2 * M, 44)
            d.text((M + 14, y + 22), etyk, font=font(15), fill=KOLORY["szary"], anchor="lm")
            d.text((W - M - 14, y + 22), wart, font=font(22, "Bold"), fill=kol, anchor="rm")
    return obramowanie(img, dane)


def ekran_alerty(t, dane, puste=False):
    puste = puste or not dane.get("alerty")
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["alerty"], 4, dane if not puste else dict(dane, alerty=[]))
    if puste:
        if pokaz(dane, 1):
            d.ellipse((W // 2 - 50, 170, W // 2 + 50, 270), outline=KOLORY["ok"], width=8)
            d.line([(W // 2 - 24, 222), (W // 2 - 6, 240), (W // 2 + 26, 204)], fill=KOLORY["ok"], width=9)
            d.text((W // 2, 300), t["brak_alertow"], font=font(20, "SemiBold"), fill=KOLORY["tekst"], anchor="mm")
        return img  # pusty stan: brak alertów, więc bez ramki
    if pokaz(dane, 0):
        # Krytyczne zawsze na górze, potem ostrzeżenia; mieszczą się 4 karty.
        alerty = sorted(dane["alerty"], key=lambda a: 0 if a[0] == "alarm" else 1)[:4]
        krytyczne = any(a[0] == "alarm" for a in alerty)
        y = 54
        for poziom, tytul, opis in alerty:
            wys = 86 if poziom == "alarm" else 72
            if poziom == "alarm":
                d.rounded_rectangle((M, y, W - M, y + wys), radius=10, fill=KOLORY["alarm_tlo"], outline=KOLORY["alarm"], width=2)
                d.text((M + 14, y + 12), t["krytyczne"], font=font(11, "Bold"), fill=KOLORY["alarm"])
                d.text((M + 14, y + 28), tytul, font=font(20, "Bold"), fill=KOLORY["tekst"])
                d.text((M + 14, y + 58), opis, font=font(14), fill=KOLORY["alarm_opis"])
            else:
                karta(d, M, y, W - 2 * M, wys)
                d.rounded_rectangle((M, y, M + 8, y + wys), radius=4, fill=KOLORY[poziom])
                d.text((M + 20, y + 14), tytul, font=font(19, "Bold"), fill=KOLORY[poziom])
                d.text((M + 20, y + 44), opis, font=font(14), fill=KOLORY["szary"])
            y += wys + 8
        if krytyczne:
            d.text((W // 2, H - M - 6), t["przypiety"], font=font(12, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    return obramowanie(img, dane)


def wszystkie(jezyk="pl", dane=None):
    """Wszystkie ekrany z danymi (domyślnie przykładowymi). Używane do makiet i testów."""
    dane = dane or PRZYKLADOWE_DANE
    t = dict(TEKSTY[jezyk], _j=jezyk)
    return {"1-system": ekran_system(t, dane), "2-dyski": ekran_dyski(t, dane), "3-docker": ekran_docker(t, dane),
            "4-parity": ekran_parity(t, dane), "5-alerty": ekran_alerty(t, dane),
            "5b-alerty-puste": ekran_alerty(t, dane, True),
            "5c-alerty-krytyczne": ekran_alerty(t, PRZYKLADOWE_DANE_KRYTYCZNE),
            "1c-system-krytyczny": ekran_system(t, dict(PRZYKLADOWE_DANE_KRYTYCZNE, **{k: v for k, v in dane.items() if k != "alerty"}))}
