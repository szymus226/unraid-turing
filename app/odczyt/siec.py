"""Stan internetu i opóźnienia: połączenie TCP do routera i do internetu.

Zwykły ping wymaga uprawnienia NET_RAW, którego kontener nie ma (cap_drop ALL),
dlatego mierzymy czas nawiązania połączenia TCP. Odmowa połączenia (RST) też jest
odpowiedzią i daje poprawny czas.
"""
from __future__ import annotations

import socket
import struct
import threading
import time
from collections import deque
from pathlib import Path

CELE_INTERNETU = (("1.1.1.1", 443), ("9.9.9.9", 443), ("8.8.8.8", 443))
PORTY_ROUTERA = (53, 80, 443)


def brama_domyslna(katalog_proc: str = "/host/proc") -> str | None:
    """Adres bramy domyślnej hosta z /proc/1/net/route (adres zapisany szesnastkowo, little-endian)."""
    try:
        linie = (Path(katalog_proc) / "1" / "net" / "route").read_text().splitlines()[1:]
    except OSError:
        return None
    for linia in linie:
        pola = linia.split()
        if len(pola) > 2 and pola[1] == "00000000" and pola[2] != "00000000":
            return socket.inet_ntoa(struct.pack("<L", int(pola[2], 16)))
    return None


def czas_tcp(adres: str, port: int, limit_s: float = 2.0) -> float | None:
    """Czas w ms do odpowiedzi (połączenie albo odmowa); None przy braku odpowiedzi."""
    start = time.perf_counter()
    try:
        with socket.create_connection((adres, port), timeout=limit_s):
            pass
    except ConnectionRefusedError:
        pass
    except OSError:
        return None
    return (time.perf_counter() - start) * 1000


class MonitorSieci:
    """Co 30 s w tle mierzy opóźnienie do routera i internetu."""

    def __init__(self, katalog_proc: str = "/host/proc", co_s: float = 30.0):
        self.katalog_proc = katalog_proc
        self.co_s = co_s
        self.internet: bool | None = None
        self.ping_router: float | None = None
        self.ping_internet: float | None = None
        self._stop = threading.Event()

    def pomiar(self) -> None:
        brama = brama_domyslna(self.katalog_proc)
        router = None
        if brama:
            for port in PORTY_ROUTERA:
                router = czas_tcp(brama, port, 1.0)
                if router is not None:
                    break
        self.ping_router = router
        internet = None
        for adres, port in CELE_INTERNETU:
            internet = czas_tcp(adres, port)
            if internet is not None:
                break
        self.ping_internet = internet
        # Bez odpowiedzi także od routera kontener nie ma wyjścia do sieci (np. sieć dodatków pulpitu bez
        # internetu): stan jest nieznany, a nie „brak połączenia”. Wtedy internet podaje pulpit.
        self.internet = True if internet is not None else (False if router is not None else None)

    def start(self) -> None:
        threading.Thread(target=self._dzialaj, name="siec", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _dzialaj(self) -> None:
        while not self._stop.is_set():
            try:
                self.pomiar()
            except Exception:
                pass
            self._stop.wait(self.co_s)


class HistoriaRuchu:
    """Średni ruch LAN z każdej minuty ostatniej godziny (do wykresu na ekranie Sieć)."""

    MIN_MINUT = 10

    def __init__(self):
        self.minuty: deque = deque(maxlen=60)
        self._biezaca: list | None = None   # [minuta, suma_rx, suma_tx, n]
        # Ostatnie odczyty: wykres po starcie aplikacji, zanim zbierze się kilka minut (zamiast 2–3 punktów).
        self.probki: deque = deque(maxlen=120)

    def dodaj(self, rx_bps: float, tx_bps: float, teraz: float | None = None) -> None:
        minuta = int((time.time() if teraz is None else teraz) // 60)
        if self._biezaca and self._biezaca[0] != minuta:
            m, r, t, n = self._biezaca
            self.minuty.append((r / n, t / n))
            self._biezaca = None
        if not self._biezaca:
            self._biezaca = [minuta, 0.0, 0.0, 0]
        self._biezaca[1] += rx_bps; self._biezaca[2] += tx_bps; self._biezaca[3] += 1
        self.probki.append((rx_bps, tx_bps))

    def serie(self) -> tuple[list[float], list[float]]:
        punkty = list(self.minuty)
        if self._biezaca and self._biezaca[3]:
            punkty.append((self._biezaca[1] / self._biezaca[3], self._biezaca[2] / self._biezaca[3]))
        if len(punkty) < self.MIN_MINUT and len(self.probki) > len(punkty):
            punkty = list(self.probki)
        if len(punkty) < 2:
            punkty = (punkty or [(0.0, 0.0)]) * 2
        return [p[0] / 1e6 for p in punkty], [p[1] / 1e6 for p in punkty]
