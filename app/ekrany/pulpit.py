"""Ekrany z pulpitu homelabbera (dodatek „Smart ekran”, etap E3): nagłówek i do sześciu kart.

Pulpit wysyła karty przez `POST /api/pulpit/ekrany` (etykieta, wartość, stan, opcjonalnie pasek, dopisek pod
wartością albo tekst po prawej). Aplikacja niczego tu nie odczytuje sama. Kolejność kart jest stała dla ekranu
(miejsce bez danych pulpit wysyła jako `null`), więc „Elementy na ekranie” ukrywają karty po numerze.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .rysuj import KOLORY, M, W, H, font, karta, naglowek, obramowanie, pasek, pokaz

PW, PH = 480, 320
KOL = 216
L, P = M, M + KOL + 12
STANY = ("ok", "uwaga", "alarm", "szary")

# klucz: (tytuł pl|en, nazwa pl|en, karty: (nazwa pl|en, opis pl|en)), przykładowe karty do podglądu
EKRANY_PULPITU: dict[str, tuple[str, str, list[tuple[str, str]], list[dict]]] = {
    "pulpit_zasilanie": ("ZASILANIE (UPS)|POWER (UPS)", "Zasilanie|Power", [
        ("Zasilanie|Mains", "Z sieci albo z baterii, napięcie|Mains or battery, voltage"),
        ("Bateria|Battery", "Procent i czas pracy|Charge and runtime"),
        ("Obciążenie|Load", "Procent i moc|Percent and power"),
        ("Plan przy zaniku|Outage plan", "Co i kiedy się wyłączy|What shuts down and when"),
        ("Ostatni zanik|Last outage", "Kiedy i jak długo|When and how long")],
     [{"etykieta": "Zasilanie", "wartosc": "z sieci · 231 V"}, {"etykieta": "Bateria", "wartosc": "100%", "pasek": 100, "prawa": "ok. 38 min"},
      {"etykieta": "Obciążenie", "wartosc": "31% · 186 W", "pasek": 31}, {"etykieta": "Plan przy zaniku", "wartosc": "wyłącz po 5 min", "pod": "serwer, potem komputery"},
      {"etykieta": "Ostatni zanik", "wartosc": "3 dni temu · 12 s"}]),
    "pulpit_pobieranie": ("POBIERANIE|DOWNLOADS", "Pobieranie|Downloads", [
        ("Torrenty|Torrents", "Prędkość i kolejka|Speed and queue"),
        ("Usenet|Usenet", "Prędkość i czas do końca|Speed and time left"),
        ("Wolne miejsce|Free space", "Na dysku pobierania|On the download disk"),
        ("Ostatnio dodane|Recently added", "Filmy i odcinki z dziś|Movies and episodes today")],
     [{"etykieta": "qBittorrent", "wartosc": "↓ 12,4 MB/s · ↑ 1,1 MB/s", "pod": "3 aktywne · 14 w kolejce"},
      {"etykieta": "SABnzbd", "wartosc": "↓ 38,0 MB/s", "pasek": 62, "prawa": "zostało 4 min"},
      {"etykieta": "Wolne miejsce", "wartosc": "1,2 TB", "pasek": 84, "stan": "uwaga"},
      {"etykieta": "Ostatnio dodane", "wartosc": "2 filmy · 5 odcinków", "pod": "dzisiaj"}]),
    "pulpit_odtwarzanie": ("ODTWARZANIE|PLAYBACK", "Odtwarzanie|Playback", [
        ("Odtwarzanie 1|Stream 1", "Gdzie, postęp, transkodowanie|Where, progress, transcoding"),
        ("Odtwarzanie 2|Stream 2", "Drugi strumień|Second stream"),
        ("Transkodowanie|Transcoding", "Liczba strumieni i GPU|Streams and GPU"),
        ("Łącze|Uplink", "Wysyłanie do internetu|Upload to the internet")],
     [{"etykieta": "Plex · Salon TV", "wartosc": "Film · 1:12 / 2:04", "pasek": 58, "prawa": "bez transkodowania"},
      {"etykieta": "Jellyfin · Telefon", "wartosc": "Serial", "pasek": 21, "prawa": "transkodowanie", "stan": "uwaga"},
      {"etykieta": "Transkodowanie", "wartosc": "1 strumień · GPU"}, {"etykieta": "Łącze do internetu", "wartosc": "↑ 6,2 Mb/s"}]),
    "pulpit_kopie": ("KOPIE ZAPASOWE|BACKUPS", "Kopie zapasowe|Backups", [
        ("Kopia pulpitu|Desktop backup", "Ostatnia i wynik|Last run and result"),
        ("Kopie online|Online backups", "Ostatnia i liczba celów|Last run and targets"),
        ("Najstarsza|Oldest", "Kopia, która dawno się nie udała|Backup that has not run for a while"),
        ("Następna|Next", "Najbliższa zaplanowana|Next scheduled")],
     [{"etykieta": "Kopia pulpitu", "wartosc": "dziś 03:00 · ok"}, {"etykieta": "Kopie online", "wartosc": "wczoraj 02:10 · ok", "pod": "2 cele"},
      {"etykieta": "Kopia appdata", "wartosc": "3 dni temu", "stan": "uwaga", "pod": "starsza niż 2 dni"}, {"etykieta": "Następna", "wartosc": "dziś 23:00"}]),
    "pulpit_kamery": ("KAMERY|CAMERAS", "Kamery|Cameras", [
        ("Zdarzenia|Events", "Dziś, według rodzaju|Today, by type"),
        ("Ostatnie|Latest", "Kamera i godzina|Camera and time"),
        ("Kamery|Cameras", "Działające i bez obrazu|Working and offline"),
        ("Nagrywanie|Recording", "Stan i miejsce|State and space")],
     [{"etykieta": "Zdarzenia dziś", "wartosc": "12 · 9 osób · 3 auta"}, {"etykieta": "Ostatnie", "wartosc": "Wejście · 19:42"},
      {"etykieta": "Kamery", "wartosc": "4 z 4 działają"}, {"etykieta": "Nagrywanie", "wartosc": "włączone · 41% dysku", "pasek": 41}]),
}
KLUCZE_PULPITU = list(EKRANY_PULPITU)


def _jezyk(tekst: str, j: str) -> str:
    pl, _, en = tekst.partition("|")
    return (en or pl) if j == "en" else pl


def _karty(klucz: str, dane: dict) -> list[tuple[int, dict]]:
    """Karty do narysowania z numerem miejsca: dane z pulpitu albo przykład (podgląd w aplikacji pulpitu)."""
    karty = (dane.get("pulpit") or {}).get(klucz)
    if karty is None:
        karty = EKRANY_PULPITU[klucz][3]
    return [(i, k) for i, k in enumerate(karty[:6]) if k and pokaz(dane, i)]


def _kolor(stan: str) -> tuple:
    return KOLORY[stan] if stan in STANY else KOLORY["ok"]


def _pionowy(klucz: str):
    def ekran(t, dane):
        img = Image.new("RGB", (W, H), KOLORY["tlo"]); d = ImageDraw.Draw(img)
        naglowek(d, _jezyk(EKRANY_PULPITU[klucz][0], t["_j"]), 0, dane)
        y = 54
        for _, k in _karty(klucz, dane):
            st = k.get("stan") or "ok"
            wys = 74 if k.get("pasek") is not None or k.get("pod") else 58
            if y + wys > H - 8:
                break
            karta(d, M, y, W - 2 * M, wys)
            d.rounded_rectangle((M, y, M + 6, y + wys), radius=3, fill=_kolor(st))
            d.text((M + 18, y + 10), k["etykieta"], font=font(13), fill=KOLORY["szary"])
            if k.get("prawa"):
                d.text((W - M - 12, y + 10), k["prawa"], font=font(12), fill=KOLORY["szary"], anchor="ra")
            d.text((M + 18, y + 28), k["wartosc"], font=font(17, "Bold"), fill=KOLORY["tekst"] if st == "ok" else _kolor(st))
            if k.get("pasek") is not None:
                pasek(d, M + 18, y + 56, W - 2 * M - 30, 8, k["pasek"], KOLORY["akcent"] if st == "ok" else _kolor(st))
            elif k.get("pod"):
                d.text((M + 18, y + 52), k["pod"], font=font(12), fill=KOLORY["szary"])
            y += wys + 8
        return obramowanie(img, dane)
    return ekran


def _poziomy(klucz: str):
    def ekran(t, dane):
        img = Image.new("RGB", (PW, PH), KOLORY["tlo"]); d = ImageDraw.Draw(img)
        naglowek(d, _jezyk(EKRANY_PULPITU[klucz][0], t["_j"]), 0, dane, w=PW)
        for n, (_, k) in enumerate(_karty(klucz, dane)):
            st = k.get("stan") or "ok"
            x, y = (L, P)[n % 2], 54 + (n // 2) * 86
            karta(d, x, y, KOL, 78)
            d.rounded_rectangle((x, y, x + 6, y + 78), radius=3, fill=_kolor(st))
            d.text((x + 18, y + 12), k["etykieta"], font=font(13), fill=KOLORY["szary"])
            d.text((x + 18, y + 32), k["wartosc"], font=font(16, "Bold"), fill=KOLORY["tekst"] if st == "ok" else _kolor(st))
            if k.get("pasek") is not None:
                pasek(d, x + 18, y + 60, KOL - 30, 7, k["pasek"], KOLORY["akcent"] if st == "ok" else _kolor(st))
            elif k.get("pod") or k.get("prawa"):
                d.text((x + 18, y + 56), k.get("pod") or k["prawa"], font=font(12), fill=KOLORY["szary"])
        return obramowanie(img, dane)
    return ekran
