"""Creality printers with the stock firmware (K1 series, no root needed). Experimental.

The printer has its own websocket on port 9999 and pushes JSON objects with the fields that
changed. 3D-PrintDash keeps the latest value of every field and builds the normal state from it.
Every field is written to the log once (and state / error changes always), so the log of a
tester shows what a printer model really sends.
"""
import asyncio
import json
import logging
import os
import time

import httpx

from ..config import redact
from ..i18n import t
from .base import BasePrinter, PrinterError

log = logging.getLogger("printdash.creality")

PORT = 9999
SILENT_ASK_S = 10       # no data for this long: ask for all values
SILENT_RECONNECT_S = 30  # still nothing: connect again
ACTIVE_CODES = (0, 7, 9)  # busy around a print (starting, finishing a cancel ...)
# changes of these fields are always logged (status, errors, filament sensor, filament system)
WATCHED = ("state", "deviceState", "err", "withSelfTest", "printFileName", "materialDetect",
           "materialDetector1", "materialStatus", "feedState", "cfsConnect")


def _num(value, digits=1):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _int(value):
    v = _num(value, 0)
    return int(v) if v is not None else None


def _short(value) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= 200 else text[:200] + " …"


def _version_parts(text) -> dict:
    """'printer hw ver:;printer sw ver:;DWIN hw ver:CR4CU…;DWIN sw ver:1.3.5.22;' →
    firmware / hardware. Printer values win over the display (DWIN) values when filled."""
    if not isinstance(text, str) or "ver:" not in text:
        return {}
    parts = {}
    for item in text.split(";"):
        name, _, value = item.partition(":")
        if value.strip():
            parts[name.strip().lower()] = value.strip()
    out = {}
    fw = parts.get("printer sw ver") or parts.get("dwin sw ver")
    hw = parts.get("printer hw ver") or parts.get("dwin hw ver")
    if fw:
        out["firmware"] = fw
    if hw:
        out["hardware"] = hw
    return out


class CrealityPrinter(BasePrinter):
    type = "creality"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.host = (cfg.get("host") or "").strip()
        self.data: dict = {}
        self.online = False
        self._ws = None
        self._task = None
        self._last_rx = 0.0
        self._seen: set = set()
        self._err_ignored = None  # error code that was already there when connecting
        self._cam_note = False

    # -- lifecycle -------------------------------------------------------
    async def start(self):
        if not self.host:
            log.warning("%s: no IP address configured", self.name)
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        if self._task:
            self._task.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass

    async def _run(self):
        import websockets
        while True:
            try:
                async with websockets.connect(
                    f"ws://{self.host}:{PORT}", subprotocols=["wsslicer"],
                    open_timeout=10, ping_interval=None, max_size=8 * 1024 * 1024,
                ) as ws:
                    self._ws = ws
                    self._last_rx = time.time()
                    log.info("%s: connected", self.name)
                    await self._send({"method": "get", "params": {"ReqPrinterPara": 1}})
                    watch = asyncio.create_task(self._watch(ws))
                    try:
                        async for message in ws:
                            await self._receive(ws, message)
                    finally:
                        watch.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                if self.online:
                    log.info("%s: not reachable (%s)", self.name, redact(exc))
            self._ws = None
            if self.online:
                log.info("%s: connection closed", self.name)
            self.online = False
            await asyncio.sleep(5)

    async def _watch(self, ws):
        """The printer only sends changes: ask when it is quiet, reconnect when it stays quiet."""
        asked = False
        while True:
            await asyncio.sleep(2)
            quiet = time.time() - self._last_rx
            if quiet > SILENT_RECONNECT_S:
                log.info("%s: no data for %s s, connecting again", self.name, int(quiet))
                await ws.close()
                return
            if quiet > SILENT_ASK_S and not asked:
                asked = True
                await self._send({"method": "get", "params": {"ReqPrinterPara": 1}})
            elif quiet <= SILENT_ASK_S:
                asked = False

    async def _send(self, obj):
        if self._ws is None:
            raise PrinterError(t("Drucker ist nicht erreichbar"))
        await self._ws.send(json.dumps(obj, separators=(",", ":")))

    async def _receive(self, ws, message):
        self._last_rx = time.time()
        if isinstance(message, bytes):
            message = message.decode(errors="replace")
        text = message.strip()
        if text == "ok":
            return
        try:
            payload = json.loads(text)
        except ValueError:
            log.info("%s: not JSON: %s", self.name, _short(text))
            return
        if not isinstance(payload, dict):
            log.info("%s: unknown message: %s", self.name, _short(payload))
            return
        if payload.get("ModeCode") == "heart_beat":
            await ws.send("ok")
            return
        if not self.online:
            self.online = True
        self._note_fields(payload)
        self.data.update(payload)

    def _note_fields(self, payload: dict):
        """Log every field once, and every change of state and error code."""
        for key, value in payload.items():
            if key not in self._seen:
                self._seen.add(key)
                log.info("%s: field %s = %s", self.name, key, _short(value))
            elif key in WATCHED and value != self.data.get(key):
                log.info("%s: %s %s → %s", self.name, key,
                         _short(self.data.get(key)), _short(value))

    # -- state -----------------------------------------------------------
    def _error_code(self) -> int:
        err = self.data.get("err")
        code = _int(err.get("errcode") if isinstance(err, dict) else err) or 0
        # some codes are never cleared by the printer: ignore the one it had when connecting
        if self._err_ignored is None and "err" in self.data:
            self._err_ignored = code
        if code == 0:
            self._err_ignored = 0
        return 0 if code == self._err_ignored else code

    def snapshot(self) -> dict:
        st = self.base_state()
        st["online"] = self.online
        st["file_types"] = []
        if not self.online:
            return st
        d = self.data
        code = d.get("state")
        path = d.get("printFileName") or ""
        progress = _num(d.get("printProgress") if d.get("printProgress") is not None else d.get("dProgress"), 0)
        left = _int(d.get("printLeftTime"))
        paused = code == 5 or d.get("pause") == 1 or bool(d.get("paused") or d.get("isPaused"))
        self_test = _int(d.get("withSelfTest")) or 0
        if path:
            # 100 % can still come with time left; the print ends with state 2 or no time left
            if code == 2 or (progress is not None and progress >= 100 and not (code in (1, 5) and left)):
                state = "finished"
            elif paused:
                state = "paused"
            elif code == 4:
                state = "cancelled"
            elif code == 1:
                state = "printing"
            elif code in ACTIVE_CODES:
                state = "preparing"
            else:
                state = "idle"
        else:
            state = "idle"
        if 1 <= self_test <= 99 and state == "idle":
            state = "preparing"
        err = self._error_code()
        if err:
            st["error"] = t("Druckerfehler {code}", code=err)
            if state not in ("printing", "paused", "preparing"):
                state = "error"
        st["state"] = state
        if path and state != "idle":
            st["filename"] = os.path.basename(path)
            st["progress"] = 100 if state == "finished" else (int(progress) if progress is not None else None)
            st["layer"] = _int(d.get("layer"))
            st["total_layers"] = _int(d.get("TotalLayer"))
            st["elapsed_s"] = _int(d.get("printJobTime"))
            if state in ("printing", "paused", "preparing") and left is not None:
                st["remaining_s"] = max(0, left)
            used = _num(d.get("usedMaterialLength"))
            st["filament_used_mm"] = used if used and used > 0 else None

        temps = []
        if "nozzleTemp" in d:
            temps.append({"label": "nozzle", "cur": _num(d.get("nozzleTemp")),
                          "target": _num(d.get("targetNozzleTemp"))})
        if "bedTemp0" in d:
            temps.append({"label": "bed", "cur": _num(d.get("bedTemp0")),
                          "target": _num(d.get("targetBedTemp0"))})
        if "boxTemp" in d:
            temps.append({"label": "chamber", "cur": _num(d.get("boxTemp")),
                          "target": _num(d.get("targetBoxTemp")) or None})
        st["temps"] = temps
        if "lightSw" in d:
            st["light"] = bool(_int(d.get("lightSw")))
        versions = []
        if d.get("model"):
            versions.append({"label": t("Modell"), "value": str(d["model"])})
        info = _version_parts(d.get("modelVersion"))
        for key, label in (("firmware", "Firmware"), ("hardware", "Hardware")):
            if info.get(key):
                versions.append({"label": label, "value": info[key]})
        if d.get("modelVersion") and not info:
            versions.append({"label": t("Modellversion"), "value": str(d["modelVersion"])})
        if d.get("hostname"):
            versions.append({"label": "Hostname", "value": str(d["hostname"])})
        st["versions"] = versions
        return st

    # -- actions ---------------------------------------------------------
    async def command(self, action: str):
        if not self.online:
            raise PrinterError(t("Drucker ist nicht erreichbar"))
        params = {"pause": {"pause": 1}, "resume": {"pause": 0}, "stop": {"stop": 1},
                  "light_on": {"lightSw": 1}, "light_off": {"lightSw": 0}}.get(action)
        if params is None:
            raise PrinterError(t("Unbekannter Befehl: {action}", action=action))
        try:
            await self._send({"method": "set", "params": params})
        except PrinterError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PrinterError(t("Drucker ist nicht erreichbar")) from exc
        log.info("%s: command %s sent", self.name, action)

    async def send_file(self, path: str, filename: str, opts: dict):
        raise PrinterError(t("Dateien senden ist bei Creality-Druckern noch nicht möglich."))

    async def fetch_job_meta(self, st: dict) -> dict | None:
        if not st.get("filename") or not self.online:
            return None
        url = f"http://{self.host}/downloads/original/current_print_image.png"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
            if r.status_code == 200 and r.content[:4] == b"\x89PNG":
                return {"thumb": r.content, "thumb_type": "image/png"}
            log.info("%s: no preview image (HTTP %s)", self.name, r.status_code)
        except httpx.HTTPError as exc:
            log.info("%s: no preview image (%s)", self.name, redact(exc))
        return None

    def camera_sources(self) -> list:
        if self.cfg.get("camera") is False:
            return []
        entity = (self.cfg.get("camera_entity") or "").strip()
        if entity:  # camera from Home Assistant, e.g. when an integration already holds it
            return [{"id": f"{self.id}-cam", "name": self.name, "url": entity,
                     "mode": "ha_camera", "printer_id": self.id}]
        override = (self.cfg.get("camera_url") or "").strip()
        if override:
            mode = "snapshot" if override.lower().split("?")[0].endswith((".jpg", ".jpeg")) \
                or "action=snapshot" in override else "ffmpeg"
            return [{"id": f"{self.id}-cam", "name": self.name, "url": override,
                     "mode": mode, "printer_id": self.id}]
        if not self.data.get("model") and "webrtcSupport" not in self.data:
            return []  # not known yet which camera the firmware has
        if self.data.get("webrtcSupport") == 1:
            if not self._cam_note:
                self._cam_note = True
                log.info("%s: camera uses WebRTC (newer firmware)", self.name)
            return [{"id": f"{self.id}-cam", "name": self.name,
                     "url": f"http://{self.host}:8000/call/webrtc_local", "mode": "creality_webrtc",
                     "printer_id": self.id}]
        return [{"id": f"{self.id}-cam", "name": self.name,
                 "url": f"http://{self.host}:8080/?action=stream", "mode": "ffmpeg",
                 "printer_id": self.id}]
