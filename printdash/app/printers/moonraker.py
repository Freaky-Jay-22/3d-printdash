"""Klipper/Moonraker driver (e.g. Snapmaker U1, Voron, Sovol ...).

Talks to the Moonraker HTTP API directly: status polling, pause/resume/
cancel, G-code for the light, file upload with optional print start.
"""
import asyncio
import json
import logging
import os
import re
import time
from urllib.parse import urlparse, quote

import httpx

from ..config import redact
from ..i18n import t
from .base import BasePrinter, PrinterError

log = logging.getLogger("printdash.moonraker")

PRINT_STATE_MAP = {
    "standby": "idle",
    "printing": "printing",
    "paused": "paused",
    "complete": "finished",
    "cancelled": "cancelled",
    "error": "failed",
}
LIGHT_PREFIXES = ("output_pin ", "led ", "neopixel ", "dotstar ", "pca9533 ", "pca9632 ")


def _to_float(value):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _parse_color(value, argb=False, rgb=False):
    """Accepts 'RRGGBBAA', '#RRGGBB', ARGB/RGB integers. Returns '#rrggbb' or None."""
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)):
        v = int(value)
        return f"#{v & 0xFFFFFF:06x}" if (argb or rgb or v > 0) else None
    text = str(value).strip().lstrip("#")
    if text.lower().startswith("0x"):
        text = text[2:]
    if re.fullmatch(r"[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", text):
        return "#" + text[:6].lower()
    return None


class MoonrakerPrinter(BasePrinter):
    type = "moonraker"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        url = (cfg.get("url") or "").strip().rstrip("/")
        if url and not url.startswith(("http://", "https://")):
            url = "http://" + url
        self.url = url
        parsed = urlparse(url) if url else None
        self.web_base = f"{parsed.scheme}://{parsed.hostname}" if parsed else ""
        headers = {}
        if cfg.get("api_key"):
            headers["X-Api-Key"] = cfg["api_key"]
        self.http = httpx.AsyncClient(base_url=url or "http://invalid", headers=headers, timeout=10)
        self.objects: list = []
        self.extruders: list = []
        self.chamber_sensor = None
        self.status: dict = {}
        self.online = False
        self.webcams: list = []
        self.snapmaker_camera = False
        self.snapmaker_error = None
        self._task = None
        self._meta_file = None
        self._estimated_time = None
        self._meta: dict = {}
        self.versions: list = []

    # -- lifecycle -------------------------------------------------------
    async def start(self):
        if not self.url:
            log.warning("%s: no URL configured", self.name)
            return
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
        await self.http.aclose()

    async def _get(self, path, **kw):
        r = await self.http.get(path, **kw)
        r.raise_for_status()
        return r.json().get("result")

    async def _post(self, path, **kw):
        r = await self.http.post(path, **kw)
        if r.status_code >= 400:
            try:
                msg = r.json().get("error", {}).get("message")
            except ValueError:
                msg = r.text[:200]
            raise PrinterError(t("Moonraker: {error}", error=msg or r.status_code))
        return r.json().get("result")

    async def _discover(self):
        self.objects = (await self._get("/printer/objects/list")).get("objects", [])
        self.extruders = sorted(o for o in self.objects if re.fullmatch(r"extruder\d*", o))
        self.chamber_sensor = self._pick_chamber_sensor()
        try:
            cams = (await self._get("/server/webcams/list")).get("webcams", [])
            self.webcams = [c for c in cams if c.get("enabled", True)]
        except httpx.HTTPError:
            self.webcams = []
        if not self.cfg.get("camera_url") and self.cfg.get("camera") is not False:
            await self._detect_snapmaker_camera()

    TEMP_PREFIXES = ("temperature_sensor ", "temperature_fan ", "heater_generic ")

    def temp_sensors(self) -> list:
        return [o for o in self.objects if o.startswith(self.TEMP_PREFIXES)]

    def _pick_chamber_sensor(self):
        """Configured chamber sensor, or one whose name suggests the chamber (U1: 'cavity')."""
        configured = (self.cfg.get("chamber_sensor") or "").strip()
        if configured == "none":
            return None
        if configured:
            return configured
        for word in ("chamber", "cavity", "enclosure", "kammer", "box"):
            for o in self.temp_sensors():
                if word in o.split(" ", 1)[-1].lower():
                    return o
        return None

    def light_object(self) -> str:
        """Configured light object, or a sensible automatic choice (e.g. U1 'led cavity_led')."""
        configured = (self.cfg.get("light_object") or "").strip()
        if configured or self.cfg.get("light_on_gcode"):
            return configured
        cands = self.light_candidates()
        for word in ("cavity", "chamber", "case", "light", "led"):
            for c in cands:
                if word in c.split(" ", 1)[-1].lower():
                    return c
        return ""

    def light_candidates(self) -> list:
        return [o for o in self.objects if o.startswith(LIGHT_PREFIXES)]

    async def _poll_loop(self):
        discovered = False
        while True:
            try:
                if not discovered:
                    await self._discover()
                    await self._load_versions()
                    discovered = True
                objs = ["webhooks", "print_stats", "virtual_sdcard",
                        "display_status", "toolhead", "heater_bed", *self.extruders]
                if self.chamber_sensor:
                    objs.append(self.chamber_sensor)
                light_obj = self.light_object()
                if light_obj:
                    objs.append(light_obj)
                for extra in ("print_task_config", "filament_detect"):
                    if extra in self.objects:
                        objs.append(extra)
                res = await self._post(
                    "/printer/objects/query", json={"objects": {o: None for o in objs}}
                )
                self.status = res.get("status", {})
                self.online = True
                await self._update_metadata()
            except (httpx.HTTPError, PrinterError, ValueError) as exc:
                if self.online:
                    log.info("%s: not reachable (%s)", self.name, redact(exc))
                self.online = False
                discovered = False
                await asyncio.sleep(5)
                continue
            await asyncio.sleep(2)

    async def _update_metadata(self):
        filename = self.status.get("print_stats", {}).get("filename")
        if filename == self._meta_file:
            return
        self._meta_file = filename
        self._estimated_time = None
        self._meta = {}
        if filename:
            try:
                meta = await self._get(f"/server/files/metadata?filename={quote(filename)}")
                self._meta = meta or {}
                self._estimated_time = self._meta.get("estimated_time")
            except httpx.HTTPError:
                pass

    async def _load_versions(self):
        versions = []
        try:
            sysinfo = (await self._get("/machine/system_info")).get("system_info", {})
            dist = sysinfo.get("distribution") or {}
            name = " ".join(str(x) for x in (dist.get("name"), dist.get("version")) if x)
            if name:
                versions.append({"label": "System", "value": name})
        except (httpx.HTTPError, AttributeError):
            pass
        try:
            info = await self._get("/printer/info")
            if info.get("software_version"):
                versions.append({"label": "Klipper", "value": info["software_version"]})
        except httpx.HTTPError:
            pass
        try:
            sinfo = await self._get("/server/info")
            if sinfo.get("moonraker_version"):
                versions.append({"label": "Moonraker", "value": sinfo["moonraker_version"]})
        except httpx.HTTPError:
            pass
        self.versions = versions

    async def fetch_job_meta(self, st: dict) -> dict | None:
        filename = st.get("filename")
        if not filename or not self.online:
            return None
        meta = self._meta if self._meta_file == filename and self._meta else None
        if meta is None:
            try:
                meta = await self._get(f"/server/files/metadata?filename={quote(filename)}") or {}
            except httpx.HTTPError:
                return None
        out = {
            "weight_g": round(meta["filament_weight_total"], 1) if meta.get("filament_weight_total") else None,
            "length_m": round(meta["filament_total"] / 1000, 2) if meta.get("filament_total") else None,
            "thumb": None, "thumb_type": "image/png",
        }
        # filament per material: Moonraker metadata, else the slicer summary at the end of the file
        from ..uploads import parse_gcode_text
        types = [t.strip() for t in str(meta.get("filament_type") or "").split(";") if t.strip()]
        weights = meta.get("filament_weights")
        if isinstance(weights, list) and types:
            out["materials"] = [{"type": types[i] if i < len(types) else types[-1], "g": float(g)}
                                for i, g in enumerate(weights) if g]
        else:
            try:
                r = await self.http.get(f"/server/files/gcodes/{quote(filename)}",
                                        headers={"Range": "bytes=-400000"}, timeout=20)
                if r.status_code in (200, 206) and len(r.content) <= 5_000_000:
                    parsed = parse_gcode_text(r.content.decode(errors="replace"))
                    out["materials"] = parsed["materials"]
                    out["weight_g"] = out["weight_g"] or parsed["weight_g"]
                    out["length_m"] = out["length_m"] or parsed["length_m"]
            except httpx.HTTPError:
                pass
            if not out.get("materials") and out["weight_g"] and len(set(types)) == 1:
                out["materials"] = [{"type": types[0], "g": out["weight_g"]}]
        thumbs = [t for t in meta.get("thumbnails") or [] if t.get("relative_path")]
        if thumbs:
            best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
            folder = os.path.dirname(filename)
            path = f"{folder}/{best['relative_path']}" if folder else best["relative_path"]
            try:
                r = await self.http.get(f"/server/files/gcodes/{quote(path)}")
                if r.status_code == 200:
                    out["thumb"] = r.content
                    out["thumb_type"] = r.headers.get("content-type", "image/png")
            except httpx.HTTPError:
                pass
        return out

    # -- state -----------------------------------------------------------
    def snapshot(self) -> dict:
        st = self.base_state()
        st["file_types"] = [".gcode"]
        st["online"] = self.online
        if not self.online:
            return st
        s = self.status
        wh = s.get("webhooks", {})
        ps = s.get("print_stats", {})

        if wh.get("state") in ("shutdown", "error"):
            st["state"] = "error"
            st["error"] = wh.get("state_message") or t("Klipper-Fehler")
        elif wh.get("state") == "startup":
            st["state"] = "preparing"
        else:
            st["state"] = PRINT_STATE_MAP.get(ps.get("state"), "idle")
            if st["state"] == "failed":
                st["error"] = ps.get("message") or t("Druck mit Fehler abgebrochen")

        if st["state"] in ("printing", "paused", "finished", "failed", "cancelled"):
            st["filename"] = ps.get("filename")
            progress = s.get("display_status", {}).get("progress") or \
                s.get("virtual_sdcard", {}).get("progress") or 0
            st["progress"] = round(progress * 100) if st["state"] != "finished" else 100
            info = ps.get("info") or {}
            st["layer"] = info.get("current_layer")
            st["total_layers"] = info.get("total_layer")
            duration = ps.get("print_duration") or 0
            st["elapsed_s"] = int(ps.get("total_duration") or 0)
            if st["state"] in ("printing", "paused"):
                if self._estimated_time:
                    st["remaining_s"] = max(0, int(self._estimated_time - duration))
                elif progress > 0.02:
                    st["remaining_s"] = int(duration / progress - duration)

        temps = []
        active = s.get("toolhead", {}).get("extruder")
        multi = len(self.extruders) > 1
        for i, name in enumerate(self.extruders):
            ex = s.get(name, {})
            if "temperature" not in ex:
                continue
            label = f"T{i}" if multi else "nozzle"
            temps.append({
                "label": label,
                "cur": _to_float(ex.get("temperature")),
                "target": _to_float(ex.get("target")),
                "active": multi and name == active,
            })
        bed = s.get("heater_bed", {})
        if "temperature" in bed:
            temps.append({"label": "bed", "cur": _to_float(bed.get("temperature")),
                          "target": _to_float(bed.get("target"))})
        if self.chamber_sensor and self.chamber_sensor in s:
            cs = s[self.chamber_sensor]
            temps.append({"label": "chamber",
                          "cur": _to_float(cs.get("temperature")),
                          "target": _to_float(cs.get("target")) or None})
        st["temps"] = temps

        st["filaments"] = self._filaments(s, active)
        st["versions"] = self.versions

        light_obj = self.light_object()
        if light_obj and light_obj in s:
            lo = s[light_obj]
            if "value" in lo:
                st["light"] = (lo.get("value") or 0) > 0
            elif "color_data" in lo:
                st["light"] = any(any(ch > 0 for ch in px) for px in lo["color_data"] or [])
        elif self.cfg.get("light_on_gcode"):
            st["light"] = False  # unknown state, but switchable
        return st

    def _filaments(self, s: dict, active_extruder) -> list:
        """Loaded filament per toolhead (Snapmaker U1: print_task_config / filament_detect)."""
        ptc = s.get("print_task_config") or {}
        rfid = (s.get("filament_detect") or {}).get("info") or []
        if not ptc and not rfid:
            return []

        def at(key, i):
            arr = ptc.get(key)
            return arr[i] if isinstance(arr, list) and i < len(arr) else None

        count = max(len(self.extruders), len(ptc.get("filament_type") or []), len(rfid))
        out = []
        for i in range(count):
            tag = rfid[i] if i < len(rfid) and isinstance(rfid[i], dict) else {}
            exist = at("filament_exist", i)
            ftype = at("filament_type", i) or tag.get("MAIN_TYPE") or ""
            sub = at("filament_sub_type", i) or tag.get("SUB_TYPE") or ""
            vendor = at("filament_vendor", i) or tag.get("VENDOR") or ""
            color = _parse_color(at("filament_color_rgba", i)) \
                or _parse_color(tag.get("ARGB_COLOR"), argb=True) \
                or _parse_color(tag.get("RGB_1"), rgb=True)
            if exist is False or str(ftype).upper() in ("", "NONE"):
                ftype, color = "", None
            label = ftype
            if sub and str(sub).lower() not in ("", "none", "basic") and ftype:
                label = f"{ftype} {sub}"
            name = self.extruders[i] if i < len(self.extruders) else None
            uid = str(tag.get("CARD_UID") or "").strip()
            out.append({
                "uid": uid.upper() if uid and set(uid) - {"0"} and ftype else None,
                "slot": f"T{i}",
                "type": label,
                "color": color,
                "vendor": vendor if ftype else "",
                "active": bool(name) and name == active_extruder,
                "remain": None,
            })
        return out

    # -- actions ---------------------------------------------------------
    async def _gcode(self, script: str):
        await self._post("/printer/gcode/script", json={"script": script})

    def _light_gcode(self, on: bool) -> str:
        custom = self.cfg.get("light_on_gcode" if on else "light_off_gcode")
        if custom:
            return custom
        obj = self.light_object()
        if not obj:
            raise PrinterError(t("Kein Licht konfiguriert (Einstellungen → Drucker)"))
        kind, _, name = obj.partition(" ")
        v = 1 if on else 0
        if kind == "output_pin":
            return f"SET_PIN PIN={name} VALUE={v}"
        # unused colour channels are ignored by Klipper (U1 cavity_led is white-only)
        return f"SET_LED LED={name} RED={v} GREEN={v} BLUE={v} WHITE={v}"

    async def command(self, action: str):
        if not self.online:
            raise PrinterError(t("Drucker ist nicht erreichbar"))
        try:
            if action == "pause":
                await self._post("/printer/print/pause")
            elif action == "resume":
                await self._post("/printer/print/resume")
            elif action == "stop":
                await self._post("/printer/print/cancel")
            elif action in ("light_on", "light_off"):
                await self._gcode(self._light_gcode(action == "light_on"))
            else:
                raise PrinterError(t("Unbekannter Befehl: {action}", action=action))
        except httpx.HTTPError as exc:
            raise PrinterError(t("Moonraker nicht erreichbar: {error}", error=redact(exc))) from exc

    async def send_file(self, path: str, filename: str, opts: dict):
        if not self.online:
            raise PrinterError(t("Drucker ist nicht erreichbar"))
        name = os.path.basename(filename)
        try:
            with open(path, "rb") as fh:
                r = await self.http.post(
                    "/server/files/upload",
                    files={"file": (name, fh, "application/octet-stream")},
                    data={"root": "gcodes", "print": "true" if opts.get("start") else "false"},
                    timeout=httpx.Timeout(600, connect=10),
                )
        except httpx.HTTPError as exc:
            raise PrinterError(t("Upload fehlgeschlagen: {error}", error=redact(exc))) from exc
        if r.status_code >= 400:
            raise PrinterError(t("Upload fehlgeschlagen: {error}", error=r.text[:200]))
        return t("'{file}' hochgeladen und Druck gestartet." if opts.get("start") else "'{file}' hochgeladen.", file=name)

    def _abs(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith(("http://", "https://", "rtsp://", "rtsps://")):
            # "localhost" in a webcam URL means the printer itself
            parsed = urlparse(url)
            if parsed.hostname in ("localhost", "127.0.0.1"):
                host = urlparse(self.url).hostname
                url = url.replace(parsed.hostname, host, 1)
            return url
        return self.web_base + ("" if url.startswith("/") else "/") + url

    # -- Snapmaker U1 stock camera ----------------------------------------
    # The stock firmware has no video stream. The built-in camera only writes
    # a still image to <moonraker>/server/files/camera/monitor.jpg while it is
    # kept awake with the JSON-RPC call "camera.start_monitor".
    SNAPMAKER_IMAGE = "/server/files/camera/monitor.jpg"

    async def snapmaker_camera_keepalive(self):
        request = {"jsonrpc": "2.0", "method": "camera.start_monitor",
                   "params": {"domain": "lan", "interval": 0}, "id": int(time.time() * 1000)}
        errors = []
        # 1) JSON-RPC over HTTP
        try:
            r = await self.http.post("/server/jsonrpc", json=request)
            if r.status_code < 400:
                data = r.json()
                if not data.get("error"):
                    return
                errors.append(f"HTTP: {data['error'].get('message', t('Fehler'))}")
            else:
                errors.append(f"HTTP {r.status_code}")
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"HTTP: {exc}")
        # 2) websocket, 3) websocket with a one-shot token (if Moonraker requires login)
        try:
            await self._jsonrpc_ws(request)
            return
        except Exception as exc:  # noqa: BLE001
            errors.append(f"WS: {exc or exc.__class__.__name__}")
        try:
            token = await self._get("/access/oneshot_token")
            await self._jsonrpc_ws(request, token=token)
            return
        except Exception as exc:  # noqa: BLE001
            errors.append(f"WS+Token: {exc or exc.__class__.__name__}")
        raise PrinterError(" | ".join(errors))

    async def _jsonrpc_ws(self, request: dict, token: str | None = None):
        import websockets  # installed with uvicorn[standard]
        ws_url = self.url.replace("https://", "wss://").replace("http://", "ws://") + "/websocket"
        if token:
            ws_url += f"?token={token}"
        headers = {"X-Api-Key": self.cfg["api_key"]} if self.cfg.get("api_key") else {}
        async with websockets.connect(ws_url, additional_headers=headers, open_timeout=5) as ws:
            await ws.send(json.dumps(request))
            deadline = time.time() + 5
            while time.time() < deadline:
                msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
                if msg.get("id") == request["id"]:
                    if msg.get("error"):
                        raise PrinterError(msg["error"].get("message", t("Fehler")))
                    return
        raise PrinterError(t("Keine Antwort vom Drucker"))

    async def _detect_snapmaker_camera(self):
        try:
            await self.snapmaker_camera_keepalive()
            self.snapmaker_camera = True
            self.snapmaker_error = None
            log.info("%s: Snapmaker camera found", self.name)
        except Exception as exc:  # noqa: BLE001
            self.snapmaker_camera = False
            self.snapmaker_error = str(exc) or exc.__class__.__name__

    def camera_sources(self) -> list:
        if self.cfg.get("camera") is False:
            return []
        override = (self.cfg.get("camera_url") or "").strip()
        if override:
            if self.SNAPMAKER_IMAGE in override:
                return [self._snapmaker_source(self._abs(override))]
            mode = "snapshot" if override.lower().split("?")[0].endswith((".jpg", ".jpeg")) \
                or "action=snapshot" in override else "ffmpeg"
            return [{"id": f"{self.id}-cam", "name": self.name, "url": override,
                     "mode": mode, "printer_id": self.id}]
        if self.snapmaker_camera:
            # stock U1: webcam entries in Moonraker point to streams that do not exist
            return [self._snapmaker_source(self.url + self.SNAPMAKER_IMAGE)]
        out = []
        for i, cam in enumerate(self.webcams):
            service = (cam.get("service") or "").lower()
            stream, snap = self._abs(cam.get("stream_url")), self._abs(cam.get("snapshot_url"))
            if self.SNAPMAKER_IMAGE in (stream + snap):
                out.append(self._snapmaker_source(snap or stream, i))
                continue
            if "mjpeg" in service or "uv4l" in service or (stream and not snap):
                url, mode = stream, "ffmpeg"
            elif snap:
                url, mode = snap, "snapshot"
            else:
                continue
            out.append({
                "id": f"{self.id}-cam{i if i else ''}",
                "name": self.name if i == 0 else f"{self.name} {cam.get('name', i + 1)}",
                "url": url,
                "mode": mode,
                "printer_id": self.id,
            })
        return out

    def _snapmaker_source(self, url: str, index: int = 0) -> dict:
        return {
            "id": f"{self.id}-cam{index if index else ''}",
            "name": self.name,
            "url": url,
            "mode": "snapshot",
            "printer_id": self.id,
            "keepalive": self.snapmaker_camera_keepalive,
        }


async def probe(url: str, api_key: str = "") -> dict:
    """Used by the settings page: check reachability and list light objects."""
    p = MoonrakerPrinter({"id": "probe", "url": url, "api_key": api_key})
    try:
        await p._discover()
        info = await p._get("/printer/info")
        camera = {"webcams": [{"name": c.get("name"), "service": c.get("service"),
                               "stream_url": redact(c.get("stream_url") or ""),
                               "snapshot_url": redact(c.get("snapshot_url") or "")}
                              for c in p.webcams],
                  "snapmaker": p.snapmaker_camera, "snapmaker_error": redact(p.snapmaker_error or "") or None}
        if p.snapmaker_camera:
            await asyncio.sleep(1.5)
            try:
                r = await p.http.get(p.SNAPMAKER_IMAGE)
                camera["image"] = t("HTTP {code}, {size} Bytes, JPEG ok" if r.content[:2] == b"\xff\xd8"
                                    else "HTTP {code}, {size} Bytes, kein JPEG", code=r.status_code, size=len(r.content))
            except httpx.HTTPError as exc:
                camera["image"] = t("Fehler: {error}", error=redact(exc))
        return {
            "camera": camera,
            "ok": True,
            "hostname": info.get("hostname"),
            "state": info.get("state"),
            "lights": p.light_candidates(),
            "auto_light": p.light_object(),
            "sensors": p.temp_sensors(),
            "auto_chamber": p.chamber_sensor,
            "cameras": [redact(c["url"]) for c in p.camera_sources()],
            "extruders": p.extruders,
        }
    except (httpx.HTTPError, PrinterError, ValueError) as exc:
        return {"ok": False, "error": redact(exc)}
    finally:
        await p.http.aclose()
