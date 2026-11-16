"""Panel WWW i API (FastAPI). Panel działa tylko w sieci domowej i nie ma logowania,
więc API nie zwraca niczego wrażliwego (bez haseł, tokenów i zmiennych kontenerów).
"""
from __future__ import annotations

import io
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Body, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import ustawienia as konfiguracja
from .ekrany import rejestr, rysuj
from .odczyt.pogoda import szukaj_miejscowosci
from .odczyt.system import CzytnikSystemu, temperatura_cpu
from .petla import Petla
from .sterownik.wykrywanie import wykryj
from .zbieracz import Zbieracz, Zrodla

logging.basicConfig(level=os.environ.get("LCD_LOG", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

KATALOG_DEV = os.environ.get("LCD_DEV", "/dev")
KATALOG_SYS = os.environ.get("LCD_SYS", "/sys")
KATALOG_PROC = os.environ.get("LCD_PROC", "/proc")
PANEL = Path(__file__).parent / "panel" / "index.html"
WERSJA = "0.2.0"

# Klucze ustawień zapisywane razem z motywem (eksport/import układu).
KLUCZE_MOTYWU = ("motyw", "orientacja", "ekrany", "progi", "sortuj_awarie", "krytyczne_przypnij",
                 "krytyczne_jasnosc", "krytyczne_ramka", "jezyk", "przelaczanie_s", "rodzaje_alertow")


def utworz_petle() -> Petla:
    katalog = konfiguracja.katalog_konfiguracji()
    zbieracz = Zbieracz(Zrodla(proc=KATALOG_PROC, sys=KATALOG_SYS), katalog_konfiguracji=katalog if katalog.is_dir() else None,
                        czytnik_systemu=CzytnikSystemu(KATALOG_PROC, KATALOG_SYS))
    return Petla(konfiguracja.wczytaj(), katalog_dev=KATALOG_DEV, katalog_sys=KATALOG_SYS, zbieracz=zbieracz)


def token_alertow() -> str:
    """Token dla alertów wysyłanych przez API (np. z pulpitu homelabbera): LCD_TOKEN albo plik /config/token.txt."""
    if os.environ.get("LCD_TOKEN"):
        return os.environ["LCD_TOKEN"]
    plik = konfiguracja.katalog_konfiguracji() / "token.txt"
    try:
        return plik.read_text().strip()
    except OSError:
        token = secrets.token_urlsafe(24)
        try:
            plik.parent.mkdir(parents=True, exist_ok=True)
            plik.write_text(token + "\n")
            os.chmod(plik, 0o600)
        except OSError:
            pass
        return token


class ZuzycieAplikacji:
    """CPU i RAM własnego procesu (do paska stanu w panelu)."""

    def __init__(self):
        self._poprzedni = (time.monotonic(), time.process_time())

    def odczyt(self) -> dict:
        teraz, cpu = time.monotonic(), time.process_time()
        dt = teraz - self._poprzedni[0]
        procent = 100 * (cpu - self._poprzedni[1]) / dt if dt > 0 else 0.0
        if dt > 5:
            self._poprzedni = (teraz, cpu)
        ram = 0
        try:
            for linia in Path("/proc/self/status").read_text().splitlines():
                if linia.startswith("VmRSS:"):
                    ram = int(linia.split()[1]) * 1024
        except OSError:
            pass
        return {"cpu": round(procent, 1), "ram_mb": round(ram / 1024**2)}


@asynccontextmanager
async def cykl_zycia(app: FastAPI):
    petla = utworz_petle()
    app.state.petla = petla
    app.state.zuzycie = ZuzycieAplikacji()
    app.state.token = token_alertow()
    petla.start()
    yield
    petla.stop()


app = FastAPI(title="Unraid LCD", version=WERSJA, lifespan=cykl_zycia, docs_url=None, redoc_url=None)


def _petla() -> Petla:
    return app.state.petla


def _png(obraz) -> Response:
    bufor = io.BytesIO()
    obraz.save(bufor, "PNG")
    return Response(bufor.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/", include_in_schema=False)
def panel():
    return FileResponse(PANEL, media_type="text/html", headers={"Cache-Control": "no-store"})


@app.get("/api/stan")
def stan():
    p = _petla()
    s = p.stan
    z = p.zbieracz
    o = z.ostatnie
    return {
        "wersja": WERSJA,
        "polaczony": s.polaczony, "tryb": s.tryb, "port": s.port, "urzadzenie": s.nazwa_urzadzenia,
        "czas_klatki_s": s.ostatnia_klatka_s, "czas_wysylki_s": s.ostatnia_wysylka_s, "blad": s.blad,
        "ekran": s.ekran, "indeks": s.indeks, "kolejka": s.kolejka, "pauza": s.pauza, "przypiety": s.przypiety,
        "noc": s.noc, "jasnosc": s.jasnosc, "nastepny_za_s": s.nastepny_za_s,
        "zrodla": {
            "unraid": o.unraid.dostepny,
            "docker": z.docker.dostepny,
            "czujniki": o.system.cpu_temp is not None,
            "vm": Path(z.z.libvirt_etc).is_dir(),
            "powiadomienia": Path(z.z.powiadomienia).is_dir(),
            "wtyczki": z._wolne.get("wtyczki") is not None,
            "aktualizacje_kontenerow": z._wolne.get("kontenery_aktualizacje") is not None,
            "internet": z.siec.internet,
        },
        "aplikacja": app.state.zuzycie.odczyt(),
        "alerty": [{"id": a.id, "poziom": a.poziom, "tytul": a.tytul, "opis": a.opis, "rodzaj": a.rodzaj,
                    "wyciszony": a.wyciszony} for a in o.alerty],
        "speedtest": {"trwa": z.speedtest.trwa, "blad": z.speedtest.blad, "nastepny": z.speedtest.nastepny},
        "pogoda": {"biezaca": z.pogoda.biezaca, "blad": z.pogoda.blad},
    }


@app.get("/api/podglad.png")
def podglad():
    klatka = _petla().klatka
    if klatka is None:
        return Response(status_code=204)
    return _png(klatka)


@app.get("/api/ekrany")
def ekrany():
    return [{"klucz": e.klucz, "nazwa": e.nazwa, "elementy": e.elementy, "warunek": e.warunek} for e in rejestr.EKRANY.values()]


@app.get("/api/ekran/{klucz}.png")
def ekran_png(klucz: str, ukryte: str = "", jezyk: str | None = None, orientacja: str | None = None,
              motyw: str | None = None):
    """Miniatura dowolnego ekranu z bieżącymi danymi (także ekranu, który nie jest teraz pokazywany)."""
    if klucz not in rejestr.EKRANY:
        raise HTTPException(404, "nieznany ekran")
    p = _petla()
    u = p.ustawienia
    dane = dict(p.dane) or rejestr.przykladowe_dane(u.jezyk)
    if klucz == "parity" and not dane.get("parity_trwa"):
        dane.setdefault("parity_postep", 0.0)
    try:
        lista_ukrytych = [int(x) for x in ukryte.split(",") if x.strip()]
    except ValueError:
        lista_ukrytych = []
    jezyk = jezyk if jezyk in ("pl", "en") else u.jezyk
    poziomo = (orientacja or u.orientacja) in ("poziomo", "poziomo_odwrocony")
    kolejka = p.stan.kolejka or [klucz]
    indeks = kolejka.index(klucz) if klucz in kolejka else 0
    with p._blokada:   # motyw kolorów jest wspólny dla pętli i miniatur
        rysuj.ustaw_motyw(motyw if motyw in konfiguracja.MOTYWY else u.motyw)
        obraz = rejestr.narysuj(klucz, dane, jezyk, poziomo, lista_ukrytych, indeks, len(kolejka))
        rysuj.ustaw_motyw(u.motyw)
    return _png(obraz)


@app.get("/api/ustawienia")
def pobierz_ustawienia():
    return asdict(_petla().ustawienia)


def _zastosuj(zmiany: dict) -> dict:
    obecne = asdict(_petla().ustawienia)
    znane = set(obecne)
    obecne.update({k: v for k, v in zmiany.items() if k in znane})
    nowe = konfiguracja.z_slownika(obecne)
    konfiguracja.zapisz(nowe)
    _petla().zastosuj(nowe)
    return asdict(nowe)


@app.put("/api/ustawienia")
def zmien_ustawienia(zmiany: dict = Body(...)):
    return _zastosuj(zmiany)


@app.get("/api/dyski")
def dyski():
    u = _petla().ustawienia
    return [{"nazwa": d.nazwa, "etykieta": d.etykieta, "rola": d.rola, "temp": d.temp, "aktywny": d.aktywny,
             "stan": d.stan, "smart": d.smart, "ssd": d.ssd,
             "wybrany": u.dyski is None or d.nazwa in u.dyski} for d in _petla().zbieracz.ostatnie.unraid.dyski]


@app.get("/api/kontenery")
def kontenery():
    u = _petla().ustawienia
    lista = _petla().zbieracz.ostatnie.kontenery
    if u.kontenery is None:
        domyslne = [k.nazwa for k in lista if k.dziala][:konfiguracja.MAKS_KONTENEROW]
    else:
        domyslne = u.kontenery
    return [{"nazwa": k.nazwa, "dziala": k.dziala, "stan": k.stan, "cpu": k.cpu,
             "ram_mb": round(k.ram_b / 1024**2) if k.ram_b is not None else None,
             "wybrany": k.nazwa in domyslne} for k in lista]


@app.get("/api/urzadzenia")
def urzadzenia():
    return [asdict(e) for e in wykryj(KATALOG_DEV, KATALOG_SYS)]


@app.post("/api/test")
def test():
    return _petla().test_polaczenia()


class Nawigacja(BaseModel):
    akcja: str = Field(pattern="^(nastepny|poprzedni|pauza|wznow|pokaz)$")
    klucz: str | None = None


@app.post("/api/nawigacja")
def nawigacja(n: Nawigacja):
    p = _petla()
    if n.akcja == "nastepny":
        p.przelacz(1)
    elif n.akcja == "poprzedni":
        p.przelacz(-1)
    elif n.akcja in ("pauza", "wznow"):
        p.ustaw_pauze(n.akcja == "pauza")
    elif n.klucz:
        p.pokaz(n.klucz)
    return {"ekran": p.stan.ekran, "pauza": p.stan.pauza}


@app.post("/api/alert-testowy")
def alert_testowy(jezyk: str = "pl"):
    """Alert krytyczny na 60 s: sprawdza przypięcie, jasność 100% i ramkę na prawdziwym ekranie."""
    tytul, opis = ("Test alertu krytycznego", "zniknie sam za 60 s") if jezyk == "pl" else ("Critical alert test", "clears itself in 60 s")
    _petla().zbieracz.dodaj_zewnetrzny("test-panelu", "alarm", tytul, opis, 60)
    _petla()._zmiana.set()
    return {"ok": True}


@app.delete("/api/alert-testowy")
def usun_alert_testowy():
    _petla().zbieracz.usun_zewnetrzny("test-panelu")
    _petla()._zmiana.set()
    return {"ok": True}


class Wyciszenie(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    wyciszony: bool


@app.post("/api/wyciszenie")
def wyciszenie(w: Wyciszenie):
    """Wycisza alert krytyczny do rozwiązania problemu (zostaje na ekranie Alerty jako zwykły)."""
    _petla().zbieracz.wycisz(w.id, w.wyciszony)
    _petla()._zmiana.set()
    return {"ok": True}


# --- alerty z zewnątrz (pulpit homelabbera); wymagają tokenu z /config/token.txt ---
class AlertZewnetrzny(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:\-]+$")
    poziom: str = Field(pattern="^(alarm|uwaga)$")
    tytul: str = Field(min_length=1, max_length=60)
    opis: str = Field(default="", max_length=80)
    wazny_s: int = Field(default=300, ge=10, le=86400)


def _sprawdz_token(authorization: str | None) -> None:
    oczekiwany = f"Bearer {app.state.token}"
    if not authorization or not secrets.compare_digest(authorization, oczekiwany):
        raise HTTPException(401, "brak lub zły token")


@app.post("/api/alerty")
def dodaj_alert(alert: AlertZewnetrzny, authorization: str | None = Header(default=None)):
    _sprawdz_token(authorization)
    _petla().zbieracz.dodaj_zewnetrzny(alert.id, alert.poziom, alert.tytul, alert.opis, alert.wazny_s)
    _petla()._zmiana.set()
    return {"ok": True}


@app.delete("/api/alerty/{id_}")
def usun_alert(id_: str, authorization: str | None = Header(default=None)):
    _sprawdz_token(authorization)
    return {"usuniety": _petla().zbieracz.usun_zewnetrzny(id_)}


# --- pogoda ---
@app.get("/api/pogoda/szukaj")
def pogoda_szukaj(q: str = Query(min_length=2, max_length=80), jezyk: str = "pl"):
    try:
        return szukaj_miejscowosci(q, jezyk if jezyk in ("pl", "en") else "pl")
    except Exception as blad:
        raise HTTPException(502, f"wyszukiwarka miejscowości niedostępna: {blad}") from blad


@app.post("/api/speedtest")
def speedtest_teraz():
    """Pomiar od razu (przycisk w panelu); działa w tle."""
    import threading
    st = _petla().zbieracz.speedtest
    if st.trwa:
        return {"trwa": True}
    threading.Thread(target=st.wykonaj, name="speedtest-teraz", daemon=True).start()
    return {"trwa": True}


# --- motywy: eksport i import układu ---
@app.get("/api/motyw/eksport")
def motyw_eksport():
    u = asdict(_petla().ustawienia)
    dane = {"format": "unraid-lcd-motyw", "wersja": 1, **{k: u[k] for k in KLUCZE_MOTYWU}}
    return Response(json.dumps(dane, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="unraid-lcd-motyw.json"'})


@app.post("/api/motyw/import")
def motyw_import(dane: dict = Body(...)):
    if dane.get("format") != "unraid-lcd-motyw":
        raise HTTPException(400, "to nie jest plik motywu Unraid LCD")
    return _zastosuj({k: dane[k] for k in KLUCZE_MOTYWU if k in dane})


# --- logi ---
@app.get("/api/logi")
def logi():
    return [{"czas": c, "poziom": p, "tekst": t} for c, p, t in _petla().stan.dziennik]


@app.get("/api/logi.txt")
def logi_txt():
    linie = [f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(c))} {p:7} {t}" for c, p, t in _petla().stan.dziennik]
    return PlainTextResponse("\n".join(linie) + "\n", headers={"Content-Disposition": 'attachment; filename="unraid-lcd.log"'})


__all__ = ["app", "temperatura_cpu"]
