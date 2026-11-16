"""Pogoda z Open-Meteo (bez klucza API). Domyślnie wyłączona, bo łączy się z internetem.

Wysyłamy tylko współrzędne miejscowości wybranej w panelu, nic więcej.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)
ADRES_PROGNOZY = "https://api.open-meteo.com/v1/forecast"
ADRES_WYSZUKIWANIA = "https://geocoding-api.open-meteo.com/v1/search"


def _pobierz_json(adres: str, parametry: dict) -> dict:
    zapytanie = urllib.request.Request(f"{adres}?{urllib.parse.urlencode(parametry)}",
                                       headers={"User-Agent": "unraid-lcd"})
    with urllib.request.urlopen(zapytanie, timeout=10) as odp:
        return json.loads(odp.read().decode("utf-8"))


def szukaj_miejscowosci(nazwa: str, jezyk: str = "pl") -> list[dict]:
    dane = _pobierz_json(ADRES_WYSZUKIWANIA, {"name": nazwa, "count": 5, "language": jezyk, "format": "json"})
    return [{"nazwa": w.get("name"), "kraj": w.get("country"), "region": w.get("admin1"),
             "lat": w.get("latitude"), "lon": w.get("longitude")} for w in dane.get("results") or []]


class Pogoda:
    """Co 15 min pobiera bieżącą temperaturę, kod pogody (WMO) i porę dnia."""

    def __init__(self, co_s: float = 900):
        self.co_s = co_s
        self.wl = False
        self.lat: float | None = None
        self.lon: float | None = None
        self.biezaca: dict | None = None
        self.blad: str | None = None
        self._stop = threading.Event()
        self._zmiana = threading.Event()

    def ustaw(self, wl: bool, lat: float | None, lon: float | None) -> None:
        if (wl, lat, lon) != (self.wl, self.lat, self.lon):
            self.wl, self.lat, self.lon = wl, lat, lon
            self.biezaca = None
            self._zmiana.set()

    def pobierz(self) -> None:
        if not self.wl or self.lat is None or self.lon is None:
            self.biezaca = None
            return
        try:
            dane = _pobierz_json(ADRES_PROGNOZY, {"latitude": self.lat, "longitude": self.lon,
                                                  "current": "temperature_2m,weather_code,is_day"})
            c = dane["current"]
            self.biezaca = {"temp": float(c["temperature_2m"]), "kod": int(c["weather_code"]), "dzien": bool(c["is_day"])}
            self.blad = None
        except Exception as blad:
            self.blad = str(blad)[:200]
            log.warning("pogoda: %s", self.blad)

    def start(self) -> None:
        threading.Thread(target=self._dzialaj, name="pogoda", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self._zmiana.set()

    def _dzialaj(self) -> None:
        while not self._stop.is_set():
            self.pobierz()
            self._zmiana.wait(self.co_s)
            self._zmiana.clear()
