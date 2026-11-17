"""Odczyt danych z plików Unraida, Dockera i libvirt na sztucznym drzewie katalogów oraz zachowanie pętli."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app.ekrany import rejestr
from app.odczyt.docker import CzytnikDockera, aktualizacje_kontenerow, czytaj_vm
from app.odczyt.dyski_io import parsuj_diskstats
from app.odczyt.historia import Historia24
from app.odczyt.powiadomienia import aktualizacje_wtyczek, czytaj_powiadomienia
from app.odczyt.siec import brama_domyslna
from app.odczyt.system import CzytnikSystemu
from app.odczyt.unraid import CzytnikUnraid, ocena_smart, parsuj_ini
from app.petla import Petla, w_oknie_nocnym
from app.ustawienia import Ustawienia, z_slownika
from app.zbieracz import Zbieracz, Zrodla

VAR_INI = '''NAME="Serwer"
version="7.2.1"
mdState="STARTED"
mdResync="0"
mdResyncPos="0"
sbSynced="1730419200"
sbSynced2="1730440800"
sbSyncErrs="0"
sbSyncExit="0"
'''

DISKS_INI = '''["parity"]
name="parity"
device="sdb"
status="DISK_OK"
type="Parity"
temp="34"
rotational="1"
color="green-on"
numErrors="0"
["disk1"]
name="disk1"
device="sdc"
status="DISK_OK"
type="Data"
temp="36"
rotational="1"
color="green-on"
fsSize="4000000000"
fsUsed="2000000000"
fsFree="2000000000"
numErrors="0"
["disk2"]
name="disk2"
device="sdd"
status="DISK_DSBL"
type="Data"
temp="*"
rotational="1"
color="red-on"
fsSize="4000000000"
fsUsed="1000000000"
numErrors="0"
["disk3"]
name="disk3"
device=""
status="DISK_NP"
type="Data"
["cache"]
name="cache"
device="nvme0n1"
status="DISK_OK"
type="Cache"
temp="41"
rotational="0"
color="green-on"
fsSize="1000000000"
fsUsed="410000000"
["flash"]
name="flash"
device="sda"
type="Flash"
'''


def _kontener(katalog: Path, id_: str, nazwa: str, dziala: bool, kod: int = 0, obraz: str = "obraz:latest"):
    k = katalog / id_
    k.mkdir(parents=True)
    (k / "config.v2.json").write_text(json.dumps({
        "Name": "/" + nazwa, "Config": {"Image": obraz, "Env": ["HASLO=tajne"]},
        "State": {"Running": dziala, "Restarting": False, "ExitCode": kod}}))


@pytest.fixture
def host(tmp_path: Path) -> Zrodla:
    emhttp = tmp_path / "emhttp"
    (emhttp / "smart").mkdir(parents=True)
    (emhttp / "var.ini").write_text(VAR_INI)
    (emhttp / "disks.ini").write_text(DISKS_INI)
    (emhttp / "smart" / "disk1").write_text(
        "SMART overall-health self-assessment test result: PASSED\n"
        "  5 Reallocated_Sector_Ct   0x0033   100   100   010    Pre-fail  Always       -       8\n")
    kont = tmp_path / "containers"
    _kontener(kont, "a" * 64, "plex", True)
    _kontener(kont, "b" * 64, "paperless", False, kod=1)
    _kontener(kont, "c" * 64, "stary", False, kod=0)
    _kontener(kont, "d" * 64, "tunel", True, obraz="cloudflare/cloudflared:latest")
    cg = tmp_path / "cgroup" / "docker" / ("a" * 64)
    cg.mkdir(parents=True)
    (cg / "cpu.stat").write_text("usage_usec 1000000\n")
    (cg / "memory.current").write_text(str(1300 * 1024**2))
    (cg / "memory.stat").write_text(f"inactive_file {100 * 1024**2}\n")
    proc = tmp_path / "proc"
    (proc / "1" / "net").mkdir(parents=True)
    (proc / "stat").write_text("cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
    (proc / "meminfo").write_text("MemTotal: 16000000 kB\nMemAvailable: 6000000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n")
    (proc / "uptime").write_text("1054800.5 100.0\n")
    (proc / "loadavg").write_text("1.42 1.18 0.97 1/300 123\n")
    (proc / "1" / "net" / "dev").write_text("a\nb\n  eth0: 1000 0 0 0 0 0 0 0 500 0 0 0 0 0 0 0\n")
    (proc / "1" / "net" / "route").write_text(
        "Iface\tDestination\tGateway\tFlags\n eth0\t00000000\t0101A8C0\t0003\n")
    (proc / "diskstats").write_text("   8      16 sdb 10 0 2000 0 20 0 4000 0 0 0 0\n   8      32 sdc 1 0 0 0 0 0 0 0 0 0 0\n")
    libvirt = tmp_path / "libvirt"
    (libvirt / "etc").mkdir(parents=True)
    (libvirt / "run").mkdir(parents=True)
    (libvirt / "etc" / "ha.xml").write_text("<domain><name>Home Assistant</name></domain>")
    (libvirt / "etc" / "win.xml").write_text("<domain><name>Windows 11</name></domain>")
    (libvirt / "run" / "Home Assistant.pid").write_text("123")
    powiadomienia = tmp_path / "notifications"
    powiadomienia.mkdir()
    (powiadomienia / "1.notify").write_text("timestamp=1700000000\nevent=Array\nsubject=Disk 2 in error state\nimportance=alert\n")
    (powiadomienia / "2.notify").write_text("timestamp=1700000001\nevent=Docker\nsubject=update\nimportance=normal\n")
    nowe, zainst = tmp_path / "plugins-nowe", tmp_path / "plugins"
    nowe.mkdir(); zainst.mkdir()
    (nowe / "a.plg").write_text('<!ENTITY version "2024.02.01">')
    (zainst / "a.plg").write_text('<!ENTITY version "2024.01.01">')
    (nowe / "b.plg").write_text('<!ENTITY version "1.0">')
    (zainst / "b.plg").write_text('<!ENTITY version "1.0">')
    (nowe / "unRAIDServer.plg").write_text('<PLUGIN name="unRAIDServer" version="7.2.2">')
    status = tmp_path / "update-status.json"
    status.write_text(json.dumps({"plex:latest": {"status": "false"}, "a:latest": {"status": "true"}}))
    return Zrodla(proc=str(proc), sys=str(tmp_path / "sys"), emhttp=str(emhttp), kontenery=str(kont),
                  cgroup=str(tmp_path / "cgroup"), status_aktualizacji=str(status),
                  libvirt_etc=str(libvirt / "etc"), libvirt_run=str(libvirt / "run"),
                  powiadomienia=str(powiadomienia), wtyczki_nowe=str(nowe), wtyczki=str(zainst))


# --- pojedyncze czytniki ---
def test_ini_z_sekcjami_i_bez():
    assert parsuj_ini('a="1"\nb=2\n') == {"a": "1", "b": "2"}
    assert parsuj_ini('["x"]\nk="v"\n')["x"] == {"k": "v"}


def test_dyski_z_emhttp(host):
    stan = CzytnikUnraid(host.emhttp).odczytaj()
    assert stan.dostepny and stan.array == "STARTED" and stan.wersja == "7.2.1"
    nazwy = {d.nazwa: d for d in stan.dyski}
    assert set(nazwy) == {"parity", "disk1", "disk2", "cache"}          # bez pustego slotu i flasha
    assert nazwy["disk2"].stan == "alarm" and not nazwy["disk2"].aktywny
    assert nazwy["disk1"].smart == "uwaga" and nazwy["disk1"].stan == "uwaga"
    assert nazwy["cache"].ssd and nazwy["cache"].rola == "pool"
    assert stan.array_rozmiar_kb == 8000000000 and stan.array_zajete_kb == 3000000000
    assert stan.cache_zajete_kb == 410000000


def test_smart_failed():
    assert ocena_smart("SMART overall-health self-assessment test result: FAILED!") == "alarm"
    assert ocena_smart("") == "brak"


def test_kontenery_bez_gniazda_dockera(host):
    czytnik = CzytnikDockera(host.kontenery, host.cgroup)
    kont = {k.nazwa: k for k in czytnik.odczytaj()}
    assert kont["plex"].dziala and kont["plex"].stan == "ok"
    assert kont["plex"].ram_b == 1200 * 1024**2
    assert kont["paperless"].stan == "uwaga"          # zatrzymany z błędem
    assert kont["stary"].stan == "szary"              # zatrzymany normalnie
    # w pamięci nie zostają zmienne środowiskowe
    assert "tajne" not in json.dumps([v[1] for v in czytnik._cache.values()])
    (Path(host.cgroup) / "docker" / ("a" * 64) / "cpu.stat").write_text("usage_usec 3000000\n")
    time.sleep(0.05)
    assert czytnik.odczytaj()[1].cpu > 0


def test_vm_i_aktualizacje(host):
    vm = czytaj_vm(host.libvirt_etc, host.libvirt_run)
    assert [(v.nazwa, v.dziala) for v in vm] == [("Home Assistant", True), ("Windows 11", False)]
    assert aktualizacje_kontenerow(host.status_aktualizacji) == 1
    assert aktualizacje_kontenerow("/nie/ma") is None
    assert aktualizacje_wtyczek(host.wtyczki_nowe, host.wtyczki) == (1, "7.2.2")
    assert aktualizacje_wtyczek("/nie/ma", host.wtyczki) == (None, None)


def test_powiadomienia(host):
    p = czytaj_powiadomienia(host.powiadomienia)
    assert [(x.poziom, x.tytul) for x in p] == [("alarm", "Array"), ("info", "Docker")]


def test_diskstats_i_brama(host):
    assert parsuj_diskstats(Path(host.proc, "diskstats").read_text())["sdb"] == (2000, 4000)
    assert brama_domyslna(host.proc) == "192.168.1.1"


def test_historia_godzinowa():
    h = Historia24()
    start = 1_700_000_000
    for minuta in range(0, 180):
        h.dodaj(10 + minuta % 2, 50, 40, teraz=start + minuta * 60)
    wynik = h.godzinowo(teraz=start + 180 * 60)
    assert len(wynik["cpu"]) in (3, 4) and all(10 <= v <= 11 for v in wynik["cpu"])


# --- zbieracz: alerty i dane ekranów ---
def test_alerty_z_serwera(host):
    z = Zbieracz(host, w_tle=False)
    u = Ustawienia(kontenery=["plex", "paperless"]).popraw()
    o = z.odczytaj(u)
    ids = {a.id: a for a in o.alerty}
    assert ids["dysk:disk2"].poziom == "alarm"
    assert ids["smart:disk1"].poziom == "uwaga"
    assert ids["kontener:paperless"].poziom == "uwaga"
    assert ids["unraid:1.notify"].poziom == "alarm"
    assert o.alerty[0].poziom == "alarm"                      # krytyczne pierwsze


def test_rodzaje_alertow_i_wyciszanie(host, tmp_path):
    z = Zbieracz(host, katalog_konfiguracji=tmp_path, w_tle=False)
    u = Ustawienia().popraw()
    ids = {a.id: a for a in z.odczytaj(u).alerty}
    assert ids["dysk:disk2"].rodzaj == "dysk" and ids["unraid:1.notify"].rodzaj == "unraid"
    # wyłączony rodzaj znika, niekrytyczny zostaje jako zwykłe ostrzeżenie
    u = Ustawienia(rodzaje_alertow={"dysk": [False, True], "unraid": [True, False]}).popraw()
    ids = {a.id: a for a in z.odczytaj(u).alerty}
    assert "dysk:disk2" not in ids
    assert ids["unraid:1.notify"].poziom == "uwaga" and not ids["unraid:1.notify"].przelacz
    # wyciszony do rozwiązania: zwykłe ostrzeżenie, zapisany na dysku, znika razem z problemem
    u = Ustawienia().popraw()
    z.wycisz("dysk:disk2", True)
    a = {a.id: a for a in z.odczytaj(u).alerty}["dysk:disk2"]
    assert a.poziom == "uwaga" and a.wyciszony
    assert "dysk:disk2" in Zbieracz(host, katalog_konfiguracji=tmp_path, w_tle=False).wyciszone
    z.wycisz("nieistniejacy", True)
    z.odczytaj(u)
    assert z.wyciszone == {"dysk:disk2"}


def test_rodzaje_alertow_w_ustawieniach():
    u = Ustawienia(rodzaje_alertow={"dysk": [False, True], "obcy": [1, 1], "smart": "zle"}).popraw()
    assert u.rodzaje_alertow["dysk"] == [False, False] and u.rodzaje_alertow["smart"] == [True, True]
    assert "obcy" not in u.rodzaje_alertow


def test_prog_musi_trwac(host):
    z = Zbieracz(host, w_tle=False)
    u = Ustawienia().popraw()
    o = z.odczytaj(u)
    o.system.cpu_temp = 90
    assert not any(a.id == "cpu_temp" for a in z.alerty(o, u, {}, teraz=1000))
    alerty = z.alerty(o, u, {}, teraz=1031)
    assert any(a.id == "cpu_temp" and a.poziom == "alarm" for a in alerty)


def test_alert_zewnetrzny_wygasa(host):
    z = Zbieracz(host, w_tle=False)
    z.dodaj_zewnetrzny("dns", "alarm", "DNS nie działa", "AdGuard", 60)
    o = z.odczytaj(Ustawienia().popraw())
    assert any(a.id == "zew:dns" for a in o.alerty)
    z.zewnetrzne["dns"].wygasa = 0
    assert not any(a.id == "zew:dns" for a in z.odczytaj(Ustawienia().popraw()).alerty)


def test_aktualizacje_z_pulpitu_zastepuja_licznik_unraida(host):
    from app.ekrany.dodatkowe import TEKSTY, wiersze_aktualizacji
    z = Zbieracz(host, w_tle=False)
    u = Ustawienia().popraw()
    assert z.dane(z.odczytaj(u), u)["aktualizacje"]["pulpit"] is None
    z.ustaw_aktualizacje_pulpitu({"available": 3, "auto": 1, "notify": 2, "outside": 1, "servers": 2, "failed": 0, "checkedAt": None})
    a = z.dane(z.odczytaj(u), u)["aktualizacje"]
    wiersz = wiersze_aktualizacji(TEKSTY["pl"], a)[2]
    assert wiersz == ("Kontenery · inne serwery: 2", "4 do aktualizacji", "uwaga")
    z.ustaw_aktualizacje_pulpitu(dict(a["pulpit"], failed=1))
    assert wiersze_aktualizacji(TEKSTY["en"], z.dane(z.odczytaj(u), u)["aktualizacje"])[2][1:] == ("4 · failed: 1", "alarm")
    # Po 15 min bez nowych liczb ekran wraca do licznika Unraida.
    assert z.aktualizacje_z_pulpitu(teraz=time.time() + 16 * 60) is None
    z.ustaw_aktualizacje_pulpitu(None)
    assert z.aktualizacje_z_pulpitu() is None


def test_ekrany_z_pulpitu_tylko_ze_swiezymi_kartami(host):
    from app.ekrany import rejestr
    z = Zbieracz(host, w_tle=False)
    u = Ustawienia().popraw()
    opis = rejestr.EKRANY["pulpit_zasilanie"]
    assert not rejestr.spelnia_warunek(opis, z.dane(z.odczytaj(u), u))
    z.ustaw_ekrany_pulpitu({"pulpit_zasilanie": [{"etykieta": "Bateria", "wartosc": "100%"}, None, {"etykieta": "X", "wartosc": "Y", "stan": "alarm"}]})
    dane = z.dane(z.odczytaj(u), u)
    assert rejestr.spelnia_warunek(opis, dane)
    for poziomo in (False, True):
        assert rejestr.narysuj("pulpit_zasilanie", dane, "pl", poziomo, ukryte=[2]).size == ((480, 320) if poziomo else (320, 480))
    assert z.ekrany_z_pulpitu(teraz=time.time() + 121) == {}
    # Nowe ekrany są w ustawieniach na końcu listy, domyślnie wyłączone.
    assert [e["klucz"] for e in u.ekrany][-5:] == ["pulpit_zasilanie", "pulpit_pobieranie", "pulpit_odtwarzanie", "pulpit_kopie", "pulpit_kamery"]
    assert not any(e["wl"] for e in u.ekrany[-5:])


@pytest.mark.parametrize("poziomo", [False, True])
@pytest.mark.parametrize("jezyk", ["pl", "en"])
def test_wszystkie_ekrany_z_prawdziwych_danych(host, jezyk, poziomo):
    z = Zbieracz(host, w_tle=False)
    u = Ustawienia(jezyk=jezyk, speedtest_co_h=3).popraw()
    dane = z.dane(z.odczytaj(u), u)
    assert dane["array_txt"] == "2,8 / 7 TB" if jezyk == "pl" else True
    assert dane["siec"]["tunel"] is True
    assert dane["aktualizacje"]["wtyczki"] == 1 and dane["aktualizacje"]["unraid_nowa"] == "7.2.2"
    for klucz in rejestr.EKRANY:
        obraz = rejestr.narysuj(klucz, dane, jezyk, poziomo)
        assert obraz.size == ((480, 320) if poziomo else (320, 480))


def test_ekrany_bez_zadnych_zrodel(tmp_path):
    """Kontener bez montowań: każdy ekran rysuje się z „—” zamiast się wysypać."""
    z = Zbieracz(Zrodla(proc="/proc", sys=str(tmp_path), emhttp=str(tmp_path / "x"),
                        kontenery=str(tmp_path / "x"), cgroup=str(tmp_path / "x")), w_tle=False)
    u = Ustawienia(speedtest_co_h=1).popraw()
    dane = z.dane(z.odczytaj(u), u)
    for klucz in rejestr.EKRANY:
        for poziomo in (False, True):
            rejestr.narysuj(klucz, dane, "pl", poziomo, ukryte=[0, 1])


# --- pętla ---
def _petla(host, **ust):
    u = Ustawienia(tryb="symulacja", **ust).popraw()
    return Petla(u, zbieracz=Zbieracz(host, w_tle=False))


def test_krytyczny_przypina_alerty_i_daje_100_procent(host):
    p = _petla(host, jasnosc=40)
    p.cykl()
    assert p.stan.przypiety and p.stan.ekran == "alerty"
    assert p.ekran.jasnosc == 100


def test_bez_przypinania_jasnosc_z_ustawien(host):
    p = _petla(host, jasnosc=40, krytyczne_przypnij=False, krytyczne_jasnosc=False)
    p.cykl()
    assert not p.stan.przypiety and p.ekran.jasnosc == 40


def test_rotacja_ekranow(host, monkeypatch):
    p = _petla(host, krytyczne_przypnij=False)
    for a in ("dysk_awaria", "kontener_stop"):
        p.ustawienia.progi[a][2] = False
    p.zbieracz.alerty = lambda *a, **k: []
    p.cykl()
    pierwszy = p.stan.ekran
    p._start_ekranu -= 100
    p.cykl()
    assert p.stan.ekran != pierwszy
    assert "parity" not in p.stan.kolejka          # kontrola parity nie trwa
    assert "speedtest" not in p.stan.kolejka       # speedtest wyłączony


def test_noc_wylacza_ekran_ale_krytyczny_go_budzi(host, monkeypatch):
    p = _petla(host, noc_wl=True, noc_od="00:00", noc_do="23:59")
    monkeypatch.setattr("app.petla.w_oknie_nocnym", lambda *a: True)
    p.cykl()
    assert p.ekran.wlaczony and not p.stan.noc         # alert krytyczny budzi ekran
    p.zbieracz.alerty = lambda *a, **k: []
    p.cykl()
    assert not p.ekran.wlaczony and p.stan.noc


def test_okno_nocne_przez_polnoc():
    noc = lambda g, m: time.struct_time((2026, 1, 1, g, m, 0, 0, 1, -1))
    assert w_oknie_nocnym("23:00", "07:00", noc(23, 30))
    assert w_oknie_nocnym("23:00", "07:00", noc(6, 59))
    assert not w_oknie_nocnym("23:00", "07:00", noc(7, 0))
    assert w_oknie_nocnym("01:00", "05:00", noc(3, 0))


def test_poziomo_daje_obraz_480x320(host):
    p = _petla(host, orientacja="poziomo")
    p.cykl()
    assert p.klatka.size == (480, 320) and p.ekran.klatka.size == (480, 320)


def test_ustawienia_ekranow_naprawiane():
    u = z_slownika({"ekrany": [{"klucz": "zegar", "wl": True, "czas_s": 1, "ukryte": [1, "x", 99]},
                               {"klucz": "nieznany"}, {"klucz": "zegar"}], "kontenery": [str(i) for i in range(9)],
                    "progi": {"ram": [95, 90, True]}, "speedtest_co_h": 5})
    assert u.ekrany[0] == {"klucz": "zegar", "wl": True, "czas_s": 3, "ukryte": [1]}
    assert len(u.ekrany) == 17 and len(u.kontenery) == 6
    assert u.progi["ram"] == [90, 95, True] and u.speedtest_co_h == 0


def test_kolejnosc_dyskow_z_ustawien(host):
    z = Zbieracz(host, w_tle=False)
    u = Ustawienia(dyski=["cache", "disk1"], sortuj_awarie=False).popraw()
    d = z.dane(z.odczytaj(u), u, adres_panelu="", teraz=0)
    nazwy = {x.etykieta: x.nazwa for x in z.ostatnie.unraid.dyski} if z.ostatnie else {}
    assert [nazwy.get(e[0], e[0]) for e in d["dyski"]] == ["cache", "disk1"]
