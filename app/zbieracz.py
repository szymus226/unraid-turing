"""Zbiera odczyty ze wszystkich źródeł w jeden słownik danych dla ekranów i liczy alerty.

Każde źródło może być niedostępne (np. brak montowania); wtedy ekran pokazuje „—”,
a reszta działa dalej.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .ekrany.dane import czas_pracy, predkosc
from .odczyt.docker import CzytnikDockera, aktualizacje_kontenerow, czytaj_vm
from .odczyt.dyski_io import CzytnikRuchuDyskow
from .odczyt.historia import Historia24
from .odczyt.pogoda import Pogoda
from .odczyt.powiadomienia import aktualizacje_wtyczek, czytaj_powiadomienia
from .odczyt.siec import HistoriaRuchu, MonitorSieci
from .odczyt.speedtest import Speedtest
from .odczyt.system import CzytnikSystemu, StanSystemu
from .odczyt.unraid import CzytnikUnraid, StanUnraid
from .ustawienia import Ustawienia

# Teksty alertów (PL/EN).
A = {
    "pl": {"cpu_temp": "Temperatura CPU", "cpu": "Obciążenie CPU", "ram": "RAM", "swap": "SWAP", "array": "Zajętość array",
           "prog": "próg", "array_stop": "Array zatrzymany", "array_stop_opis": "dyski niedostępne",
           "dysk_wyl": "wyłączony", "dysk_wyl_opis": "usunięty z array lub emulowany", "smart": "SMART",
           "smart_blad": "dysk zgłasza awarię", "smart_uwaga": "realokowane lub oczekujące sektory",
           "bledy_odczytu": "błędy odczytu", "parity_bledy": "Błędy parity", "parity_opis": "ostatnia kontrola",
           "kontener": "zatrzymany", "kontener_blad": "zatrzymany z błędem", "powiadomienie": "powiadomienie Unraida",
           "uruchomiony": "uruchomiony", "zatrzymany": "zatrzymany", "nieznany": "brak danych",
           "dzis": "dziś", "wczoraj": "wczoraj", "dni": "dni", "brak": "—", "nie_uzywany": "nie używany"},
    "en": {"cpu_temp": "CPU temperature", "cpu": "CPU load", "ram": "RAM", "swap": "Swap", "array": "Array usage",
           "prog": "threshold", "array_stop": "Array stopped", "array_stop_opis": "disks unavailable",
           "dysk_wyl": "disabled", "dysk_wyl_opis": "removed from array or emulated", "smart": "SMART",
           "smart_blad": "drive reports failure", "smart_uwaga": "reallocated or pending sectors",
           "bledy_odczytu": "read errors", "parity_bledy": "Parity errors", "parity_opis": "last check",
           "kontener": "stopped", "kontener_blad": "stopped with error", "powiadomienie": "Unraid notification",
           "uruchomiony": "started", "zatrzymany": "stopped", "nieznany": "no data",
           "dzis": "today", "wczoraj": "yesterday", "dni": "days", "brak": "—", "nie_uzywany": "not used"},
}
log = logging.getLogger(__name__)
TRWANIE_S = 30   # próg musi być przekroczony tyle sekund, zanim pojawi się alert (bez fałszywych skoków)


# Liczby aktualizacji z pulpitu są ważne 15 min (pulpit wysyła je co minutę).
AKTUALIZACJE_PULPITU_S = 15 * 60
# Karty ekranów z pulpitu są ważne 2 min (pulpit wysyła je co 30 s); starsze: ekran wypada z przełączania.
EKRANY_PULPITU_S = 120


def _liczba(v: float, jezyk: str, miejsca: int = 1) -> str:
    tekst = f"{v:.{miejsca}f}"
    return tekst.replace(".", ",") if jezyk == "pl" else tekst


def rozmiar_kb(kb: float, jezyk: str) -> str:
    for granica, jedn in ((1024**3, "TB"), (1024**2, "GB"), (1024, "MB")):
        if kb >= granica:
            return f"{_liczba(kb / granica, jezyk)} {jedn}"
    return f"{kb:.0f} kB"


def para_rozmiarow(zajete_kb: float, razem_kb: float, jezyk: str) -> str:
    for granica, jedn in ((1024**3, "TB"), (1024**2, "GB")):
        if razem_kb >= granica:
            return f"{_liczba(zajete_kb / granica, jezyk)} / {razem_kb / granica:.0f} {jedn}"
    return f"{zajete_kb / 1024:.0f} / {razem_kb / 1024:.0f} MB"


def bajty(b: int | None, jezyk: str) -> str:
    if b is None:
        return "—"
    if b >= 1024**3:
        return f"{_liczba(b / 1024**3, jezyk)} GB"
    return f"{b / 1024**2:.0f} MB"


def data_wzgledna(znacznik: float | None, jezyk: str, teraz: float | None = None) -> str:
    if not znacznik:
        return "—"
    teraz = time.time() if teraz is None else teraz
    dzien = time.localtime(znacznik)
    roznica_dni = (time.mktime(time.localtime(teraz)[:3] + (0, 0, 0, 0, 0, -1))
                   - time.mktime(dzien[:3] + (0, 0, 0, 0, 0, -1))) // 86400
    godzina = time.strftime("%H:%M", dzien)
    if roznica_dni == 0:
        return f"{A[jezyk]['dzis']} {godzina}"
    if roznica_dni == 1:
        return f"{A[jezyk]['wczoraj']} {godzina}"
    from .ekrany.dodatkowe import MIESIACE
    if jezyk == "pl":
        return f"{dzien.tm_mday} {MIESIACE['pl'][dzien.tm_mon - 1][:3]}"
    return f"{MIESIACE['en'][dzien.tm_mon - 1][:3]} {dzien.tm_mday}"


@dataclass
class AlertZewnetrzny:
    """Alert przysłany przez API (np. z pulpitu homelabbera)."""
    id: str
    poziom: str
    tytul: str
    opis: str
    wygasa: float


def rodzaj_alertu(id_: str) -> str:
    """Rodzaj alertu krytycznego po jego identyfikatorze (te same rodzaje co w panelu)."""
    if id_ == "zew:test-panelu":
        return "test"
    for przedrostek, rodzaj in (("dysk:", "dysk"), ("smart:", "smart"), ("array_stop", "array"),
                                ("parity", "parity"), ("unraid:", "unraid"), ("zew:", "pulpit")):
        if id_.startswith(przedrostek):
            return rodzaj
    return "prog"   # temperatura, CPU, RAM, SWAP, zajętość array


@dataclass
class Alert:
    id: str
    poziom: str          # alarm (krytyczny) albo uwaga
    tytul: str
    opis: str
    przelacz: bool = False
    rodzaj: str | None = None   # rodzaj alertu krytycznego (ustawienia „rodzaje_alertow”), None dla zwykłych
    wyciszony: bool = False     # krytyczny wyciszony do rozwiązania: na ekranie jako zwykłe ostrzeżenie

    def krotka(self):
        return (self.poziom, self.tytul, self.opis)


@dataclass
class Zrodla:
    """Ścieżki montowane w kontenerze (wszystkie tylko do odczytu)."""
    proc: str = os.environ.get("LCD_PROC", "/proc")
    sys: str = os.environ.get("LCD_SYS", "/sys")
    emhttp: str = os.environ.get("LCD_EMHTTP", "/host/emhttp")
    kontenery: str = os.environ.get("LCD_DOCKER", "/host/docker/containers")
    cgroup: str = os.environ.get("LCD_CGROUP", "/host/cgroup")
    status_aktualizacji: str = os.environ.get("LCD_DOCKER_AKTUALIZACJE", "/host/docker-update-status.json")
    libvirt_etc: str = os.environ.get("LCD_LIBVIRT_ETC", "/host/libvirt-etc/qemu")
    libvirt_run: str = os.environ.get("LCD_LIBVIRT_RUN", "/host/libvirt-run/qemu")
    powiadomienia: str = os.environ.get("LCD_POWIADOMIENIA", "/host/notifications/unread")
    wtyczki_nowe: str = os.environ.get("LCD_WTYCZKI_NOWE", "/host/plugins-nowe")
    wtyczki: str = os.environ.get("LCD_WTYCZKI", "/host/plugins")


@dataclass
class Odczyty:
    """Ostatni komplet odczytów (do panelu i do budowy danych ekranów)."""
    system: StanSystemu = field(default_factory=StanSystemu)
    unraid: StanUnraid = field(default_factory=StanUnraid)
    kontenery: list = field(default_factory=list)
    vm: list = field(default_factory=list)
    io: dict = field(default_factory=dict)
    alerty: list = field(default_factory=list)


class Zbieracz:
    def __init__(self, zrodla: Zrodla | None = None, katalog_konfiguracji: Path | None = None,
                 czytnik_systemu: CzytnikSystemu | None = None, w_tle: bool = True):
        self.z = zrodla or Zrodla()
        self.system = czytnik_systemu or CzytnikSystemu(self.z.proc, self.z.sys)
        self.unraid = CzytnikUnraid(self.z.emhttp)
        self.docker = CzytnikDockera(self.z.kontenery, self.z.cgroup)
        self.ruch = CzytnikRuchuDyskow(self.z.proc)
        self.historia24 = Historia24(katalog_konfiguracji / "historia.json" if katalog_konfiguracji else None)
        self.historia_ruchu = HistoriaRuchu()
        self.historia_cpu: list[tuple[float, float]] = []   # (czas, cpu) z ostatnich 60 s
        self.siec = MonitorSieci(self.z.proc)
        self.speedtest = Speedtest(katalog_konfiguracji / "speedtest.json" if katalog_konfiguracji else None)
        self.pogoda = Pogoda()
        self.zewnetrzne: dict[str, AlertZewnetrzny] = {}
        # Liczby aktualizacji z pulpitu homelabbera (dodatek „Smart ekran”) i czas ich nadejścia.
        self.aktualizacje_pulpitu: dict | None = None
        # Karty ekranów z pulpitu: klucz → (karty, czas nadejścia).
        self.ekrany_pulpitu: dict[str, tuple[list, float]] = {}
        self.polaczenia_pulpitu: tuple[list[dict], float] | None = None
        self._aktualizacje_pulpitu_czas = 0.0
        self._blokada = threading.Lock()
        self._od_kiedy: dict[str, float] = {}
        self._wolne: dict = {}          # wyniki wolnych odczytów (aktualizacje, powiadomienia, VM)
        self._wolne_czas = 0.0
        self._plik_wyciszonych = katalog_konfiguracji / "wyciszone.json" if katalog_konfiguracji else None
        self.wyciszone: set[str] = self._wczytaj_wyciszone()
        self.ostatnie = Odczyty()
        self.w_tle = w_tle

    def start(self) -> None:
        if self.w_tle:
            self.siec.start()
            self.speedtest.start()
            self.pogoda.start()

    def stop(self) -> None:
        self.siec.stop(); self.speedtest.stop(); self.pogoda.stop()
        self.historia24.zapisz()

    # --- alerty z API ---
    def dodaj_zewnetrzny(self, id_: str, poziom: str, tytul: str, opis: str, wazny_s: int) -> None:
        with self._blokada:
            self.zewnetrzne[id_] = AlertZewnetrzny(id_, poziom, tytul[:60], opis[:80], time.time() + wazny_s)

    def usun_zewnetrzny(self, id_: str) -> bool:
        with self._blokada:
            return self.zewnetrzne.pop(id_, None) is not None

    # --- ekrany z pulpitu ---
    def ustaw_ekrany_pulpitu(self, ekrany: dict[str, list] | None) -> None:
        """Zastępuje karty wszystkich ekranów z pulpitu (`None` = pulpit wyłączył ekrany)."""
        with self._blokada:
            teraz = time.time()
            self.ekrany_pulpitu = {k: (v, teraz) for k, v in (ekrany or {}).items()}

    def ekrany_z_pulpitu(self, teraz: float | None = None) -> dict[str, list]:
        teraz = time.time() if teraz is None else teraz
        return {k: v for k, (v, czas) in self.ekrany_pulpitu.items() if teraz - czas <= EKRANY_PULPITU_S}

    # --- ikony połączeń z pulpitu ---
    def ustaw_polaczenia_pulpitu(self, ikony: list[dict] | None) -> None:
        with self._blokada:
            self.polaczenia_pulpitu = (ikony, time.time()) if ikony else None

    def polaczenia_z_pulpitu(self, teraz: float | None = None) -> list[dict] | None:
        """Ikony do nagłówka, jeśli przyszły w ostatnich 2 min; `None` = nagłówek bez ikon."""
        teraz = time.time() if teraz is None else teraz
        p = self.polaczenia_pulpitu
        if not p or teraz - p[1] > EKRANY_PULPITU_S:
            return None
        return p[0]

    # --- liczby aktualizacji z pulpitu ---
    def ustaw_aktualizacje_pulpitu(self, liczby: dict | None) -> None:
        with self._blokada:
            self.aktualizacje_pulpitu = liczby
            self._aktualizacje_pulpitu_czas = time.time()

    def aktualizacje_z_pulpitu(self, teraz: float | None = None) -> dict | None:
        """Liczby z pulpitu, jeśli przyszły w ostatnich 15 min; `None` = ekran pokazuje licznik Unraida."""
        teraz = time.time() if teraz is None else teraz
        if self.aktualizacje_pulpitu is None or teraz - self._aktualizacje_pulpitu_czas > AKTUALIZACJE_PULPITU_S:
            return None
        return self.aktualizacje_pulpitu

    # --- wyciszanie alertów krytycznych (do rozwiązania problemu) ---
    def _wczytaj_wyciszone(self) -> set[str]:
        try:
            dane = json.loads(self._plik_wyciszonych.read_text()) if self._plik_wyciszonych else []
            return {str(x) for x in dane if isinstance(x, str)}
        except (OSError, ValueError):
            return set()

    def _zapisz_wyciszone(self) -> None:
        if not self._plik_wyciszonych:
            return
        try:
            self._plik_wyciszonych.write_text(json.dumps(sorted(self.wyciszone)))
        except OSError:
            log.warning("nie mogę zapisać listy wyciszonych alertów")

    def wycisz(self, id_: str, wyciszony: bool) -> None:
        with self._blokada:
            (self.wyciszone.add if wyciszony else self.wyciszone.discard)(id_)
            self._zapisz_wyciszone()

    # --- odczyt ---
    def _wolne_odczyty(self) -> dict:
        """Rzadziej zmieniające się dane: co 60 s."""
        if time.monotonic() - self._wolne_czas > 60 or not self._wolne:
            wtyczki, nowy_unraid = aktualizacje_wtyczek(self.z.wtyczki_nowe, self.z.wtyczki)
            self._wolne = {
                "vm": czytaj_vm(self.z.libvirt_etc, self.z.libvirt_run),
                "powiadomienia": czytaj_powiadomienia(self.z.powiadomienia),
                "kontenery_aktualizacje": aktualizacje_kontenerow(self.z.status_aktualizacji),
                "wtyczki": wtyczki, "unraid_nowa": nowy_unraid,
            }
            self._wolne_czas = time.monotonic()
        return self._wolne

    def odczytaj(self, u: Ustawienia) -> Odczyty:
        self.speedtest.ustaw(u.speedtest_co_h)
        self.pogoda.ustaw(u.pogoda_wl, u.pogoda_lat, u.pogoda_lon)
        o = Odczyty(system=self.system.odczytaj(), unraid=self.unraid.odczytaj(),
                    kontenery=self.docker.odczytaj(), io=self.ruch.odczytaj())
        wolne = self._wolne_odczyty()
        o.vm = wolne["vm"]
        s = o.system
        teraz = time.monotonic()
        self.historia_cpu = [p for p in self.historia_cpu if teraz - p[0] <= 60] + [(teraz, s.cpu)]
        self.historia24.dodaj(s.cpu, s.ram_procent, s.cpu_temp)
        self.historia_ruchu.dodaj(s.rx_bps, s.tx_bps)
        o.alerty = self.alerty(o, u, wolne)
        self.ostatnie = o
        return o

    # --- alerty ---
    def _trwa(self, klucz: str, warunek: bool, teraz: float) -> bool:
        if not warunek:
            self._od_kiedy.pop(klucz, None)
            return False
        start = self._od_kiedy.setdefault(klucz, teraz)
        return teraz - start >= TRWANIE_S

    def alerty(self, o: Odczyty, u: Ustawienia, wolne: dict, teraz: float | None = None) -> list[Alert]:
        teraz = time.time() if teraz is None else teraz
        j = u.jezyk
        t = A[j]
        wynik: list[Alert] = []
        progi = u.progi

        def prog(klucz, wartosc, tytul, jedn, id_=None):
            uwaga, alarm, przelacz = progi[klucz]
            id_ = id_ or klucz
            if wartosc is None:
                self._trwa(id_, False, teraz)
                return
            if self._trwa(id_, wartosc >= alarm, teraz):
                wynik.append(Alert(id_, "alarm", f"{tytul}: {wartosc:.0f}{jedn}", f"{t['prog']} {alarm}{jedn}", przelacz))
            elif self._trwa(id_ + ":u", wartosc >= uwaga, teraz):
                wynik.append(Alert(id_, "uwaga", f"{tytul}: {wartosc:.0f}{jedn}", f"{t['prog']} {uwaga}{jedn}", przelacz))
            if wartosc < alarm:
                self._od_kiedy.pop(id_, None)
            if wartosc < uwaga:
                self._od_kiedy.pop(id_ + ":u", None)

        s, un = o.system, o.unraid
        prog("cpu_temp", s.cpu_temp, t["cpu_temp"], "°C")
        prog("cpu", s.cpu, t["cpu"], "%")
        prog("ram", s.ram_procent, t["ram"], "%")
        prog("swap", s.swap_procent, t["swap"], "%")
        if un.array_rozmiar_kb:
            prog("array", 100 * un.array_zajete_kb / un.array_rozmiar_kb, t["array"], "%")
        if un.dostepny and un.array not in ("STARTED", "nieznany"):
            wynik.append(Alert("array_stop", "alarm", t["array_stop"], t["array_stop_opis"], True))
        przelacz_dysk = progi["dysk_awaria"][2]
        for d in un.dyski:
            if d.stan == "alarm" and d.smart != "alarm":
                wynik.append(Alert(f"dysk:{d.nazwa}", "alarm", f"{d.etykieta}: {t['dysk_wyl']}", t["dysk_wyl_opis"], przelacz_dysk))
            if d.smart == "alarm":
                wynik.append(Alert(f"smart:{d.nazwa}", "alarm", f"{t['smart']} {d.etykieta}", t["smart_blad"], przelacz_dysk))
            elif d.smart == "uwaga":
                wynik.append(Alert(f"smart:{d.nazwa}", "uwaga", f"{t['smart']} {d.etykieta}", t["smart_uwaga"], False))
            elif d.bledy:
                wynik.append(Alert(f"bledy:{d.nazwa}", "uwaga", d.etykieta, f"{t['bledy_odczytu']}: {d.bledy}", False))
            if d.temp is not None and d.aktywny:
                prog("ssd_temp" if d.ssd else "hdd_temp", d.temp, d.etykieta, "°C", id_=f"temp:{d.nazwa}")
        if un.parity_ostatnia_bledy and not un.parity_trwa:
            wynik.append(Alert("parity", "alarm", f"{t['parity_bledy']}: {un.parity_ostatnia_bledy}",
                               f"{t['parity_opis']} {data_wzgledna(un.parity_ostatnia, j, teraz)}", True))
        przelacz_k = progi["kontener_stop"][2]
        for k in o.kontenery:
            wybrany = u.kontenery is not None and k.nazwa in u.kontenery
            if wybrany and not k.dziala:
                wynik.append(Alert(f"kontener:{k.nazwa}", "uwaga", k.nazwa, t["kontener"], przelacz_k))
            elif u.kontenery is None and k.stan == "uwaga":
                wynik.append(Alert(f"kontener:{k.nazwa}", "uwaga", k.nazwa, t["kontener_blad"], przelacz_k))
        for p in wolne.get("powiadomienia", []):
            if p.poziom in ("alarm", "uwaga"):
                wynik.append(Alert(f"unraid:{p.plik}", p.poziom, p.tytul, p.opis or t["powiadomienie"], p.poziom == "alarm"))
        with self._blokada:
            for id_, z in list(self.zewnetrzne.items()):
                if z.wygasa < teraz:
                    del self.zewnetrzne[id_]
                    continue
                wynik.append(Alert(f"zew:{id_}", z.poziom, z.tytul, z.opis, z.poziom == "alarm"))
        wynik = self._zastosuj_rodzaje(wynik, u)
        # krytyczne pierwsze, potem ostrzeżenia
        wynik.sort(key=lambda a: 0 if a.poziom == "alarm" else 1)
        return wynik

    def _zastosuj_rodzaje(self, alerty: list[Alert], u: Ustawienia) -> list[Alert]:
        """Rodzaje alertów z panelu: wyłączone znikają, niekrytyczne i wyciszone stają się zwykłym ostrzeżeniem."""
        wynik, krytyczne_id = [], set()
        for a in alerty:
            if a.poziom != "alarm":
                wynik.append(a)
                continue
            a.rodzaj = rodzaj_alertu(a.id)
            pokaz, krytyczny = u.rodzaje_alertow.get(a.rodzaj, [True, True])
            if not pokaz:
                continue
            if not krytyczny:
                a.poziom, a.przelacz = "uwaga", False
            else:
                krytyczne_id.add(a.id)
                if a.id in self.wyciszone:
                    a.poziom, a.przelacz, a.wyciszony = "uwaga", False, True
            wynik.append(a)
        with self._blokada:
            # wyciszenie trwa do rozwiązania: znika razem z alertem
            if self.wyciszone - krytyczne_id:
                self.wyciszone &= krytyczne_id
                self._zapisz_wyciszone()
        return wynik

    # --- dane dla ekranów ---
    def adres_panelu(self) -> str:
        """Adres do kodu QR: LCD_ADRES_PANELU albo http://<nazwa serwera>.local:<port>."""
        if os.environ.get("LCD_ADRES_PANELU"):
            return os.environ["LCD_ADRES_PANELU"]
        nazwa = (self.unraid.nazwa_serwera() or "tower").lower()
        return f"http://{nazwa}.local:{os.environ.get('LCD_PORT_PANELU', '8766')}"

    def dane(self, o: Odczyty, u: Ustawienia, adres_panelu: str | None = None, teraz: float | None = None) -> dict:
        teraz = time.time() if teraz is None else teraz
        j = u.jezyk
        t = A[j]
        s, un = o.system, o.unraid
        lok = time.localtime(teraz)
        d: dict = {
            "godzina": time.strftime("%H:%M", lok),
            "sortuj_awarie": u.sortuj_awarie, "_ramka": u.krytyczne_ramka, "_progi": u.progi,
            # system
            "cpu": s.cpu, "rdzenie": s.rdzenie or [s.cpu], "cpu_temp": s.cpu_temp, "ram": s.ram_procent,
            "ram_txt": f"{_liczba(s.ram_uzyte / 1024**3, j)} / {s.ram_calkowite / 1024**3:.0f} GB",
            "swap": s.swap_procent, "uptime": czas_pracy(s.uptime_s), "load": s.load,
            "rx": predkosc(s.rx_bps, j), "tx": predkosc(s.tx_bps, j),
            "historia_cpu": [p[1] for p in self.historia_cpu] if len(self.historia_cpu) >= 2 else [s.cpu, s.cpu],
            "alerty": [a.krotka() for a in o.alerty],
            "adres_panelu": adres_panelu or self.adres_panelu(),
        }
        # array i dyski
        if un.dostepny:
            uruchomiony = un.array == "STARTED"
            d["array_stan"] = "ok" if uruchomiony else "alarm"
            d["array_opis"] = t["uruchomiony"] if uruchomiony else t["zatrzymany"]
        else:
            d["array_stan"], d["array_opis"] = "szary", t["nieznany"]
        d["array_uzycie"] = round(100 * un.array_zajete_kb / un.array_rozmiar_kb) if un.array_rozmiar_kb else 0
        d["array_txt"] = para_rozmiarow(un.array_zajete_kb, un.array_rozmiar_kb, j) if un.array_rozmiar_kb else "—"
        d["cache_uzycie"] = round(100 * un.cache_zajete_kb / un.cache_rozmiar_kb) if un.cache_rozmiar_kb else 0
        d["cache_txt"] = para_rozmiarow(un.cache_zajete_kb, un.cache_rozmiar_kb, j) if un.cache_rozmiar_kb else "—"
        dyski = [x for x in un.dyski if u.dyski is None or x.nazwa in u.dyski]
        if u.dyski is not None:   # kolejność ustawiona w aplikacji pulpitu (przeciąganie wierszy)
            dyski.sort(key=lambda x: u.dyski.index(x.nazwa))
        d["dyski"] = [(x.etykieta, x.temp or 0, x.stan, x.aktywny) for x in dyski]
        d["dyski_io"] = [(x.etykieta, x.aktywny, *o.io.get(x.urzadzenie, (0.0, 0.0)), x.stan) for x in dyski]
        # kontenery i VM
        kont = o.kontenery
        if u.kontenery is not None:
            wybrane = [k for k in kont if k.nazwa in u.kontenery]
            wybrane.sort(key=lambda k: u.kontenery.index(k.nazwa))
            for k in wybrane:
                if not k.dziala:
                    k.stan = "uwaga"
        else:
            wybrane = [k for k in kont if k.dziala or k.stan == "uwaga"]
        d["kontenery_dzialaja"] = sum(1 for k in kont if k.dziala)
        d["kontenery_wszystkie"] = len(kont)
        d["kontenery"] = [(k.nazwa, k.stan, k.cpu or 0.0, bajty(k.ram_b, j) if k.dziala else "—") for k in wybrane]
        d["vm"] = [(v.nazwa, "ok" if v.dziala else "szary") for v in o.vm]
        # parity
        d["parity_trwa"] = un.parity_trwa
        d["parity_postep"] = un.parity_postep
        d["parity_predkosc"] = f"{un.parity_predkosc_kbs / 1024:.0f} MB/s" if un.parity_predkosc_kbs else "—"
        if un.parity_eta_s:
            g, m = divmod(int(un.parity_eta_s // 60), 60)
            d["parity_eta"] = f"{g}h {m:02d}m" if g else f"{m}m"
        else:
            d["parity_eta"] = "—"
        d["parity_bledy"] = un.parity_bledy
        # historia 24 h
        h = self.historia24.godzinowo(teraz)
        for klucz, zapas in (("cpu", s.cpu), ("ram", s.ram_procent), ("temp", s.cpu_temp or 0)):
            seria = h[klucz] + [zapas]
            d[f"hist_{klucz}"] = seria if len(seria) >= 2 else seria * 2
        # sieć
        rx, tx = self.historia_ruchu.serie()
        tunel = [k for k in kont if "cloudflared" in k.obraz.lower() or "cloudflared" in k.nazwa.lower()]
        d["siec"] = {"internet": self.siec.internet, "ping_bramka": self.siec.ping_router,
                     "ping_internet": self.siec.ping_internet, "rx": d["rx"], "tx": d["tx"],
                     "hist_rx": rx, "hist_tx": tx, "tunel": any(k.dziala for k in tunel) if tunel else None}
        # speedtest
        d["speedtest_wl"] = u.speedtest_co_h > 0
        wyn = self.speedtest.wyniki
        nast = self.speedtest.nastepny
        d["speedtest"] = {"pobieranie": [w["pobieranie"] for w in wyn], "wysylanie": [w["wysylanie"] for w in wyn],
                          "ping": [w["ping"] for w in wyn], "co_h": _liczba(u.speedtest_co_h, j, 1).rstrip("0").rstrip(",.") if u.speedtest_co_h else "—",
                          "ostatni": time.strftime("%H:%M", time.localtime(wyn[-1]["czas"])) if wyn else "—",
                          "nastepny": time.strftime("%H:%M", time.localtime(nast)) if nast else "—",
                          "trwa": self.speedtest.trwa}
        # aktualizacje
        wolne = self._wolne
        d["aktualizacje"] = {
            "wersja": un.wersja or "—", "unraid_nowa": wolne.get("unraid_nowa") if wolne.get("unraid_nowa") not in (None, un.wersja) else None,
            "wtyczki": wolne.get("wtyczki"), "kontenery": wolne.get("kontenery_aktualizacje"),
            "pulpit": self.aktualizacje_z_pulpitu(),
            "kopia": "—", "kopia_stan": "szary",
            "parity": data_wzgledna(un.parity_ostatnia, j, teraz) if un.parity_ostatnia else "—",
            "parity_bledy": un.parity_ostatnia_bledy,
            "restart": czas_pracy(s.uptime_s),
        }
        # zegar
        d["pulpit"] = self.ekrany_z_pulpitu()
        d["_polaczenia"] = self.polaczenia_z_pulpitu(teraz) if u.naglowek_polaczenia else None
        d["zegar"] = {"godzina": d["godzina"], "dzien_tyg": lok.tm_wday, "dzien": lok.tm_mday, "miesiac": lok.tm_mon,
                      "pogoda": self.pogoda.biezaca}
        return d
