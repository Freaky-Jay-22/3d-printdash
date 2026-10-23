# Dev-Umgebung (Tests ohne echte Drucker)

Alles läuft lokal, ohne Hardware. Die Fakes stellen nach:

| Datei | Simuliert | Port |
|---|---|---|
| `fake_moonraker.py` | Snapmaker U1 (Klipper/Moonraker, 4 Werkzeugköpfe, Kamera via `camera.start_monitor`, Filament-Erkennung) **und** einen Home Assistant (`/api/states`, `/api/services`, `/api/template`, `/api/image_proxy`) | 7125 |
| `broker.yaml` + `amqtt` | MQTT-Broker eines Bambu-Druckers (TLS) | 8883 |
| `fakebambu.py` | Bambu X1C, antwortet auf `pushall` mit Status, AMS (inkl. Temp/Feuchte) | über Broker, Seriennummer `SER123` |
| `fake_bambu_cam.py` | Kamera eines Bambu P1/A1 (TLS, Port 6000, Einzelbilder) | `python3 fake_bambu_cam.py 6000 12345678` |
| `implicit_ftps.py` | Bambu-FTPS (implicit TLS) für die Vorschau aus der .3mf | 990 (`FTPS_PORT`) |
| `frames/*.jpg` | Kamerabilder | – |
| `ui_test_example.py` | Playwright-Beispiel (Screenshots + JS-Fehler sammeln) | – |
| `make_test_app.py` | Baut die lokale Test-App «3D-PrintDash TEST» (eigener Slug, oranger Balken, gleiche Funktionen): `python3 make_test_app.py ../printdash <zielordner>` | – |

## Einrichten

```bash
pip install -r ../printdash/requirements.txt amqtt pyftpdlib playwright
# TLS-Zertifikat für Broker + FTPS (selbstsigniert)
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"
```

## Starten (jeweils eigenes Terminal oder im Hintergrund)

```bash
cd dev
amqtt -c broker.yaml
python3 -m uvicorn fake_moonraker:app --port 7125
python3 fakebambu.py
# App (aus dem Ordner printdash/):
PRINTDASH_DATA=../dev/data HA_URL=http://127.0.0.1:7125 HA_TOKEN=x \
  python3 -m uvicorn app.main:app --port 8090
```

Wichtig: `HA_URL` **ohne** `/api` angeben, die App hängt `/api` selbst an.

In der App dann Drucker anlegen:
- Moonraker: URL `http://127.0.0.1:7125`
- Bambu: IP `127.0.0.1`, Seriennummer `SER123`, Zugangscode `12345678`

## Test-Hooks des Fake-Moonraker

- `POST /_set` mit JSON, z. B. `{"state":"error"}`, `{"state":"standby"}`, `{"cold":true}`, `{"webhooks":"shutdown"}`
- `GET /_state`: Zustand und empfangene Benachrichtigungen (`notified`), gedrückte HA-Buttons (`pressed`), G-Code
- `GET /_cam?mode=ws`: die Kamera nur über Websocket statt HTTP-JSON-RPC

## Stolperfallen

- Prozesse nicht mit `pkill -f uvicorn` beenden, wenn das Muster auch im eigenen Shell-Befehl steht (der Befehl beendet sich sonst selbst). Besser:
  `ps -eo pid,args | awk '/[u]vicorn app.main/ {print $1}' | xargs -r kill`
- Der Docker-Build wurde in der Entwicklungsumgebung nie getestet (Registry gesperrt). Er sollte in CI geprüft werden.
