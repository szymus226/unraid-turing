"""Główna pętla: odczyt danych, wybór ekranu, rysowanie i wysyłka zmienionych fragmentów.

Zasady wyboru ekranu:
- ekrany przełączają się po kolei, każdy przez swój czas (0 w „Przełączanie ekranów” wyłącza rotację),
- nowy alert z progu oznaczonego „Przełącz na Alerty” od razu pokazuje ekran Alerty,
- alert krytyczny przypina ekran Alerty (rotacja stoi), ustawia jasność 100%
  i włącza ekran także w godzinach nocnych (każde z tych zachowań można wyłączyć).
Po odłączeniu ekranu pętla co 5 s szuka go ponownie i po połączeniu wysyła pełną klatkę.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from PIL import Image

from .ekrany import rejestr, rysuj
from .odczyt.system import CzytnikSystemu
from .roznice import zmienione_obszary
from .sterownik.baza import BladEkranu, Ekran, Orientacja
from .sterownik.rev_a import EkranRevA
from .sterownik.symulator import EkranSymulowany
from .sterownik.wykrywanie import ZnalezionyEkran, wykryj
from .ustawienia import Ustawienia
from .zbieracz import Zbieracz, Zrodla

log = logging.getLogger(__name__)

PONOWNE_LACZENIE_S = 5.0


def w_oknie_nocnym(od: str, do: str, teraz: time.struct_time) -> bool:
    """Czy bieżąca minuta jest w przedziale [od, do); przedział może przechodzić przez północ."""
    minuta = teraz.tm_hour * 60 + teraz.tm_min
    a = int(od[:2]) * 60 + int(od[3:])
    b = int(do[:2]) * 60 + int(do[3:])
    if a == b:
        return False
    return a <= minuta < b if a < b else minuta >= a or minuta < b


@dataclass
class StanPetli:
    polaczony: bool = False
    tryb: str = "symulacja"
    port: str | None = None
    nazwa_urzadzenia: str | None = None
    ostatnia_klatka_s: float | None = None    # czas wysyłki pełnej klatki
    ostatnia_wysylka_s: float | None = None   # czas ostatniej wysyłki zmian
    blad: str | None = None
    ekran: str = "system"                     # klucz bieżącego ekranu
    indeks: int = 0
    kolejka: list = field(default_factory=list)
    pauza: bool = False
    przypiety: bool = False                   # ekran Alerty przypięty przez alert krytyczny
    noc: bool = False                         # ekran wyłączony na noc
    jasnosc: int = 0                          # jasność ustawiona na ekranie
    nastepny_za_s: float | None = None
    dziennik: deque = field(default_factory=lambda: deque(maxlen=300))


class Petla:
    def __init__(self, ustawienia: Ustawienia, czytnik: CzytnikSystemu | None = None,
                 katalog_dev: str = "/dev", katalog_sys: str = "/sys",
                 fabryka_ekranu=None, wykrywacz=None, zbieracz: Zbieracz | None = None):
        self.ustawienia = ustawienia
        self.zbieracz = zbieracz or Zbieracz(Zrodla(sys=katalog_sys), czytnik_systemu=czytnik, w_tle=False)
        self.katalog_dev = katalog_dev
        self.katalog_sys = katalog_sys
        self._fabryka_ekranu = fabryka_ekranu or (lambda port: EkranRevA(port))
        self._wykrywacz = wykrywacz or (lambda: wykryj(self.katalog_dev, self.katalog_sys))
        self.stan = StanPetli()
        self.ekran: Ekran | None = None
        self.klatka: Image.Image | None = None        # ostatnio narysowana klatka (podgląd w panelu)
        self.dane: dict = {}                          # ostatnie dane ekranów (miniatury w panelu)
        self._wyslana: Image.Image | None = None      # to, co jest teraz na fizycznym ekranie
        self._zatrzymaj = threading.Event()
        self._zmiana = threading.Event()
        self._blokada = threading.RLock()
        self._ostatnia_proba = 0.0
        self._watek: threading.Thread | None = None
        self._start_ekranu = time.monotonic()
        self._znane_przelaczajace: set[str] = set()
        self._wylaczony = False

    # --- dziennik widoczny w panelu ---
    def _zapisz(self, poziom: str, tekst: str) -> None:
        self.stan.dziennik.append((time.time(), poziom, tekst))
        getattr(log, poziom.lower(), log.info)(tekst)

    # --- ekran ---
    def _otworz_ekran(self) -> None:
        u = self.ustawienia
        if u.tryb == "symulacja":
            self.ekran = EkranSymulowany()
            self.stan.tryb, self.stan.port, self.stan.nazwa_urzadzenia = "symulacja", None, None
        else:
            self.stan.tryb = "usb"
            if u.port and u.port != "auto":
                znaleziony = ZnalezionyEkran(port=u.port, nazwa=u.port)
            else:
                lista = self._wykrywacz()
                if not lista:
                    raise BladEkranu("nie znaleziono ekranu USB (1a86:5722)")
                znaleziony = lista[0]
            ekran = self._fabryka_ekranu(znaleziony.port)
            ekran.polacz()
            self.ekran = ekran
            self.stan.port, self.stan.nazwa_urzadzenia = znaleziony.port, znaleziony.nazwa
        self.ekran.ustaw_orientacje(Orientacja(u.orientacja))
        self.stan.jasnosc = -1                    # wymusza ustawienie jasności w tym cyklu
        self._wylaczony = False
        self._wyslana = None
        self.stan.polaczony, self.stan.blad = True, None
        self._zapisz("INFO", f"ekran połączony: {self.stan.port or 'symulacja'}")

    def _zamknij_ekran(self, blad: str | None = None) -> None:
        if self.ekran is not None:
            self.ekran.rozlacz()
        self.ekran = None
        self._wyslana = None
        self.stan.polaczony = False
        if blad:
            self.stan.blad = blad
            self._zapisz("WARNING", f"ekran odłączony: {blad}; ponawiam co {PONOWNE_LACZENIE_S:.0f} s")

    # --- wybór ekranu ---
    def _kolejka(self, dane: dict) -> list[dict]:
        kolejka = [e for e in self.ustawienia.ekrany
                   if e["wl"] and rejestr.spelnia_warunek(rejestr.EKRANY[e["klucz"]], dane)]
        return kolejka or [{"klucz": "system", "wl": True, "czas_s": 10, "ukryte": []}]

    def _wybierz(self, dane: dict, alerty: list, teraz: float) -> dict:
        u, s = self.ustawienia, self.stan
        kolejka = self._kolejka(dane)
        klucze = [e["klucz"] for e in kolejka]
        s.kolejka = klucze
        krytyczne = any(a.poziom == "alarm" for a in alerty)
        # nowy alert z flagą „przełącz na Alerty” pokazuje ekran Alerty od razu
        przelaczajace = {a.id for a in alerty if a.przelacz}
        nowe = przelaczajace - self._znane_przelaczajace
        self._znane_przelaczajace = przelaczajace
        if nowe:
            s.ekran, self._start_ekranu = "alerty", teraz
            self._zapisz("INFO", f"alert: przełączam na ekran Alerty ({', '.join(sorted(nowe))[:120]})")
        s.przypiety = krytyczne and u.krytyczne_przypnij
        if s.przypiety:
            s.ekran = "alerty"
        elif s.ekran not in klucze and s.ekran != "alerty":
            s.ekran, self._start_ekranu = klucze[0], teraz
        elif u.przelaczanie_s > 0 and not s.pauza:
            biezacy = next((e for e in kolejka if e["klucz"] == s.ekran), None)
            czas = biezacy["czas_s"] if biezacy else u.przelaczanie_s
            if teraz - self._start_ekranu >= czas:
                self._przesun(1, klucze, teraz)
        biezacy = next((e for e in kolejka if e["klucz"] == s.ekran), None)
        czas = biezacy["czas_s"] if biezacy else u.przelaczanie_s
        s.nastepny_za_s = None if (s.przypiety or s.pauza or not u.przelaczanie_s) else max(0.0, czas - (teraz - self._start_ekranu))
        s.indeks = klucze.index(s.ekran) if s.ekran in klucze else 0
        ustawienia_ekranu = next((e for e in u.ekrany if e["klucz"] == s.ekran), None)
        return {"klucz": s.ekran, "ukryte": ustawienia_ekranu["ukryte"] if ustawienia_ekranu else [],
                "indeks": s.indeks, "razem": len(klucze)}

    def _przesun(self, krok: int, klucze: list, teraz: float) -> None:
        i = klucze.index(self.stan.ekran) if self.stan.ekran in klucze else -1
        self.stan.ekran = klucze[(i + krok) % len(klucze)]
        self._start_ekranu = teraz

    # --- sterowanie z panelu ---
    def przelacz(self, krok: int) -> None:
        with self._blokada:
            if self.stan.kolejka:
                self._przesun(krok, self.stan.kolejka, time.monotonic())
        self._zmiana.set()

    def pokaz(self, klucz: str) -> None:
        with self._blokada:
            if klucz in rejestr.EKRANY:
                self.stan.ekran, self._start_ekranu = klucz, time.monotonic()
        self._zmiana.set()

    def ustaw_pauze(self, pauza: bool) -> None:
        with self._blokada:
            self.stan.pauza = pauza
            self._start_ekranu = time.monotonic()
        self._zmiana.set()

    # --- jeden cykl ---
    def rysuj(self) -> Image.Image:
        u = self.ustawienia
        teraz = time.monotonic()
        odczyty = self.zbieracz.odczytaj(u)
        dane = self.zbieracz.dane(odczyty, u)
        self.dane = dane
        wybor = self._wybierz(dane, odczyty.alerty, teraz)
        rysuj.ustaw_motyw(u.motyw)
        return rejestr.narysuj(wybor["klucz"], dane, u.jezyk, u.poziomo, wybor["ukryte"], wybor["indeks"], wybor["razem"])

    def _jasnosc_i_noc(self) -> None:
        """Jasność, tryb nocny i wybudzenie alertem krytycznym."""
        u, s = self.ustawienia, self.stan
        krytyczne = any(a.poziom == "alarm" for a in self.zbieracz.ostatnie.alerty)
        priorytet = krytyczne and u.krytyczne_jasnosc
        s.noc = u.noc_wl and w_oknie_nocnym(u.noc_od, u.noc_do, time.localtime()) and not priorytet
        jasnosc = 100 if priorytet else u.jasnosc
        if self.ekran is None:
            s.jasnosc = jasnosc
            return
        if s.noc != self._wylaczony:
            self.ekran.wlacz(not s.noc)
            self._wylaczony = s.noc
            self._zapisz("INFO", "tryb nocny: ekran wyłączony" if s.noc else "ekran włączony")
        if jasnosc != s.jasnosc:
            self.ekran.ustaw_jasnosc(jasnosc)
            s.jasnosc = jasnosc

    def cykl(self) -> None:
        with self._blokada:
            if self.ekran is None and time.monotonic() - self._ostatnia_proba >= PONOWNE_LACZENIE_S:
                self._ostatnia_proba = time.monotonic()
                try:
                    self._otworz_ekran()
                except BladEkranu as blad:
                    if self.stan.blad != str(blad):
                        self._zapisz("WARNING", str(blad))
                    self.stan.blad = str(blad)
            obraz = self.rysuj()
            self.klatka = obraz
            if self.ekran is None:
                return
            try:
                self._jasnosc_i_noc()
                if self.stan.noc:
                    return
                if self._wyslana is not None and self._wyslana.size != obraz.size:
                    self._wyslana = None
                obszary = zmienione_obszary(self._wyslana, obraz)
                if not obszary:
                    return
                start = time.monotonic()
                for x0, y0, x1, y1 in obszary:
                    self.ekran.wyslij_obszar(obraz.crop((x0, y0, x1, y1)), x0, y0)
            except BladEkranu as blad:
                self._zamknij_ekran(str(blad))
                return
            czas = time.monotonic() - start
            if self._wyslana is None:
                self.stan.ostatnia_klatka_s = czas
            self.stan.ostatnia_wysylka_s = czas
            self._wyslana = obraz

    # --- zmiany ustawień z panelu ---
    def zastosuj(self, nowe: Ustawienia) -> None:
        with self._blokada:
            stare = self.ustawienia
            self.ustawienia = nowe
            if (stare.tryb, stare.port) != (nowe.tryb, nowe.port):
                self._zamknij_ekran()
                self._ostatnia_proba = 0.0
            elif self.ekran is not None:
                try:
                    if stare.orientacja != nowe.orientacja:
                        self.ekran.ustaw_orientacje(Orientacja(nowe.orientacja))
                        self._wyslana = None
                    if (stare.jezyk, stare.motyw) != (nowe.jezyk, nowe.motyw):
                        self._wyslana = None
                except BladEkranu as blad:
                    self._zamknij_ekran(str(blad))
        self._zmiana.set()

    def test_polaczenia(self) -> dict:
        """Wysyła pełną klatkę i mierzy czas. Używane przez przycisk w panelu."""
        with self._blokada:
            self._wyslana = None
        self.cykl()
        return {"polaczony": self.stan.polaczony, "czas_klatki_s": self.stan.ostatnia_klatka_s,
                "port": self.stan.port, "blad": self.stan.blad}

    # --- wątek ---
    def start(self) -> None:
        self.zbieracz.start()
        self._watek = threading.Thread(target=self._dzialaj, name="petla-lcd", daemon=True)
        self._watek.start()

    def stop(self) -> None:
        self._zatrzymaj.set()
        self._zmiana.set()
        if self._watek:
            self._watek.join(timeout=5)
        self.zbieracz.stop()
        with self._blokada:
            self._zamknij_ekran()

    def _dzialaj(self) -> None:
        self._zapisz("INFO", f"start, tryb {self.ustawienia.tryb}")
        while not self._zatrzymaj.is_set():
            try:
                self.cykl()
            except Exception:  # pętla nie może paść przez jeden błędny odczyt
                log.exception("błąd cyklu")
            self._zmiana.wait(self.ustawienia.odswiezanie_s)
            self._zmiana.clear()
