"""Okresowy pomiar prędkości łącza (speedtest.net przez bibliotekę speedtest-cli) z historią z 72 h.

Domyślnie wyłączony: każdy pomiar wysyła ruch do zewnętrznego serwera i pobiera ok. 100–300 MB.
Historia zapisuje się w /config/speedtest.json, więc przetrwa restart kontenera.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)
OKNO_S = 72 * 3600


def zmierz() -> dict:
    import speedtest  # import tylko przy pomiarze: biblioteka przy imporcie nic nie łączy, ale jest spora

    st = speedtest.Speedtest(secure=True)
    st.get_best_server()
    st.download()
    st.upload(pre_allocate=False)
    w = st.results.dict()
    return {"czas": time.time(), "pobieranie": w["download"] / 1e6, "wysylanie": w["upload"] / 1e6, "ping": w["ping"]}


class Speedtest:
    def __init__(self, plik: Path | None = None, pomiar=zmierz):
        self.plik = plik
        self._pomiar = pomiar
        self.co_h: float = 0
        self.wyniki: list[dict] = []
        self.trwa = False
        self.blad: str | None = None
        self._stop = threading.Event()
        self._zmiana = threading.Event()
        self._wczytaj()

    def _wczytaj(self) -> None:
        if not self.plik:
            return
        try:
            surowe = json.loads(self.plik.read_text(encoding="utf-8"))
            self.wyniki = [w for w in surowe if isinstance(w, dict) and {"czas", "pobieranie", "wysylanie", "ping"} <= set(w)]
        except (OSError, ValueError):
            pass

    def _zapisz(self) -> None:
        if not self.plik:
            return
        try:
            tmp = self.plik.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.wyniki), encoding="utf-8")
            tmp.replace(self.plik)
        except OSError:
            pass

    def ustaw(self, co_h: float) -> None:
        if co_h != self.co_h:
            self.co_h = co_h
            self._zmiana.set()

    @property
    def nastepny(self) -> float | None:
        if not self.co_h:
            return None
        ostatni = self.wyniki[-1]["czas"] if self.wyniki else 0
        return max(time.time(), ostatni + self.co_h * 3600)

    def wykonaj(self) -> None:
        self.trwa = True
        try:
            wynik = self._pomiar()
            granica = time.time() - OKNO_S
            self.wyniki = [w for w in self.wyniki if w["czas"] >= granica] + [wynik]
            self.blad = None
            self._zapisz()
            log.info("speedtest: %.0f/%.0f Mb/s, ping %.0f ms", wynik["pobieranie"], wynik["wysylanie"], wynik["ping"])
        except Exception as blad:  # brak internetu, serwer niedostępny itp.
            self.blad = str(blad)[:200]
            log.warning("speedtest: %s", self.blad)
        finally:
            self.trwa = False

    def start(self) -> None:
        threading.Thread(target=self._dzialaj, name="speedtest", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self._zmiana.set()

    def _dzialaj(self) -> None:
        # Pierwszy pomiar najwcześniej 2 min po starcie, żeby nie obciążać łącza przy restarcie.
        self._stop.wait(120)
        while not self._stop.is_set():
            nastepny = self.nastepny
            if nastepny is not None and time.time() >= nastepny:
                self.wykonaj()
                continue
            self._zmiana.wait(60 if nastepny is None else min(60, max(1, nastepny - time.time())))
            self._zmiana.clear()
