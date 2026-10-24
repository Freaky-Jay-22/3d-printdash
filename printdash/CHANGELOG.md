# Changelog

## 0.3.1

**English**
- New: **compatibility mode** for the camera of Bambu printers (Settings → Printers → Camera →
  Camera connection) for cameras that start slowly or lag behind (e.g. P2S, weak VM): faster start,
  connection stays open for 60 s, low delay, less CPU load (max. 960 px, 5 images/s). Default is unchanged.
- The log shows how long each camera took to show its first image (helps with camera problems).
- Newer Bambu printers (e.g. P2S) are recognised by the model name they report, no serial number needed.

**Deutsch**
- Neu: **Kompatibilitätsmodus** für die Kamera von Bambu-Druckern (Einstellungen → Drucker → Kamera →
  Kamera-Verbindung) für Kameras, die langsam starten oder nachhängen (z. B. P2S, schwache VM): schnellerer
  Start, Verbindung bleibt 60 s offen, geringe Verzögerung, weniger Rechenlast (max. 960 px, 5 Bilder/s).
  Der Standard bleibt unverändert.
- Im Log steht, wie lange jede Kamera bis zum ersten Bild gebraucht hat (hilft bei Kamera-Problemen).
- Neuere Bambu-Drucker (z. B. P2S) werden am gemeldeten Modellnamen erkannt, ohne Seriennummer.

## 0.3.0

**English**
- New: **Timelapse** (optional, per printer). One camera image per layer, an MP4 video when the print
  ends, watch or download it in the history. Camera selectable. Videos can be stored internally, in the
  Home Assistant media folder (e.g. a NAS added as network storage) or the share folder; old videos are
  deleted after a set number of days. The settings show the storage path and free space.
  Works in every control mode (also prints started in Bambu Studio / Handy). Single prints can be
  recorded with a "Start timelapse" button on the printer card. Videos can be downloaded and deleted in
  the video window and under Settings → Timelapse → "Manage videos". README explains how to use a USB drive.
- New: **Design**. Light, dark or automatic, plus an accent colour of your choice (Settings → General).
- The app now also has access to the Home Assistant share folder (for timelapse videos).

**Deutsch**
- Neu: **Zeitraffer** (optional, pro Drucker). Ein Kamerabild pro Schicht, am Ende ein MP4-Video,
  ansehen oder herunterladen in der Historie. Kamera wählbar. Speicherort intern, im Medien-Ordner von
  Home Assistant (z. B. eine als Netzwerkspeicher eingebundene NAS) oder im Freigabe-Ordner; alte Videos
  werden nach einstellbaren Tagen gelöscht. Die Einstellungen zeigen Speicherort und freien Platz.
  Funktioniert in jedem Steuerungsmodus (auch bei Drucken aus Bambu Studio / Handy). Einzelne Drucke
  lassen sich mit dem Knopf „Zeitraffer starten“ auf der Druckerkarte aufnehmen. Videos lassen sich im
  Video-Fenster und unter Einstellungen → Zeitraffer → „Videos verwalten“ herunterladen und löschen. Das README erklärt,
  wie eine USB-Festplatte genutzt werden kann.
- Neu: **Design**. Hell, dunkel oder automatisch, dazu eine Akzentfarbe nach Wahl (Einstellungen → Allgemein).
- Die App hat jetzt auch Zugriff auf den Freigabe-Ordner von Home Assistant (für Zeitraffer-Videos).

## 0.2.1

- **English:** A material added under Filament → Brands (e.g. PETG-GF) now appears under Settings →
  Filament prices automatically, starting with the price used so far. The new button "Add from brands"
  adds the materials of existing brands.
- **Deutsch:** Ein Material, das unter Filament → Marken neu erfasst wird (z. B. PETG-GF), erscheint jetzt
  automatisch unter Einstellungen → Filamentpreise, mit dem bisher verwendeten Preis. Der neue Knopf
  „Aus Marken übernehmen“ ergänzt die Materialien bestehender Marken.

## 0.2.0

**English**
- New: **Room climate** (optional). Shows Home Assistant sensors of your print room at the top of the
  overview: temperature, humidity, air quality (VOC, CO₂, fine dust PM2.5), air pressure and battery.
  Values turn yellow or red when it gets too humid or the air is bad; limits can be changed.
  Set up under Settings → Room climate.

**Deutsch**
- Neu: **Raumklima** (optional). Zeigt Sensoren deines Druckraums aus Home Assistant oben in der
  Übersicht: Temperatur, Luftfeuchtigkeit, Luftqualität (VOC, CO₂, Feinstaub PM2.5), Luftdruck und
  Batterie. Die Werte werden gelb bzw. rot, wenn es zu feucht wird oder die Luft schlecht ist; die
  Grenzwerte sind einstellbar. Einrichten unter Einstellungen → Raumklima.

## 0.1.1

- **English:** Bambu printers: the chamber light can now also be switched in the "Monitor only" mode.
  The firmware accepts this command without Developer Mode.
- **Deutsch:** Bambu-Drucker: Das Kammerlicht lässt sich jetzt auch im Modus „Nur überwachen“ schalten.
  Die Firmware nimmt diesen Befehl auch ohne Developer Mode an.

## 0.1.0 – First release

**English**

First public version of 3D-PrintDash.

- Overview of all printers with camera, status, progress, estimated finish, temperatures and
  loaded filaments, plus a detail view with all cameras and controls
- Bambu Lab printers over LAN (MQTT, FTPS): camera on the X1 and H2 series (video) and on P1 and A1
  (still images, not yet tested on a real printer), print upload with plate selection and AMS mapping
- Klipper printers with Moonraker, including multiple toolheads (e.g. Snapmaker U1)
- External RTSP/MJPEG cameras that can be assigned to a printer
- Filament management: storage locations you can name and sort yourself, AMS as its own location,
  detection of loaded spools, optional usage tracking, low-stock warning, dryer timers
- Print history with final image, filament usage and cost, statistics and CSV export
- Maintenance reminders for cleaning and lubrication
- Notifications with camera image through Home Assistant, smart plugs with automatic switch-off
- System load of the Home Assistant machine (CPU, RAM, storage, temperatures)
- Backup, restore and import from another installation
- English and German, any currency
- Security: direct access in a browser is off by default; optional password with protection against
  password guessing; serial numbers, IP addresses and access codes are hidden in the settings

**Deutsch**

Erste öffentliche Version von 3D-PrintDash.

- Übersicht aller Drucker mit Kamera, Status, Fortschritt, Fertig-Zeit, Temperaturen und geladenem
  Filament, dazu eine Detailansicht mit allen Kameras und der Steuerung
- Bambu-Lab-Drucker über LAN (MQTT, FTPS): Kamera bei X1 und H2 (Video) sowie P1 und A1
  (Einzelbilder, noch nicht an einem echten Drucker getestet), Druck hochladen mit Plattenwahl und
  AMS-Zuordnung
- Klipper-Drucker mit Moonraker, auch mit mehreren Werkzeugköpfen (z. B. Snapmaker U1)
- Externe RTSP/MJPEG-Kameras, die einem Drucker zugewiesen werden können
- Filamentverwaltung: frei benennbare und sortierbare Lagerorte, AMS als eigener Lagerort, Erkennung
  der geladenen Spulen, Verbrauch abziehen (optional), Warnung bei knappem Filament, Trockner-Timer
- Historie mit Abschlussbild, Filamentverbrauch und Kosten, Statistik und CSV-Export
- Wartungserinnerungen fürs Reinigen und Schmieren
- Benachrichtigungen mit Kamerabild über Home Assistant, Steckdosen mit automatischem Ausschalten
- Auslastung des Home-Assistant-Rechners (CPU, RAM, Speicher, Temperaturen)
- Datensicherung, Wiederherstellung und Übernahme von einer anderen Installation
- Deutsch und Englisch, beliebige Währung
- Sicherheit: direkter Zugriff im Browser ist anfangs ausgeschaltet, optionales Passwort mit Schutz
  gegen Passwort-Raten, Seriennummern, IP-Adressen und Zugangscodes werden in den Einstellungen verdeckt
