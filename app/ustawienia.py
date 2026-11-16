"""Ustawienia w pliku JSON w katalogu konfiguracji (na Unraid: /mnt/user/appdata/unraid-lcd/)."""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .sterownik.baza import Orientacja

# Kolejność i domyślne ustawienia ekranów (klucz, włączony, czas w sekundach).
DOMYSLNE_EKRANY = [
    ("system", True, 10), ("dyski", True, 10), ("docker", True, 10), ("parity", True, 15),
    ("alerty", True, 10), ("ruch", True, 10), ("historia", True, 15), ("siec", True, 10),
    ("speedtest", False, 10), ("aktualizacje", True, 10), ("zegar", True, 10), ("qr", False, 10),
]
KLUCZE_EKRANOW = [k for k, _, _ in DOMYSLNE_EKRANY]

# Progi: (ostrzeżenie, alarm, przełącz na Alerty). None = nie dotyczy.
DOMYSLNE_PROGI = {
    "cpu_temp": [70, 85, True], "hdd_temp": [45, 50, True], "ssd_temp": [60, 70, True],
    "cpu": [70, 90, False], "ram": [80, 92, True], "swap": [50, 80, False], "array": [85, 95, False],
    "kontener_stop": [None, None, True], "dysk_awaria": [None, None, True],
}

# Rodzaje alertów krytycznych (te same nazwy w panelu): [na ekranie, krytyczny].
RODZAJE_ALERTOW = ("dysk", "smart", "array", "parity", "prog", "unraid", "pulpit")

MOTYWY = ("granatowy", "czarny", "jasny")
MAKS_KONTENEROW = 6
GODZINA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
CZESTOTLIWOSCI_SPEEDTESTU = (0, 0.5, 1, 2, 3, 6, 12, 24)


def _domyslne_ekrany() -> list[dict]:
    return [{"klucz": k, "wl": wl, "czas_s": c, "ukryte": []} for k, wl, c in DOMYSLNE_EKRANY]


@dataclass
class Ustawienia:
    tryb: str = "usb"                # "usb" albo "symulacja"
    port: str = "auto"               # "auto" albo ścieżka do portu
    jasnosc: int = 60                # 0–100
    orientacja: str = Orientacja.PIONOWO.value
    odswiezanie_s: float = 2.0       # co ile sekund nowe dane
    przelaczanie_s: int = 10         # 0 = bez przełączania; inaczej czas z ustawień ekranu
    jezyk: str = "pl"                # język tekstów na ekranie: "pl" albo "en"
    motyw: str = "granatowy"
    noc_wl: bool = False             # wyłącz ekran nocą
    noc_od: str = "23:00"
    noc_do: str = "07:00"
    sortuj_awarie: bool = True       # dyski, kontenery i VM z awarią na górze
    ekrany: list = field(default_factory=_domyslne_ekrany)
    dyski: list | None = None        # nazwy dysków na ekranie; None = wszystkie
    kontenery: list | None = None    # nazwy kontenerów (maks. 6); None = pierwsze działające
    progi: dict = field(default_factory=lambda: json.loads(json.dumps(DOMYSLNE_PROGI)))
    krytyczne_przypnij: bool = True
    krytyczne_jasnosc: bool = True   # 100% i wybudzenie z trybu nocnego
    krytyczne_ramka: bool = True
    speedtest_co_h: float = 0        # 0 = wyłączony
    pogoda_wl: bool = False
    pogoda_miejsce: str = ""
    pogoda_lat: float | None = None
    pogoda_lon: float | None = None
    rodzaje_alertow: dict = field(default_factory=lambda: {k: [True, True] for k in RODZAJE_ALERTOW})

    def popraw(self) -> "Ustawienia":
        """Przycina wartości do bezpiecznych zakresów i uzupełnia brakujące elementy."""
        self.tryb = self.tryb if self.tryb in ("usb", "symulacja") else "usb"
        self.port = str(self.port or "auto")
        self.jasnosc = max(0, min(100, int(self.jasnosc)))
        self.odswiezanie_s = max(1.0, min(60.0, float(self.odswiezanie_s)))
        self.przelaczanie_s = max(0, min(600, int(self.przelaczanie_s)))
        self.jezyk = self.jezyk if self.jezyk in ("pl", "en") else "pl"
        self.motyw = self.motyw if self.motyw in MOTYWY else "granatowy"
        if self.orientacja not in {o.value for o in Orientacja}:
            self.orientacja = Orientacja.PIONOWO.value
        self.noc_wl = bool(self.noc_wl)
        self.noc_od = self.noc_od if GODZINA.match(str(self.noc_od)) else "23:00"
        self.noc_do = self.noc_do if GODZINA.match(str(self.noc_do)) else "07:00"
        self.sortuj_awarie = bool(self.sortuj_awarie)
        self.ekrany = _popraw_ekrany(self.ekrany)
        self.dyski = _lista_nazw(self.dyski)
        self.kontenery = _lista_nazw(self.kontenery)
        if self.kontenery is not None:
            self.kontenery = self.kontenery[:MAKS_KONTENEROW]
        self.progi = _popraw_progi(self.progi)
        for nazwa in ("krytyczne_przypnij", "krytyczne_jasnosc", "krytyczne_ramka", "pogoda_wl"):
            setattr(self, nazwa, bool(getattr(self, nazwa)))
        try:
            co = float(self.speedtest_co_h)
        except (TypeError, ValueError):
            co = 0
        self.speedtest_co_h = co if co in CZESTOTLIWOSCI_SPEEDTESTU else 0
        self.pogoda_miejsce = str(self.pogoda_miejsce or "")[:80]
        for nazwa, granica in (("pogoda_lat", 90), ("pogoda_lon", 180)):
            v = getattr(self, nazwa)
            try:
                v = float(v) if v is not None else None
            except (TypeError, ValueError):
                v = None
            setattr(self, nazwa, v if v is not None and -granica <= v <= granica else None)
        self.rodzaje_alertow = _popraw_rodzaje(self.rodzaje_alertow)
        return self

    @property
    def poziomo(self) -> bool:
        return self.orientacja in (Orientacja.POZIOMO.value, Orientacja.POZIOMO_ODWROCONY.value)


def _popraw_ekrany(ekrany) -> list[dict]:
    """Zachowuje kolejność użytkownika, usuwa nieznane klucze i dopisuje brakujące ekrany na końcu."""
    domyslne = {e["klucz"]: e for e in _domyslne_ekrany()}
    wynik, widziane = [], set()
    for e in ekrany if isinstance(ekrany, list) else []:
        if not isinstance(e, dict) or e.get("klucz") not in domyslne or e["klucz"] in widziane:
            continue
        widziane.add(e["klucz"])
        try:
            czas = max(3, min(300, int(e.get("czas_s", 10))))
        except (TypeError, ValueError):
            czas = 10
        ukryte = sorted({int(i) for i in e.get("ukryte", []) if isinstance(i, int) and 0 <= i < 20})
        wynik.append({"klucz": e["klucz"], "wl": bool(e.get("wl", True)), "czas_s": czas, "ukryte": ukryte})
    wynik += [domyslne[k] for k in KLUCZE_EKRANOW if k not in widziane]
    return wynik


def _popraw_rodzaje(rodzaje) -> dict:
    wynik = {k: [True, True] for k in RODZAJE_ALERTOW}
    if isinstance(rodzaje, dict):
        for k in RODZAJE_ALERTOW:
            v = rodzaje.get(k)
            if isinstance(v, (list, tuple)) and len(v) == 2:
                pokaz = bool(v[0])
                wynik[k] = [pokaz, pokaz and bool(v[1])]
    return wynik


def _lista_nazw(lista) -> list[str] | None:
    if lista is None or not isinstance(lista, list):
        return None
    return [str(x)[:64] for x in lista if isinstance(x, (str, int))][:64]


def _popraw_progi(progi) -> dict:
    wynik = json.loads(json.dumps(DOMYSLNE_PROGI))
    if not isinstance(progi, dict):
        return wynik
    for klucz, (u_dom, a_dom, _) in DOMYSLNE_PROGI.items():
        p = progi.get(klucz)
        if not isinstance(p, (list, tuple)) or len(p) != 3:
            continue
        u, a, przelacz = p
        if u_dom is not None:
            try:
                u, a = max(0, min(150, float(u))), max(0, min(150, float(a)))
            except (TypeError, ValueError):
                u, a = u_dom, a_dom
            if a < u:
                u, a = a, u
            u, a = (int(u) if float(u).is_integer() else u), (int(a) if float(a).is_integer() else a)
        else:
            u, a = None, None
        wynik[klucz] = [u, a, bool(przelacz)]
    return wynik


def katalog_konfiguracji() -> Path:
    return Path(os.environ.get("LCD_KONFIGURACJA", "/config"))


def wczytaj(katalog: Path | None = None) -> Ustawienia:
    plik = (katalog or katalog_konfiguracji()) / "ustawienia.json"
    try:
        surowe = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Ustawienia().popraw()
    return z_slownika(surowe if isinstance(surowe, dict) else {})


def z_slownika(surowe: dict) -> Ustawienia:
    znane = {f.name for f in fields(Ustawienia)}
    return Ustawienia(**{k: v for k, v in surowe.items() if k in znane}).popraw()


def zapisz(ustawienia: Ustawienia, katalog: Path | None = None) -> None:
    """Zapis atomowy: najpierw plik tymczasowy, potem zamiana nazwy."""
    zapisz_json(asdict(ustawienia.popraw()), "ustawienia.json", katalog)


def zapisz_json(dane, nazwa: str, katalog: Path | None = None) -> None:
    katalog = katalog or katalog_konfiguracji()
    katalog.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=katalog, delete=False, encoding="utf-8", suffix=".tmp") as tmp:
        json.dump(dane, tmp, ensure_ascii=False, indent=2)
    os.replace(tmp.name, katalog / nazwa)
