"""Historia CPU, RAM i temperatury z ostatnich 24 h (próbka co minutę, zapis do /config co 10 min)."""
from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path

PROBEK = 24 * 60


class Historia24:
    def __init__(self, plik: Path | None = None):
        self.plik = plik
        self.probki: deque = deque(maxlen=PROBEK)     # (czas, cpu, ram, temp)
        self._suma = [0.0, 0.0, 0.0, 0]               # średnia z bieżącej minuty
        self._minuta: int | None = None
        self._zapis = 0.0
        self._wczytaj()

    def _wczytaj(self) -> None:
        if not self.plik:
            return
        try:
            surowe = json.loads(self.plik.read_text(encoding="utf-8"))
            granica = time.time() - 24 * 3600
            self.probki.extend(tuple(p) for p in surowe if isinstance(p, list) and len(p) == 4 and p[0] >= granica)
        except (OSError, ValueError, TypeError):
            pass

    def dodaj(self, cpu: float, ram: float, temp: float | None, teraz: float | None = None) -> None:
        teraz = time.time() if teraz is None else teraz
        minuta = int(teraz // 60)
        if self._minuta is not None and minuta != self._minuta and self._suma[3]:
            n = self._suma[3]
            self.probki.append((self._minuta * 60, round(self._suma[0] / n, 1), round(self._suma[1] / n, 1),
                                round(self._suma[2] / n, 1) if self._suma[2] else None))
            self._suma = [0.0, 0.0, 0.0, 0]
        self._minuta = minuta
        self._suma[0] += cpu; self._suma[1] += ram; self._suma[2] += temp or 0; self._suma[3] += 1
        if self.plik and teraz - self._zapis > 600:
            self._zapis = teraz
            self.zapisz()

    def zapisz(self) -> None:
        if not self.plik:
            return
        try:
            tmp = self.plik.with_suffix(".tmp")
            tmp.write_text(json.dumps(list(self.probki)), encoding="utf-8")
            tmp.replace(self.plik)
        except OSError:
            pass

    def godzinowo(self, teraz: float | None = None) -> dict[str, list[float]]:
        """24 średnie godzinowe (od najstarszej); godziny bez danych pomijane."""
        teraz = time.time() if teraz is None else teraz
        kosze: dict[int, list] = {}
        for t, cpu, ram, temp in self.probki:
            if t < teraz - 24 * 3600:
                continue
            kosze.setdefault(int(t // 3600), []).append((cpu, ram, temp))
        wynik = {"cpu": [], "ram": [], "temp": []}
        for godz in sorted(kosze):
            wart = kosze[godz]
            wynik["cpu"].append(sum(w[0] for w in wart) / len(wart))
            wynik["ram"].append(sum(w[1] for w in wart) / len(wart))
            temp = [w[2] for w in wart if w[2] is not None]
            if temp:
                wynik["temp"].append(sum(temp) / len(temp))
        return wynik
