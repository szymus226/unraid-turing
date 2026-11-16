"""Ustawienia w pliku JSON w katalogu konfiguracji (na Unraid: /mnt/user/appdata/unraid-lcd/)."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .sterownik.baza import Orientacja


@dataclass
class Ustawienia:
    tryb: str = "usb"                # "usb" albo "symulacja"
    port: str = "auto"               # "auto" albo ścieżka do portu
    jasnosc: int = 60                # 0–100
    orientacja: str = Orientacja.PIONOWO.value
    odswiezanie_s: float = 2.0       # co ile sekund nowe dane
    przelaczanie_s: int = 10         # co ile sekund następny ekran (0 = bez przełączania)
    jezyk: str = "pl"                # język tekstów na ekranie: "pl" albo "en"

    def popraw(self) -> "Ustawienia":
        """Przycina wartości do bezpiecznych zakresów."""
        self.tryb = self.tryb if self.tryb in ("usb", "symulacja") else "usb"
        self.jasnosc = max(0, min(100, int(self.jasnosc)))
        self.odswiezanie_s = max(1.0, min(60.0, float(self.odswiezanie_s)))
        self.przelaczanie_s = max(0, min(600, int(self.przelaczanie_s)))
        self.jezyk = self.jezyk if self.jezyk in ("pl", "en") else "pl"
        # Układy są na razie tylko pionowe; poziome wymagają osobnych makiet.
        if self.orientacja not in (Orientacja.PIONOWO.value, Orientacja.PIONOWO_ODWROCONY.value):
            self.orientacja = Orientacja.PIONOWO.value
        return self


def katalog_konfiguracji() -> Path:
    return Path(os.environ.get("LCD_KONFIGURACJA", "/config"))


def wczytaj(katalog: Path | None = None) -> Ustawienia:
    plik = (katalog or katalog_konfiguracji()) / "ustawienia.json"
    try:
        surowe = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Ustawienia().popraw()
    znane = {f.name for f in fields(Ustawienia)}
    return Ustawienia(**{k: v for k, v in surowe.items() if k in znane}).popraw()


def zapisz(ustawienia: Ustawienia, katalog: Path | None = None) -> None:
    """Zapis atomowy: najpierw plik tymczasowy, potem zamiana nazwy."""
    katalog = katalog or katalog_konfiguracji()
    katalog.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=katalog, delete=False, encoding="utf-8", suffix=".tmp") as tmp:
        json.dump(asdict(ustawienia.popraw()), tmp, ensure_ascii=False, indent=2)
    os.replace(tmp.name, katalog / "ustawienia.json")
