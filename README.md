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

### Liczby aktualizacji z pulpitu homelabbera

`POST /api/aktualizacje` (ten sam token) przyjmuje
`{"available", "auto", "notify", "outside", "servers", "failed", "checkedAt"}`. Ekran „Aktualizacje”
pokazuje wtedy w karcie „Kontenery” liczbę z pulpitu (jego kontenery i te spoza niego), nieudane
aktualizacje i liczbę innych serwerów. Pulpit wysyła liczby co minutę; gdy przez 15 min nic nie
przyjdzie albo pulpit wyśle `DELETE /api/aktualizacje`, karta wraca do licznika Unraida.

### Ekrany z pulpitu homelabbera

`POST /api/pulpit/ekrany` (ten sam token) przyjmuje `{"ekrany": {"pulpit_zasilanie": [karta, …], …}}`.
Karta to `{"etykieta", "wartosc", "stan": "ok"|"uwaga"|"alarm"|"szary", "pasek": 0–100, "prawa", "pod"}`,
najwyżej 6 na ekran, `null` = puste miejsce. Ekrany: `pulpit_zasilanie`, `pulpit_pobieranie`,
`pulpit_odtwarzanie`, `pulpit_kopie`, `pulpit_kamery`, `pulpit_polaczenia`. Są na liście ekranów (domyślnie wyłączone) i pokazują
się tylko wtedy, gdy pulpit przysłał karty w ostatnich 2 min. Aplikacja tylko je rysuje: nie łączy się
z żadną usługą. `DELETE /api/pulpit/ekrany` czyści karty.

### Połączenia w nagłówku

`POST /api/pulpit/polaczenia` (ten sam token) przyjmuje `{"ikony": [{"rodzaj", "stan", "liczba"}]}`, najwyżej 6:
`rodzaj` to `internet`, `vpn`, `tunel`, `bt` albo `cast`, `stan` to `ok`, `uwaga`, `alarm`, `szary` albo `gra`,
`liczba` (opcjonalnie) stoi przy ikonie. Ikony rysują się przed godziną na każdym ekranie, a kropki ekranów
zmieniają się wtedy w cienki pasek pod nagłówkiem. Gdy brakuje miejsca, odpadają ostatnie ikony. Po 2 min bez
nowych ikon albo po `DELETE /api/pulpit/polaczenia` nagłówek wraca do zwykłego wyglądu. Ustawienie
„Połączenia w nagłówku” (`naglowek_polaczenia`, domyślnie włączone) wyłącza ikony.

### Tryb dodatku (pulpit homelabbera)

Dodatek „Smart ekran” w homelabberze instaluje tę aplikację i ma własne okno z ustawieniami.
Uruchamia kontener ze zmiennymi `LCD_PANEL=0` (własny panel wyłączony) i `LCD_TYLKO_TOKEN=1`
(każde wywołanie `/api/*` wymaga tokenu). Kontener nie publikuje wtedy żadnego portu na serwerze,
a do ekranu dociera się tylko przez zalogowany pulpit. `LCD_ADRES_PANELU` ustawia adres w kodzie QR.

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

**Update counts from the homelabber desktop:** `POST /api/aktualizacje` (same token) takes
`{"available", "auto", "notify", "outside", "servers", "failed", "checkedAt"}`. The "Updates" screen then
shows the desktop's count in the "Containers" card (its containers and the ones outside it), failed updates
and the number of other servers. The desktop sends them every minute; after 15 min without new counts, or
after `DELETE /api/aktualizacje`, the card goes back to Unraid's own counter.

**Screens from the homelabber desktop:** `POST /api/pulpit/ekrany` (same token) takes
`{"ekrany": {"pulpit_zasilanie": [card, …], …}}`; a card is `{"etykieta", "wartosc", "stan", "pasek", "prawa", "pod"}`,
at most 6 per screen, `null` for an empty slot. Screens: `pulpit_zasilanie`, `pulpit_pobieranie`,
`pulpit_odtwarzanie`, `pulpit_kopie`, `pulpit_kamery`, `pulpit_polaczenia`. They are in the screen list (off by default) and only show
when the desktop sent cards in the last 2 min. The app only draws them and connects to nothing.

**Connections in the header:** `POST /api/pulpit/polaczenia` (same token) takes `{"ikony": [{"rodzaj", "stan", "liczba"}]}`,
at most 6: `rodzaj` is `internet`, `vpn`, `tunel`, `bt` or `cast`, `stan` is `ok`, `uwaga`, `alarm`, `szary` or `gra`,
and the optional `liczba` is shown next to the icon. The icons are drawn before the clock on every screen, and the
screen dots turn into a thin bar under the header. When space runs out the last icons are dropped. After 2 min
without new icons, or after `DELETE /api/pulpit/polaczenia`, the header looks as before. The "Connections in the
header" setting (`naglowek_polaczenia`, on by default) turns the icons off.

**Add-on mode** (homelabber desktop): the "Smart screen" add-on installs this app and has its own settings
window. It runs the container with `LCD_PANEL=0` (own panel off) and `LCD_TYLKO_TOKEN=1` (every `/api/*`
call needs the token), so no port is published on the server. `LCD_ADRES_PANELU` sets the QR code address.

**License:** GPLv3. The display protocol follows
[turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPLv3).
The Inter font (SIL OFL 1.1) comes from the `fonts-inter` package.
