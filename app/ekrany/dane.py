"""Zamiana odczytów na słownik danych, który przyjmują funkcje rysujące."""
from __future__ import annotations

import time
from collections import deque

from ..odczyt.system import StanSystemu


def _gb(bajty: int, jezyk: str) -> str:
    tekst = f"{bajty / 1024**3:.1f}"
    return tekst.replace(".", ",") if jezyk == "pl" else tekst


def predkosc(bps: float, jezyk: str) -> str:
    for granica, jednostka in ((1024**3, "GB/s"), (1024**2, "MB/s"), (1024, "kB/s")):
        if bps >= granica:
            tekst = f"{bps / granica:.1f}"
            return (tekst.replace(".", ",") if jezyk == "pl" else tekst) + " " + jednostka
    return f"{bps:.0f} B/s"


def czas_pracy(sekundy: float) -> str:
    dni, reszta = divmod(int(sekundy), 86400)
    godz, reszta = divmod(reszta, 3600)
    if dni:
        return f"{dni}d {godz}h"
    return f"{godz}h {reszta // 60}m"


class HistoriaCpu:
    """Ostatnie odczyty CPU do wykresu liniowego (domyślnie 20 punktów)."""

    def __init__(self, dlugosc: int = 20):
        self.wartosci: deque[float] = deque(maxlen=dlugosc)

    def dodaj(self, wartosc: float) -> list[float]:
        self.wartosci.append(wartosc)
        lista = list(self.wartosci)
        return lista if len(lista) >= 2 else [lista[0] if lista else 0.0] * 2


def dane_systemu(stan: StanSystemu, historia: list[float], jezyk: str, teraz: float | None = None) -> dict:
    return {
        "godzina": time.strftime("%H:%M", time.localtime(teraz)),
        "cpu": stan.cpu,
        "rdzenie": stan.rdzenie or [stan.cpu],
        "cpu_temp": stan.cpu_temp,
        "ram": stan.ram_procent,
        "ram_txt": f"{_gb(stan.ram_uzyte, jezyk)} / {stan.ram_calkowite / 1024**3:.0f} GB",
        "swap": stan.swap_procent,
        "uptime": czas_pracy(stan.uptime_s),
        "load": stan.load,
        "rx": predkosc(stan.rx_bps, jezyk),
        "tx": predkosc(stan.tx_bps, jezyk),
        "historia_cpu": historia,
    }
