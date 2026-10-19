# Changelog

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
