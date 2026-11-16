"""API panelu: odpowiedzi, zapis ustawień, token alertów, motywy."""
import json

import pytest
from fastapi.testclient import TestClient

from app import serwer


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setenv("LCD_KONFIGURACJA", str(tmp_path))
    monkeypatch.setenv("LCD_TOKEN", "token-testowy")
    (tmp_path / "ustawienia.json").write_text(json.dumps({"tryb": "symulacja"}))
    with TestClient(serwer.app) as k:
        yield k


def test_panel_i_stan(klient):
    r = klient.get("/")
    assert r.status_code == 200 and "Unraid LCD" in r.text and "__IMGS__" not in r.text
    s = klient.get("/api/stan").json()
    assert s["tryb"] == "symulacja" and "zrodla" in s and "aplikacja" in s


def test_zapis_ustawien_i_miniatury(klient, tmp_path):
    u = klient.put("/api/ustawienia", json={"orientacja": "poziomo", "jasnosc": 30, "nieznane": 1}).json()
    assert u["orientacja"] == "poziomo" and u["jasnosc"] == 30 and "nieznane" not in u
    assert json.loads((tmp_path / "ustawienia.json").read_text())["jasnosc"] == 30
    r = klient.get("/api/ekran/system.png?ukryte=1,2&jezyk=en")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert klient.get("/api/ekran/nieznany.png").status_code == 404
    assert len(klient.get("/api/ekrany").json()) == 12


def test_nawigacja(klient):
    assert klient.post("/api/nawigacja", json={"akcja": "pauza"}).json()["pauza"] is True
    assert klient.post("/api/nawigacja", json={"akcja": "zle"}).status_code == 422


def test_alerty_wymagaja_tokenu(klient):
    alert = {"id": "tunel", "poziom": "alarm", "tytul": "Tunel", "opis": "nie działa"}
    assert klient.post("/api/alerty", json=alert).status_code == 401
    assert klient.post("/api/alerty", json=alert, headers={"Authorization": "Bearer zly"}).status_code == 401
    assert klient.post("/api/alerty", json=alert, headers={"Authorization": "Bearer token-testowy"}).status_code == 200
    assert klient.delete("/api/alerty/tunel", headers={"Authorization": "Bearer token-testowy"}).json()["usuniety"]


def test_alert_testowy(klient):
    klient.post("/api/alert-testowy")
    assert "test-panelu" in serwer.app.state.petla.zbieracz.zewnetrzne
    klient.delete("/api/alert-testowy")
    assert "test-panelu" not in serwer.app.state.petla.zbieracz.zewnetrzne


def test_motyw_eksport_import(klient):
    klient.put("/api/ustawienia", json={"motyw": "jasny"})
    plik = klient.get("/api/motyw/eksport").json()
    assert plik["format"] == "unraid-lcd-motyw" and plik["motyw"] == "jasny" and "tryb" not in plik
    klient.put("/api/ustawienia", json={"motyw": "czarny"})
    assert klient.post("/api/motyw/import", json=plik).json()["motyw"] == "jasny"
    assert klient.post("/api/motyw/import", json={"motyw": "jasny"}).status_code == 400


def test_logi(klient):
    assert isinstance(klient.get("/api/logi").json(), list)
    assert klient.get("/api/logi.txt").status_code == 200
