"""API panelu (FastAPI). Strony panelu powstaną po akceptacji makiet."""
from __future__ import annotations

import io
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, Response
from pydantic import BaseModel

from . import ustawienia as konfiguracja
from .odczyt.system import CzytnikSystemu
from .petla import Petla
from .sterownik.wykrywanie import wykryj

logging.basicConfig(level=os.environ.get("LCD_LOG", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

KATALOG_DEV = os.environ.get("LCD_DEV", "/dev")
KATALOG_SYS = os.environ.get("LCD_SYS", "/sys")
KATALOG_PROC = os.environ.get("LCD_PROC", "/proc")


def utworz_petle() -> Petla:
    return Petla(konfiguracja.wczytaj(), CzytnikSystemu(KATALOG_PROC, KATALOG_SYS),
                 katalog_dev=KATALOG_DEV, katalog_sys=KATALOG_SYS)


@asynccontextmanager
async def cykl_zycia(app: FastAPI):
    petla = utworz_petle()
    app.state.petla = petla
    petla.start()
    yield
    petla.stop()


app = FastAPI(title="Unraid LCD", lifespan=cykl_zycia)


class ZmianaUstawien(BaseModel):
    tryb: str | None = None
    port: str | None = None
    jasnosc: int | None = None
    orientacja: str | None = None
    odswiezanie_s: float | None = None
    przelaczanie_s: int | None = None
    jezyk: str | None = None


@app.get("/api/stan")
def stan():
    s = app.state.petla.stan
    return {
        "polaczony": s.polaczony, "tryb": s.tryb, "port": s.port, "urzadzenie": s.nazwa_urzadzenia,
        "czas_klatki_s": s.ostatnia_klatka_s, "czas_wysylki_s": s.ostatnia_wysylka_s,
        "blad": s.blad, "ekran": s.ekran,
    }


@app.get("/api/podglad.png")
def podglad():
    klatka = app.state.petla.klatka
    if klatka is None:
        return Response(status_code=204)
    bufor = io.BytesIO()
    klatka.save(bufor, "PNG")
    return Response(bufor.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/api/ustawienia")
def pobierz_ustawienia():
    return asdict(app.state.petla.ustawienia)


@app.put("/api/ustawienia")
def zmien_ustawienia(zmiana: ZmianaUstawien):
    obecne = asdict(app.state.petla.ustawienia)
    obecne.update({k: v for k, v in zmiana.model_dump().items() if v is not None})
    nowe = konfiguracja.Ustawienia(**obecne).popraw()
    konfiguracja.zapisz(nowe)
    app.state.petla.zastosuj(nowe)
    return asdict(nowe)


@app.get("/api/urzadzenia")
def urzadzenia():
    return [asdict(e) for e in wykryj(KATALOG_DEV, KATALOG_SYS)]


@app.post("/api/test")
def test():
    return app.state.petla.test_polaczenia()


@app.get("/api/logi")
def logi():
    return [{"czas": c, "poziom": p, "tekst": t} for c, p, t in app.state.petla.stan.dziennik]
