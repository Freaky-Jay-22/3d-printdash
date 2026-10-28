# Changelog

## 0.3.6

**English**
- New: **automatic filament system** for Klipper printers (Settings → Printers → "Automatic filament
  system"). 3D-PrintDash detects which spool is in which slot or toolhead and treats it like a Bambu AMS:
  spools on the printer card, matched with your inventory, own storage location in the Filament tab
  (spools in it when the printer is switched off are moved there). Detected automatically, can also be
  chosen by hand or switched off.
- Supported: **Qidi Box** (e.g. Qidi Q2, firmware 01.01.03 or newer, incl. box temperature and humidity)
  and **Snapmaker U1** (filament per toolhead; now also gets its own storage location).
- Filament tab: "goes back to" now shows the spool's real home location for spools parked in an AMS/box.
- Filament tab: the storage locations of the printers (AMS, filament systems) are always shown first,
  before your own locations.
- Filament tab: assigning a spool by hand now shows the spools in stock with a colour dot, the most similar
  colour first, so equal materials (e.g. several PLA Matte) can be told apart.
- Filament tab: the spool on the external holder (Bambu, Qidi Box) gets its own storage location
  "<printer> (external)" and is moved there when the printer is switched off, like the spools in the AMS / box.
- Filament tab: the storage locations fill the columns without big gaps.
- Printer details: long file names under "Recent prints" are shortened with "…", the status badges are aligned.
- Filament tab: print costs now use the price of the loaded spool's material (e.g. "SNAPSPEED PLA") when it
  has its own price, instead of the plain type from the print file ("PLA").
- Filament tab: spools named with a product name first ("SNAPSPEED PLA", "Silk PLA") are now recognised as
  PLA and matched automatically.
- Bambu X1: the first layer inspection (HMS 0C00_0300_0003_000B) is a normal step, not an error. It is no
  longer shown as an error and no longer sends a notification. A problem found by the inspection is still
  reported.
- Bambu: instructions and questions on the printer screen are no longer shown as errors and send no
  notification. Checked against Bambu's full list of printer messages, e.g. when loading or unloading the
  external spool ("Please pull out the filament", "Please feed the filament", "Filament extruded? Continue /
  Retry"), "Printing was paused by the user", AMS drying hints, air purification after the print and the
  backup spool taking over. Real errors (e.g. "Extruding filament failed" from the AMS) are still reported.
- Bambu: new setting **"Get filament usage from"** (print file on the SD card / Home Assistant / AMS level /
  automatic). Prints sent through the Bambu cloud, or printers without SD card, showed 0 g before; the usage
  can now come from the "print weight" sensor of the Home Assistant Bambu Lab integration or from the drop
  of the AMS level (Bambu spools). Usage, cost and stock deduction work for these prints too.
- Klipper: cancelled prints and prints without a weight from the slicer now use the filament really
  extruded (reported by Klipper) instead of an estimate.

**Deutsch**
- Neu: **automatisches Filamentsystem** für Klipper-Drucker (Einstellungen → Drucker → «Automatisches
  Filamentsystem»). 3D-PrintDash erkennt, welche Spule in welchem Fach oder Werkzeugkopf steckt, und
  behandelt es wie ein Bambu-AMS: Spulen auf der Druckerkarte, Abgleich mit dem Bestand, eigener Lagerort
  im Filament-Tab (Spulen, die beim Ausschalten darin stecken, werden dorthin verschoben). Wird
  automatisch erkannt, lässt sich aber auch von Hand wählen oder ausschalten.
- Unterstützt: **Qidi Box** (z. B. Qidi Q2, Firmware 01.01.03 oder neuer, inkl. Temperatur und
  Feuchtigkeit der Box) und **Snapmaker U1** (Filament pro Werkzeugkopf; bekommt jetzt ebenfalls einen
  eigenen Lagerort).
- Filament-Tab: «zurück nach» zeigt bei Spulen, die im AMS/in der Box geparkt sind, jetzt den richtigen
  Heimatort.
- Filament-Tab: Die Lagerorte der Drucker (AMS, Filamentsysteme) stehen immer zuoberst, vor den eigenen
  Lagerorten.
- Filament-Tab: Beim Zuordnen von Hand zeigt die Liste die Spulen im Bestand mit einem Farbpunkt, die
  ähnlichste Farbe zuerst. So lassen sich gleiche Materialien (z. B. mehrere PLA Matte) unterscheiden.
- Filament-Tab: Die Spule am externen Halter (Bambu, Qidi Box) bekommt einen eigenen Lagerort
  «<Drucker> (extern)» und wandert beim Ausschalten des Druckers dorthin, wie die Spulen im AMS bzw. in der Box.
- Filament-Tab: Die Lagerorte füllen die Spalten ohne grosse Lücken.
- Druckerdetails: Lange Dateinamen unter «Letzte Drucke» werden mit «…» gekürzt, die Status-Anzeigen stehen bündig.
- Filament-Tab: Die Druckkosten nehmen jetzt den Preis des Materials der geladenen Spule (z. B.
  «SNAPSPEED PLA»), wenn es einen eigenen Preis hat, statt des einfachen Typs aus der Druckdatei («PLA»).
- Filament-Tab: Spulen, deren Material mit einem Produktnamen beginnt («SNAPSPEED PLA», «Silk PLA»), werden
  jetzt als PLA erkannt und automatisch zugeordnet.
- Bambu X1: Die Prüfung der ersten Schicht (HMS 0C00_0300_0003_000B) ist ein normaler Arbeitsschritt und
  kein Fehler. Sie erscheint nicht mehr als Fehler und löst keine Benachrichtigung mehr aus. Findet die
  Prüfung ein Problem, wird das weiterhin gemeldet.
- Bambu: Anweisungen und Rückfragen auf dem Druckerdisplay erscheinen nicht mehr als Fehler und lösen keine
  Benachrichtigung aus. Geprüft gegen Bambus vollständige Liste der Druckermeldungen, z. B. beim Laden oder
  Entladen der externen Spule («Filament herausziehen», «Filament einführen», «Filament extrudiert? Weiter /
  Wiederholen»), «Druck vom Benutzer pausiert», Hinweise zum AMS-Trocknen, Luftreinigung nach dem Druck und
  das Umschalten auf die Ersatzspule. Echte Fehler (z. B. «Extrudieren fehlgeschlagen» vom AMS) werden
  weiterhin gemeldet.
- Bambu: neue Einstellung **«Filamentverbrauch ermitteln über»** (Druckdatei auf der SD-Karte / Home
  Assistant / AMS-Füllstand / automatisch). Drucke über die Bambu-Cloud oder Drucker ohne SD-Karte zeigten
  bisher 0 g; der Verbrauch kann jetzt aus dem Sensor «Gewicht des Drucks» der Bambu-Lab-Integration in
  Home Assistant oder aus der Abnahme des AMS-Füllstands (Bambu-Spulen) kommen. Verbrauch, Kosten und Abzug
  vom Bestand funktionieren damit auch für diese Drucke.
- Klipper: Abgebrochene Drucke und Drucke ohne Gewichtsangabe des Slicers nutzen jetzt das tatsächlich
  extrudierte Filament (von Klipper gemeldet) statt einer Schätzung.

## 0.3.5

**English**
- New: **rotate and mirror the camera image** (Settings → Rotate and mirror camera image) for every camera,
  built-in or external: 90°, 180°, 270° and/or mirrored horizontally or vertically. Also applies to
  notification images and timelapses. "Automatic" uses the printer's own setting; for Klipper printers
  the webcam setting from Fluidd/Mainsail is taken over automatically.

**Deutsch**
- Neu: **Kamerabild drehen und spiegeln** (Einstellungen → Kamerabild drehen und spiegeln) für jede Kamera,
  eingebaut oder extern: 90°, 180°, 270° und/oder horizontal bzw. vertikal gespiegelt. Gilt auch für
  Benachrichtigungsbilder und Zeitraffer. «Automatisch» übernimmt die Einstellung des Druckers; bei
  Klipper-Druckern wird die Webcam-Einstellung aus Fluidd/Mainsail automatisch übernommen.

## 0.3.4

**English**
- Docker: new option `PRINTDASH_NO_PASSWORD_WARNING=1` hides the "no password" warning bar, for
  installations where the port is only reachable from the same machine (e.g. behind hass_ingress).

**Deutsch**
- Docker: Neue Option `PRINTDASH_NO_PASSWORD_WARNING=1` blendet den Warnbalken «ohne Passwort» aus, für
  Installationen, deren Port nur vom eigenen Rechner erreichbar ist (z. B. hinter hass_ingress).

## 0.3.3

**English**
- The log now contains a **camera measurement** about 30 s after a video camera starts: image size,
  images per second sent by the printer, how often a full image arrives and how long the start took.
  Helps to find the cause of slow cameras (e.g. P2S). Costs almost no CPU, nothing personal is logged.
- Camera compatibility mode now ignores the printer's timestamps and uses the arrival time instead. Some
  printers (e.g. P2S) send broken timestamps, which made the picture start late, stall or update slowly.

**Deutsch**
- Im Log steht jetzt etwa 30 s nach dem Start einer Video-Kamera eine **Kamera-Messung**: Bildgrösse,
  Bilder pro Sekunde vom Drucker, wie oft ein vollständiges Bild kommt und wie lange der Start gedauert
  hat. Hilft, die Ursache langsamer Kameras zu finden (z. B. P2S). Kostet kaum Rechenleistung, es wird
  nichts Persönliches protokolliert.
- Der Kamera-Kompatibilitätsmodus ignoriert jetzt die Zeitangaben des Druckers und nimmt die Ankunftszeit
  der Bilder. Manche Drucker (z. B. P2S) schicken fehlerhafte Zeitangaben, dadurch startete das Bild spät,
  blieb hängen oder aktualisierte sich nur langsam.

## 0.3.2

**English**
- Fix: after an update the browser sometimes kept showing the old interface from its cache (e.g. new
  settings were missing). The interface files now carry a version mark, so every update loads right away.

**Deutsch**
- Behoben: Nach einem Update zeigte der Browser manchmal noch die alte Oberfläche aus dem Cache (z. B.
  fehlten neue Einstellungen). Die Dateien der Oberfläche tragen jetzt eine Versionsmarke, jedes Update
  wird sofort geladen.

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
