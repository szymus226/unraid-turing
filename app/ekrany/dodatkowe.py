"""Dodatkowe ekrany LCD: ruch dysków, historia 24 h, sieć, aktualizacje i kopie, zegar, kod QR.

Rysowane tymi samymi klockami co ekrany podstawowe (rysuj.py), z tym samym marginesem M.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .rysuj import (H, KOLORY, M, W, font, karta, kolor_progu, liczba, naglowek, obramowanie,
                    problemy_na_gorze)

TEKSTY = {
    "pl": {"ruch_dyskow": "RUCH DYSKÓW", "historia": "OSTATNIE 24 H", "siec_t": "SIEĆ", "aktualizacje": "AKTUALIZACJE",
           "zegar": "", "qr": "PANEL", "odczyt": "odczyt", "zapis": "zapis", "uspiony": "uśpiony",
           "razem": "Razem", "min": "min", "maks": "maks", "sr": "śr.", "temp_cpu": "Temp. CPU",
           "internet": "Internet", "dziala": "działa", "brak": "brak połączenia", "bramka": "Router",
           "pobieranie": "Pobieranie", "wysylanie": "Wysyłanie", "ip": "Publiczne IP", "ukryte": "ukryte",
           "tunel": "Tunel Cloudflare", "tailscale": "Tailscale", "z_pulpitu": "z pulpitu",
           "system_unraid": "Unraid", "aktualny": "aktualny", "wtyczki": "Wtyczki", "kontenery": "Kontenery",
           "do_aktualizacji": "do aktualizacji", "kopia": "Kopia appdata", "parity": "Kontrola parity",
           "restart": "Ostatni restart", "temu": "temu", "bledow": "błędów",
           "wszystko_ok": "Wszystko w porządku", "zeskanuj": "Zeskanuj telefonem, żeby otworzyć panel",
           "tylko_lan": "działa tylko w sieci domowej", "pogoda": "pochmurno"},
    "en": {"ruch_dyskow": "DISK ACTIVITY", "historia": "LAST 24 H", "siec_t": "NETWORK", "aktualizacje": "UPDATES",
           "zegar": "", "qr": "PANEL", "odczyt": "read", "zapis": "write", "uspiony": "spun down",
           "razem": "Total", "min": "min", "maks": "max", "sr": "avg", "temp_cpu": "CPU temp.",
           "internet": "Internet", "dziala": "up", "brak": "down", "bramka": "Router",
           "pobieranie": "Download", "wysylanie": "Upload", "ip": "Public IP", "ukryte": "hidden",
           "tunel": "Cloudflare tunnel", "tailscale": "Tailscale", "z_pulpitu": "from desktop",
           "system_unraid": "Unraid", "aktualny": "up to date", "wtyczki": "Plugins", "kontenery": "Containers",
           "do_aktualizacji": "to update", "kopia": "Appdata backup", "parity": "Parity check",
           "restart": "Last restart", "temu": "ago", "bledow": "errors",
           "wszystko_ok": "All good", "zeskanuj": "Scan with your phone to open the panel",
           "tylko_lan": "works on your home network only", "pogoda": "cloudy"},
}

DNI = {"pl": ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"],
       "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
MIESIACE = {"pl": ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
                   "września", "października", "listopada", "grudnia"],
            "en": ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"]}

# Indeksy nowych ekranów w kolejce (po pięciu podstawowych).
INDEKS = {"ruch": 5, "historia": 6, "siec": 7, "aktualizacje": 8, "zegar": 9, "qr": 10}


def _wykres(d, x0, y0, szer, wys, wartosci, kolor, maks=None, wypelnienie=True):
    """Wykres liniowy z delikatnym wypełnieniem i zaznaczonym ostatnim punktem."""
    maks = maks or max(max(wartosci), 1)
    krok = szer / (len(wartosci) - 1)
    pkt = [(x0 + i * krok, y0 + wys - wys * min(v, maks) / maks) for i, v in enumerate(wartosci)]
    if wypelnienie:
        tlo = tuple(int(c * 0.25 + k * 0.75) for c, k in zip(kolor, KOLORY["karta"]))
        d.polygon(pkt + [(x0 + szer, y0 + wys), (x0, y0 + wys)], fill=tlo)
    d.line(pkt, fill=kolor, width=2)
    x, y = pkt[-1]
    d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=kolor)


def ekran_ruch_dyskow(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["ruch_dyskow"], INDEKS["ruch"], dane)
    io = dane["dyski_io"]
    suma_r = sum(x[2] for x in io if x[1]); suma_z = sum(x[3] for x in io if x[1])
    karta(d, M, 54, W - 2 * M, 62)
    d.text((M + 12, 64), t["razem"], font=font(13), fill=KOLORY["szary"])
    d.text((M + 12, 84), f"↓ {liczba(suma_r, t['_j'])} MB/s", font=font(18, "Bold"), fill=KOLORY["ok"])
    d.text((W - M - 12, 84), f"↑ {liczba(suma_z, t['_j'])} MB/s", font=font(18, "Bold"), fill=KOLORY["akcent"], anchor="ra")
    d.text((W - M - 12, 64), f"{t['odczyt']} · {t['zapis']}", font=font(13), fill=KOLORY["szary"], anchor="ra")
    maks = max([x[2] for x in io] + [x[3] for x in io] + [1])
    for i, (nazwa, aktywny, r, z, stan) in enumerate(problemy_na_gorze(io, 4, dane)):
        y = 130 + i * 52
        d.ellipse((M + 2, y + 6, M + 14, y + 18), fill=KOLORY[stan] if aktywny else KOLORY["linia"])
        d.text((M + 24, y + 12), nazwa, font=font(16, "SemiBold"), fill=KOLORY["tekst"] if aktywny else KOLORY["szary"], anchor="lm")
        if not aktywny:
            d.text((W - M, y + 12), t["uspiony"], font=font(13), fill=KOLORY["szary"], anchor="rm")
            d.line((M, y + 44, W - M, y + 44), fill=KOLORY["linia"])
            continue
        d.text((W - M, y + 12), f"↓ {liczba(r, t['_j'])}  ↑ {liczba(z, t['_j'])}", font=font(13, "SemiBold"), fill=KOLORY["tekst"], anchor="rm")
        szer = W - 2 * M - 24
        for j, (v, kolor) in enumerate(((r, KOLORY["ok"]), (z, KOLORY["akcent"]))):
            yy = y + 28 + j * 7
            d.rounded_rectangle((M + 24, yy, M + 24 + szer, yy + 4), radius=2, fill=KOLORY["linia"])
            if v > 0:
                d.rounded_rectangle((M + 24, yy, M + 24 + max(4, int(szer * v / maks)), yy + 4), radius=2, fill=kolor)
        d.line((M, y + 44, W - M, y + 44), fill=KOLORY["linia"])
    return obramowanie(img, dane)


def ekran_historia(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["historia"], INDEKS["historia"], dane)
    serie = [("CPU", dane["hist_cpu"], "%", KOLORY["akcent"], 100),
             ("RAM", dane["hist_ram"], "%", KOLORY["ok"], 100),
             (t["temp_cpu"], dane["hist_temp"], "°C", KOLORY["uwaga"], 100)]
    for i, (nazwa, wart, jedn, kolor, maks) in enumerate(serie):
        y = 54 + i * 136
        karta(d, M, y, W - 2 * M, 126)
        d.text((M + 12, y + 10), nazwa, font=font(14, "SemiBold"), fill=KOLORY["tekst"])
        d.text((W - M - 12, y + 8), f"{wart[-1]:.0f}{jedn}", font=font(20, "Bold"), fill=kolor, anchor="ra")
        _wykres(d, M + 12, y + 38, W - 2 * M - 24, 58, wart, kolor, maks)
        sr = sum(wart) / len(wart)
        opis = f"{t['min']} {min(wart):.0f}{jedn}   {t['sr']} {sr:.0f}{jedn}   {t['maks']} {max(wart):.0f}{jedn}"
        d.text((M + 12, y + 106), opis, font=font(12), fill=KOLORY["szary"], anchor="lm")
    return obramowanie(img, dane)


def _wiersz_stanu(d, y, etykieta, wartosc, stan):
    d.ellipse((M + 2, y + 6, M + 14, y + 18), fill=KOLORY[stan])
    d.text((M + 24, y + 12), etykieta, font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    d.text((W - M, y + 12), wartosc, font=font(14, "SemiBold"),
           fill=KOLORY["szary"] if stan == "szary" else KOLORY["tekst"], anchor="rm")
    d.line((M, y + 30, W - M, y + 30), fill=KOLORY["linia"])


def ekran_siec(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["siec_t"], INDEKS["siec"], dane)
    s = dane["siec"]
    stan = "ok" if s["internet"] else "alarm"
    karta(d, M, 54, W - 2 * M, 70)
    d.ellipse((M + 12, 66, M + 26, 80), fill=KOLORY[stan])
    d.text((M + 34, 73), t["internet"], font=font(16, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    d.text((W - M - 12, 73), t["dziala"] if s["internet"] else t["brak"], font=font(16, "Bold"), fill=KOLORY[stan], anchor="rm")
    d.text((M + 12, 104), f"{t['bramka']} {liczba(s['ping_bramka'], t['_j'])} ms", font=font(13), fill=KOLORY["szary"], anchor="lm")
    d.text((W - M - 12, 104), f"{t['internet']} {s['ping_internet']} ms", font=font(13), fill=KOLORY["szary"], anchor="rm")
    # ruch z ostatniej godziny
    karta(d, M, 134, W - 2 * M, 150)
    d.text((M + 12, 144), t["pobieranie"], font=font(13), fill=KOLORY["szary"])
    d.text((M + 12, 162), s["rx"], font=font(20, "Bold"), fill=KOLORY["ok"])
    d.text((W - M - 12, 144), t["wysylanie"], font=font(13), fill=KOLORY["szary"], anchor="ra")
    d.text((W - M - 12, 162), s["tx"], font=font(20, "Bold"), fill=KOLORY["akcent"], anchor="ra")
    maks = max(s["hist_rx"] + s["hist_tx"])
    _wykres(d, M + 12, 196, W - 2 * M - 24, 76, s["hist_rx"], KOLORY["ok"], maks)
    _wykres(d, M + 12, 196, W - 2 * M - 24, 76, s["hist_tx"], KOLORY["akcent"], maks, wypelnienie=False)
    y = 296
    _wiersz_stanu(d, y, t["tunel"], t["dziala"] if s["tunel"] else t["brak"], "ok" if s["tunel"] else "alarm")
    _wiersz_stanu(d, y + 38, t["tailscale"], t["z_pulpitu"], "szary")
    _wiersz_stanu(d, y + 76, t["ip"], t["ukryte"], "szary")
    return obramowanie(img, dane)


def ekran_aktualizacje(t, dane):
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["aktualizacje"], INDEKS["aktualizacje"], dane)
    a = dane["aktualizacje"]
    wiersze = [
        (t["system_unraid"], f"{a['wersja']} · {t['aktualny']}" if not a["unraid_nowa"] else a["unraid_nowa"], "ok" if not a["unraid_nowa"] else "uwaga"),
        (t["wtyczki"], f"{a['wtyczki']} {t['do_aktualizacji']}", "uwaga" if a["wtyczki"] else "ok"),
        (t["kontenery"], f"{a['kontenery']} {t['do_aktualizacji']}", "uwaga" if a["kontenery"] else "ok"),
        (t["kopia"], a["kopia"], a["kopia_stan"]),
        (t["parity"], f"{a['parity']} · {a['parity_bledy']} {t['bledow']}", "ok" if not a["parity_bledy"] else "alarm"),
        (t["restart"], f"{a['restart']} {t['temu']}", "ok"),
    ]
    wiersze = problemy_na_gorze(wiersze, 2, dane)
    for i, (etykieta, wartosc, stan) in enumerate(wiersze):
        y = 54 + i * 66
        karta(d, M, y, W - 2 * M, 58)
        d.rounded_rectangle((M, y, M + 6, y + 58), radius=3, fill=KOLORY[stan])
        d.text((M + 18, y + 10), etykieta, font=font(13), fill=KOLORY["szary"])
        d.text((M + 18, y + 28), wartosc, font=font(17, "Bold"), fill=KOLORY["tekst"] if stan == "ok" else KOLORY[stan])
    return obramowanie(img, dane)


def ekran_zegar(t, dane):
    """Ekran nocny: duży zegar, data, opcjonalna pogoda i jedna linia stanu serwera."""
    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    z = dane["zegar"]
    d.text((W // 2, 150), z["godzina"], font=font(96, "Bold"), fill=KOLORY["tekst"], anchor="mm")
    d.text((W // 2, 222), DNI[t["_j"]][z["dzien_tyg"]], font=font(20, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    d.text((W // 2, 250), f"{z['dzien']} {MIESIACE[t['_j']][z['miesiac'] - 1]}", font=font(20, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    if z.get("pogoda") is not None:
        d.text((W // 2, 310), f"{z['pogoda']}°C · {t['pogoda']}", font=font(18), fill=KOLORY["tekst"], anchor="mm")
    krytyczne, ostrzezenia = (sum(1 for a in dane.get("alerty", []) if a[0] == p) for p in ("alarm", "uwaga"))
    if krytyczne:
        stan, tekst = "alarm", f"{krytyczne} {t['krytyczne'].lower()}"
    elif ostrzezenia:
        stan, tekst = "uwaga", f"! {ostrzezenia}"
    else:
        stan, tekst = "ok", t["wszystko_ok"]
    szer = d.textlength(tekst, font=font(15, "SemiBold"))
    x = W // 2 - (szer + 22) / 2
    d.ellipse((x, H - M - 26, x + 12, H - M - 14), fill=KOLORY[stan])
    d.text((x + 22, H - M - 20), tekst, font=font(15, "SemiBold"), fill=KOLORY["szary"], anchor="lm")
    return obramowanie(img, dane)


def ekran_qr(t, dane):
    import segno

    img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    naglowek(d, t["qr"], INDEKS["qr"], dane)
    kod = segno.make(dane["adres_panelu"], error="m")
    macierz = list(kod.matrix)
    n = len(macierz)
    modul = min((W - 2 * M - 40) // (n + 8), 8)
    bok = modul * (n + 8)
    x0, y0 = (W - bok) // 2, 70
    d.rounded_rectangle((x0, y0, x0 + bok, y0 + bok), radius=10, fill=(255, 255, 255))
    for r, wiersz in enumerate(macierz):
        for c, bit in enumerate(wiersz):
            if bit:
                x, y = x0 + (c + 4) * modul, y0 + (r + 4) * modul
                d.rectangle((x, y, x + modul - 1, y + modul - 1), fill=(0, 0, 0))
    y = y0 + bok + 22
    d.text((W // 2, y), dane["adres_panelu"], font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="mm")
    d.text((W // 2, y + 30), t["zeskanuj"], font=font(13), fill=KOLORY["szary"], anchor="mm")
    d.text((W // 2, y + 50), t["tylko_lan"], font=font(13), fill=KOLORY["szary"], anchor="mm")
    return obramowanie(img, dane)


PRZYKLADOWE = {
    "ekrany_razem": 11,
    "dyski_io": [("Parity", True, 0.0, 12.4, "ok"), ("Disk 1", True, 45.2, 12.4, "ok"), ("Disk 2", False, 0, 0, "ok"),
                 ("Disk 3", True, 0.8, 0.0, "uwaga"), ("Disk 4", False, 0, 0, "ok"), ("Cache", True, 3.1, 22.7, "ok")],
    "hist_cpu": [12, 10, 9, 8, 8, 9, 14, 22, 35, 28, 24, 20, 26, 31, 44, 38, 29, 25, 23, 27, 33, 29, 24, 23],
    "hist_ram": [55, 55, 54, 54, 54, 55, 56, 58, 62, 63, 62, 61, 61, 62, 64, 64, 63, 62, 61, 61, 62, 62, 61, 61],
    "hist_temp": [44, 43, 42, 42, 41, 42, 45, 49, 56, 53, 51, 50, 52, 54, 61, 58, 54, 52, 51, 52, 55, 54, 52, 52],
    "siec": {"internet": True, "ping_bramka": 0.6, "ping_internet": 14, "rx": "4,2 MB/s", "tx": "0,8 MB/s",
             "hist_rx": [1.2, 1.5, 0.9, 2.2, 3.8, 6.1, 5.2, 4.0, 3.1, 2.4, 2.9, 4.4, 5.8, 4.9, 4.2],
             "hist_tx": [0.3, 0.2, 0.4, 0.5, 0.9, 1.4, 1.1, 0.8, 0.6, 0.5, 0.6, 0.7, 1.0, 0.9, 0.8], "tunel": True},
    "aktualizacje": {"wersja": "7.2.1", "unraid_nowa": None, "wtyczki": 2, "kontenery": 5,
                     "kopia": "wczoraj 03:00", "kopia_stan": "ok", "parity": "1 lis", "parity_bledy": 0, "restart": "12 dni"},
    "zegar": {"godzina": "21:42", "dzien_tyg": 0, "dzien": 16, "miesiac": 11, "pogoda": 4},
    "adres_panelu": "http://tower.local:8766",
}


def wszystkie(jezyk="pl", dane=None):
    from .rysuj import PRZYKLADOWE_DANE, TEKSTY as TEKSTY_PODST

    dane = dict(PRZYKLADOWE_DANE, **PRZYKLADOWE, **(dane or {}))
    if jezyk == "en":
        dane["aktualizacje"] = dict(dane["aktualizacje"], kopia="yesterday 03:00", parity="Nov 1", restart="12 days")
    t = dict(TEKSTY_PODST[jezyk], **TEKSTY[jezyk], _j=jezyk)
    return {"6-ruch-dyskow": ekran_ruch_dyskow(t, dane), "7-historia": ekran_historia(t, dane),
            "8-siec": ekran_siec(t, dane), "9-aktualizacje": ekran_aktualizacje(t, dane),
            "10-zegar": ekran_zegar(t, dane), "11-qr": ekran_qr(t, dane)}
