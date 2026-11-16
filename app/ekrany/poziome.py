"""Ekrany w układzie poziomym 480×320 (ekran położony bokiem, np. kabel USB z boku).

Te same dane, teksty i klocki co w układzie pionowym; inny tylko rozkład elementów:
zwykle dwie kolumny po 216 px z odstępem 12 px.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from . import dodatkowe as dod
from .pogoda import OPISY, ikona, rodzaj_pogody
from .rysuj import (KOLORY, M, font, karta, kolor_progu, liczba, luk, naglowek, obramowanie, pasek,
                    problemy_na_gorze, tekst_w_kole)

PW, PH = 480, 320
KOL = 216                    # szerokość kolumny
L, P = M, M + KOL + 12       # x lewej i prawej kolumny
G, D = 52, PH - M            # góra i dół treści


def _nowy(t, tytul, indeks, dane):
    img = Image.new("RGB", (PW, PH), KOLORY["tlo"]); d = ImageDraw.Draw(img)
    if tytul is not None:
        naglowek(d, tytul, indeks, dane, w=PW)
    return img, d


def _wiersz(d, x, szer, y, etykieta, wartosc, stan, wys=30):
    """Wiersz listy: kropka stanu, etykieta po lewej, wartość po prawej, linia pod spodem."""
    d.ellipse((x + 2, y + wys / 2 - 6, x + 14, y + wys / 2 + 6), fill=KOLORY[stan] if stan in KOLORY else KOLORY["szary"])
    d.text((x + 24, y + wys / 2), etykieta, font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    d.text((x + szer, y + wys / 2), wartosc, font=font(14, "SemiBold"),
           fill=KOLORY["szary"] if stan == "szary" else KOLORY["tekst"], anchor="rm")
    d.line((x, y + wys + 4, x + szer, y + wys + 4), fill=KOLORY["linia"])


# --- ekrany podstawowe ---
def ekran_system(t, dane):
    img, d = _nowy(t, t["system"], 0, dane)
    # łuk CPU
    luk(d, L + 64, 116, 56, dane["cpu"], kolor_progu(dane["cpu"], 70, 90))
    tekst_w_kole(d, L + 64, 110, f"{dane['cpu']:.0f}%", 56, 26, KOLORY["tekst"])
    d.text((L + 64, 140), t["cpu"], font=font(13, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    # temperatura i czas pracy obok łuku
    temp = dane["cpu_temp"]
    kt = kolor_progu(temp, 70, 85) if temp is not None else KOLORY["szary"]
    x0, sz = L + 138, KOL - 138
    karta(d, x0, G, sz, 58)
    d.text((x0 + 10, G + 8), t["temp"], font=font(12), fill=KOLORY["szary"])
    d.text((x0 + sz - 10, G + 26), f"{temp:.0f}°C" if temp is not None else "—", font=font(22, "Bold"), fill=kt, anchor="ra")
    karta(d, x0, G + 66, sz, 58)
    d.text((x0 + 10, G + 74), t["uptime"], font=font(12), fill=KOLORY["szary"])
    d.text((x0 + sz - 10, G + 94), dane["uptime"], font=font(17, "Bold"), fill=KOLORY["tekst"], anchor="ra")
    # rdzenie i historia CPU w prawej kolumnie
    n = len(dane["rdzenie"]); szer = (KOL - (n - 1) * 4) / n
    for i, v in enumerate(dane["rdzenie"]):
        x = P + i * (szer + 4)
        d.rectangle((x, G, x + szer, G + 50), fill=KOLORY["linia"])
        h = int(50 * v / 100)
        d.rectangle((x, G + 50 - h, x + szer, G + 50), fill=kolor_progu(v, 70, 90))
    karta(d, P, G + 60, KOL, 64)
    hist = dane["historia_cpu"]; krok = (KOL - 20) / (len(hist) - 1)
    d.line([(P + 10 + i * krok, G + 116 - v * 0.48) for i, v in enumerate(hist)], fill=KOLORY["akcent"], width=2)
    # RAM i SWAP
    y = 190
    d.text((L, y), t["ram"], font=font(14, "SemiBold"), fill=KOLORY["tekst"])
    d.text((L + KOL, y), f"{dane['ram_txt']}  {dane['ram']:.0f}%", font=font(14, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
    pasek(d, L, y + 24, KOL, 10, dane["ram"], kolor_progu(dane["ram"], 80, 92))
    d.text((P, y), t["swap"], font=font(14, "SemiBold"), fill=KOLORY["szary"])
    if dane.get("swap") is None:
        d.text((P + KOL, y), "—", font=font(14, "SemiBold"), fill=KOLORY["szary"], anchor="ra")
        pasek(d, P, y + 24, KOL, 10, 0, KOLORY["linia"])
    else:
        d.text((P + KOL, y), f"{dane['swap']:.0f}%", font=font(14, "SemiBold"), fill=KOLORY["tekst"], anchor="ra")
        pasek(d, P, y + 24, KOL, 10, dane["swap"], kolor_progu(dane["swap"], 50, 80))
    # load i sieć
    y = 244
    karta(d, L, y, KOL, D - y); karta(d, P, y, KOL, D - y)
    d.text((L + 10, y + 8), t["load"], font=font(12), fill=KOLORY["szary"])
    d.text((L + KOL - 10, y + 30), "  ".join(liczba(v, t["_j"], 2) for v in dane["load"]), font=font(15, "SemiBold"),
           fill=KOLORY["tekst"], anchor="ra")
    d.text((P + 10, y + 8), t["siec"], font=font(12), fill=KOLORY["szary"])
    d.text((P + 10, y + 30), f"↓ {dane['rx']}", font=font(14, "SemiBold"), fill=KOLORY["ok"])
    d.text((P + KOL - 10, y + 30), f"↑ {dane['tx']}", font=font(14, "SemiBold"), fill=KOLORY["akcent"], anchor="ra")
    return obramowanie(img, dane)


def ekran_dyski(t, dane):
    img, d = _nowy(t, t["dyski"], 1, dane)
    d.ellipse((L, G + 4, L + 14, G + 18), fill=KOLORY["ok"])
    d.text((L + 22, G + 11), f"{t['array']}: {t['uruchomiony']}", font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    for i, (nazwa, proc, txt) in enumerate([(t["array"], dane["array_uzycie"], dane["array_txt"]),
                                             (t["cache"], dane["cache_uzycie"], dane["cache_txt"])]):
        y = G + 34 + i * 66
        karta(d, L, y, KOL, 58)
        d.text((L + 12, y + 10), nazwa, font=font(14, "SemiBold"), fill=KOLORY["tekst"])
        d.text((L + KOL - 12, y + 10), f"{proc}%", font=font(14, "Bold"), fill=KOLORY["tekst"], anchor="ra")
        d.text((L + 12, y + 30), txt, font=font(12), fill=KOLORY["szary"])
        pasek(d, L + 12, y + 46, KOL - 24, 6, proc, kolor_progu(proc, 85, 95))
    aktywne = sum(1 for x in dane["dyski"] if x[3])
    d.text((L, D - 8), f"{aktywne} {t['aktywne']} · {len(dane['dyski']) - aktywne} {t['uspione']}",
           font=font(13), fill=KOLORY["szary"], anchor="ls")
    for i, (nazwa, temp, smart, aktywny) in enumerate(problemy_na_gorze(dane["dyski"], 2, dane)[:6]):
        y = G + i * 42
        d.ellipse((P + 2, y + 11, P + 14, y + 23), fill=KOLORY[smart] if aktywny else KOLORY["linia"])
        d.text((P + 24, y + 17), nazwa, font=font(15, "SemiBold"), fill=KOLORY["tekst"] if aktywny else KOLORY["szary"], anchor="lm")
        tekst = f"{temp}°C" if aktywny else "—"
        d.text((P + KOL, y + 17), tekst, font=font(18, "Bold"), fill=kolor_progu(temp, 45, 50) if aktywny else KOLORY["szary"], anchor="rm")
        if aktywny:
            d.text((P + KOL - 66, y + 17), "SMART", font=font(10, "SemiBold"),
                   fill=KOLORY[smart] if smart != "ok" else KOLORY["szary"], anchor="rm")
        d.line((P, y + 36, P + KOL, y + 36), fill=KOLORY["linia"])
    return obramowanie(img, dane)


def ekran_docker(t, dane):
    img, d = _nowy(t, t["docker"], 2, dane)
    dz, wsz = dane["kontenery_dzialaja"], dane["kontenery_wszystkie"]
    karta(d, L, G, KOL, 96)
    d.text((L + 14, G + 10), t["kontenery"], font=font(13), fill=KOLORY["szary"])
    d.text((L + 14, G + 28), str(dz), font=font(40, "Bold"), fill=KOLORY["ok"])
    d.text((L + 82, G + 46), f"/ {wsz} {t['dzialaja']}", font=font(15, "SemiBold"), fill=KOLORY["szary"])
    d.text((L + 14, G + 76), f"{wsz - dz} {t['zatrzymane']}", font=font(13, "SemiBold"), fill=KOLORY["uwaga"])
    y = G + 112
    d.text((L, y), t["maszyny"], font=font(13), fill=KOLORY["szary"])
    for i, (nazwa, stan) in enumerate(problemy_na_gorze(dane["vm"], 1, dane)[:3]):
        yy = y + 22 + i * 28
        d.ellipse((L + 2, yy + 5, L + 12, yy + 15), fill=KOLORY[stan])
        d.text((L + 22, yy + 10), nazwa, font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    for i, (nazwa, stan, cpu, ram) in enumerate(problemy_na_gorze(dane["kontenery"], 1, dane)[:6]):
        y = G + i * 42
        d.ellipse((P + 2, y + 11, P + 14, y + 23), fill=KOLORY[stan])
        d.text((P + 24, y + 17), nazwa, font=font(14, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
        d.text((P + KOL, y + 17), ram, font=font(12), fill=KOLORY["szary"], anchor="rm")
        d.text((P + KOL - 56, y + 17), f"{liczba(cpu, t['_j'])}%", font=font(13, "SemiBold"), fill=KOLORY["tekst"], anchor="rm")
        d.line((P, y + 36, P + KOL, y + 36), fill=KOLORY["linia"])
    return obramowanie(img, dane)


def ekran_parity(t, dane):
    img, d = _nowy(t, "PARITY", 3, dane)
    p = dane["parity_postep"]
    cx, cy = L + KOL // 2, 178
    luk(d, cx, cy, 96, p, KOLORY["akcent2"], grubosc=18)
    tekst_w_kole(d, cx, cy - 8, f"{liczba(p, t['_j'])}%", 130, 40, KOLORY["tekst"])
    d.text((cx, cy + 30), t["postep"], font=font(14, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    for i, (etyk, wart, kol) in enumerate([(t["predkosc"], dane["parity_predkosc"], KOLORY["tekst"]),
                                            (t["koniec"], dane["parity_eta"], KOLORY["tekst"]),
                                            (t["bledy"], str(dane["parity_bledy"]), KOLORY["ok"])]):
        y = G + 12 + i * 80
        karta(d, P, y, KOL, 70)
        d.text((P + 14, y + 12), etyk, font=font(13), fill=KOLORY["szary"])
        d.text((P + KOL - 14, y + 34), wart, font=font(24, "Bold"), fill=kol, anchor="ra")
    return obramowanie(img, dane)


def ekran_alerty(t, dane, puste=False):
    img, d = _nowy(t, t["alerty"], 4, dane if not puste else dict(dane, alerty=[]))
    if puste:
        cx = PW // 2
        d.ellipse((cx - 46, 100, cx + 46, 192), outline=KOLORY["ok"], width=8)
        d.line([(cx - 22, 148), (cx - 5, 165), (cx + 24, 132)], fill=KOLORY["ok"], width=9)
        d.text((cx, 228), t["brak_alertow"], font=font(20, "SemiBold"), fill=KOLORY["tekst"], anchor="mm")
        return img
    # Siatka 2×2: krytyczne zawsze pierwsze.
    alerty = sorted(dane["alerty"], key=lambda a: 0 if a[0] == "alarm" else 1)[:4]
    krytyczne = any(a[0] == "alarm" for a in alerty)
    wys = 106 if krytyczne else 116
    for i, (poziom, tytul, opis) in enumerate(alerty):
        x, y = (L, P)[i % 2], G + (i // 2) * (wys + 10)
        if poziom == "alarm":
            d.rounded_rectangle((x, y, x + KOL, y + wys), radius=10, fill=(64, 18, 22), outline=KOLORY["alarm"], width=2)
            d.text((x + 14, y + 12), t["krytyczne"], font=font(11, "Bold"), fill=KOLORY["alarm"])
            d.text((x + 14, y + 30), tytul, font=font(18, "Bold"), fill=KOLORY["tekst"])
            d.text((x + 14, y + 62), opis, font=font(12), fill=(230, 180, 180))
        else:
            karta(d, x, y, KOL, wys)
            d.rounded_rectangle((x, y, x + 8, y + wys), radius=4, fill=KOLORY[poziom])
            d.text((x + 20, y + 16), tytul, font=font(17, "Bold"), fill=KOLORY[poziom])
            d.text((x + 20, y + 48), opis, font=font(12), fill=KOLORY["szary"])
    if krytyczne:
        d.text((PW // 2, D - 4), t["przypiety"], font=font(12, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    return obramowanie(img, dane)


# --- ekrany dodatkowe ---
def ekran_ruch_dyskow(t, dane):
    img, d = _nowy(t, t["ruch_dyskow"], dod.INDEKS["ruch"], dane)
    io = dane["dyski_io"]
    suma_r = sum(x[2] for x in io if x[1]); suma_z = sum(x[3] for x in io if x[1])
    karta(d, L, G, PW - 2 * M, 40)
    d.text((L + 12, G + 20), t["razem"], font=font(13), fill=KOLORY["szary"], anchor="lm")
    d.text((PW // 2, G + 20), f"↓ {liczba(suma_r, t['_j'])} MB/s", font=font(17, "Bold"), fill=KOLORY["ok"], anchor="mm")
    d.text((PW - M - 12, G + 20), f"↑ {liczba(suma_z, t['_j'])} MB/s", font=font(17, "Bold"), fill=KOLORY["akcent"], anchor="rm")
    maks = max([x[2] for x in io] + [x[3] for x in io] + [1])
    for i, (nazwa, aktywny, r, z, stan) in enumerate(problemy_na_gorze(io, 4, dane)[:6]):
        x, y = (L, P)[i // 3], G + 52 + (i % 3) * 66
        d.ellipse((x + 2, y + 6, x + 14, y + 18), fill=KOLORY[stan] if aktywny else KOLORY["linia"])
        d.text((x + 24, y + 12), nazwa, font=font(15, "SemiBold"), fill=KOLORY["tekst"] if aktywny else KOLORY["szary"], anchor="lm")
        if not aktywny:
            d.text((x + KOL, y + 12), t["uspiony"], font=font(12), fill=KOLORY["szary"], anchor="rm")
        else:
            d.text((x + KOL, y + 12), f"↓ {liczba(r, t['_j'])}  ↑ {liczba(z, t['_j'])}", font=font(12, "SemiBold"),
                   fill=KOLORY["tekst"], anchor="rm")
            for j, (v, kolor) in enumerate(((r, KOLORY["ok"]), (z, KOLORY["akcent"]))):
                yy = y + 30 + j * 8
                d.rounded_rectangle((x + 24, yy, x + KOL, yy + 4), radius=2, fill=KOLORY["linia"])
                if v > 0:
                    d.rounded_rectangle((x + 24, yy, x + 24 + max(4, int((KOL - 24) * v / maks)), yy + 4), radius=2, fill=kolor)
        d.line((x, y + 52, x + KOL, y + 52), fill=KOLORY["linia"])
    return obramowanie(img, dane)


def ekran_historia(t, dane):
    img, d = _nowy(t, t["historia"], dod.INDEKS["historia"], dane)
    serie = [("CPU", dane["hist_cpu"], "%", KOLORY["akcent"]), ("RAM", dane["hist_ram"], "%", KOLORY["ok"]),
             (t["temp_cpu"], dane["hist_temp"], "°C", KOLORY["uwaga"])]
    sz = (PW - 2 * M - 2 * 10) // 3
    for i, (nazwa, wart, jedn, kolor) in enumerate(serie):
        x = M + i * (sz + 10)
        karta(d, x, G, sz, D - G)
        d.text((x + 10, G + 10), nazwa, font=font(13, "SemiBold"), fill=KOLORY["tekst"])
        d.text((x + 10, G + 30), f"{wart[-1]:.0f}{jedn}", font=font(26, "Bold"), fill=kolor)
        dod._wykres(d, x + 10, G + 80, sz - 20, 100, wart, kolor, 100)
        sr = sum(wart) / len(wart)
        for j, (etyk, v) in enumerate(((t["min"], min(wart)), (t["sr"], sr), (t["maks"], max(wart)))):
            yy = G + 196 + j * 17
            d.text((x + 10, yy), etyk, font=font(12), fill=KOLORY["szary"], anchor="lm")
            d.text((x + sz - 10, yy), f"{v:.0f}{jedn}", font=font(12, "SemiBold"), fill=KOLORY["tekst"], anchor="rm")
    return obramowanie(img, dane)


def ekran_siec(t, dane):
    img, d = _nowy(t, t["siec_t"], dod.INDEKS["siec"], dane)
    s = dane["siec"]
    stan = "ok" if s["internet"] else "alarm"
    karta(d, L, G, KOL, 64)
    d.ellipse((L + 12, G + 12, L + 26, G + 26), fill=KOLORY[stan])
    d.text((L + 34, G + 19), t["internet"], font=font(15, "SemiBold"), fill=KOLORY["tekst"], anchor="lm")
    d.text((L + KOL - 12, G + 19), t["dziala"] if s["internet"] else t["brak"], font=font(15, "Bold"), fill=KOLORY[stan], anchor="rm")
    d.text((L + 12, G + 46), f"{t['bramka']} {liczba(s['ping_bramka'], t['_j'])} ms", font=font(12), fill=KOLORY["szary"], anchor="lm")
    d.text((L + KOL - 12, G + 46), f"{t['internet']} {s['ping_internet']} ms", font=font(12), fill=KOLORY["szary"], anchor="rm")
    y = G + 74
    karta(d, L, y, KOL, D - y)
    d.text((L + 12, y + 10), t["pobieranie"], font=font(12), fill=KOLORY["szary"])
    d.text((L + 12, y + 26), s["rx"], font=font(17, "Bold"), fill=KOLORY["ok"])
    d.text((L + KOL - 12, y + 10), t["wysylanie"], font=font(12), fill=KOLORY["szary"], anchor="ra")
    d.text((L + KOL - 12, y + 26), s["tx"], font=font(17, "Bold"), fill=KOLORY["akcent"], anchor="ra")
    maks = max(s["hist_rx"] + s["hist_tx"])
    dod._wykres(d, L + 12, y + 58, KOL - 24, D - y - 72, s["hist_rx"], KOLORY["ok"], maks)
    dod._wykres(d, L + 12, y + 58, KOL - 24, D - y - 72, s["hist_tx"], KOLORY["akcent"], maks, wypelnienie=False)
    wiersze = [(t["tunel"], t["dziala"] if s["tunel"] else t["brak"], "ok" if s["tunel"] else "alarm"),
               (t["tailscale"], t["z_pulpitu"], "szary"), (t["ip"], t["ukryte"], "szary")]
    if dane.get("speedtest"):
        st = dane["speedtest"]
        wiersze.append(("Speedtest", f"↓ {st['pobieranie'][-1]:.0f}  ↑ {st['wysylanie'][-1]:.0f}", "ok"))
    for i, (e, w, st) in enumerate(wiersze):
        _wiersz(d, P, KOL, G + 4 + i * 44, e, w, st)
    return obramowanie(img, dane)


def ekran_speedtest(t, dane):
    img, d = _nowy(t, t["speedtest"], dod.INDEKS["speedtest"], dane)
    s = dane["speedtest"]
    sz = 150
    for i, (etyk, wart, jedn, kolor) in enumerate(((t["pobieranie"], f"↓ {s['pobieranie'][-1]:.0f}", "Mb/s", KOLORY["ok"]),
                                                   (t["wysylanie"], f"↑ {s['wysylanie'][-1]:.0f}", "Mb/s", KOLORY["akcent"]),
                                                   (t["ping"], f"{s['ping'][-1]:.0f}", "ms", KOLORY["tekst"]))):
        y = G + i * 70
        karta(d, L, y, sz, 62)
        d.text((L + 12, y + 9), etyk, font=font(12), fill=KOLORY["szary"])
        d.text((L + 12, y + 26), wart, font=font(24, "Bold"), fill=kolor)
        d.text((L + sz - 12, y + 9), jedn, font=font(12), fill=KOLORY["szary"], anchor="ra")
    d.text((L, D - 26), f"{t['ostatni']} {s['ostatni']}", font=font(12), fill=KOLORY["szary"], anchor="ls")
    d.text((L, D - 6), f"{t['nastepny']} {s['nastepny']}", font=font(12), fill=KOLORY["szary"], anchor="ls")
    x0 = L + sz + 12; szer = PW - M - x0
    karta(d, x0, G, szer, D - G)
    d.text((x0 + 12, G + 10), t["h72"], font=font(13, "SemiBold"), fill=KOLORY["tekst"])
    d.text((x0 + szer - 12, G + 10), f"{t['co']} {s['co_h']} h", font=font(12), fill=KOLORY["szary"], anchor="ra")
    xw, ww, yw, hw = x0 + 12, szer - 24, G + 40, 150
    for i in range(1, 3):
        x = xw + ww * i / 3
        for yy in range(yw, yw + hw, 6):
            d.line((x, yy, x, yy + 2), fill=KOLORY["linia"])
    maks = max(s["pobieranie"]) * 1.1
    dod._wykres(d, xw, yw, ww, hw, s["pobieranie"], KOLORY["ok"], maks)
    dod._wykres(d, xw, yw, ww, hw, s["wysylanie"], KOLORY["akcent"], maks, wypelnienie=False)
    for i, etykieta in enumerate(("-72 h", "-48 h", "-24 h", t["teraz"])):
        d.text((xw + ww * i / 3, yw + hw + 8), etykieta, font=font(11), fill=KOLORY["szary"],
               anchor="la" if i == 0 else "ra" if i == 3 else "ma")
    p = s["pobieranie"]
    d.text((xw, D - 10), f"↓ {t['min']} {min(p):.0f} · {t['sr']} {sum(p) / len(p):.0f} · {t['maks']} {max(p):.0f}",
           font=font(12), fill=KOLORY["szary"], anchor="ls")
    return obramowanie(img, dane)


def ekran_aktualizacje(t, dane):
    img, d = _nowy(t, t["aktualizacje"], dod.INDEKS["aktualizacje"], dane)
    a = dane["aktualizacje"]
    wiersze = [
        (t["system_unraid"], f"{a['wersja']} · {t['aktualny']}" if not a["unraid_nowa"] else a["unraid_nowa"], "ok" if not a["unraid_nowa"] else "uwaga"),
        (t["wtyczki"], f"{a['wtyczki']} {t['do_aktualizacji']}", "uwaga" if a["wtyczki"] else "ok"),
        (t["kontenery"], f"{a['kontenery']} {t['do_aktualizacji']}", "uwaga" if a["kontenery"] else "ok"),
        (t["kopia"], a["kopia"], a["kopia_stan"]),
        (t["parity"], f"{a['parity']} · {a['parity_bledy']} {t['bledow']}", "ok" if not a["parity_bledy"] else "alarm"),
        (t["restart"], f"{a['restart']} {t['temu']}", "ok"),
    ]
    for i, (etykieta, wartosc, stan) in enumerate(problemy_na_gorze(wiersze, 2, dane)):
        x, y = (L, P)[i % 2], G + (i // 2) * 84
        karta(d, x, y, KOL, 76)
        d.rounded_rectangle((x, y, x + 6, y + 76), radius=3, fill=KOLORY[stan])
        d.text((x + 18, y + 14), etykieta, font=font(13), fill=KOLORY["szary"])
        d.text((x + 18, y + 36), wartosc, font=font(16, "Bold"), fill=KOLORY["tekst"] if stan == "ok" else KOLORY[stan])
    return obramowanie(img, dane)


def ekran_zegar(t, dane):
    img, d = _nowy(t, None, 0, dane)
    z = dane["zegar"]
    d.text((PW // 2, 92), z["godzina"], font=font(100, "Bold"), fill=KOLORY["tekst"], anchor="mm")
    data = f"{dod.DNI[t['_j']][z['dzien_tyg']]}, {z['dzien']} {dod.MIESIACE[t['_j']][z['miesiac'] - 1]}"
    d.text((PW // 2, 168), data, font=font(20, "SemiBold"), fill=KOLORY["szary"], anchor="mm")
    if z.get("pogoda") is not None:
        p = z["pogoda"]
        rodzaj = rodzaj_pogody(p["kod"])
        temp, opis = f"{liczba(p['temp'], t['_j'], 0)}°C", OPISY[t["_j"]][rodzaj]
        ft, fo = font(30, "Bold"), font(15)
        szer = 56 + 12 + max(d.textlength(temp, font=ft), d.textlength(opis, font=fo))
        x = round(PW / 2 - szer / 2)
        img.paste(ikona(rodzaj, p.get("dzien", True), 56, KOLORY["tlo"]), (x, 206))
        d.text((x + 68, 234), temp, font=ft, fill=KOLORY["tekst"], anchor="ls")
        d.text((x + 68, 256), opis, font=fo, fill=KOLORY["szary"], anchor="ls")
    krytyczne, ostrzezenia = (sum(1 for a in dane.get("alerty", []) if a[0] == p) for p in ("alarm", "uwaga"))
    if krytyczne:
        stan, tekst = "alarm", f"{krytyczne} {t['krytyczne'].lower()}"
    elif ostrzezenia:
        stan, tekst = "uwaga", f"! {ostrzezenia}"
    else:
        stan, tekst = "ok", t["wszystko_ok"]
    szer = d.textlength(tekst, font=font(14, "SemiBold"))
    x = PW // 2 - (szer + 20) / 2
    d.ellipse((x, D - 12, x + 12, D), fill=KOLORY[stan])
    d.text((x + 20, D - 6), tekst, font=font(14, "SemiBold"), fill=KOLORY["szary"], anchor="lm")
    return obramowanie(img, dane)


def ekran_qr(t, dane):
    import segno

    img, d = _nowy(t, t["qr"], dod.INDEKS["qr"], dane)
    macierz = list(segno.make(dane["adres_panelu"], error="m").matrix)
    n = len(macierz)
    modul = (D - G) // (n + 8)
    bok = modul * (n + 8)
    x0, y0 = L, G + (D - G - bok) // 2
    d.rounded_rectangle((x0, y0, x0 + bok, y0 + bok), radius=10, fill=(255, 255, 255))
    for r, wiersz in enumerate(macierz):
        for c, bit in enumerate(wiersz):
            if bit:
                x, y = x0 + (c + 4) * modul, y0 + (r + 4) * modul
                d.rectangle((x, y, x + modul - 1, y + modul - 1), fill=(0, 0, 0))
    xt = x0 + bok + 20
    d.text((xt, 120), dane["adres_panelu"], font=font(15, "SemiBold"), fill=KOLORY["tekst"])
    # zawijanie tekstu do szerokości kolumny
    y = 156
    for zdanie in (t["zeskanuj"], t["tylko_lan"]):
        linia = ""
        for slowo in zdanie.split():
            proba = f"{linia} {slowo}".strip()
            if d.textlength(proba, font=font(13)) > PW - M - xt:
                d.text((xt, y), linia, font=font(13), fill=KOLORY["szary"]); y += 20; linia = slowo
            else:
                linia = proba
        d.text((xt, y), linia, font=font(13), fill=KOLORY["szary"]); y += 30
    return obramowanie(img, dane)


def wszystkie(jezyk="pl", dane=None):
    """Wszystkie ekrany poziome z danymi przykładowymi (makiety i testy)."""
    from .rysuj import PRZYKLADOWE_DANE, PRZYKLADOWE_DANE_KRYTYCZNE, TEKSTY as TEKSTY_PODST

    dane = dict(PRZYKLADOWE_DANE, **dod.PRZYKLADOWE, **(dane or {}))
    if jezyk == "en":
        dane["aktualizacje"] = dict(dane["aktualizacje"], kopia="yesterday 03:00", parity="Nov 1", restart="12 days")
    t = dict(TEKSTY_PODST[jezyk], **dod.TEKSTY[jezyk], _j=jezyk)
    kryt = dict(dane, alerty=PRZYKLADOWE_DANE_KRYTYCZNE["alerty"])
    return {"1-system": ekran_system(t, dane), "2-dyski": ekran_dyski(t, dane), "3-docker": ekran_docker(t, dane),
            "4-parity": ekran_parity(t, dane), "5-alerty": ekran_alerty(t, dane),
            "5c-alerty-krytyczne": ekran_alerty(t, kryt), "1c-system-krytyczny": ekran_system(t, kryt),
            "6-ruch-dyskow": ekran_ruch_dyskow(t, dane), "7-historia": ekran_historia(t, dane),
            "8-siec": ekran_siec(t, dane), "8b-speedtest": ekran_speedtest(t, dane),
            "9-aktualizacje": ekran_aktualizacje(t, dane), "10-zegar": ekran_zegar(t, dane), "11-qr": ekran_qr(t, dane)}
