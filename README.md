# Unraid LCD (Turing Smart Screen 3,5")

**PL** · [EN](#english)

Aplikacja w kontenerze Docker, która pokazuje stan serwera Unraid na małym ekranie USB
Turing Smart Screen / TURZX 3,5" (320×480). Działa lokalnie, bez Windows, AIDA64
i oprogramowania producenta. Ma panel WWW na porcie 8766.

> Stan: wersja 0.2 do testów. Makiety: [docs/makiety](docs/makiety).

## Co pokazuje

12 ekranów, każdy w wersji pionowej i poziomej, przełączanych automatycznie:

| Ekran | Dane |
|---|---|
| System | CPU, rdzenie, temperatura, RAM, SWAP, czas pracy, obciążenie, sieć LAN |
| Dyski | stan array, zajętość array i cache, temperatura i SMART wybranych dysków |
| Docker | działające kontenery, CPU i RAM wybranych (maks. 6), maszyny VM |
| Parity | postęp, prędkość, czas do końca, błędy (tylko gdy trwa kontrola) |
| Alerty | awarie dysków, SMART, przekroczone progi, zatrzymane kontenery, powiadomienia Unraida |
| Ruch dysków | odczyt i zapis, uśpione dyski |
| Ostatnie 24 h | CPU, RAM i temperatura CPU |
| Sieć | internet, opóźnienie do routera i internetu, ruch z ostatniej godziny, tunel Cloudflare |
| Speedtest | wyniki z 72 h (domyślnie wyłączony, łączy się z internetem) |
| Aktualizacje | Unraid, wtyczki, kontenery, ostatnia kontrola parity, czas pracy |
| Zegar | godzina, data, pogoda z Open-Meteo (domyślnie wyłączona, łączy się z internetem) |
| Kod QR | adres panelu w sieci domowej (domyślnie wyłączony) |

Alert krytyczny (np. dysk wyłączony z array) przypina ekran Alerty, ustawia jasność 100%
(także w godzinach nocnych) i dodaje czerwoną ramkę. Każdą z tych reakcji wyłączysz w panelu.
W sekcji „Alerty krytyczne” wybierzesz, które rodzaje alertów są krytyczne lub w ogóle widoczne,
i wyciszysz aktywny alert do rozwiązania problemu (zostaje wtedy na ekranie Alerty jako zwykłe ostrzeżenie).

## Obsługiwany sprzęt

| Model | USB VID:PID | Nazwa w `/dev/serial/by-id` |
|---|---|---|
| Turing Smart Screen 3,5" (rev A), UsbMonitor 3,5" | `1a86:5722` | `usb-Turing_UsbMonitor_USB35INCHIPSV2-if00` |

Sprawdzenie na Unraid: `lsusb` powinien pokazać `1a86:5722 QinHeng Electronics UsbMonitor`.
Ekran jest wykrywany automatycznie, także po odłączeniu i ponownym podłączeniu.

## Instalacja na Unraid

1. Skopiuj repozytorium na serwer i zbuduj obraz: `docker compose build`
   (gotowy obraz w rejestrze pojawi się przy pierwszym wydaniu).
2. Opcjonalnie odkomentuj w `docker-compose.yml` montowania dla ekranu Aktualizacje
   (tylko te ścieżki, które istnieją na serwerze).
3. Uruchom: `docker compose up -d`. Konfiguracja trafia do `/mnt/user/appdata/unraid-lcd/`.
4. Otwórz panel: `http://<adres-serwera>:8766`. Pasek na górze panelu pokazuje,
   czy aplikacja widzi ekran, dane Unraida, Dockera i czujniki temperatury.

### Co kontener widzi i dlaczego

Wszystkie montowania są tylko do odczytu.

| Ścieżka na serwerze | Po co |
|---|---|
| `/dev` → `/dev-host` | wykrywanie ekranu; reguła `c 166:* rw` pozwala otworzyć tylko porty USB ACM |
| `/proc` → `/host/proc` | CPU, RAM, sieć, ruch dysków |
| `/var/local/emhttp` | array, dyski, SMART, parity, nazwa serwera |
| `/var/lib/docker/containers` | nazwy i stan kontenerów (aplikacja zapamiętuje tylko nazwę, obraz i stan, nigdy zmiennych środowiskowych) |
| `/sys/fs/cgroup` | CPU i RAM kontenerów |
| `/etc/libvirt`, `/var/run/libvirt` | lista maszyn VM i to, które działają |
| `/tmp/notifications` | powiadomienia Unraida |

### Bezpieczeństwo

- Kontener **nie** działa w trybie privileged i nie ma żadnych dodatkowych uprawnień (`cap_drop: ALL`),
  system plików kontenera jest tylko do odczytu.
- **Nie** montujemy gniazda Dockera (`/var/run/docker.sock`): daje ono pełną kontrolę nad serwerem,
  nawet w trybie tylko do odczytu.
- Pomiar opóźnienia działa przez połączenie TCP, bez uprawnienia `NET_RAW`.
- Panel nie ma logowania: **udostępniaj go tylko w sieci domowej**, nie wystawiaj do internetu.
  API panelu nie zwraca haseł, tokenów ani zmiennych kontenerów.
- Speedtest i pogoda łączą się z internetem, więc są domyślnie wyłączone i oznaczone w panelu.

### Alerty z zewnątrz (np. pulpit homelabbera)

`POST /api/alerty` dodaje alert na ekranie, `DELETE /api/alerty/{id}` go usuwa.
Oba wymagają nagłówka `Authorization: Bearer <token>`. Token jest w pliku
`/mnt/user/appdata/unraid-lcd/token.txt` (tworzony przy pierwszym starcie, prawa 600)
albo w zmiennej `LCD_TOKEN`. Panel nigdy go nie pokazuje.

```json
{"id": "tunel", "poziom": "alarm", "tytul": "Tunel Cloudflare", "opis": "brak połączenia", "wazny_s": 300}
```

`poziom` to `alarm` (krytyczny) albo `uwaga`. Alert znika sam po `wazny_s` sekundach.

## Licencja

GPLv3. Protokół ekranu opisano na podstawie projektu
[turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPLv3).
Czcionka Inter (SIL OFL 1.1) jest instalowana z pakietu `fonts-inter`.

---

## English

A Docker app that shows Unraid server status on the small Turing Smart Screen / TURZX 3.5"
USB display (320×480). Runs fully locally, no Windows, AIDA64 or vendor software. Web panel on port 8766.

> Status: version 0.2 for testing. Mockups: [docs/makiety](docs/makiety).

**Screens** (12, each in portrait and landscape, rotating automatically): System, Disks, Docker,
Parity (only while a check runs), Alerts, Disk activity, Last 24 h, Network, Speed test (off by default,
connects to the internet), Updates, Clock with Open-Meteo weather (off by default, connects to the
internet), Panel QR code (off by default).

A critical alert (e.g. a disk disabled in the array) pins the Alerts screen, sets 100% brightness
(also during night hours) and adds a red frame. Each of these can be turned off in the panel. In the "Critical alerts" section
you choose which alert types are critical or shown at all, and mute an active alert until it is resolved (it then
stays on the Alerts screen as a normal warning).

**Supported hardware:** Turing Smart Screen 3.5" (rev A) / UsbMonitor 3.5", USB `1a86:5722`.
The display is detected automatically, also after unplugging and plugging it back in.

**Install on Unraid:** `docker compose build`; optionally uncomment the Updates screen mounts in
`docker-compose.yml` (only paths that exist on your server); `docker compose up -d`; config lives in
`/mnt/user/appdata/unraid-lcd/`; open `http://<server-address>:8766`. The bar at the top of the panel
shows whether the app sees the display, Unraid data, Docker and temperature sensors.

**What the container sees:** all mounts are read-only: `/dev` (display detection, the cgroup rule only
allows USB ACM ports), `/proc`, `/var/local/emhttp` (array, disks, SMART, parity),
`/var/lib/docker/containers` (container names and state; the app keeps only name, image and state, never
environment variables), `/sys/fs/cgroup` (container CPU and RAM), `/etc/libvirt` and `/var/run/libvirt`
(VMs), `/tmp/notifications` (Unraid notifications).

**Security:** not privileged, all capabilities dropped, read-only container filesystem. The Docker
socket is **not** mounted: it gives full control of the server, even read-only. Latency is measured
over TCP, without `NET_RAW`. The panel has no login: **keep it on your home network only**, do not expose
it to the internet. The panel API never returns passwords, tokens or container variables. Speed test and
weather connect to the internet, so they are off by default and labelled in the panel.

**External alerts** (e.g. the homelabber desktop): `POST /api/alerty` adds an alert, `DELETE /api/alerty/{id}`
removes it. Both need `Authorization: Bearer <token>`; the token is in
`/mnt/user/appdata/unraid-lcd/token.txt` (created on first start, mode 600) or in `LCD_TOKEN`. The panel
never shows it. Body: `{"id", "poziom": "alarm"|"uwaga", "tytul", "opis", "wazny_s"}`; the alert clears
itself after `wazny_s` seconds.

**License:** GPLv3. The display protocol follows
[turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPLv3).
The Inter font (SIL OFL 1.1) comes from the `fonts-inter` package.
