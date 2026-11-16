# Unraid LCD (Turing Smart Screen 3,5")

**PL** · [EN](#english)

Aplikacja w kontenerze Docker, która pokazuje stan serwera Unraid na małym ekranie USB
Turing Smart Screen / TURZX 3,5" (320×480). Działa lokalnie, bez Windows, AIDA64
i oprogramowania producenta. Ma panel WWW na porcie 8766.

> Stan: wczesny prototyp (etap 2). Działa ekran „System” (CPU, rdzenie, temperatura,
> RAM, SWAP, czas pracy, obciążenie, sieć) i tryb symulacji. Dane Unraida (array, dyski,
> parity, Docker, VM), panel WWW i pozostałe ekrany są w przygotowaniu.
> Makiety: [docs/makiety](docs/makiety).

## Obsługiwany sprzęt

| Model | USB VID:PID | Nazwa w `/dev/serial/by-id` |
|---|---|---|
| Turing Smart Screen 3,5" (rev A), UsbMonitor 3,5" | `1a86:5722` | `usb-Turing_UsbMonitor_USB35INCHIPSV2-if00` |

Sprawdzenie na Unraid: `lsusb` powinien pokazać `1a86:5722 QinHeng Electronics UsbMonitor`.
Ekran jest wykrywany automatycznie, także po odłączeniu i ponownym podłączeniu.

## Instalacja na Unraid

1. Skopiuj repozytorium na serwer i zbuduj obraz: `docker compose build`
   (gotowy obraz w rejestrze pojawi się przy pierwszym wydaniu).
2. Uruchom: `docker compose up -d`. Konfiguracja trafia do `/mnt/user/appdata/unraid-lcd/`.
3. Otwórz panel: `http://<adres-serwera>:8766` (port zmienisz w `docker-compose.yml`).

### Bezpieczeństwo

- Kontener **nie** działa w trybie privileged i nie ma żadnych dodatkowych uprawnień (`cap_drop: ALL`).
- Widzi katalog `/dev` hosta tylko do odczytu, a reguła `c 166:* rw` pozwala mu otwierać
  wyłącznie porty szeregowe USB ACM (czyli ekran). Inne urządzenia są niedostępne.
- `/proc` hosta jest montowany tylko do odczytu (ruch sieciowy serwera).
- Panel nie ma logowania: **udostępniaj go tylko w sieci domowej**, nie wystawiaj do internetu.

## Licencja

GPLv3. Protokół ekranu opisano na podstawie projektu
[turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPLv3).
Czcionka Inter (SIL OFL 1.1) jest instalowana z pakietu `fonts-inter`.

---

## English

A Docker app that shows Unraid server status on the small Turing Smart Screen / TURZX 3.5"
USB display (320×480). Runs fully locally, no Windows, AIDA64 or vendor software. Web panel on port 8766.

> Status: early prototype (stage 2). The "System" screen (CPU, cores, temperature, RAM, swap,
> uptime, load, network) and simulation mode work. Unraid data (array, disks, parity, Docker, VMs),
> the web panel and the other screens are in progress. Mockups: [docs/makiety](docs/makiety).

**Supported hardware:** Turing Smart Screen 3.5" (rev A) / UsbMonitor 3.5", USB `1a86:5722`.
The display is detected automatically, also after unplugging and plugging it back in.

**Install on Unraid:** `docker compose build`, then `docker compose up -d`; config lives in
`/mnt/user/appdata/unraid-lcd/`; open `http://<server-address>:8766`.

**Security:** not privileged, all capabilities dropped; host `/dev` is read-only and the cgroup rule
only allows USB ACM serial ports; host `/proc` is read-only. The panel has no login: **keep it on your
home network only**, do not expose it to the internet.

**License:** GPLv3. The display protocol follows
[turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPLv3).
The Inter font (SIL OFL 1.1) comes from the `fonts-inter` package.
