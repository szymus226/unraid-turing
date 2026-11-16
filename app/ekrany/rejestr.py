"""Rejestr ekranów: funkcje rysujące (pion i poziom), nazwy i elementy do edytora w panelu.

Kolejność elementów odpowiada numerom w pokaz(dane, n) w funkcjach rysujących.
Teksty w formacie "polski|English".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import dodatkowe, poziome, rysuj


@dataclass
class OpisEkranu:
    klucz: str
    nazwa: str
    pion: object
    poziom: object
    elementy: list = field(default_factory=list)      # (element, parametr, wygląd)
    warunek: str | None = None                         # np. "parity": tylko gdy trwa kontrola


EKRANY: dict[str, OpisEkranu] = {e.klucz: e for e in [
    OpisEkranu("system", "System|System", rysuj.ekran_system, poziome.ekran_system, [
        ("Wskaźnik duży|Large gauge", "Obciążenie CPU|CPU load", "łuk|arc"),
        ("Kafelek 1|Tile 1", "Temperatura CPU|CPU temperature", "liczba|number"),
        ("Kafelek 2|Tile 2", "Czas pracy|Uptime", "liczba|number"),
        ("Słupki|Bars", "Rdzenie CPU|CPU cores", "słupki|bars"),
        ("Wykres|Chart", "CPU, ostatnie 60 s|CPU, last 60 s", "linia|line"),
        ("Paski|Bars", "RAM, SWAP|RAM, swap", "pasek|bar"),
        ("Kafelki dolne|Bottom tiles", "Load, sieć LAN|Load, LAN", "liczba|number")]),
    OpisEkranu("dyski", "Dyski|Disks", rysuj.ekran_dyski, poziome.ekran_dyski, [
        ("Nagłówek|Header", "Stan array|Array state", "kropka i tekst|dot and text"),
        ("Paski|Bars", "Zajętość array i cache|Array and cache usage", "pasek|bar"),
        ("Lista|List", "Wybrane dyski: temp. i SMART|Selected disks: temp. and SMART", "wiersze|rows")]),
    OpisEkranu("docker", "Docker|Docker", rysuj.ekran_docker, poziome.ekran_docker, [
        ("Kafelek|Tile", "Liczba działających kontenerów|Running containers", "liczba|number"),
        ("Lista|List", "Wybrane kontenery: CPU i RAM|Selected containers: CPU and RAM", "wiersze|rows"),
        ("Lista|List", "Maszyny VM|VMs", "wiersze|rows")]),
    OpisEkranu("parity", "Parity|Parity", rysuj.ekran_parity, poziome.ekran_parity, [
        ("Wskaźnik duży|Large gauge", "Postęp kontroli parity|Parity check progress", "łuk|arc"),
        ("Kafelki|Tiles", "Prędkość, koniec za, błędy|Speed, finishes in, errors", "liczba|number")], warunek="parity"),
    OpisEkranu("alerty", "Alerty|Alerts", rysuj.ekran_alerty, poziome.ekran_alerty, [
        ("Lista|List", "Aktywne alerty|Active alerts", "karty|cards"),
        ("Pusty stan|Empty state", "Wszystko w porządku|All good", "ikona|icon")]),
    OpisEkranu("ruch", "Ruch dysków|Disk activity", dodatkowe.ekran_ruch_dyskow, poziome.ekran_ruch_dyskow, [
        ("Kafelek|Tile", "Odczyt i zapis razem|Total read and write", "liczba|number"),
        ("Lista|List", "Wybrane dyski: odczyt, zapis, uśpienie|Selected disks: read, write, spun down", "paski|bars")]),
    OpisEkranu("historia", "Ostatnie 24 h|Last 24 h", dodatkowe.ekran_historia, poziome.ekran_historia, [
        ("Wykres|Chart", "CPU|CPU", "linia z wypełnieniem|filled line"),
        ("Wykres|Chart", "RAM|RAM", "linia z wypełnieniem|filled line"),
        ("Wykres|Chart", "Temperatura CPU|CPU temperature", "linia z wypełnieniem|filled line")]),
    OpisEkranu("siec", "Sieć|Network", dodatkowe.ekran_siec, poziome.ekran_siec, [
        ("Kafelek|Tile", "Internet i opóźnienie do routera i internetu|Internet and latency to router and internet", "stan|state"),
        ("Wykres|Chart", "Pobieranie i wysyłanie, ostatnia godzina|Download and upload, last hour", "linia|line"),
        ("Lista|List", "Tunel Cloudflare (kontener)|Cloudflare tunnel (container)", "stan|state"),
        ("Lista|List", "Tailscale (z pulpitu, później)|Tailscale (from desktop, later)", "stan|state"),
        ("Lista|List", "Publiczne IP: domyślnie ukryte|Public IP: hidden by default", "tekst|text")]),
    OpisEkranu("speedtest", "Speedtest|Speed test", dodatkowe.ekran_speedtest, poziome.ekran_speedtest, [
        ("Kafelek|Tile", "Ostatni wynik: pobieranie, wysyłanie, ping|Last result: download, upload, ping", "liczba|number"),
        ("Wykres|Chart", "Ostatnie 72 h z min, średnią i maks|Last 72 h with min, avg and max", "linia z wypełnieniem|filled line"),
        ("Stan|Status", "Następny test (co ile, ustawiasz w „Dyski i kontenery”)|Next test (interval set in “Disks & containers”)", "tekst|text")],
        warunek="speedtest"),
    OpisEkranu("aktualizacje", "Aktualizacje|Updates", dodatkowe.ekran_aktualizacje, poziome.ekran_aktualizacje, [
        ("Karty|Cards", "Unraid, wtyczki, kontenery do aktualizacji|Unraid, plugins, containers to update", "stan|state"),
        ("Karty|Cards", "Kopia appdata, kontrola parity, ostatni restart|Appdata backup, parity check, last restart", "stan|state")]),
    OpisEkranu("zegar", "Zegar|Clock", dodatkowe.ekran_zegar, poziome.ekran_zegar, [
        ("Zegar|Clock", "Godzina i data|Time and date", "duże cyfry|large digits"),
        ("Pogoda|Weather", "Ikona, temperatura i opis (Open-Meteo, łączy się z internetem, domyślnie wyłączona)|Icon, temperature and description (Open-Meteo, connects to the internet, off by default)", "ikona i tekst|icon and text"),
        ("Stan|Status", "Jedna linia stanu serwera|One-line server status", "kropka|dot")]),
    OpisEkranu("qr", "Kod QR panelu|Panel QR code", dodatkowe.ekran_qr, poziome.ekran_qr, [
        ("Kod QR|QR code", "Adres panelu w sieci domowej|Panel address on the home network", "kod|code")]),
]}


def teksty(jezyk: str) -> dict:
    return dict(rysuj.TEKSTY[jezyk], **dodatkowe.TEKSTY[jezyk], _j=jezyk)


def spelnia_warunek(opis: OpisEkranu, dane: dict) -> bool:
    if opis.warunek == "parity":
        return bool(dane.get("parity_trwa"))
    if opis.warunek == "speedtest":
        return bool(dane.get("speedtest_wl"))
    return True


def narysuj(klucz: str, dane: dict, jezyk: str, poziomo: bool, ukryte=(), indeks: int = 0, razem: int = 1):
    """Rysuje jeden ekran z podanymi danymi; indeks i razem trafiają do wskaźnika w nagłówku."""
    opis = EKRANY[klucz]
    dane = dict(dane, _ukryte=set(ukryte), _indeks=indeks, ekrany_razem=razem)
    funkcja = opis.poziom if poziomo else opis.pion
    return funkcja(teksty(jezyk), dane)


def przykladowe_dane(jezyk: str = "pl") -> dict:
    """Dane z makiet (tryb pokazowy i testy)."""
    dane = dict(rysuj.PRZYKLADOWE_DANE, **dodatkowe.PRZYKLADOWE, parity_trwa=True, speedtest_wl=True)
    if jezyk == "en":
        dane["aktualizacje"] = dict(dane["aktualizacje"], kopia="yesterday 03:00", parity="Nov 1", restart="12 days")
    return dane
