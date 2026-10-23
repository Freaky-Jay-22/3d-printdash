"""Translations for messages created in the backend (errors, notifications).

The German text is the key (like gettext): t("Drucker {name} ...", name=x).
Language: setting "ui.language" (de/en); if that is "automatic", the language
of the browser that last opened 3D-PrintDash is used ("ui.lang_hint").
To add a language, add a dict to MESSAGES with the same keys as "en".
"""
LANGUAGES = ("de", "en")
_lang = "en"


def set_lang(cfg: dict) -> None:
    global _lang
    ui = cfg.get("ui") or {}
    lang = ui.get("language") or ui.get("lang_hint") or "en"
    _lang = lang if lang in LANGUAGES else "en"


def lang() -> str:
    return _lang


def t(text: str, **kw) -> str:
    out = text if _lang == "de" else MESSAGES.get(_lang, {}).get(text, MESSAGES["en"].get(text, text))
    return out.format(**kw) if kw else out


MESSAGES = {
    "en": {
        # login / general
        "Anmeldung erforderlich": "Login required",
        "Zu viele Fehlversuche. Bitte in {min} min erneut versuchen.": "Too many failed attempts. Please try again in {min} min.",
        "Falsches Passwort": "Wrong password",
        "Passwort muss mindestens 6 Zeichen haben": "The password needs at least 6 characters",
        "Drucker nicht gefunden": "Printer not found",
        "Kamera nicht gefunden": "Camera not found",
        "Kein Bild verfügbar": "No image available",
        "Unbekannter Druckertyp": "Unknown printer type",
        # uploads / printing
        "Datei zu gross (max. {mb} MB)": "File too large (max. {mb} MB)",
        "Datei nicht mehr vorhanden, bitte erneut hochladen": "File no longer available, please upload it again",
        "{printer} kann keine {ext}-Dateien drucken": "{printer} cannot print {ext} files",
        "{printer} druckt gerade": "{printer} is printing",
        "Keine gültige .3mf-Datei": "Not a valid .3mf file",
        "In diesem Slot ist nichts geladen": "Nothing is loaded in this slot",
        # notifications
        "Testbenachrichtigung. Alles funktioniert!": "Test notification. Everything works!",
        "Kein Benachrichtigungsdienst eingerichtet (Einstellungen → Benachrichtigungen)":
            "No notification service set up (Settings → Notifications)",
        "Home Assistant nicht erreichbar (nur als Add-on oder mit HA_URL/HA_TOKEN)":
            "Home Assistant not reachable (only as an add-on or with HA_URL/HA_TOKEN)",
        "Home Assistant: Fehler {code} beim Senden über notify.{service}": "Home Assistant: error {code} sending via notify.{service}",
        "Home Assistant nicht erreichbar ({error})": "Home Assistant not reachable ({error})",
        "⚠️ {printer}: Fehler": "⚠️ {printer}: error",
        "⚠️ {printer}: Warnung": "⚠️ {printer}: warning",
        "⏸️ {printer}: pausiert": "⏸️ {printer}: paused",
        "✅ {printer}: fertig": "✅ {printer}: finished",
        "⏹️ {printer}: abgebrochen": "⏹️ {printer}: cancelled",
        "❌ {printer}: fehlgeschlagen": "❌ {printer}: failed",
        "Druck wurde pausiert.": "Print was paused.",
        "Druck abgeschlossen.": "Print finished.",
        "Der Druck wurde abgebrochen.": "The print was cancelled.",
        "Der Druck ist fehlgeschlagen oder wurde abgebrochen.": "The print failed or was cancelled.",
        "Datei: {file}": "File: {file}",
        "Fortschritt: {progress} %": "Progress: {progress} %",
        "🌀 {dryer} fertig": "🌀 {dryer} done",
        "Trocknung fertig nach {duration}. Zurück an ihren Platz:": "Drying finished after {duration}. Put them back:",
        "Spule": "Spool",
        "Filamentlager": "Filament storage",
        # Home Assistant
        "Home Assistant nicht verbunden": "Home Assistant not connected",
        "Home Assistant nicht erreichbar: {error}": "Home Assistant not reachable: {error}",
        "Entität nicht gefunden": "Entity not found",
        "Home Assistant: Fehler {code}": "Home Assistant: error {code}",
        "{entity} ist keine schaltbare Entität": "{entity} is not a switchable entity",
        "{entity} kann nicht ausgelöst werden (erwartet button.…, script.… o. ä.)":
            "{entity} cannot be triggered (expected button.…, script.… or similar)",
        "{entity} ist kein Licht": "{entity} is not a light",
        "Home Assistant: {error}": "Home Assistant: {error}",
        # smart plugs
        "Für diesen Drucker ist keine Steckdose eingerichtet": "No smart plug is set up for this printer",
        "{printer} druckt gerade – Ausschalten würde den Druck abbrechen":
            "{printer} is printing – switching off would stop the print",
        # filament
        "Bitte einen Namen angeben": "Please enter a name",
        "Marke „{name}“ gibt es schon": "Brand “{name}” already exists",
        "Zu viele Lagerorte": "Too many storage locations",
        "Unbekannter Ort": "Unknown location",
        "Der letzte Lagerort kann nicht gelöscht werden": "The last storage location cannot be deleted",
        "Bitte wählen, wohin die Spulen verschoben werden": "Please choose where the spools should be moved",
        "Trockner {n}": "Dryer {n}",
        "Ein Trockner, der entfernt würde, ist gerade in Betrieb": "A dryer that would be removed is running",
        "Trockner nicht gefunden": "Dryer not found",
        "Bitte eine Trocknungszeit angeben": "Please enter a drying time",
        "Von {spool} sind nur {free} verfügbar": "Only {free} of {spool} available",
        "Bitte mindestens eine Spule wählen": "Please choose at least one spool",
        "Trockner läuft nicht": "Dryer is not running",
        "Bitte eine Verlängerung in Minuten angeben": "Please enter the extension in minutes",
        "Spule nicht gefunden": "Spool not found",
        "Drucker": "Printer",
        "Datei": "File",
        "Start": "Start",
        "Ende": "End",
        "Dauer (h)": "Duration (h)",
        "Status": "Status",
        "Filament (g)": "Filament (g)",
        "Filament (m)": "Filament (m)",
        "Kosten": "Cost",
        "Materialien": "Materials",
        "🧵 Filament knapp": "🧵 Filament running low",
        "🔧 {printer}: Wartung fällig": "🔧 {printer}: maintenance due",
        "{task} ist fällig ({hours} Druckstunden bzw. {days} Tage seit dem letzten Mal).":
            "{task} is due ({hours} print hours or {days} days since the last time).",
        "Drucker reinigen": "Clean the printer",
        "Schmieren": "Lubricate",
        "{spool}: noch {left} g ({printer}, Slot {slot})": "{spool}: {left} g left ({printer}, slot {slot})",
        "Das ist keine 3D-PrintDash-Sicherung": "This is not a 3D-PrintDash backup",
        "Sicherung ist zu gross": "Backup is too large",
        "Sicherung ist beschädigt: {error}": "Backup is damaged: {error}",
        "Das ist keine gültige Zip-Datei": "This is not a valid zip file",
        "Falsches Passwort für die andere Installation": "Wrong password for the other installation",
        "Die andere Installation verlangt ein Passwort": "The other installation requires a password",
        "Andere Installation nicht erreichbar: {error}": "Other installation not reachable: {error}",
        "Unerwartete Antwort der anderen Installation": "Unexpected answer from the other installation",
        "Es sind nur {n} Spulen vorhanden": "There are only {n} spools",
        # cameras
        "Kamera": "Camera",
        "Kamera lässt sich nicht aktivieren: {error}": "Camera cannot be activated: {error}",
        "Antwort ist kein JPEG-Bild": "Response is not a JPEG image",
        "Bild aktualisiert sich nicht mehr": "Image is no longer updating",
        "Keine Bilder vom Stream (Timeout)": "No images from the stream (timeout)",
        "Stream beendet": "Stream ended",
        "Keine Bilder vom Stream": "No images from the stream",
        "Kamera hat die Verbindung beendet (Zugangscode und „LAN Only Liveview“ prüfen)":
            "Camera closed the connection (check the access code and “LAN Only Liveview”)",
        # Bambu
        "Verbindung abgelehnt ({reason}). Zugangscode prüfen.": "Connection refused ({reason}). Check the access code.",
        "Drucker hat '{command}' abgelehnt ({reason}). Ohne Developer Mode erlaubt die Bambu-Firmware nur das Überwachen.":
            "Printer refused '{command}' ({reason}). Without Developer Mode the Bambu firmware only allows monitoring.",
        "Nicht verbunden": "Not connected",
        "Druckfehler {code}": "Print error {code}",
        "Kein HA-Knopf für '{action}' eingerichtet (Einstellungen → Drucker)":
            "No HA button set up for '{action}' (Settings → Printers)",
        "Unbekannter Befehl: {action}": "Unknown command: {action}",
        "Nur Überwachung eingestellt – bitte über Bambu Handy oder Bambu Studio steuern":
            "Set to monitoring only – please control the printer with Bambu Handy or Bambu Studio",
        "Drucker ist nicht verbunden": "Printer is not connected",
        "Gerade läuft kein Druck": "No print is running right now",
        "Datei zu gross": "File too large",
        "Upload zum Drucker fehlgeschlagen: {error}": "Upload to the printer failed: {error}",
        "Druckstart ist nur mit Developer Mode möglich. Bitte „Nur hochladen“ wählen und den Druck in Bambu Studio oder der Handy-App starten.":
            "Starting a print needs Developer Mode. Please choose “Upload only” and start the print in Bambu Studio or the Handy app.",
        "'{file}' auf den Drucker hochgeladen.": "'{file}' uploaded to the printer.",
        "'{file}' hochgeladen und Druckstart gesendet.": "'{file}' uploaded and print start sent.",
        # Moonraker
        "Moonraker: {error}": "Moonraker: {error}",
        "Klipper-Fehler": "Klipper error",
        "Druck mit Fehler abgebrochen": "Print stopped with an error",
        "Kein Licht konfiguriert (Einstellungen → Drucker)": "No light configured (Settings → Printers)",
        "Drucker ist nicht erreichbar": "Printer is not reachable",
        "Moonraker nicht erreichbar: {error}": "Moonraker not reachable: {error}",
        "Upload fehlgeschlagen: {error}": "Upload failed: {error}",
        "'{file}' hochgeladen.": "'{file}' uploaded.",
        "'{file}' hochgeladen und Druck gestartet.": "'{file}' uploaded and print started.",
        "Keine Antwort vom Drucker": "No response from the printer",
        "Fehler": "Error",
        "Fehler: {error}": "Error: {error}",
        "HTTP {code}, {size} Bytes, JPEG ok": "HTTP {code}, {size} bytes, JPEG ok",
        "HTTP {code}, {size} Bytes, kein JPEG": "HTTP {code}, {size} bytes, not a JPEG",
    },
}
