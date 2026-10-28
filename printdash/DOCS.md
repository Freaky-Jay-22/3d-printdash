# 3D-PrintDash

**English** below · **Deutsch** weiter unten („Anleitung auf Deutsch“)

A local dashboard for your 3D printers – Bambu Lab (LAN) and Klipper/Moonraker. Everything runs on your
own network, without cloud. Open it with **Open web UI** (German: „Benutzeroberfläche öffnen“) or from the sidebar.

---

## Guide in English

A local dashboard for your 3D printers. 3D-PrintDash runs as an app (formerly "add-on") in Home Assistant
or as a Docker container and talks to your printers directly on your network – no cloud and no
Home Assistant integrations required.

> 3D-PrintDash is an independent open-source project and is not affiliated with Bambu Lab, Snapmaker,
> Klipper or Home Assistant. Product names are only used to describe which devices are supported.

### Why 3D-PrintDash?

If you run more than one printer, you probably know this: one app for the Bambu printer, a web interface
for the Klipper printer, a spreadsheet or notes for your filament, and Home Assistant for the smart plugs.

3D-PrintDash brings this together in **one local dashboard for your whole print farm**:

- **Bambu Lab and Klipper printers side by side** – different brands, one interface
- **Filament manager built in** – know which spool is where and how much is left, without an extra tool
- **Made for Home Assistant** – runs as an app, opens in the sidebar, uses HA for notifications and smart plugs
- **Fully local** – no cloud account, no data leaves your network

### Features

- **Overview:** one card per printer with camera, status, progress, time left and estimated finish,
  layer, temperatures and loaded filaments
- **Detail view** (click a card): all cameras large, plus all details, controls and recent prints,
  optionally full screen
- **Cameras:** printer cameras and any external RTSP/MJPEG cameras, which you can assign to a printer
- **Control:** pause, resume, stop, light (for Bambu printers see "Control of Bambu printers" below)
- **Printing:** upload and start files, for Bambu printers with plate selection and AMS mapping
- **History** of all prints with final image, duration, filament usage and cost
- **Filament management:** inventory by storage location, brands, detection of loaded spools, optional
  usage tracking, low-stock warning, dryer timers
- **Maintenance reminders** for cleaning and lubrication per printer
- **Statistics** per month, printer and material, CSV export
- **Backup** and restore, import from another installation
- **Notifications** with camera image via the Home Assistant app
- **Smart plugs** from Home Assistant, with automatic switch-off after a print
- **Timelapse** (optional): one image per layer, a video in the history, stored internally or on a NAS
- **Design**: light or dark, accent colour of your choice
- **Room climate** (optional): temperature, humidity, air quality and sensor battery of your print room
- **System load** of the Home Assistant machine (CPU, RAM, storage, temperatures) at the bottom of the overview
- **English and German**, any currency

### Screenshots

![Overview with a Bambu Lab and a Klipper printer](https://raw.githubusercontent.com/Freaky-Jay-22/3d-printdash/main/docs/screenshots/overview.jpg)

**Overview** with a Bambu Lab and a Klipper printer side by side.
① Several cameras per printer (built-in and external) ② AMS temperature, humidity and sensor battery
from Home Assistant ③ Loaded filament per toolhead

![Filament management](https://raw.githubusercontent.com/Freaky-Jay-22/3d-printdash/main/docs/screenshots/filament.png)

**Filament:** ① inventory at a glance ② spools in the printer are detected automatically ③ dryer timer

![Detail view of a printer](https://raw.githubusercontent.com/Freaky-Jay-22/3d-printdash/main/docs/screenshots/detail.jpg)

**Detail view** with all cameras, status and controls. ① Maintenance reminders for cleaning and lubrication

![All cameras](https://raw.githubusercontent.com/Freaky-Jay-22/3d-printdash/main/docs/screenshots/cameras.jpg)

**Cameras:** all printer cameras and external cameras on one page.

### Supported printers

| Printer | Connection | Notes |
|---|---|---|
| **Bambu Lab printers** | LAN (MQTT, FTPS) | Camera: video stream on the X1 and H2 series, still images on P1 and A1 (new, not yet tested on a real P1/A1). For control see below. |
| **Klipper printers with Moonraker** | HTTP API | e.g. Voron, Sovol, Snapmaker U1, Qidi Q2. Multiple toolheads and the Qidi Box are supported. |

So far 3D-PrintDash has been tested with Bambu Lab X1C and P1S, a Snapmaker U1 and (by users) a Qidi Q2.
Feedback about other models is welcome.

### Updates

Updates appear in Home Assistant like for any other app. Your settings and data are kept.
Do not uninstall the app to update it – that deletes all data.

### Security

- In the Home Assistant sidebar, 3D-PrintDash is protected by your Home Assistant login.
- For **direct access** via port 8090, set a password under **Settings → General** (at least
  6 characters). Without a password, any device on your network can stop prints, watch cameras and
  switch smart plugs.
- After 5 wrong passwords within 15 minutes, the device is locked out for 15 minutes.
- **Do not forward the port on your router.** For access on the go, use the Home Assistant app or a
  VPN (e.g. WireGuard, Tailscale).
- Access codes, passwords, serial numbers and IP addresses stay on your device and are only shown masked
  in the browser (e.g. `192.xx.xx.xx`). To change one, simply type the new value.

### Setting up printers

Everything is under **Settings** in 3D-PrintDash; click **Save** afterwards.

#### Bambu Lab printers

| Field | Where do I find it? |
|---|---|
| IP address | In the printer's network settings or in your router. Best give the printer a fixed IP in the router. |
| Serial number | In the printer's device information or in Bambu Studio under "Device". |
| LAN access code | In the printer's network settings ("Access Code"). |

**Camera:** switch on **"LAN Only Liveview"** in the printer's network settings, otherwise the image
stays black. X1/H2 deliver a video stream, P1/A1 still images (about 1 per second). The model is detected
from the serial number; if needed, choose it under "Camera type".

**Files to print:** in Bambu Studio or OrcaSlicer choose **"Export plate sliced file"** after slicing.
A normal project file without G-code cannot be printed.

**AMS climate:** choose the source in the printer settings under "AMS climate":
- **Values from the AMS itself:** temperature and humidity straight from the printer (depending on the
  firmware, humidity only as a level 1–5).
- **Own sensor (Home Assistant):** e.g. a separate thermometer inside the AMS. Only its values are shown
  then. Humidity above the limit and battery below 20 % turn red.

##### Camera problems

Each Bambu printer has a **camera connection** setting (Settings → Printers → Camera):

| Setting | When to use |
|---|---|
| **Default** | Works for most printers. |
| **Compatibility mode** | The camera starts slowly or lags behind (e.g. P2S, or a weak computer/VM). Ignores broken timestamps from the printer, starts faster, keeps the connection open for 60 s instead of reconnecting, keeps the delay low and needs less CPU (max. 960 px, 5 images per second). |

The log (Settings → Apps → 3D-PrintDash → Log) shows how long each camera took to show its first image.
For video cameras it also writes a **measurement** line about 30 s after the start, e.g.
`measurement: 1920x1080 h264, received 15.0 images/s, full image every 10.0 s, timestamp jumps: 0, stream ready after 0.6 s, first image after 7.6 s`.
A picture can only be shown once the printer sends a full image, so if full images are rare, the camera
takes that long to start. "Timestamp jumps" means the printer sends broken timing information,
which makes the picture stall or start late; compatibility mode ignores it. Please add this line when reporting camera problems (it contains nothing personal).

##### Control of Bambu printers

Current Bambu firmware only accepts control commands (pause, stop, light, starting a print) from other
programs in **Developer Mode**. 3D-PrintDash therefore offers three modes (Settings → Printers → "Control"):

| Mode | What works |
|---|---|
| **Monitor only** (default) | Status, camera, preview, history, notifications, smart plug, chamber light and file upload. Control via Bambu Handy or Bambu Studio. |
| **Direct** | Full control. Requires **LAN Only mode and Developer Mode** on the printer. The Bambu Handy app and cloud printing no longer work then. |
| **Via Home Assistant** | Uses the buttons of the Bambu Lab integration for Home Assistant (if installed). Only works as far as the firmware allows. |

3D-PrintDash deliberately does not bypass the firmware restriction, e.g. with keys extracted from Bambu
software, and will not do so in the future.

#### Klipper printers (Moonraker)

- **Moonraker URL:** `http://<printer-ip>:7125`, if that does not work `http://<printer-ip>`.
- Click **"Test connection"**. The light objects, temperature sensors and cameras found are offered afterwards.
- **Camera:** taken from Moonraker's webcam settings. You can enter another address under "Camera URL".
- **Light:** detected automatically. If your light is switched by a macro, enter the macro name under
  "Light on/off: custom G-code".
- **Chamber temperature:** detected automatically if a sensor is called "chamber" or similar, otherwise choose it.
- **Snapmaker U1:** the stock firmware has no video stream. 3D-PrintDash detects this and shows the
  built-in camera at about 2 frames per second. Leave "Camera URL" empty for this. Filaments per toolhead
  (material, colour, vendor) are shown if the printer knows them.
- **Automatic filament system:** some Klipper printers know which spool is in which slot or toolhead.
  3D-PrintDash detects this by itself (setting "Automatic filament system" = "Detect automatically") and
  treats it like a Bambu AMS: the spools show up on the printer card, are matched with your inventory and
  get their own storage location in the Filament tab (spools in it when the printer is switched off are
  moved there). Supported so far:
  - **Qidi Box** (e.g. Qidi Q2, firmware 01.01.03 or newer), including the box's temperature and humidity
  - **Snapmaker U1** (filament per toolhead)

  You can also pick the system by hand or switch it off with "None".

#### External cameras

Under **External cameras**, enter an address such as `rtsp://user:password@192.168.1.50:554/stream1`.
If you assign the camera to a printer, it also appears on that printer's card and is used for
notifications. Cameras only run while someone is watching.

##### Rotating and mirroring the image

Cameras that are mounted upside down or turned can be fixed under **Settings → Rotate and mirror
camera image**. This works for every camera, built-in or external: rotate by 90°, 180° or 270°
(clockwise) and/or mirror horizontally or vertically. It also applies to notification images and
timelapses. "Automatic" uses the printer's own setting: for Klipper printers that is the webcam
setting from Fluidd/Mainsail, so the picture is right without doing anything.

#### Smart plugs

If a printer is connected to a switchable plug in Home Assistant, you can switch it on and off in 3D-PrintDash:

- Settings → Printers → choose **"Smart plug (Home Assistant)"** (all `switch.`, `light.` and
  `input_boolean.` entities).
- Optionally **"Switch off after the print (min.)"**: the plug is only switched off once the time has passed
  and nozzle and bed are below 50 °C. This only happens after a print.
- During a print, 3D-PrintDash asks before switching off.

### Filament

#### Storage locations and inventory

- Create **storage locations** freely (e.g. shelf, AMS, cabinet, basement): **+ Storage location**,
  rename, reorder or delete via ⚙. When deleting, you choose where the spools go.
- Optionally per location: Home Assistant sensors for temperature, humidity and battery, with a humidity limit.
- **AMS as a location:** tick **"AMS installed"** for a Bambu printer (Settings → Printers). The location
  "AMS – <printer>" is created automatically. When the printer is switched off (offline or smart plug off),
  the spools detected in the AMS move there – of several identical spools only the loaded number. Each
  parked spool remembers where it came from ("↩ from shelf"); if you take it out while the printer is
  running, it goes back there automatically.
- **External spool as a location:** every Bambu printer (and a Qidi Box with a spool on the external holder)
  also gets the location "<printer> (external)". The spool on the external holder is parked there when the
  printer is switched off, in the same way.
- **Spools** with brand, material, colour, count and condition (new / opened, optionally remaining weight).
  The top row shows count, total amount and value. With **"→ …"** you move spools to another location;
  if an entry has several spools, you choose how many go.
- **Brands** (sub-tab): spool weight, materials and colours per brand. They are offered when you add filament.

#### Detecting spools in the printer

At the top, 3D-PrintDash shows which spools are currently loaded in the printers. These spools are
"moved" there from their storage location and return automatically when unloaded. Your saved inventory
does not change.

This is how 3D-PrintDash finds the matching spool in your inventory:

1. **Assigned by hand:** always wins and applies until another spool is loaded.
2. **ID:** if printer and inventory report the same ID (e.g. the spool's RFID chip), the match is unique.
3. **Material and colour:** otherwise the spool with a matching material and the most similar colour is
   used. Variants count as the same base material (e.g. PLA and PLA Matte, PETG and PETG-CF), because many
   printers only report the base material.

Each spool is assigned at most as often as it is in stock. Unknown spools can be added to the inventory
with **"Add"**.

#### Usage and low stock

- **Subtract usage** (Settings → Filament, off by default): after each print, the grams according to the
  slicer are subtracted from the spools that were active during the print (proportionally if cancelled).
  A new spool becomes "opened"; of several identical spools one is split off. The history shows what was
  subtracted from which spool.
- **Low stock:** opened spools below a set weight (default 100 g) are marked "low" and you get a
  notification (can be switched off).

#### Dryers

Up to 4 dryers with a timer: load spools from the inventory, choose duration and optionally temperature
(3D-PrintDash suggests guide values per material; the manufacturer's data takes priority). When the time
is up, you get a notification and the spools return to their location, marked as "dried". The timer keeps
running even when the browser is closed.

### Preview, usage and cost

- **Preview image** of the part on the card and in the history. It comes from the print file; for Bambu
  printers 3D-PrintDash fetches the file from the printer.
- **Filament usage** according to the slicer, per print in grams and metres, proportionally for cancelled prints.
  For Bambu printers you choose where the usage comes from (Settings → Printers → "Get filament usage from"):
  - **Print file on the SD card** (most accurate, per material): only works with an SD card in the printer,
    and for prints sent through the Bambu cloud only if the printer keeps the file there.
  - **Home Assistant:** the "print weight" sensor of the Bambu Lab integration in cloud mode (per AMS slot),
    also for cloud prints.
  - **AMS level:** the drop of the AMS level in percent, turned into grams. Works without SD card and
    integration, but only with Bambu spools and roughly (1 % ≈ 10 g for 1 kg spools).
  - **Automatic** (default): print file, else Home Assistant, else AMS level.

  Klipper printers report the filament really extruded. 3D-PrintDash uses it for cancelled prints and when
  the slicer wrote no weight into the file.
- **Cost:** under Settings → **Filament prices**, set a price per kg for each material. Variants such as
  "PLA Basic" count as the base material, anything unknown uses the default price. A material you add
  under Filament → Brands appears there automatically (starting with the price used so far);
  "Add from brands" adds the ones of older brands.
- **Firmware versions** in the detail view, as far as the printer reports them.

### Maintenance

Per printer (Settings → Printers → "Maintenance"): **cleaning** and **lubrication** after a number of print
hours and/or days (0 = off; default 100 h / 300 h). The print hours come from the history. The detail view
shows the progress with a **"Done"** button; when a task is due, the card shows a hint and you get a
notification.

### History, statistics and CSV

The history lists every print. **📊 Statistics** shows the print time per month (last 12 months) and
tables per printer and material; **⬇ CSV** downloads all prints for Excel or similar. The printer filter
applies to both.

### Backup

Under **Settings → Backup**:
- **Download backup:** settings, filament inventory, maintenance and history including images as a zip
  file. It contains access codes, so keep it safe.
- **Restore backup:** replaces all data; the current state is saved automatically before
  (in `/data/backups`).
- **Import from another installation:** enter the address (e.g. `http://192.168.1.10:8090`) and password
  of a running installation – for example an older version – to fetch all data over the network. Access
  codes are not transferred; you will be told which ones to enter again.

### Timelapse

3D-PrintDash can record a timelapse of every print: one camera image per layer (every 30 s for
printers that don't report layers), turned into an MP4 video when the print ends. Watch or download it
in the **History** with 🎞 (the video window also has buttons to download or delete it). Under
**Settings → Timelapse → "Manage videos"** you see all videos with their size and can play, download or
delete them.

1. Turn it on per printer under **Settings → Printers → "Record timelapse"**. Optionally choose which
   camera to use, e.g. an external camera with a better view. It works in every control mode, also when
   the print was started in Bambu Studio or the Bambu Handy app.
   Without the tick, you can still record single prints: while printing, press **"🎞 Start timelapse"**
   on the printer card (and stop it the same way).
2. Under **Settings → Timelapse**, choose where the videos are saved:
   - **Internal** – inside 3D-PrintDash
   - **Media folder (/media)** – e.g. a NAS or USB drive. In Home Assistant go to **Settings → System →
     Storage → "Add network storage"**, add the share with usage **"Media"** and enter its name as
     sub folder (e.g. `NAS/3d-printing`). The videos then also show up in the Home Assistant media browser.
   - **Share folder (/share)** – same, with usage "Share"
3. Videos older than the set number of days are deleted automatically (0 = keep forever). The settings
   show where videos go and how much space is left.

If the chosen folder is not available (e.g. the NAS is offline), the video is saved internally instead.
Videos inside 3D-PrintDash are not part of the backup.

**Saving to a USB drive:** Home Assistant OS cannot use a USB drive directly as a media folder, only
network storage. Connect the USB drive to your router or NAS instead (most routers and NAS systems share
it on the network), add that share in Home Assistant as network storage with usage "Media" and choose
"Media folder" in 3D-PrintDash. With Docker, simply mount the USB drive to `/media`.

### Design

Under **Settings → General → Design** you can choose light, dark or automatic (like your device) and
an accent colour for buttons and progress bars. The change is previewed right away.

### Room climate

Optionally, 3D-PrintDash shows the climate of the room your printers are in at the top of the overview –
e.g. from an air quality sensor that is already in Home Assistant. Set it up under
**Settings → Room climate → + Room** and pick the sensors you have. Every sensor is optional:

| Sensor | Yellow | Red |
|---|---|---|
| Temperature | – | above your limit (off by default) |
| Humidity | – | above 60 % |
| Air quality: VOC | from 250 ppb | from 2000 ppb |
| Air quality: CO₂ | from 1000 ppm | from 1500 ppm |
| Air quality: fine dust PM2.5 | from 15 µg/m³ | from 35 µg/m³ |
| Air pressure | – | – |
| Battery | – | below 20 % |

You can change all limits under **Limits**. Several rooms are possible.

### Notifications

Under **Settings → Notifications**, choose a Home Assistant notify service (e.g. the companion app on your
phone) and check it with **"Save & send test"**. The camera image is attached.

Available: errors and warnings, print finished, cancelled, paused, dryer done, filament running low,
maintenance due.

### Language and currency

- **Language:** English or German under Settings → General. "Automatic" uses the browser language.
  Also applies to notifications.
- **Currency:** under Settings → Filament prices. "Automatic" picks it from your browser's country
  (e.g. United States → USD, Germany → EUR).

### Data

Everything is stored in the app's data folder (`/data`): `config.json` (settings), `filament.json`
(inventory), `maintenance.json` (maintenance), `history.db` (history), `snapshots/` (images) and
`backups/` (automatic copies before a restore).

### Contributing

Bugs and ideas are welcome as an [issue](https://github.com/Freaky-Jay-22/3d-printdash/issues). More
languages can be added in `printdash/app/static/lang/` and `printdash/app/i18n.py`. How to develop without
real printers is described in [`dev/README.md`](https://github.com/Freaky-Jay-22/3d-printdash/blob/main/dev/README.md).

### License

[MIT](https://github.com/Freaky-Jay-22/3d-printdash/blob/main/LICENSE)

---

## Anleitung auf Deutsch

Ein lokales Dashboard für deine 3D-Drucker. 3D-PrintDash läuft als App (früher „Add-on“) in Home Assistant
oder als Docker-Container und spricht die Drucker direkt in deinem Netzwerk an, ohne Cloud und ohne
Home-Assistant-Integrationen.

> 3D-PrintDash ist ein unabhängiges Open-Source-Projekt und steht in keiner Verbindung zu Bambu Lab,
> Snapmaker, Klipper oder Home Assistant. Produktnamen werden nur verwendet, um zu beschreiben,
> welche Geräte unterstützt werden.

### Warum 3D-PrintDash?

Wer mehr als einen Drucker hat, kennt das: eine App für den Bambu-Drucker, eine Weboberfläche für den
Klipper-Drucker, eine Tabelle oder Notizen fürs Filament und Home Assistant für die Steckdosen.

3D-PrintDash bringt das zusammen in **einem lokalen Dashboard für deine ganze Druckfarm**:

- **Bambu-Lab- und Klipper-Drucker nebeneinander** – verschiedene Marken, eine Oberfläche
- **Filamentverwaltung eingebaut** – du weisst, welche Spule wo ist und wie viel noch drauf ist, ohne Zusatz-Tool
- **Für Home Assistant gemacht** – läuft als App, öffnet sich in der Seitenleiste, nutzt HA für Benachrichtigungen und Steckdosen
- **Komplett lokal** – kein Cloud-Konto, keine Daten verlassen dein Netzwerk

### Funktionen

- **Übersicht:** eine Karte pro Drucker mit Kamera, Status, Fortschritt, Restzeit und voraussichtlichem
  Ende, Schicht, Temperaturen und geladenen Filamenten
- **Detailansicht** (Karte anklicken): alle Kameras gross, dazu alle Infos, Steuerung und die letzten
  Drucke, auf Wunsch im Vollbild
- **Kameras:** Druckerkameras und beliebige externe RTSP-/MJPEG-Kameras, die du einem Drucker zuordnen kannst
- **Steuerung:** Pause, Fortsetzen, Stopp, Licht (bei Bambu-Druckern siehe „Steuerung bei Bambu-Druckern“ weiter unten)
- **Drucken:** Datei hochladen und starten, bei Bambu-Druckern mit Plattenwahl und AMS-Zuordnung
- **Historie** aller Drucke mit Endbild, Dauer, Filamentverbrauch und Kosten
- **Filament-Verwaltung:** Bestand nach Lagerorten, Marken, Erkennung der geladenen Spulen, optional
  Verbrauch abziehen, Warnung bei knappem Filament, Trockner-Timer
- **Wartungserinnerungen** fürs Reinigen und Schmieren pro Drucker
- **Statistik** pro Monat, Drucker und Material, CSV-Export
- **Datensicherung** und Wiederherstellung, Übernahme von einer anderen Installation
- **Benachrichtigungen** mit Kamerabild über die Home-Assistant-App
- **Steckdosen** aus Home Assistant schalten, mit automatischem Ausschalten nach dem Druck
- **Zeitraffer** (optional): ein Bild pro Schicht, ein Video in der Historie, intern oder auf einer NAS gespeichert
- **Design**: hell oder dunkel, Akzentfarbe nach Wahl
- **Raumklima** (optional): Temperatur, Luftfeuchtigkeit, Luftqualität und Sensor-Batterie deines Druckraums
- **Systemauslastung** des Home-Assistant-Rechners (CPU, RAM, Speicher, Temperaturen) unten in der Übersicht
- **Deutsch und Englisch**, Währung frei wählbar


### Unterstützte Drucker

| Drucker | Verbindung | Hinweise |
|---|---|---|
| **Bambu-Lab-Drucker** | LAN (MQTT, FTPS) | Kamera: Video-Stream bei der X1- und H2-Serie, Einzelbilder bei P1 und A1 (neu, an einem echten P1/A1 noch ungetestet). Steuerung siehe unten. |
| **Klipper-Drucker mit Moonraker** | HTTP-API | z. B. Voron, Sovol, Snapmaker U1, Qidi Q2. Mehrere Werkzeugköpfe und die Qidi Box werden unterstützt. |

Getestet ist 3D-PrintDash bisher mit Bambu Lab X1C und P1S, einem Snapmaker U1 und (von Nutzern) einem Qidi Q2.
Rückmeldungen zu anderen Modellen sind willkommen.

### Updates

Updates zeigt Home Assistant wie bei jeder anderen App an. Einstellungen und Daten bleiben erhalten.
Deinstalliere die App nicht, um sie zu aktualisieren, denn das löscht alle Daten.

### Sicherheit

- Über die Seitenleiste von Home Assistant ist 3D-PrintDash durch deinen Home-Assistant-Login geschützt.
- Für den **direkten Zugriff** über Port 8090 unter **Einstellungen → Allgemein** ein Passwort setzen
  (mindestens 6 Zeichen). Ohne Passwort kann jedes Gerät in deinem Netzwerk Drucke stoppen, Kameras
  ansehen und Steckdosen schalten.
- Nach 5 falschen Passwörtern innert 15 Minuten wird das Gerät für 15 Minuten gesperrt.
- **Den Port nicht im Router nach aussen freigeben.** Für Zugriff von unterwegs eignen sich die
  Home-Assistant-App oder ein VPN (z. B. WireGuard, Tailscale).
- Zugangscodes, Passwörter, Seriennummern und IP-Adressen bleiben auf deinem Gerät und werden im Browser
  nur verdeckt angezeigt (z. B. `192.xx.xx.xx`). Zum Ändern einfach den neuen Wert eintippen.

### Drucker einrichten

Alles unter **Einstellungen** in 3D-PrintDash, danach **Speichern**.

#### Bambu-Lab-Drucker

| Feld | Wo finde ich das? |
|---|---|
| IP-Adresse | Am Drucker in den Netzwerk-Einstellungen oder im Router. Am besten im Router eine feste IP vergeben. |
| Seriennummer | Am Drucker in den Geräteinformationen oder in Bambu Studio unter „Gerät“. |
| LAN-Zugangscode | Am Drucker in den Netzwerk-Einstellungen („Access Code“). |

**Kamera:** Am Drucker in den Netzwerk-Einstellungen **„LAN Only Liveview“** einschalten, sonst bleibt
das Bild schwarz. X1/H2 liefern einen Video-Stream, P1/A1 Einzelbilder (etwa 1 pro Sekunde). Das Modell
wird an der Seriennummer erkannt; falls nötig unter „Kamera-Art“ von Hand wählen.

**Dateien zum Drucken:** In Bambu Studio oder OrcaSlicer nach dem Slicen **„Druckplatte geslict
exportieren“** wählen. Eine normale Projektdatei ohne G-Code kann nicht gedruckt werden.

**AMS-Klima:** In den Drucker-Einstellungen unter „AMS-Klima“ die Quelle wählen:
- **Werte vom AMS selbst:** Temperatur und Feuchte direkt vom Drucker (je nach Firmware Feuchte nur als Stufe 1–5).
- **Eigener Sensor (Home Assistant):** z. B. ein separates Thermometer im AMS. Dann werden nur dessen
  Werte angezeigt. Feuchte über dem Grenzwert und Batterie unter 20 % werden rot.

##### Probleme mit der Kamera

Jeder Bambu-Drucker hat die Einstellung **Kamera-Verbindung** (Einstellungen → Drucker → Kamera):

| Einstellung | Wann verwenden |
|---|---|
| **Standard** | Funktioniert bei den meisten Druckern. |
| **Kompatibilitätsmodus** | Die Kamera startet langsam oder hängt nach (z. B. P2S oder ein schwacher Rechner/VM). Ignoriert fehlerhafte Zeitangaben des Druckers, startet schneller, hält die Verbindung 60 s offen statt neu zu verbinden, hält die Verzögerung klein und braucht weniger Rechenleistung (max. 960 px, 5 Bilder pro Sekunde). |

Im Log (Einstellungen → Apps → 3D-PrintDash → Log) steht, wie lange jede Kamera bis zum ersten Bild gebraucht hat.
Bei Video-Kameras folgt nach etwa 30 s zusätzlich eine **Messzeile** (measurement), z. B.
`measurement: 1920x1080 h264, received 15.0 images/s, full image every 10.0 s, timestamp jumps: 0, stream ready after 0.6 s, first image after 7.6 s`.
Ein Bild lässt sich erst anzeigen, wenn der Drucker ein vollständiges Bild schickt. Kommen vollständige
Bilder nur selten, dauert der Kamerastart entsprechend lange. «Timestamp jumps» heisst, dass der Drucker fehlerhafte
Zeitangaben schickt. Dann bleibt das Bild hängen oder startet spät; der Kompatibilitätsmodus ignoriert sie. Bitte diese Zeile bei Kamera-Problemen
mitschicken (sie enthält nichts Persönliches).

##### Steuerung bei Bambu-Druckern

Aktuelle Bambu-Firmware nimmt Steuerbefehle (Pause, Stopp, Licht, Druckstart) von anderen Programmen
nur im **Developer Mode** an. 3D-PrintDash bietet deshalb drei Modi (Einstellungen → Drucker → „Steuerung“):

| Modus | Was geht |
|---|---|
| **Nur überwachen** (Standard) | Status, Kamera, Vorschau, Historie, Benachrichtigungen, Steckdose, Kammerlicht und Datei-Upload. Steuern über Bambu Handy oder Bambu Studio. |
| **Direkt** | Volle Steuerung. Braucht am Drucker **LAN-Only-Modus und Developer Mode**. Die Bambu Handy App und Cloud-Druck funktionieren dann nicht mehr. |
| **Über Home Assistant** | Nutzt die Knöpfe der Bambu-Lab-Integration für Home Assistant (falls installiert). Funktioniert nur, soweit die Firmware das zulässt. |

3D-PrintDash umgeht die Sperre der Firmware bewusst nicht, z. B. durch ausgelesene Schlüssel aus
Bambu-Programmen. Das bleibt auch so.

#### Klipper-Drucker (Moonraker)

- **Moonraker-URL:** `http://<ip-des-druckers>:7125`, falls das nicht geht `http://<ip-des-druckers>`.
- **„Verbindung testen“** klicken. Danach werden die gefundenen Licht-Objekte, Temperatursensoren und
  Kameras angeboten.
- **Kamera:** wird aus den Webcam-Einstellungen von Moonraker übernommen. Eine andere Adresse kannst du
  bei „Kamera-URL“ eintragen.
- **Licht:** wird automatisch erkannt. Wird dein Licht über ein Makro geschaltet, bei „Licht an/aus:
  eigener G-Code“ den Makronamen eintragen.
- **Kammertemperatur:** wird automatisch erkannt, wenn ein Sensor „chamber“ o. Ä. heisst, sonst auswählen.
- **Snapmaker U1:** Die Original-Firmware hat keinen Video-Stream. 3D-PrintDash erkennt das und zeigt die
  eingebaute Kamera mit etwa 2 Bildern pro Sekunde. „Kamera-URL“ dafür leer lassen. Filamente pro
  Werkzeugkopf (Material, Farbe, Hersteller) werden angezeigt, sofern der Drucker sie kennt.
- **Automatisches Filamentsystem:** Manche Klipper-Drucker wissen, welche Spule in welchem Fach oder
  Werkzeugkopf steckt. 3D-PrintDash erkennt das selbst (Einstellung «Automatisches Filamentsystem» =
  «Automatisch erkennen») und behandelt es wie ein Bambu-AMS: Die Spulen erscheinen auf der Druckerkarte,
  werden mit dem Bestand abgeglichen und bekommen im Filament-Tab einen eigenen Lagerort (Spulen, die beim
  Ausschalten darin stecken, werden dorthin verschoben). Bisher unterstützt:
  - **Qidi Box** (z. B. Qidi Q2, Firmware 01.01.03 oder neuer), inkl. Temperatur und Feuchtigkeit der Box
  - **Snapmaker U1** (Filament pro Werkzeugkopf)

  Das System lässt sich auch von Hand wählen oder mit «Keines» ausschalten.

#### Externe Kameras

Unter **Externe Kameras** eine Adresse eintragen, z. B. `rtsp://benutzer:passwort@192.168.1.50:554/stream1`.
Ordnest du die Kamera einem Drucker zu, erscheint sie zusätzlich auf dessen Karte und wird für
Benachrichtigungen genutzt. Kameras laufen nur, solange jemand zuschaut.

##### Bild drehen und spiegeln

Kameras, die kopfüber oder gedreht montiert sind, lassen sich unter **Einstellungen → Kamerabild drehen
und spiegeln** korrigieren. Das geht für jede Kamera, eingebaut oder extern: um 90°, 180° oder 270°
drehen (im Uhrzeigersinn) und/oder horizontal bzw. vertikal spiegeln. Es gilt auch für
Benachrichtigungsbilder und Zeitraffer. «Automatisch» übernimmt die Einstellung des Druckers: Bei
Klipper-Druckern ist das die Webcam-Einstellung aus Fluidd/Mainsail, das Bild stimmt also ohne Zutun.

#### Steckdosen

Hängt ein Drucker an einer schaltbaren Steckdose in Home Assistant, kannst du ihn in 3D-PrintDash ein-
und ausschalten:

- Einstellungen → Drucker → **„Steckdose (Home Assistant)“** wählen (alle `switch.`-, `light.`- und
  `input_boolean.`-Entitäten).
- Optional **„Nach Druckende ausschalten (Min.)“**: Ausgeschaltet wird erst nach Ablauf der Zeit und wenn
  Düse und Bett unter 50 °C sind. Das passiert nur nach einem Druck.
- Während eines Drucks fragt 3D-PrintDash vor dem Ausschalten nach.

### Filament

#### Lagerorte und Bestand

- **Lagerorte** frei anlegen (z. B. Regal, AMS, Schrank, Keller): **+ Lagerort**, über ⚙ umbenennen,
  sortieren oder löschen. Beim Löschen wählst du, wohin die Spulen kommen.
- Pro Lagerort optional Sensoren aus Home Assistant für Temperatur, Feuchte und Batterie, mit
  Feuchte-Grenzwert.
- **AMS als Lagerort:** Bei einem Bambu-Drucker **„AMS vorhanden“** ankreuzen (Einstellungen → Drucker).
  Der Lagerort „AMS – <Drucker>“ entsteht automatisch. Beim Ausschalten des Druckers (offline oder
  Steckdose aus) wandern die im AMS erkannten Spulen dorthin, von mehreren gleichen Spulen nur die
  geladene Anzahl. Jede geparkte Spule merkt sich ihre Herkunft („↩ aus Lager“). Nimmst du sie bei
  laufendem Drucker heraus, kommt sie automatisch dorthin zurück.
- **Externe Spule als Lagerort:** Jeder Bambu-Drucker (und eine Qidi Box mit Spule am externen Halter)
  bekommt zusätzlich den Lagerort „<Drucker> (extern)“. Die Spule am externen Halter wird beim Ausschalten
  des Druckers genauso dorthin geparkt.
- **Spulen** mit Marke, Material, Farbe, Anzahl und Zustand (neu / angefangen, optional Restgewicht).
  Oben stehen Anzahl, Gesamtmenge und Warenwert. Mit **„→ …“** verschiebst du Spulen an einen anderen Ort;
  hat ein Eintrag mehrere Spulen, wählst du, wie viele mitgehen.
- **Marken** (Unter-Reiter): Spulengewicht, Materialien und Farben pro Marke. Beim Erfassen von Filament
  stehen sie dann als Auswahl bereit.

#### Erkennung der Spulen im Drucker

Ganz oben zeigt 3D-PrintDash, welche Spulen gerade in den Druckern stecken. Diese Spulen werden aus ihrem
Lagerort dorthin „verschoben“ und kommen beim Entladen automatisch zurück. Dein gespeicherter Bestand
ändert sich dabei nicht.

So findet 3D-PrintDash die passende Spule aus deinem Bestand:

1. **Von Hand zugeordnet:** hat immer Vorrang und gilt, bis eine andere Spule eingelegt wird.
2. **Kennung:** Melden Drucker und Bestand dieselbe Kennung (z. B. RFID-Chip der Spule), ist die Zuordnung eindeutig.
3. **Material und Farbe:** Sonst wird die Spule mit passendem Material und der ähnlichsten Farbe genommen.
   Varianten zählen zur selben Grundsorte (z. B. PLA und PLA Matte, PETG und PETG-CF), weil viele Drucker
   nur die Grundsorte melden.

Jede Spule wird höchstens so oft zugeordnet, wie sie im Bestand vorhanden ist. Unbekannte Spulen
übernimmst du mit **„Erfassen“** in den Bestand.

#### Verbrauch und knappes Filament

- **Verbrauch abziehen** (Einstellungen → Filament, standardmässig aus): Nach jedem Druck werden die
  Gramm laut Slicer von den Spulen abgezogen, die während des Drucks aktiv waren (bei Abbruch anteilig).
  Eine neue Spule wird zu „angefangen“, von mehreren gleichen wird eine abgespalten. In der Historie
  steht, wovon wie viel abgezogen wurde.
- **Knappes Filament:** Angefangene Spulen unter einem einstellbaren Gewicht (Standard 100 g) werden als
  „knapp“ markiert, dazu kommt eine Benachrichtigung (abschaltbar).

#### Trockner

Bis zu 4 Trockner mit Timer: Spulen aus dem Bestand einlegen, Dauer und optional Temperatur wählen
(3D-PrintDash schlägt Richtwerte je Material vor, die Angaben des Herstellers haben Vorrang). Ist die Zeit
um, kommt eine Benachrichtigung, und die Spulen kehren als „getrocknet“ markiert an ihren Ort zurück.
Der Timer läuft auch weiter, wenn der Browser geschlossen ist.

### Vorschau, Verbrauch und Kosten

- **Vorschaubild** des Teils auf der Karte und in der Historie. Es kommt aus der Druckdatei, bei
  Bambu-Druckern holt 3D-PrintDash die Datei dafür vom Drucker.
- **Filamentverbrauch** laut Slicer pro Druck in Gramm und Metern, bei abgebrochenen Drucken anteilig.
  Bei Bambu-Druckern wählst du, woher der Verbrauch kommt (Einstellungen → Drucker → «Filamentverbrauch
  ermitteln über»):
  - **Druckdatei auf der SD-Karte** (am genauesten, pro Material): geht nur mit SD-Karte im Drucker, bei
    Drucken über die Bambu-Cloud nur, wenn der Drucker die Datei dort ablegt.
  - **Home Assistant:** Sensor «Gewicht des Drucks» der Bambu-Lab-Integration im Cloud-Modus (pro AMS-Fach),
    auch für Cloud-Drucke.
  - **AMS-Füllstand:** die Abnahme des AMS-Füllstands in Prozent, umgerechnet in Gramm. Geht ohne SD-Karte
    und Integration, aber nur mit Bambu-Spulen und grob (1 % ≈ 10 g bei 1-kg-Spulen).
  - **Automatisch** (Standard): Druckdatei, sonst Home Assistant, sonst AMS-Füllstand.

  Klipper-Drucker melden das tatsächlich extrudierte Filament. 3D-PrintDash verwendet es bei abgebrochenen
  Drucken und wenn der Slicer kein Gewicht in die Datei geschrieben hat.
- **Kosten:** unter Einstellungen → **Filamentpreise** einen Preis pro kg je Material. Varianten wie
  „PLA Basic“ zählen zum Grundmaterial, alles Unbekannte zum Standardpreis. Ein Material, das du unter
  Filament → Marken neu erfasst, erscheint dort automatisch (mit dem bisher verwendeten Preis);
  „Aus Marken übernehmen“ ergänzt die Materialien älterer Marken.
- **Firmware-Versionen** in der Detailansicht, soweit der Drucker sie meldet.

### Wartung

Pro Drucker (Einstellungen → Drucker → „Wartung“): **Reinigen** und **Schmieren** nach Druckstunden
und/oder Tagen (0 = aus; Vorgabe 100 h bzw. 300 h). Die Druckstunden kommen aus der Historie. Die
Detailansicht zeigt den Fortschritt mit einem Knopf **„Erledigt“**; ist etwas fällig, erscheint ein
Hinweis auf der Karte und eine Benachrichtigung.

### Historie, Statistik und CSV

Die Historie listet jeden Druck. **📊 Statistik** zeigt die Druckzeit pro Monat (letzte 12 Monate) und
Tabellen pro Drucker und Material; **⬇ CSV** lädt alle Drucke für Excel o. Ä. herunter. Der
Drucker-Filter gilt für beides.

### Datensicherung

Unter **Einstellungen → Datensicherung**:
- **Backup herunterladen:** Einstellungen, Filamentbestand, Wartung und Historie mit Bildern als
  Zip-Datei. Sie enthält Zugangscodes, also sicher aufbewahren.
- **Backup wiederherstellen:** ersetzt alle Daten; der aktuelle Stand wird vorher automatisch gesichert
  (in `/data/backups`).
- **Von anderer Installation übernehmen:** Adresse (z. B. `http://192.168.1.10:8090`) und Passwort einer
  laufenden Installation eingeben, z. B. einer älteren Version, und alle Daten übers Netzwerk holen.
  Zugangscodes werden nicht übertragen; du bekommst eine Liste, was neu einzutragen ist.

### Zeitraffer

3D-PrintDash kann von jedem Druck einen Zeitraffer aufnehmen: ein Kamerabild pro Schicht (alle 30 s bei
Druckern, die keine Schichten melden), am Ende als MP4-Video. Ansehen oder herunterladen in der
**Historie** mit 🎞 (im Video-Fenster gibt es auch Knöpfe zum Herunterladen und Löschen). Unter
**Einstellungen → Zeitraffer → „Videos verwalten“** siehst du alle Videos mit Grösse und kannst sie
abspielen, herunterladen oder löschen.

1. Pro Drucker einschalten unter **Einstellungen → Drucker → „Zeitraffer aufnehmen“**. Optional wählen,
   welche Kamera verwendet wird, z. B. eine externe Kamera mit besserem Blickwinkel. Das funktioniert in
   jedem Steuerungsmodus, auch wenn der Druck in Bambu Studio oder der Bambu Handy App gestartet wurde.
   Ohne Häkchen kannst du trotzdem einzelne Drucke aufnehmen: während des Drucks auf der Druckerkarte
   **„🎞 Zeitraffer starten“** drücken (und genauso wieder stoppen).
2. Unter **Einstellungen → Zeitraffer** festlegen, wo die Videos gespeichert werden:
   - **Intern** – bei 3D-PrintDash
   - **Medien-Ordner (/media)** – z. B. eine NAS oder USB-Festplatte. In Home Assistant unter
     **Einstellungen → System → Speicher → „Netzwerkspeicher hinzufügen“** die Freigabe mit der Verwendung
     **„Medien“** einbinden und ihren Namen als Unterordner eintragen (z. B. `NAS/3d-druck`). Die Videos
     erscheinen dann auch im Medienbrowser von Home Assistant.
   - **Freigabe-Ordner (/share)** – gleich, mit der Verwendung „Freigabe“
3. Videos, die älter als die eingestellte Anzahl Tage sind, werden automatisch gelöscht (0 = nie). In den
   Einstellungen siehst du, wohin die Videos gehen und wie viel Platz noch frei ist.

Ist der gewählte Ordner nicht erreichbar (z. B. NAS ausgeschaltet), wird das Video intern gespeichert.
Videos bei 3D-PrintDash sind nicht Teil der Datensicherung.

**Auf einer USB-Festplatte speichern:** Home Assistant OS kann eine USB-Festplatte nicht direkt als
Medien-Ordner verwenden, nur Netzwerkspeicher. Schliesse die USB-Festplatte darum am Router oder an der
NAS an (die meisten Router und NAS geben sie im Netzwerk frei), binde diese Freigabe in Home Assistant als
Netzwerkspeicher mit der Verwendung „Medien“ ein und wähle in 3D-PrintDash „Medien-Ordner“. Bei Docker
die USB-Festplatte einfach unter `/media` einhängen.

### Design

Unter **Einstellungen → Allgemein → Design** wählst du hell, dunkel oder automatisch (wie das Gerät) und
eine Akzentfarbe für Knöpfe und Fortschrittsbalken. Die Änderung siehst du sofort als Vorschau.

### Raumklima

Auf Wunsch zeigt 3D-PrintDash oben in der Übersicht das Klima des Raums, in dem die Drucker stehen –
z. B. von einem Luftqualitäts-Sensor, der schon in Home Assistant ist. Einrichten unter
**Einstellungen → Raumklima → + Raum** und die vorhandenen Sensoren auswählen. Jeder Sensor ist optional:

| Sensor | Gelb | Rot |
|---|---|---|
| Temperatur | – | über deinem Grenzwert (standardmässig aus) |
| Luftfeuchtigkeit | – | über 60 % |
| Luftqualität: VOC | ab 250 ppb | ab 2000 ppb |
| Luftqualität: CO₂ | ab 1000 ppm | ab 1500 ppm |
| Luftqualität: Feinstaub PM2.5 | ab 15 µg/m³ | ab 35 µg/m³ |
| Luftdruck | – | – |
| Batterie | – | unter 20 % |

Alle Grenzwerte lassen sich unter **Grenzwerte** ändern. Mehrere Räume sind möglich.

### Benachrichtigungen

Unter **Einstellungen → Benachrichtigungen** einen notify-Dienst von Home Assistant wählen (z. B. die
Companion-App auf dem Handy) und mit **„Speichern & Test senden“** prüfen. Das Kamerabild wird mitgeschickt.

Auswählbar: Fehler und Warnungen, Druck fertig, abgebrochen, pausiert, Trockner fertig, Filament knapp,
Wartung fällig.

### Sprache und Währung

- **Sprache:** Deutsch oder Englisch unter Einstellungen → Allgemein. „Automatisch“ nimmt die
  Browsersprache. Gilt auch für Benachrichtigungen.
- **Währung:** unter Einstellungen → Filamentpreise. „Automatisch“ wählt sie nach dem Land deines
  Browsers (z. B. Schweiz → CHF, Deutschland → EUR).

### Daten

Alles liegt im Datenordner der App (`/data`): `config.json` (Einstellungen), `filament.json` (Bestand),
`maintenance.json` (Wartung), `history.db` (Historie), `snapshots/` (Bilder) und `backups/` (automatische
Sicherungen vor einer Wiederherstellung).

### Mitmachen

Fehler und Ideen gerne als [Issue](https://github.com/Freaky-Jay-22/3d-printdash/issues). Weitere Sprachen
lassen sich über `printdash/app/static/lang/` und `printdash/app/i18n.py` ergänzen. Hinweise zum Entwickeln ohne echte
Drucker stehen in [`dev/README.md`](https://github.com/Freaky-Jay-22/3d-printdash/blob/main/dev/README.md).

### Lizenz

[MIT](https://github.com/Freaky-Jay-22/3d-printdash/blob/main/LICENSE)
