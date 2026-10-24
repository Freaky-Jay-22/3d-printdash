"""Bambu Lab driver: local MQTT (status + commands) and FTPS (file upload).

Works directly against the printer on your LAN, no Bambu cloud involved.
  MQTT:   port 8883, TLS, user "bblp", password = LAN access code
  FTPS:   port 990 (implicit TLS), same credentials
  Camera: X1/H2 series RTSPS on port 322 ("LAN Only Liveview" must be on)

Note: with current firmware, a printer that is NOT in Developer Mode only
accepts monitoring. Commands (pause/stop/light/start) may be refused; the
refusal is shown to the user.
"""
import asyncio
import ftplib
import json
import logging
import os
import re
import ssl
import tempfile
import threading
import time

import paho.mqtt.client as mqtt

from ..i18n import t
from .base import BasePrinter, PrinterError

log = logging.getLogger("printdash.bambu")

CANCELLED_ERROR = 0x0300400C  # "Print was cancelled" error code
HMS_SEVERITY = {1: "fatal", 2: "serious", 3: "common", 4: "info"}
GCODE_STATE_MAP = {
    "IDLE": "idle",
    "INIT": "idle",
    "PREPARE": "preparing",
    "SLICING": "preparing",
    "RUNNING": "printing",
    "PAUSE": "paused",
    "FINISH": "finished",
    "FAILED": "failed",
}


def _deep_merge(dst: dict, src: dict):
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value


def _to_float(value):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _color(hex_rgba):
    if not isinstance(hex_rgba, str) or not re.fullmatch(r"[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", hex_rgba):
        return None
    return "#" + hex_rgba[:6].lower()


def _uid(value) -> str | None:
    """Spool serial (RFID) – Bambu sends zeros when there is none."""
    v = str(value or "").strip()
    return v.upper() if v and set(v) - {"0"} else None


# model from the first three characters of the serial number
MODEL_BY_PREFIX = {
    "00M": "X1C", "00W": "X1", "03W": "X1E",
    "01S": "P1P", "01P": "P1S",
    "030": "A1 mini", "039": "A1",
    "094": "H2D",
}


def product_model_name(product_name: str) -> str | None:
    """'Bambu Lab X1 Carbon' -> 'X1C', 'Bambu Lab P2S' -> 'P2S', 'Bambu Lab A1 mini' -> 'A1 mini'"""
    name = str(product_name or "").strip()
    if name.lower().startswith("bambu lab "):
        name = name[10:].strip()
    special = {"X1 CARBON": "X1C", "X1-CARBON": "X1C"}
    return special.get(name.upper(), name) or None


def model_family(model: str | None) -> str:
    """x1 | p1 | a1 | h2 – used for the wiki links and the camera type."""
    m = (model or "").upper()
    for fam in ("P1", "A1", "H2", "X1"):
        if m.startswith(fam):
            return fam.lower()
    return "x1"


def hms_code(attr: int, code: int) -> str:
    return f"{attr >> 16:04X}_{attr & 0xFFFF:04X}_{code >> 16:04X}_{code & 0xFFFF:04X}"


class ImplicitFTPS(ftplib.FTP_TLS):
    """FTP over implicit TLS with TLS session reuse (required by Bambu)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sock = None

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, value):
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value, server_hostname=self.host)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(
                conn, server_hostname=self.host, session=self.sock.session
            )
        return conn, size

    def store_file(self, remote_name: str, fh, progress=None):
        # Own implementation: Bambu printers hang on the TLS unwrap that
        # ftplib.storbinary does at the end of a transfer.
        self.voidcmd("TYPE I")
        conn = self.transfercmd(f"STOR {remote_name}")
        try:
            sent = 0
            while True:
                block = fh.read(65536)
                if not block:
                    break
                conn.sendall(block)
                sent += len(block)
                if progress:
                    progress(sent)
        finally:
            conn.close()
        return self.voidresp()


class BambuPrinter(BasePrinter):
    type = "bambu"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.host = cfg.get("host", "").strip()
        self.serial = cfg.get("serial", "").strip()
        self.access_code = cfg.get("access_code", "").strip()
        self.raw: dict = {}
        self.connected = False
        self.last_msg = 0.0
        self._lock = threading.Lock()
        self._client = None
        self._seq = 0
        self._pushall_task = None
        self.versions: dict = {}
        self.preview_debug: dict = {}

    # -- lifecycle -------------------------------------------------------
    async def start(self):
        if not (self.host and self.serial and self.access_code):
            log.warning("%s: IP, Seriennummer oder Zugangscode fehlt", self.name)
            return
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"printdash-{self.id}",
            protocol=mqtt.MQTTv311,
        )
        client.username_pw_set("bblp", self.access_code)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        client.tls_set_context(ctx)
        client.reconnect_delay_set(min_delay=2, max_delay=30)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        self._client = client
        client.connect_async(self.host, 8883, keepalive=30)
        client.loop_start()
        self._pushall_task = asyncio.create_task(self._pushall_loop())

    async def stop(self):
        if self._pushall_task:
            self._pushall_task.cancel()
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
            self._client = None

    async def _pushall_loop(self):
        # Request a full status now and then (and whenever messages stop)
        while True:
            await asyncio.sleep(30)
            if self.connected and time.time() - self.last_msg > 20:
                self._publish({"pushing": {"command": "pushall"}})

    # -- MQTT callbacks (run in paho's thread) ---------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.warning("%s: MQTT connection refused: %s", self.name, reason_code)
            self.set_cmd_message(t("Verbindung abgelehnt ({reason}). Zugangscode prüfen.", reason=reason_code))
            return
        log.info("%s: connected", self.name)
        self.connected = True
        client.subscribe(f"device/{self.serial}/report")
        self._publish({"pushing": {"command": "pushall"}})
        self._publish({"info": {"command": "get_version"}})

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if self.connected:
            log.info("%s: disconnected (%s)", self.name, reason_code)
        self.connected = False

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            return
        self.last_msg = time.time()
        info = payload.get("info")
        if isinstance(info, dict) and info.get("command") == "get_version":
            modules = [m for m in info.get("module") or [] if isinstance(m, dict)]
            self.versions = {m.get("name"): m.get("sw_ver") for m in modules if m.get("sw_ver")}
            # newer firmware names the printer model, e.g. "Bambu Lab P2S" (no serial number needed)
            for m in modules:
                name = str(m.get("product_name") or "")
                if name.lower().startswith("bambu lab "):
                    self.product_model = product_model_name(name)
                    break
        with self._lock:
            for section in ("print", "system"):
                part = payload.get(section)
                if not isinstance(part, dict):
                    continue
                result = str(part.get("result", "")).lower()
                command = part.get("command")
                if result and result not in ("success", "ok") and command not in (
                    "push_status", "get_version",
                ) and self.control_mode == "direct":
                    reason = part.get("reason") or part.get("err_code") or result
                    self.set_cmd_message(t(
                        "Drucker hat '{command}' abgelehnt ({reason}). "
                        "Ohne Developer Mode erlaubt die Bambu-Firmware nur das Überwachen.",
                        command=command, reason=reason))
                if section == "print":
                    _deep_merge(self.raw, part)

    def _publish(self, payload: dict):
        if not self._client:
            raise PrinterError(t("Nicht verbunden"))
        self._seq += 1
        for section in payload.values():
            if isinstance(section, dict):
                section.setdefault("sequence_id", str(self._seq))
        self._client.publish(f"device/{self.serial}/request", json.dumps(payload))

    # -- state -----------------------------------------------------------
    def snapshot(self) -> dict:
        st = self.base_state()
        st["file_types"] = [".3mf", ".gcode"]
        st["control"] = self.control_mode
        st["model"] = self.model
        online = self.connected and time.time() - self.last_msg < 90
        st["online"] = online
        if not online:
            return st
        with self._lock:
            p = json.loads(json.dumps(self.raw))

        gstate = str(p.get("gcode_state", "")).upper()
        state = GCODE_STATE_MAP.get(gstate, "idle")
        print_error = int(p.get("print_error") or 0)
        if state == "failed" and print_error == CANCELLED_ERROR:
            state = "cancelled"
        st["state"] = state

        if state in ("preparing", "printing", "paused", "finished", "failed", "cancelled"):
            st["progress"] = p.get("mc_percent")
            st["filename"] = p.get("subtask_name") or p.get("gcode_file")
            st["layer"] = p.get("layer_num")
            st["total_layers"] = p.get("total_layer_num")
        if state in ("preparing", "printing", "paused"):
            remaining = p.get("mc_remaining_time")
            if isinstance(remaining, (int, float)):
                st["remaining_s"] = int(remaining) * 60

        temps = [
            ("nozzle", p.get("nozzle_temper"), p.get("nozzle_target_temper")),
            ("bed", p.get("bed_temper"), p.get("bed_target_temper")),
        ]
        chamber, chamber_target = self._chamber(p)
        if chamber is not None:
            temps.append(("chamber", chamber, chamber_target))
        st["temps"] = [
            {"label": label, "cur": _to_float(cur), "target": _to_float(tgt)}
            for label, cur, tgt in temps if cur is not None
        ]

        for light in p.get("lights_report") or []:
            if light.get("node") == "chamber_light":
                st["light"] = light.get("mode") in ("on", "flashing")

        if print_error and print_error != CANCELLED_ERROR:
            st["error"] = t("Druckfehler {code}", code=f"{print_error >> 16:04X}_{print_error & 0xFFFF:04X}")

        hms = []
        for item in p.get("hms") or []:
            attr, code = int(item.get("attr", 0)), int(item.get("code", 0))
            c = hms_code(attr, code)
            hms.append({
                "code": c,
                "severity": HMS_SEVERITY.get(code >> 16, "info"),
                "url": f"https://wiki.bambulab.com/en/{model_family(self.model)}/troubleshooting/hmscode/{c}",
            })
        st["hms"] = hms

        filaments = []
        ams = p.get("ams") or {}
        tray_now = str(ams.get("tray_now", "255"))
        for unit in ams.get("ams") or []:
            for tray in unit.get("tray") or []:
                slot = int(unit.get("id", 0)) * 4 + int(tray.get("id", 0))
                filaments.append({
                    "slot": slot + 1,
                    "type": tray.get("tray_type") or "",
                    "color": _color(tray.get("tray_color")),
                    "active": tray_now == str(slot),
                    # -1 = unknown; 0 is a real value (empty spool)
                    "remain": tray.get("remain") if isinstance(tray.get("remain"), (int, float))
                    and tray.get("remain") >= 0 else None,
                    "uid": _uid(tray.get("tray_uuid")) or _uid(tray.get("tag_uid")),
                })
        vt = p.get("vt_tray")
        if isinstance(vt, dict) and vt.get("tray_type"):
            filaments.append({
                "slot": "Ext",
                "type": vt.get("tray_type"),
                "color": _color(vt.get("tray_color")),
                "active": tray_now == "254",
                "remain": None,
            })
        st["filaments"] = filaments
        # AMS climate: temperature, humidity level 1-5 and (newer firmware) humidity in %
        units = []
        for unit in ams.get("ams") or []:
            uid = int(unit.get("id", 0))
            raw = _to_float(unit.get("humidity_raw"))
            level = _to_float(unit.get("humidity"))
            units.append({
                "name": f"AMS {uid + 1}" if len(ams.get("ams") or []) > 1 else "AMS",
                "temp": _to_float(unit.get("temp")) or None,
                "hum": raw if raw is not None and raw > 0 else None,
                "hum_level": int(level) if level else None,
            })
        st["ams"] = units
        versions = []
        if self.versions.get("ota"):
            versions.append({"label": "Firmware", "value": self.versions["ota"]})
        for name, ver in sorted(self.versions.items()):
            if name.startswith("ams/") or name.startswith("n3f/"):
                versions.append({"label": f"AMS {int(name.split('/')[1]) + 1}", "value": ver})
        st["versions"] = versions
        return st

    @staticmethod
    def _chamber(p: dict):
        """Chamber temperature. Older firmware: 'chamber_temper'. Newer firmware /
        H2 series: device.ctc.info.temp, packed as (target << 16) | current."""
        ctc = (((p.get("device") or {}).get("ctc") or {}).get("info") or {}).get("temp")
        if isinstance(ctc, (int, float)) and ctc > 0:
            ctc = int(ctc)
            return float(ctc & 0xFFFF), (float(ctc >> 16) or None)
        value = p.get("chamber_temper")
        if isinstance(value, (int, float)) and value > 0:
            return value, None
        return None, None

    def raw_status(self) -> dict:
        with self._lock:
            data = json.loads(json.dumps(self.raw))
        data["_versions"] = self.versions
        data["_preview"] = self.preview_debug
        return data

    # -- actions ---------------------------------------------------------
    @property
    def control_mode(self) -> str:
        """monitor (default, works with normal firmware) | direct (Developer Mode) | ha"""
        mode = self.cfg.get("control") or "monitor"
        return mode if mode in ("monitor", "direct", "ha") else "monitor"

    @property
    def control_via_ha(self) -> bool:
        return self.control_mode == "ha"

    async def _command_via_ha(self, action: str):
        from .. import ha  # local import to avoid a cycle
        ents = self.cfg.get("ha_entities") or {}
        try:
            if action in ("pause", "resume", "stop"):
                entity = (ents.get(action) or "").strip()
                if not entity:
                    raise PrinterError(t("Kein HA-Knopf für '{action}' eingerichtet (Einstellungen → Drucker)", action=action))
                await ha.press(entity)
            elif action in ("light_on", "light_off"):
                entity = (ents.get("light") or "").strip()
                if not entity or entity == "direct":
                    await self._command_direct(action)  # the printer accepts the light directly
                else:
                    await ha.set_light(entity, action == "light_on")
            else:
                raise PrinterError(t("Unbekannter Befehl: {action}", action=action))
        except ha.HAError as exc:
            raise PrinterError(t("Home Assistant: {error}", error=exc)) from exc

    async def command(self, action: str):
        if self.control_mode == "monitor":
            if action in ("light_on", "light_off"):
                await self._command_direct(action)  # the firmware accepts the light without Developer Mode
                return
            raise PrinterError(t("Nur Überwachung eingestellt – bitte über Bambu Handy oder Bambu Studio steuern"))
        if self.control_via_ha:
            await self._command_via_ha(action)
            return
        await self._command_direct(action)

    async def _command_direct(self, action: str):
        if not self.connected:
            raise PrinterError(t("Drucker ist nicht verbunden"))
        if action in ("pause", "resume", "stop"):
            self._publish({"print": {"command": action, "param": ""}})
        elif action in ("light_on", "light_off"):
            self._publish({"system": {
                "command": "ledctrl",
                "led_node": "chamber_light",
                "led_mode": "on" if action == "light_on" else "off",
                "led_on_time": 500,
                "led_off_time": 500,
                "loop_times": 0,
                "interval_time": 0,
            }})
        else:
            raise PrinterError(t("Unbekannter Befehl: {action}", action=action))

    # -- job preview / filament (read the .3mf back from the printer) ----
    def _ftp(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ftp = ImplicitFTPS(context=ctx)
        ftp.connect(self.host, 990, timeout=20)
        ftp.login("bblp", self.access_code)
        ftp.prot_p()
        return ftp

    @staticmethod
    def _ftp_read(ftp, cmd: str, limit: int = 200 * 1024 * 1024) -> bytes:
        ftp.voidcmd("TYPE I")
        conn = ftp.transfercmd(cmd)
        chunks, total = [], 0
        try:
            while True:
                block = conn.recv(65536)
                if not block:
                    break
                chunks.append(block)
                total += len(block)
                if total > limit:
                    raise PrinterError(t("Datei zu gross"))
        finally:
            conn.close()
        ftp.voidresp()
        return b"".join(chunks)

    def _fetch_job_meta(self, subtask: str, gcode_file: str) -> dict | None:
        from .. import uploads  # local import to avoid a cycle

        def norm(text):
            text = re.sub(r"(\.gcode)?\.3mf$", "", os.path.basename(str(text)), flags=re.I)
            return re.sub(r"[^0-9a-z]+", "", text.lower())

        want = norm(subtask)
        dbg = {"subtask": subtask, "gcode_file": gcode_file, "folders": {}, "match": None}
        self.preview_debug = dbg
        ftp = self._ftp()
        try:
            path = gcode_file if gcode_file.lower().endswith(".3mf") else None
            if not path:
                candidates = []
                for folder in ("/cache", "/"):
                    try:
                        listing = self._ftp_read(ftp, f"NLST {folder}").decode(errors="replace")
                    except ftplib.Error as exc:
                        dbg["folders"][folder] = f"Error: {exc}"
                        continue
                    # one name per line; names may contain spaces and commas
                    names = [n.strip() for n in listing.splitlines() if n.strip()]
                    dbg["folders"][folder] = names[:60]
                    for n in names:
                        if n.lower().endswith(".3mf"):
                            full = n if n.startswith("/") else f"{folder.rstrip('/')}/{os.path.basename(n)}"
                            candidates.append(full)
                exact = [c for c in candidates if norm(c) == want]
                fuzzy = [c for c in candidates if want and len(want) >= 5
                         and (want in norm(c) or (len(norm(c)) >= 5 and norm(c) in want))]
                path = (exact or fuzzy or [None])[0]
            dbg["match"] = path
            if not path:
                return None
            data = self._ftp_read(ftp, f"RETR {path}")
        finally:
            try:
                ftp.quit()
            except Exception:  # noqa: BLE001
                ftp.close()
        m = re.search(r"plate_(\d+)", gcode_file or "")
        plate = int(m.group(1)) if m else 1
        with tempfile.NamedTemporaryFile(suffix=".3mf") as tmp:
            tmp.write(data)
            tmp.flush()
            return uploads.job_meta_from_3mf(tmp.name, plate)

    async def fetch_job_meta(self, st: dict) -> dict | None:
        if not st.get("filename"):
            return None
        meta = None
        if self.connected:
            with self._lock:
                gcode_file = str(self.raw.get("gcode_file") or "")
            try:
                meta = await asyncio.to_thread(self._fetch_job_meta, st["filename"], gcode_file)
            except (OSError, ftplib.Error, PrinterError) as exc:
                log.info("%s: preview from the printer not available (%s)", self.name, exc)
                self.preview_debug = {**self.preview_debug, "error": str(exc)}
        if not (meta and meta.get("thumb")):
            cover = await self._cover_from_ha()
            if cover:
                meta = {**(meta or {}), "thumb": cover[0], "thumb_type": cover[1]}
        return meta

    async def _cover_from_ha(self):
        """Fallback: cover image of the Home Assistant Bambu Lab integration."""
        from .. import ha  # local import to avoid a cycle
        entity = (self.cfg.get("ha_cover") or "").strip()
        if entity == "off" or not ha.available():
            return None
        try:
            if not entity:
                images = await ha.bambu_images()
                covers = [i for i in images if i["cover"]] or images
                entity = covers[0]["entity_id"] if covers else ""
            if not entity:
                return None
            self.preview_debug = {**self.preview_debug, "ha_cover": entity}
            return await ha.get_image(entity)
        except ha.HAError as exc:
            self.preview_debug = {**self.preview_debug, "ha_cover_error": str(exc)}
            return None

    def _upload(self, path: str, remote_name: str):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ftp = ImplicitFTPS(context=ctx)
        try:
            ftp.connect(self.host, 990, timeout=30)
            ftp.login("bblp", self.access_code)
            ftp.prot_p()
            with open(path, "rb") as fh:
                ftp.store_file(remote_name, fh)
        except (OSError, ftplib.Error) as exc:
            raise PrinterError(t("Upload zum Drucker fehlgeschlagen: {error}", error=exc)) from exc
        finally:
            try:
                ftp.quit()
            except Exception:  # noqa: BLE001
                ftp.close()

    async def send_file(self, path: str, filename: str, opts: dict):
        if not self.connected:
            raise PrinterError(t("Drucker ist nicht verbunden"))
        remote = os.path.basename(filename).replace(" ", "_")
        if opts.get("start") and self.control_mode != "direct":
            raise PrinterError(t("Druckstart ist nur mit Developer Mode möglich. Bitte „Nur hochladen“ wählen "
                                 "und den Druck in Bambu Studio oder der Handy-App starten."))
        await asyncio.to_thread(self._upload, path, remote)
        if not opts.get("start"):
            return t("'{file}' auf den Drucker hochgeladen.", file=remote)

        if remote.lower().endswith(".gcode"):
            self._publish({"print": {"command": "gcode_file", "param": f"/sdcard/{remote}"}})
        else:
            plate = int(opts.get("plate") or 1)
            use_ams = bool(opts.get("use_ams"))
            cmd = {
                "command": "project_file",
                "param": f"Metadata/plate_{plate}.gcode",
                "url": f"file:///sdcard/{remote}",
                "subtask_name": os.path.splitext(remote)[0],
                "project_id": "0",
                "profile_id": "0",
                "task_id": "0",
                "subtask_id": "0",
                "md5": "",
                "timelapse": bool(opts.get("timelapse")),
                "bed_type": "auto",
                "bed_levelling": bool(opts.get("bed_leveling", True)),
                "bed_leveling": bool(opts.get("bed_leveling", True)),
                "flow_cali": False,
                "vibration_cali": False,
                "layer_inspect": False,
                "use_ams": use_ams,
            }
            mapping = opts.get("ams_mapping")
            if use_ams and mapping:
                cmd["ams_mapping"] = mapping
            self._publish({"print": cmd})
        return t("'{file}' hochgeladen und Druckstart gesendet.", file=remote)

    @property
    def model(self) -> str | None:
        by_serial = MODEL_BY_PREFIX.get(self.serial[:3].upper()) if self.serial else None
        return by_serial or getattr(self, "product_model", None)

    def camera_kind(self) -> str:
        """rtsp (X1, H2: video stream on port 322) or jpeg (P1, A1: still images on port 6000)."""
        kind = self.cfg.get("camera_type") or "auto"
        if kind in ("rtsp", "jpeg"):
            return kind
        return "jpeg" if model_family(self.model) in ("p1", "a1") else "rtsp"

    def camera_source(self) -> str:
        """direct (default) | compat (compatibility mode for slow or lagging cameras)"""
        src = self.cfg.get("camera_source") or "direct"
        return src if src in ("direct", "compat") else "direct"

    def camera_sources(self) -> list:
        if not self.cfg.get("camera", True):
            return []
        if not self.host or not self.access_code:
            return []
        compat = self.camera_source() == "compat"
        if self.camera_kind() == "jpeg":
            return [{
                "id": f"{self.id}-cam",
                "name": self.name,
                "url": f"bambu-jpeg://{self.host}:6000",   # no access code in the URL (logs!)
                "auth": self.access_code,
                "mode": "bambu_jpeg",
                "printer_id": self.id,
                "compat": compat,
            }]
        return [{
            "id": f"{self.id}-cam",
            "name": self.name,
            "url": f"rtsps://bblp:{self.access_code}@{self.host}:322/streaming/live/1",
            "mode": "ffmpeg",
            "printer_id": self.id,
            "compat": compat,
        }]
