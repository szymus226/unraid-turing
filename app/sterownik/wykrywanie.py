"""Automatyczne wykrywanie ekranu po identyfikatorze USB.

Kontener widzi katalog /dev hosta (tylko do odczytu) pod ścieżką z ustawienia `katalog_dev`.
Najpierw sprawdzamy stałe nazwy w serial/by-id, potem identyfikatory VID:PID z /sys.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .rev_a import NUMER_SERYJNY_TURING, PID, VID


@dataclass
class ZnalezionyEkran:
    port: str          # ścieżka do otwarcia, np. /dev-host/ttyACM0
    nazwa: str         # nazwa z serial/by-id albo nazwa urządzenia
    model: str = "Turing Smart Screen 3,5\" (rev A)"
    vid_pid: str = f"{VID:04x}:{PID:04x}"


def _pasuje_nazwa(nazwa: str) -> bool:
    return NUMER_SERYJNY_TURING in nazwa or "UsbMonitor" in nazwa


def _vid_pid_tty(sys_class_tty: Path, tty: str) -> tuple[int, int] | None:
    """Odczytuje VID:PID urządzenia USB, do którego należy port ttyACM."""
    urzadzenie = sys_class_tty / tty / "device"
    try:
        sciezka = urzadzenie.resolve()
    except OSError:
        return None
    for katalog in (sciezka, *sciezka.parents):
        vid, pid = katalog / "idVendor", katalog / "idProduct"
        if vid.exists() and pid.exists():
            try:
                return int(vid.read_text().strip(), 16), int(pid.read_text().strip(), 16)
            except (OSError, ValueError):
                return None
    return None


def wykryj(katalog_dev: str = "/dev", katalog_sys: str = "/sys") -> list[ZnalezionyEkran]:
    dev = Path(katalog_dev)
    wyniki: list[ZnalezionyEkran] = []
    widziane: set[str] = set()

    by_id = dev / "serial" / "by-id"
    if by_id.is_dir():
        for wpis in sorted(by_id.iterdir()):
            if not _pasuje_nazwa(wpis.name):
                continue
            # Dowiązanie wskazuje ../../ttyACMx względem katalogu dev hosta.
            cel = dev / Path(os.readlink(wpis)).name if wpis.is_symlink() else wpis
            if cel.name in widziane:
                continue
            widziane.add(cel.name)
            wyniki.append(ZnalezionyEkran(port=str(cel), nazwa=wpis.name))

    sys_tty = Path(katalog_sys) / "class" / "tty"
    if sys_tty.is_dir():
        for wpis in sorted(sys_tty.glob("ttyACM*")):
            if wpis.name in widziane:
                continue
            if _vid_pid_tty(sys_tty, wpis.name) == (VID, PID):
                widziane.add(wpis.name)
                wyniki.append(ZnalezionyEkran(port=str(dev / wpis.name), nazwa=wpis.name))
    return wyniki
