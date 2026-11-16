"""Testy bez fizycznego ekranu: protokół, wykrywanie, odczyt /proc, różnice obrazu, pętla."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from app.odczyt.system import CzytnikSystemu, parsuj_net_dev, parsuj_stat, procent_cpu
from app.petla import Petla
from app.roznice import zmienione_obszary
from app.sterownik.baza import BladEkranu, Orientacja
from app.sterownik.rev_a import EkranRevA, do_rgb565, naglowek
from app.sterownik.wykrywanie import wykryj
from app.ustawienia import Ustawienia, wczytaj, zapisz


class PortTestowy:
    def __init__(self, awaria_po: int | None = None):
        self.zapisy: list[bytes] = []
        self.awaria_po = awaria_po

    def write(self, dane):
        if self.awaria_po is not None and len(self.zapisy) >= self.awaria_po:
            raise OSError("urządzenie odłączone")
        self.zapisy.append(bytes(dane))

    def close(self):
        pass


# --- protokół rev A ---
def test_naglowek_pakuje_wspolrzedne_jak_oryginal():
    # Wartości policzone wzorem z turing-smart-screen-python (SendCommand).
    x, y, ex, ey = 10, 20, 319, 479
    oczekiwane = bytes([x >> 2, ((x & 3) << 6) + (y >> 4), ((y & 15) << 4) + (ex >> 6),
                        ((ex & 63) << 2) + (ey >> 8), ey & 255, 197])
    assert naglowek(197, x, y, ex, ey) == oczekiwane


def test_rgb565_little_endian():
    obraz = Image.new("RGB", (3, 1))
    obraz.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
    assert do_rgb565(obraz).hex() == "00f8e0071f00"


def test_wysylka_obszaru_naglowek_i_piksele():
    port = PortTestowy()
    ekran = EkranRevA("/dev/ttyACM0", otworz_port=lambda p: port)
    ekran.polacz()
    ekran.wyslij_obszar(Image.new("RGB", (10, 4), (255, 255, 255)), 5, 7)
    assert port.zapisy[0] == naglowek(197, 5, 7, 14, 10)
    assert b"".join(port.zapisy[1:]) == b"\xff\xff" * 40


def test_jasnosc_odwrocona_skala():
    port = PortTestowy()
    ekran = EkranRevA("x", otworz_port=lambda p: port)
    ekran.polacz()
    ekran.ustaw_jasnosc(100)
    ekran.ustaw_jasnosc(0)
    assert port.zapisy[0] == naglowek(110, 0, 0, 0, 0)
    assert port.zapisy[1] == naglowek(110, 255, 0, 0, 0)


def test_blad_zapisu_rozlacza():
    port = PortTestowy(awaria_po=0)
    ekran = EkranRevA("x", otworz_port=lambda p: port)
    ekran.polacz()
    with pytest.raises(BladEkranu):
        ekran.ustaw_jasnosc(50)
    assert not ekran.polaczony


# --- wykrywanie ---
def test_wykrywanie_po_nazwie_by_id(tmp_path: Path):
    dev = tmp_path / "dev"
    (dev / "serial" / "by-id").mkdir(parents=True)
    (dev / "ttyACM3").touch()
    os.symlink("../../ttyACM3", dev / "serial" / "by-id" / "usb-Turing_UsbMonitor_USB35INCHIPSV2-if00")
    os.symlink("../../ttyUSB0", dev / "serial" / "by-id" / "usb-Inne_urzadzenie-if00")
    wyniki = wykryj(str(dev), str(tmp_path / "sys"))
    assert [w.port for w in wyniki] == [str(dev / "ttyACM3")]


def test_wykrywanie_po_vid_pid_z_sys(tmp_path: Path):
    usb = tmp_path / "sys" / "devices" / "usb1" / "1-2"
    (usb / "1-2:1.0").mkdir(parents=True)
    (usb / "idVendor").write_text("1a86\n")
    (usb / "idProduct").write_text("5722\n")
    tty = tmp_path / "sys" / "class" / "tty" / "ttyACM1"
    tty.mkdir(parents=True)
    os.symlink(usb / "1-2:1.0", tty / "device")
    wyniki = wykryj(str(tmp_path / "dev"), str(tmp_path / "sys"))
    assert [w.port for w in wyniki] == [str(tmp_path / "dev" / "ttyACM1")]


# --- odczyt systemu ---
STAT_1 = "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 50 0 50 400 0 0 0 0 0 0\ncpu1 50 0 50 400 0 0 0 0 0 0\n"
STAT_2 = "cpu  200 0 200 1000 0 0 0 0 0 0\ncpu0 150 0 50 500 0 0 0 0 0 0\ncpu1 50 0 150 500 0 0 0 0 0 0\n"


def test_procent_cpu():
    a, b = parsuj_stat(STAT_1), parsuj_stat(STAT_2)
    assert procent_cpu(a["cpu"], b["cpu"]) == pytest.approx(50.0)


def test_net_dev_pomija_wirtualne():
    tekst = ("Inter-|   Receive\n face |bytes\n"
             "    lo: 999 0 0 0 0 0 0 0 999 0 0 0 0 0 0 0\n"
             "  eth0: 1000 0 0 0 0 0 0 0 500 0 0 0 0 0 0 0\n"
             "docker0: 77 0 0 0 0 0 0 0 77 0 0 0 0 0 0 0\n"
             "vethab: 55 0 0 0 0 0 0 0 55 0 0 0 0 0 0 0\n")
    assert parsuj_net_dev(tekst) == (1000, 500)


def _sztuczny_proc(katalog: Path, stat: str) -> None:
    (katalog / "1" / "net").mkdir(parents=True, exist_ok=True)
    (katalog / "stat").write_text(stat)
    (katalog / "meminfo").write_text("MemTotal: 16000000 kB\nMemFree: 1000 kB\nMemAvailable: 6000000 kB\n"
                                     "SwapTotal: 0 kB\nSwapFree: 0 kB\n")
    (katalog / "uptime").write_text("1054800.5 100.0\n")
    (katalog / "loadavg").write_text("1.42 1.18 0.97 1/300 123\n")
    (katalog / "1" / "net" / "dev").write_text("a\nb\n  eth0: 1000 0 0 0 0 0 0 0 500 0 0 0 0 0 0 0\n")


def test_czytnik_systemu(tmp_path: Path):
    proc, sys_ = tmp_path / "proc", tmp_path / "sys"
    hw = sys_ / "class" / "hwmon" / "hwmon0"
    hw.mkdir(parents=True)
    (hw / "name").write_text("coretemp\n")
    (hw / "temp1_input").write_text("52000\n")
    (hw / "temp1_label").write_text("Package id 0\n")
    _sztuczny_proc(proc, STAT_1)
    czytnik = CzytnikSystemu(str(proc), str(sys_))
    czytnik.odczytaj()
    (proc / "stat").write_text(STAT_2)
    stan = czytnik.odczytaj()
    assert stan.cpu == pytest.approx(50.0)
    assert stan.rdzenie == pytest.approx([50.0, 50.0])
    assert stan.cpu_temp == 52.0
    assert stan.ram_procent == pytest.approx(62.5)
    assert stan.swap_procent is None
    assert stan.load == (1.42, 1.18, 0.97)


def test_temperatura_cpu_calego_procesora_nie_rdzenia(tmp_path: Path):
    from app.odczyt.system import temperatura_cpu
    hw = tmp_path / "class" / "hwmon" / "hwmon1"
    hw.mkdir(parents=True)
    (hw / "name").write_text("coretemp\n")
    for nr, etykieta, wartosc in ((1, "CPU Temp", 70000), (2, "Core 0", 67000), (10, "Core 8", 85000)):
        (hw / f"temp{nr}_input").write_text(f"{wartosc}\n")
        (hw / f"temp{nr}_label").write_text(etykieta + "\n")
    assert temperatura_cpu(tmp_path) == 70.0
    (hw / "temp1_label").write_text("cokolwiek\n")
    assert temperatura_cpu(tmp_path) == 70.0  # bez etykiety: pierwszy numerycznie, nie temp10


def test_problemy_na_gorze():
    from app.ekrany.rysuj import problemy_na_gorze
    lista = [("a", "ok"), ("b", "uwaga"), ("c", "ok"), ("d", "alarm")]
    assert [x[0] for x in problemy_na_gorze(lista, 1, {})] == ["d", "b", "a", "c"]
    assert [x[0] for x in problemy_na_gorze(lista, 1, {"sortuj_awarie": False})] == ["a", "b", "c", "d"]


# --- różnice obrazu ---
def test_brak_zmian_nic_nie_wysyla():
    a = Image.new("RGB", (320, 480))
    assert zmienione_obszary(a, a.copy()) == []


def test_mala_zmiana_maly_obszar():
    a = Image.new("RGB", (320, 480))
    b = a.copy()
    b.putpixel((100, 200), (255, 255, 255))
    assert zmienione_obszary(a, b) == [(100, 192, 101, 208)]


def test_pierwsza_klatka_w_calosci():
    assert zmienione_obszary(None, Image.new("RGB", (320, 480))) == [(0, 0, 320, 480)]


# --- ustawienia ---
def test_ustawienia_zapis_i_odczyt(tmp_path: Path):
    zapisz(Ustawienia(jasnosc=150, jezyk="de", orientacja="poziomo"), tmp_path)
    u = wczytaj(tmp_path)
    assert (u.jasnosc, u.jezyk, u.orientacja) == (100, "pl", "pionowo")


# --- pętla ---
def test_petla_symulacja_rysuje_i_wysyla(tmp_path: Path):
    _sztuczny_proc(tmp_path / "proc", STAT_1)
    petla = Petla(Ustawienia(tryb="symulacja"), CzytnikSystemu(str(tmp_path / "proc"), str(tmp_path / "sys")))
    petla.cykl()
    assert petla.stan.polaczony and petla.klatka.size == (320, 480)
    assert petla.ekran.wyslane_bajty == 320 * 480 * 2
    assert petla.ekran.klatka.tobytes() == petla.klatka.tobytes()


def test_petla_ponowne_laczenie_po_odlaczeniu(tmp_path: Path, monkeypatch):
    import app.petla as modul
    monkeypatch.setattr(modul, "PONOWNE_LACZENIE_S", 0.0)
    _sztuczny_proc(tmp_path / "proc", STAT_1)
    porty = [PortTestowy(awaria_po=3), PortTestowy()]
    from app.sterownik.wykrywanie import ZnalezionyEkran
    petla = Petla(Ustawienia(tryb="usb"), CzytnikSystemu(str(tmp_path / "proc"), str(tmp_path / "sys")),
                  fabryka_ekranu=lambda port: EkranRevA(port, otworz_port=lambda p: porty.pop(0)),
                  wykrywacz=lambda: [ZnalezionyEkran(port="/dev/ttyACM0", nazwa="test")])
    petla.cykl()                      # połączenie i awaria w trakcie pierwszej klatki
    assert not petla.stan.polaczony and "odłączone" in petla.stan.blad
    petla.cykl()                      # ponowne wykrycie i pełna klatka
    assert petla.stan.polaczony
    assert petla.ekran.orientacja == Orientacja.PIONOWO
