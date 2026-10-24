<img src="printdash/logo.png" alt="3D-PrintDash" height="72">

# 3D-PrintDash

[English](README.md) · **Deutsch**

Ein lokales Dashboard für deine 3D-Drucker. 3D-PrintDash läuft als App (früher „Add-on“) in Home Assistant
oder als Docker-Container und spricht die Drucker direkt in deinem Netzwerk an, ohne Cloud und ohne
Home-Assistant-Integrationen.

> 3D-PrintDash ist ein unabhängiges Open-Source-Projekt und steht in keiner Verbindung zu Bambu Lab,
> Snapmaker, Klipper oder Home Assistant. Produktnamen werden nur verwendet, um zu beschreiben,
> welche Geräte unterstützt werden.

## Warum 3D-PrintDash?

Wer mehr als einen Drucker hat, kennt das: eine App für den Bambu-Drucker, eine Weboberfläche für den
Klipper-Drucker, eine Tabelle oder Notizen fürs Filament und Home Assistant für die Steckdosen.

3D-PrintDash bringt das zusammen in **einem lokalen Dashboard für deine ganze Druckfarm**:

- **Bambu-Lab- und Klipper-Drucker nebeneinander** – verschiedene Marken, eine Oberfläche
- **Filamentverwaltung eingebaut** – du weisst, welche Spule wo ist und wie viel noch drauf ist, ohne Zusatz-Tool
- **Für Home Assistant gemacht** – läuft als App, öffnet sich in der Seitenleiste, nutzt HA für Benachrichtigungen und Steckdosen
- **Komplett lokal** – kein Cloud-Konto, keine Daten verlassen dein Netzwerk

## Funktionen

- **Übersicht:** eine Karte pro Drucker mit Kamera, Status, Fortschritt, Restzeit und voraussichtlichem
  Ende, Schicht, Temperaturen und geladenen Filamenten
- **Detailansicht** (Karte anklicken): alle Kameras gross, dazu alle Infos, Steuerung und die letzten
  Drucke, auf Wunsch im Vollbild
- **Kameras:** Druckerkameras und beliebige externe RTSP-/MJPEG-Kameras, die du einem Drucker zuordnen kannst
- **Steuerung:** Pause, Fortsetzen, Stopp, Licht (bei Bambu-Druckern siehe [Steuerung](#steuerung-bei-bambu-druckern))
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

## Screenshots

![Übersicht mit einem Bambu-Lab- und einem Klipper-Drucker](https://raw.githubusercontent.com/Freaky-Jay-22/3d-printdash/main/docs/screenshots/overview.jpg)

**Übersicht** mit einem Bambu-Lab- und einem Klipper-Drucker nebeneinander.
① Mehrere Kameras pro Drucker (eingebaut und extern) ② AMS-Temperatur, -Feuchtigkeit und Sensor-Batterie
aus Home Assistant ③ Geladenes Filament pro Werkzeugkopf

![Filamentverwaltung](https://raw.githubusercontent.com/Freaky-Jay-22/3d-printdash/main/docs/screenshots/filament.png)

**Filament:** ① Bestand auf einen Blick ② Spulen im Drucker werden automatisch erkannt ③ Trockner-Timer

![Detailansicht eines Druckers](https://raw.githubusercontent.com/Freaky-Jay-22/3d-printdash/main/docs/screenshots/detail.jpg)

**Detailansicht** mit allen Kameras, Status und Steuerung. ① Wartungserinnerungen fürs Reinigen und Schmieren

![Alle Kameras](https://raw.githubusercontent.com/Freaky-Jay-22/3d-printdash/main/docs/screenshots/cameras.jpg)

**Kameras:** alle Drucker- und externen Kameras auf einer Seite.

## Unterstützte Drucker

| Drucker | Verbindung | Hinweise |
|---|---|---|
| **Bambu-Lab-Drucker** | LAN (MQTT, FTPS) | Kamera: Video-Stream bei der X1- und H2-Serie, Einzelbilder bei P1 und A1 (neu, an einem echten P1/A1 noch ungetestet). Steuerung siehe unten. |
| **Klipper-Drucker mit Moonraker** | HTTP-API | z. B. Voron, Sovol, Snapmaker U1. Mehrere Werkzeugköpfe werden unterstützt. |

Getestet ist 3D-PrintDash bisher mit einem Bambu-Lab-Drucker der X1-Serie und einem Snapmaker U1.
Rückmeldungen zu anderen Modellen sind willkommen.

## Installation

### Als Home-Assistant-App (empfohlen)

[![Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FFreaky-Jay-22%2F3d-printdash)

Oder von Hand:

1. In Home Assistant **Einstellungen → Apps → App-Store** öffnen (ältere Versionen: „Add-ons“ statt „Apps“).
2. Oben rechts **⋮ → Repositories** wählen und `https://github.com/Freaky-Jay-22/3d-printdash` hinzufügen.
3. **3D-PrintDash** in der Liste suchen, **Installieren** und danach **Starten**.
4. **In Seitenleiste anzeigen** einschalten.

Geöffnet wird 3D-PrintDash über die Seitenleiste von Home Assistant.

**Direkter Zugriff im Browser** (ohne Home Assistant) ist anfangs ausgeschaltet. So schaltest du ihn ein:
1. In Home Assistant **Einstellungen → Apps → 3D-PrintDash → Konfiguration** öffnen.
2. Unter **Netzwerk** einen Port eintragen (z. B. `8090`), speichern und die App neu starten.
3. `http://<ip-deines-home-assistant>:8090` öffnen und sofort unter **Einstellungen → Allgemein** ein
   Passwort setzen. Solange keines gesetzt ist, zeigt 3D-PrintDash eine Warnung. Siehe [Sicherheit](#sicherheit).

**Updates** zeigt Home Assistant wie bei jeder anderen App an. Deine Einstellungen und Daten bleiben
dabei erhalten. Deinstalliere die App nicht, um sie zu aktualisieren, denn das löscht alle Daten.

### Mit Docker Compose (ohne Home Assistant)

```bash
docker compose up -d
```

Danach ist 3D-PrintDash unter `http://<rechner-ip>:8090` erreichbar. Die Daten liegen im Ordner `./data`.
Für Steckdosen, Sensoren und Benachrichtigungen aus Home Assistant in der `docker-compose.yml`
`HA_URL` (ohne `/api`) und `HA_TOKEN` (langlebiges Zugriffstoken) eintragen.
Um Zeitraffer-Videos auf einer NAS oder einem anderen Laufwerk zu speichern, dieses in der
`docker-compose.yml` unter `/media` einbinden (z. B. `- /mnt/nas/3d-druck:/media`) und in den
Zeitraffer-Einstellungen „Medien-Ordner“ wählen.

### Home Assistant ohne Apps (Container / Core)

Hat deine Home-Assistant-Installation keine Apps (z. B. Home Assistant Container oder Core), startest du
3D-PrintDash wie oben beschrieben mit Docker Compose. In die Seitenleiste von Home Assistant bekommst du
es trotzdem, mit der HACS-Integration [hass_ingress](https://github.com/lovelylain/hass_ingress):

1. **hass_ingress** über HACS installieren und Home Assistant neu starten.
2. Das hier in die `configuration.yaml` eintragen und Home Assistant nochmals neu starten:

```yaml
ingress:
  printdash:
    title: 3D-PrintDash
    icon: mdi:printer-3d
    require_admin: true
    url: http://127.0.0.1:8090
    index: '#overview'
```

   Als Adresse die nehmen, unter der Home Assistant 3D-PrintDash erreicht. `127.0.0.1` passt, wenn beide
   auf demselben Rechner laufen und Home Assistant das Host-Netzwerk nutzt.
3. **3D-PrintDash** erscheint jetzt in der Seitenleiste (wegen `require_admin: true` nur für Admins).

Nutzt du es nur über die Seitenleiste, mach den Port nur auf dem eigenen Rechner erreichbar: In der
`docker-compose.yml` die Port-Zeile auf `- "127.0.0.1:8090:8090"` ändern. Sonst unbedingt in
3D-PrintDash ein Passwort setzen (Einstellungen → Allgemein), denn der Port ist im ganzen Netzwerk offen.

*Danke an den Reddit-Nutzer geo38 für den Tipp.*

## Sicherheit

- Über die Seitenleiste von Home Assistant ist 3D-PrintDash durch deinen Home-Assistant-Login geschützt.
- Für den **direkten Zugriff** über Port 8090 unter **Einstellungen → Allgemein** ein Passwort setzen
  (mindestens 6 Zeichen). Ohne Passwort kann jedes Gerät in deinem Netzwerk Drucke stoppen, Kameras
  ansehen und Steckdosen schalten.
- Nach 5 falschen Passwörtern innert 15 Minuten wird das Gerät für 15 Minuten gesperrt.
- **Den Port nicht im Router nach aussen freigeben.** Für Zugriff von unterwegs eignen sich die
  Home-Assistant-App oder ein VPN (z. B. WireGuard, Tailscale).
- Zugangscodes, Passwörter, Seriennummern und IP-Adressen bleiben auf deinem Gerät und werden im Browser
  nur verdeckt angezeigt (z. B. `192.xx.xx.xx`). Zum Ändern einfach den neuen Wert eintippen.

## Drucker einrichten

Alles unter **Einstellungen** in 3D-PrintDash, danach **Speichern**.

### Bambu-Lab-Drucker

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

#### Probleme mit der Kamera

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

#### Steuerung bei Bambu-Druckern

Aktuelle Bambu-Firmware nimmt Steuerbefehle (Pause, Stopp, Licht, Druckstart) von anderen Programmen
nur im **Developer Mode** an. 3D-PrintDash bietet deshalb drei Modi (Einstellungen → Drucker → „Steuerung“):

| Modus | Was geht |
|---|---|
| **Nur überwachen** (Standard) | Status, Kamera, Vorschau, Historie, Benachrichtigungen, Steckdose, Kammerlicht und Datei-Upload. Steuern über Bambu Handy oder Bambu Studio. |
| **Direkt** | Volle Steuerung. Braucht am Drucker **LAN-Only-Modus und Developer Mode**. Die Bambu Handy App und Cloud-Druck funktionieren dann nicht mehr. |
| **Über Home Assistant** | Nutzt die Knöpfe der Bambu-Lab-Integration für Home Assistant (falls installiert). Funktioniert nur, soweit die Firmware das zulässt. |

3D-PrintDash umgeht die Sperre der Firmware bewusst nicht, z. B. durch ausgelesene Schlüssel aus
Bambu-Programmen. Das bleibt auch so.

### Klipper-Drucker (Moonraker)

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

### Externe Kameras

Unter **Externe Kameras** eine Adresse eintragen, z. B. `rtsp://benutzer:passwort@192.168.1.50:554/stream1`.
Ordnest du die Kamera einem Drucker zu, erscheint sie zusätzlich auf dessen Karte und wird für
Benachrichtigungen genutzt. Kameras laufen nur, solange jemand zuschaut.

### Steckdosen

Hängt ein Drucker an einer schaltbaren Steckdose in Home Assistant, kannst du ihn in 3D-PrintDash ein-
und ausschalten:

- Einstellungen → Drucker → **„Steckdose (Home Assistant)“** wählen (alle `switch.`-, `light.`- und
  `input_boolean.`-Entitäten).
- Optional **„Nach Druckende ausschalten (Min.)“**: Ausgeschaltet wird erst nach Ablauf der Zeit und wenn
  Düse und Bett unter 50 °C sind. Das passiert nur nach einem Druck.
- Während eines Drucks fragt 3D-PrintDash vor dem Ausschalten nach.

## Filament

### Lagerorte und Bestand

- **Lagerorte** frei anlegen (z. B. Regal, AMS, Schrank, Keller): **+ Lagerort**, über ⚙ umbenennen,
  sortieren oder löschen. Beim Löschen wählst du, wohin die Spulen kommen.
- Pro Lagerort optional Sensoren aus Home Assistant für Temperatur, Feuchte und Batterie, mit
  Feuchte-Grenzwert.
- **AMS als Lagerort:** Bei einem Bambu-Drucker **„AMS vorhanden“** ankreuzen (Einstellungen → Drucker).
  Der Lagerort „AMS – <Drucker>“ entsteht automatisch. Beim Ausschalten des Druckers (offline oder
  Steckdose aus) wandern die im AMS erkannten Spulen dorthin, von mehreren gleichen Spulen nur die
  geladene Anzahl. Jede geparkte Spule merkt sich ihre Herkunft („↩ aus Lager“). Nimmst du sie bei
  laufendem Drucker heraus, kommt sie automatisch dorthin zurück.
- **Spulen** mit Marke, Material, Farbe, Anzahl und Zustand (neu / angefangen, optional Restgewicht).
  Oben stehen Anzahl, Gesamtmenge und Warenwert. Mit **„→ …“** verschiebst du Spulen an einen anderen Ort;
  hat ein Eintrag mehrere Spulen, wählst du, wie viele mitgehen.
- **Marken** (Unter-Reiter): Spulengewicht, Materialien und Farben pro Marke. Beim Erfassen von Filament
  stehen sie dann als Auswahl bereit.

### Erkennung der Spulen im Drucker

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

### Verbrauch und knappes Filament

- **Verbrauch abziehen** (Einstellungen → Filament, standardmässig aus): Nach jedem Druck werden die
  Gramm laut Slicer von den Spulen abgezogen, die während des Drucks aktiv waren (bei Abbruch anteilig).
  Eine neue Spule wird zu „angefangen“, von mehreren gleichen wird eine abgespalten. In der Historie
  steht, wovon wie viel abgezogen wurde.
- **Knappes Filament:** Angefangene Spulen unter einem einstellbaren Gewicht (Standard 100 g) werden als
  „knapp“ markiert, dazu kommt eine Benachrichtigung (abschaltbar).

### Trockner

Bis zu 4 Trockner mit Timer: Spulen aus dem Bestand einlegen, Dauer und optional Temperatur wählen
(3D-PrintDash schlägt Richtwerte je Material vor, die Angaben des Herstellers haben Vorrang). Ist die Zeit
um, kommt eine Benachrichtigung, und die Spulen kehren als „getrocknet“ markiert an ihren Ort zurück.
Der Timer läuft auch weiter, wenn der Browser geschlossen ist.

## Vorschau, Verbrauch und Kosten

- **Vorschaubild** des Teils auf der Karte und in der Historie. Es kommt aus der Druckdatei, bei
  Bambu-Druckern holt 3D-PrintDash die Datei dafür vom Drucker.
- **Filamentverbrauch** laut Slicer pro Druck in Gramm und Metern, bei abgebrochenen Drucken anteilig.
- **Kosten:** unter Einstellungen → **Filamentpreise** einen Preis pro kg je Material. Varianten wie
  „PLA Basic“ zählen zum Grundmaterial, alles Unbekannte zum Standardpreis. Ein Material, das du unter
  Filament → Marken neu erfasst, erscheint dort automatisch (mit dem bisher verwendeten Preis);
  „Aus Marken übernehmen“ ergänzt die Materialien älterer Marken.
- **Firmware-Versionen** in der Detailansicht, soweit der Drucker sie meldet.

## Wartung

Pro Drucker (Einstellungen → Drucker → „Wartung“): **Reinigen** und **Schmieren** nach Druckstunden
und/oder Tagen (0 = aus; Vorgabe 100 h bzw. 300 h). Die Druckstunden kommen aus der Historie. Die
Detailansicht zeigt den Fortschritt mit einem Knopf **„Erledigt“**; ist etwas fällig, erscheint ein
Hinweis auf der Karte und eine Benachrichtigung.

## Historie, Statistik und CSV

Die Historie listet jeden Druck. **📊 Statistik** zeigt die Druckzeit pro Monat (letzte 12 Monate) und
Tabellen pro Drucker und Material; **⬇ CSV** lädt alle Drucke für Excel o. Ä. herunter. Der
Drucker-Filter gilt für beides.

## Datensicherung

Unter **Einstellungen → Datensicherung**:
- **Backup herunterladen:** Einstellungen, Filamentbestand, Wartung und Historie mit Bildern als
  Zip-Datei. Sie enthält Zugangscodes, also sicher aufbewahren.
- **Backup wiederherstellen:** ersetzt alle Daten; der aktuelle Stand wird vorher automatisch gesichert
  (in `/data/backups`).
- **Von anderer Installation übernehmen:** Adresse (z. B. `http://192.168.1.10:8090`) und Passwort einer
  laufenden Installation eingeben, z. B. einer älteren Version, und alle Daten übers Netzwerk holen.
  Zugangscodes werden nicht übertragen; du bekommst eine Liste, was neu einzutragen ist.

## Zeitraffer

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

## Design

Unter **Einstellungen → Allgemein → Design** wählst du hell, dunkel oder automatisch (wie das Gerät) und
eine Akzentfarbe für Knöpfe und Fortschrittsbalken. Die Änderung siehst du sofort als Vorschau.

## Raumklima

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

## Benachrichtigungen

Unter **Einstellungen → Benachrichtigungen** einen notify-Dienst von Home Assistant wählen (z. B. die
Companion-App auf dem Handy) und mit **„Speichern & Test senden“** prüfen. Das Kamerabild wird mitgeschickt.

Auswählbar: Fehler und Warnungen, Druck fertig, abgebrochen, pausiert, Trockner fertig, Filament knapp,
Wartung fällig.

## Sprache und Währung

- **Sprache:** Deutsch oder Englisch unter Einstellungen → Allgemein. „Automatisch“ nimmt die
  Browsersprache. Gilt auch für Benachrichtigungen.
- **Währung:** unter Einstellungen → Filamentpreise. „Automatisch“ wählt sie nach dem Land deines
  Browsers (z. B. Schweiz → CHF, Deutschland → EUR).

## Daten

Alles liegt im Datenordner der App (`/data`): `config.json` (Einstellungen), `filament.json` (Bestand),
`maintenance.json` (Wartung), `history.db` (Historie), `snapshots/` (Bilder) und `backups/` (automatische
Sicherungen vor einer Wiederherstellung).

## Mitmachen

Fehler und Ideen gerne als [Issue](https://github.com/Freaky-Jay-22/3d-printdash/issues). Weitere Sprachen
lassen sich über `printdash/app/static/lang/` und `printdash/app/i18n.py` ergänzen. Hinweise zum Entwickeln ohne echte
Drucker stehen in [`dev/README.md`](dev/README.md).

## Lizenz

[MIT](LICENSE)
