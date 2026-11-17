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
    assert len(klient.get("/api/ekrany").json()) == 18


def test_nawigacja(klient):
    assert klient.post("/api/nawigacja", json={"akcja": "pauza"}).json()["pauza"] is True
    assert klient.post("/api/nawigacja", json={"akcja": "zle"}).status_code == 422


def test_alerty_wymagaja_tokenu(klient):
    alert = {"id": "tunel", "poziom": "alarm", "tytul": "Tunel", "opis": "nie działa"}
    assert klient.post("/api/alerty", json=alert).status_code == 401
    assert klient.post("/api/alerty", json=alert, headers={"Authorization": "Bearer zly"}).status_code == 401
    assert klient.post("/api/alerty", json=alert, headers={"Authorization": "Bearer token-testowy"}).status_code == 200
    assert klient.delete("/api/alerty/tunel", headers={"Authorization": "Bearer token-testowy"}).json()["usuniety"]


def test_aktualizacje_z_pulpitu_wymagaja_tokenu(klient):
    liczby = {"available": 2, "auto": 1, "notify": 1, "outside": 0, "servers": 0, "failed": 0, "checkedAt": "2026-11-17T03:00:00Z"}
    assert klient.post("/api/aktualizacje", json=liczby).status_code == 401
    ok = {"Authorization": "Bearer token-testowy"}
    assert klient.post("/api/aktualizacje", json=dict(liczby, available=-1), headers=ok).status_code == 422
    assert klient.post("/api/aktualizacje", json=liczby, headers=ok).status_code == 200
    assert klient.delete("/api/aktualizacje", headers=ok).status_code == 200


def test_ekrany_z_pulpitu(klient):
    ok = {"Authorization": "Bearer token-testowy"}
    karty = {"ekrany": {"pulpit_zasilanie": [{"etykieta": "Bateria", "wartosc": "100%", "pasek": 100}, None]}}
    assert klient.post("/api/pulpit/ekrany", json=karty).status_code == 401
    assert klient.post("/api/pulpit/ekrany", json={"ekrany": {"obcy": []}}, headers=ok).status_code == 422
    assert klient.post("/api/pulpit/ekrany", json={"ekrany": {"pulpit_kopie": [None] * 7}}, headers=ok).status_code == 422
    assert klient.post("/api/pulpit/ekrany", json=karty, headers=ok).status_code == 200
    assert klient.get("/api/ekran/pulpit_zasilanie.png").headers["content-type"] == "image/png"
    assert any(e["klucz"] == "pulpit_kamery" and e["warunek"] == "pulpit" for e in klient.get("/api/ekrany").json())
    assert klient.delete("/api/pulpit/ekrany", headers=ok).status_code == 200
    assert klient.post("/api/pulpit/ekrany", json={"ekrany": {"pulpit_polaczenia": [{"etykieta": "Internet", "wartosc": "działa"}]}}, headers=ok).status_code == 200


def test_ikony_polaczen_z_pulpitu(klient):
    ok = {"Authorization": "Bearer token-testowy"}
    ikony = {"ikony": [{"rodzaj": "internet", "stan": "ok"}, {"rodzaj": "bt", "liczba": 2}, {"rodzaj": "cast", "stan": "gra"}]}
    assert klient.post("/api/pulpit/polaczenia", json=ikony).status_code == 401
    assert klient.post("/api/pulpit/polaczenia", json={"ikony": [{"rodzaj": "radio"}]}, headers=ok).status_code == 422
    assert klient.post("/api/pulpit/polaczenia", json={"ikony": [{"rodzaj": "internet"}] * 7}, headers=ok).status_code == 422
    assert klient.post("/api/pulpit/polaczenia", json=ikony, headers=ok).status_code == 200
    assert klient.get("/api/ekran/system.png").status_code == 200
    assert klient.put("/api/ustawienia", json={"naglowek_polaczenia": False}).json()["naglowek_polaczenia"] is False
    assert klient.delete("/api/pulpit/polaczenia", headers=ok).status_code == 200


def test_alert_testowy(klient):
    klient.post("/api/alert-testowy")
    assert "test-panelu" in serwer.app.state.petla.zbieracz.zewnetrzne
    klient.delete("/api/alert-testowy")
    assert "test-panelu" not in serwer.app.state.petla.zbieracz.zewnetrzne


def test_wyciszenie(klient):
    assert klient.post("/api/wyciszenie", json={"id": "dysk:disk2", "wyciszony": True}).json()["ok"]
    assert "dysk:disk2" in serwer.app.state.petla.zbieracz.wyciszone


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


def test_tryb_dodatku(tmp_path, monkeypatch):
    monkeypatch.setenv("LCD_KONFIGURACJA", str(tmp_path))
    monkeypatch.setenv("LCD_TOKEN", "token-testowy")
    monkeypatch.setenv("LCD_PANEL", "0")
    monkeypatch.setenv("LCD_TYLKO_TOKEN", "1")
    (tmp_path / "ustawienia.json").write_text('{"tryb": "symulacja"}')
    from app import serwer
    with TestClient(serwer.app) as k:
        assert k.get("/").status_code == 404
        assert k.get("/api/stan").status_code == 401
        assert k.get("/api/stan", headers={"Authorization": "Bearer zly"}).status_code == 401
        ok = {"Authorization": "Bearer token-testowy"}
        assert k.get("/api/stan", headers=ok).status_code == 200
        r = k.get("/api/podglad.png", headers=ok)
        assert r.status_code in (200, 204)  # 204: pierwsza klatka jeszcze się nie narysowała
        if r.status_code == 200:
            assert r.headers["content-type"] == "image/png"
        assert k.post("/api/alerty", json={"id": "x", "poziom": "uwaga", "tytul": "T"}, headers=ok).status_code == 200
