"""Główna pętla: odczyt danych, rysowanie ekranu, wysyłka zmienionych fragmentów.

Pętla działa w osobnym wątku. Po odłączeniu ekranu co 5 s szuka go ponownie
i po połączeniu wysyła pełną klatkę.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from PIL import Image

from .ekrany import rysuj
from .ekrany.dane import HistoriaCpu, dane_systemu
from .odczyt.system import CzytnikSystemu
from .roznice import zmienione_obszary
from .sterownik.baza import BladEkranu, Ekran, Orientacja
from .sterownik.rev_a import EkranRevA
from .sterownik.symulator import EkranSymulowany
from .sterownik.wykrywanie import ZnalezionyEkran, wykryj
from .ustawienia import Ustawienia

log = logging.getLogger(__name__)

PONOWNE_LACZENIE_S = 5.0


@dataclass
class StanPetli:
    polaczony: bool = False
    tryb: str = "symulacja"
    port: str | None = None
    nazwa_urzadzenia: str | None = None
    ostatnia_klatka_s: float | None = None    # czas wysyłki pełnej klatki
    ostatnia_wysylka_s: float | None = None   # czas ostatniej wysyłki zmian
    blad: str | None = None
    ekran: str = "system"
    dziennik: deque = field(default_factory=lambda: deque(maxlen=200))


class Petla:
    def __init__(self, ustawienia: Ustawienia, czytnik: CzytnikSystemu | None = None,
                 katalog_dev: str = "/dev", katalog_sys: str = "/sys",
                 fabryka_ekranu=None, wykrywacz=None):
        self.ustawienia = ustawienia
        self.czytnik = czytnik or CzytnikSystemu()
        self.katalog_dev = katalog_dev
        self.katalog_sys = katalog_sys
        self._fabryka_ekranu = fabryka_ekranu or (lambda port: EkranRevA(port))
        self._wykrywacz = wykrywacz or (lambda: wykryj(self.katalog_dev, self.katalog_sys))
        self.stan = StanPetli()
        self.historia = HistoriaCpu()
        self.ekran: Ekran | None = None
        self.klatka: Image.Image | None = None        # ostatnio narysowana klatka (podgląd w panelu)
        self._wyslana: Image.Image | None = None      # to, co jest teraz na fizycznym ekranie
        self._zatrzymaj = threading.Event()
        self._zmiana = threading.Event()
        self._blokada = threading.Lock()
        self._ostatnia_proba = 0.0
        self._watek: threading.Thread | None = None

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
        self.ekran.ustaw_jasnosc(u.jasnosc)
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

    # --- jeden cykl ---
    def rysuj(self) -> Image.Image:
        stan = self.czytnik.odczytaj()
        historia = self.historia.dodaj(stan.cpu)
        t = dict(rysuj.TEKSTY[self.ustawienia.jezyk], _j=self.ustawienia.jezyk)
        return rysuj.ekran_system(t, dane_systemu(stan, historia, self.ustawienia.jezyk))

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
            obszary = zmienione_obszary(self._wyslana, obraz)
            if not obszary:
                return
            start = time.monotonic()
            try:
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
                    if stare.jasnosc != nowe.jasnosc:
                        self.ekran.ustaw_jasnosc(nowe.jasnosc)
                    if stare.jezyk != nowe.jezyk:
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
        self._watek = threading.Thread(target=self._dzialaj, name="petla-lcd", daemon=True)
        self._watek.start()

    def stop(self) -> None:
        self._zatrzymaj.set()
        self._zmiana.set()
        if self._watek:
            self._watek.join(timeout=5)
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
