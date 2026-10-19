"""Owns printers and cameras, watches state changes, writes history, notifies."""
import asyncio
import logging
import re
import time

from . import config as config_store
from . import costs, filament, ha, history, i18n, maintenance, notify, rooms, system
from .i18n import t
from .camera import CameraHub
from .printers import ACTIVE_STATES, create

log = logging.getLogger("printdash.manager")

END_STATUS = {"finished": "finished", "failed": "failed", "cancelled": "cancelled",
              "error": "failed", "idle": "unknown"}
NOTIFY_HMS = ("fatal", "serious", "common")
META_STATES = ("preparing", "printing", "paused", "finished", "failed", "cancelled")


def file_stem(name) -> str:
    """Comparable job name: no folder/extension, spaces/underscores ignored."""
    base = str(name or "").rsplit("/", 1)[-1]
    base = re.sub(r"(\.gcode)?\.(3mf|gcode|bgcode)$", "", base, flags=re.I)
    return re.sub(r"[\s_]+", "", base).lower()


def fmt_duration(seconds) -> str:
    if seconds is None:
        return "–"
    seconds = int(seconds)
    h, m = divmod(seconds // 60, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


class Manager:
    def __init__(self):
        self.cfg = config_store.load()
        i18n.set_lang(self.cfg)
        self.printers = {}
        self.cameras: dict[str, CameraHub] = {}
        self._prev = {}
        self._jobs = {}
        self._hms_seen = {}
        self._first = set()
        self._task = None
        self._power_task = None
        self.power = {}          # printer id -> {entity, on, available, error}
        self.ams_sensors = {}    # printer id -> {temp, hum, bat} from Home Assistant
        self.room_data = {}      # room id -> sensor values from Home Assistant (rooms.py)
        self._auto_off = {}      # printer id -> time the last print ended
        self.job_meta = {}       # printer id -> {key, thumb, thumb_type, weight_g, length_m, at}
        self.pending_meta = {}   # printer id -> {stem, meta} for files sent from 3D-PrintDash
        self._meta_loading = set()
        self._ams_state = {}     # printer id -> {online, since, slots{slot: item_id}} for AMS parking
        self._job_slots = {}     # printer id -> slots that were active during the running print
        self.maint = {}          # printer id -> maintenance task status (refreshed every 30 s)
        self._maint_at = 0.0
        self.started_at = time.time()

    # -- lifecycle -------------------------------------------------------
    async def start(self):
        history.init()
        await asyncio.to_thread(filament.ensure_printer_locations, self.cfg.get("printers", []))
        await self._build()
        self._task = asyncio.create_task(self._loop())
        self._power_task = asyncio.create_task(self._power_loop())
        self._dryer_task = asyncio.create_task(self._dryer_loop())

    async def shutdown(self):
        for task in (self._task, self._power_task, getattr(self, "_dryer_task", None)):
            if task:
                task.cancel()
        await self._teardown()

    async def _build(self):
        for pcfg in self.cfg.get("printers", []):
            try:
                printer = create(pcfg)
                self.printers[printer.id] = printer
                await printer.start()
                self._first.add(printer.id)
            except Exception as exc:  # noqa: BLE001
                log.error("Printer %s could not be started: %s", pcfg.get("name"), exc)
        self._sync_cameras()

    async def _teardown(self):
        for printer in self.printers.values():
            try:
                await printer.stop()
            except Exception:  # noqa: BLE001
                pass
        for cam in self.cameras.values():
            await cam.stop()
        self.printers, self.cameras = {}, {}
        self._prev, self._jobs, self._hms_seen = {}, {}, {}

    async def reload(self, new_cfg: dict):
        config_store.save(new_cfg)
        await self._teardown()
        self._ams_state = {}  # printers reconnect now; this is no "switched off"
        self.cfg = new_cfg
        i18n.set_lang(new_cfg)
        await self._build()

    # -- cameras ---------------------------------------------------------
    def _camera_sources(self) -> list:
        sources = []
        for printer in self.printers.values():
            sources += printer.camera_sources()
        for cam in self.cfg.get("cameras", []):
            if cam.get("url"):
                sources.append({
                    "id": cam["id"], "name": cam.get("name") or t("Kamera"),
                    "url": cam["url"].strip(),
                    "mode": "snapshot" if cam.get("snapshot") else "ffmpeg",
                    "printer_id": cam.get("printer_id") or None,
                })
        return sources

    def _sync_cameras(self):
        ccfg = self.cfg.get("camera", {})
        wanted = {s["id"]: s for s in self._camera_sources()}
        for cam_id in list(self.cameras):
            hub = self.cameras[cam_id]
            src = wanted.get(cam_id)
            if not src or src["url"] != hub.url or src["mode"] != hub.mode:
                asyncio.create_task(hub.stop())
                del self.cameras[cam_id]
        for cam_id, src in wanted.items():
            if cam_id not in self.cameras:
                self.cameras[cam_id] = CameraHub(src, ccfg.get("fps"), ccfg.get("width"))

    def cameras_for(self, printer_id) -> list:
        cams = [c for c in self.cameras.values() if c.printer_id == printer_id]
        # the printer's own camera first, then assigned external cameras
        return sorted(cams, key=lambda c: not c.id.startswith(f"{printer_id}-cam"))

    async def printer_snapshot(self, printer_id) -> bytes | None:
        for cam in self.cameras_for(printer_id):
            img = await cam.snapshot(timeout=10)
            if img:
                return img
        return None

    # -- state -----------------------------------------------------------
    def state(self) -> dict:
        printers = []
        for printer in self.printers.values():
            st = printer.snapshot()
            st["cameras"] = [c.id for c in self.cameras_for(printer.id)]
            st["power"] = self.power.get(printer.id) if self._power_entity(printer.id) else None
            meta = self.job_meta.get(printer.id)
            st["job"] = None
            if meta and st.get("filename") and meta["key"] == st["filename"]:
                cost, mats = costs.job_cost(self.cfg, meta.get("materials"), meta.get("weight_g"))
                st["job"] = {"key": meta["key"], "thumb": bool(meta.get("thumb")),
                             "weight_g": meta.get("weight_g"), "length_m": meta.get("length_m"),
                             "cost": cost, "materials": mats}
            st["ams"] = self._ams_view(printer.id, st.get("ams") or [])
            st["ams_hum_max"] = self._pcfg(printer.id).get("ams_hum_max") or 30
            st["has_ams"] = self._pcfg(printer.id).get("has_ams")  # None = not set (older settings)
            st["maintenance"] = self.maint.get(printer.id, [])
            if st["power"] and st["power"].get("on") is False:
                st["state"] = "off"
            printers.append(st)
        return {
            "printers": printers,
            "cameras": [c.info() for c in self.cameras.values()],
            "addon": bool(notify.SUPERVISOR_TOKEN),
            "ha": ha.available(),
            "costs": costs.settings(self.cfg),
            "language": (self.cfg.get("ui") or {}).get("language") or "",
            "filament_low_g": float((self.cfg.get("filament") or {}).get("low_warn_g") or 0),
            "system": system.snapshot() if (self.cfg.get("ui") or {}).get("show_system", True) else None,
            "rooms": rooms.view(self.cfg.get("rooms") or [], self.room_data),
        }

    def _ams_source(self, pid) -> str:
        """'ams' = values of the AMS itself, 'ha' = own sensor from Home Assistant."""
        cfg = self._pcfg(pid)
        src = cfg.get("ams_source")
        if src in ("ams", "ha"):
            return src
        # older configs: an entity chosen means the own sensor is wanted
        return "ha" if any((cfg.get(f) or "").strip() for _, f in self.AMS_KEYS) else "ams"

    def _ams_view(self, pid, units: list) -> list:
        """AMS climate: either from the AMS itself or only from the own HA sensor."""
        if self._ams_source(pid) != "ha":
            return units
        extra = self.ams_sensors.get(pid) or {}
        name = (self._pcfg(pid).get("ams_sensor_name") or "").strip() or "AMS"
        return [{"name": name, "temp": extra.get("temp"), "hum": extra.get("hum"), "hum_level": None,
                 "bat": extra.get("bat"), "src": "ha",
                 "configured": {k: bool((self._pcfg(pid).get(f) or "").strip()) for k, f in self.AMS_KEYS}}]

    # -- smart plugs (via Home Assistant) ----------------------------------
    def _pcfg(self, pid) -> dict:
        return next((p for p in self.cfg.get("printers", []) if p.get("id") == pid), {})

    def _power_entity(self, pid) -> str:
        return (self._pcfg(pid).get("power_entity") or "").strip()

    async def _refresh_power(self, pid):
        entity = self._power_entity(pid)
        if not entity:
            self.power.pop(pid, None)
            return
        try:
            st = await ha.get_state(entity)
            state = st.get("state")
            self.power[pid] = {
                "entity": entity,
                "on": True if state == "on" else False if state == "off" else None,
                "available": state not in ("unavailable", "unknown", None),
                "error": None,
            }
        except ha.HAError as exc:
            self.power[pid] = {"entity": entity, "on": None, "available": False, "error": str(exc)}

    AMS_KEYS = (("temp", "ams_temp_entity"), ("hum", "ams_hum_entity"), ("bat", "ams_bat_entity"))

    async def _refresh_ams_sensors(self, pid):
        """Optional Home Assistant sensors for the AMS (e.g. an extra sensor in the AMS)."""
        cfg = self._pcfg(pid)
        wanted = {k: (cfg.get(f) or "").strip() for k, f in self.AMS_KEYS}
        if self._ams_source(pid) != "ha" or not any(wanted.values()) or not ha.available():
            self.ams_sensors.pop(pid, None)
            return
        values = await ha.sensor_values(list(wanted.values()))
        out = {}
        for key, eid in wanted.items():
            if not eid:
                continue
            try:
                out[key] = float(values.get(eid, {}).get("state"))
            except (TypeError, ValueError):
                out[key] = None
        self.ams_sensors[pid] = out

    async def _power_loop(self):
        tick = 0
        while True:
            for pid in list(self.printers):
                await self._refresh_power(pid)
                try:
                    await self._check_ams_parking(self.printers.get(pid))
                except Exception:  # noqa: BLE001
                    log.exception("AMS parking")
                if tick % 2 == 0:  # AMS sensors every 10 s
                    try:
                        await self._refresh_ams_sensors(pid)
                    except Exception:  # noqa: BLE001
                        log.exception("AMS sensors")
            if tick % 2 == 0:  # room sensors every 10 s
                try:
                    self.room_data = await rooms.read(self.cfg.get("rooms") or [])
                except Exception:  # noqa: BLE001
                    log.exception("Room sensors")
            if time.time() - self._maint_at > 30:
                try:
                    await self.refresh_maintenance()
                except Exception:  # noqa: BLE001
                    log.exception("Maintenance")
            tick += 1
            await asyncio.sleep(5)

    # -- spools in the AMS while the printer is off --------------------------
    AMS_SETTLE_S = 120  # after switching on, wait before treating a missing spool as removed

    async def _check_ams_parking(self, printer):
        """Bambu printer with "AMS vorhanden": remember which stored spools are in the AMS.
        Switched off (offline or plug off) -> they move to the printer's AMS location.
        Taken out while the printer runs -> back to where they came from."""
        if printer is None:
            return
        pid = printer.id
        if printer.type != "bambu" or not self._pcfg(pid).get("has_ams"):
            self._ams_state.pop(pid, None)
            return
        st = printer.snapshot()
        plug_off = (self.power.get(pid) or {}).get("on") is False
        online = bool(st.get("online")) and not plug_off
        state = self._ams_state.setdefault(pid, {"online": False, "since": 0.0, "slots": {}})
        if not online:
            if state["online"] and state["slots"]:
                moved = await asyncio.to_thread(filament.park_in_ams, pid, state["slots"])
                if moved:
                    log.info("%s: switched off, %s spool(s) parked in the AMS location", printer.name, moved)
            state.update(online=False, slots={})
            return
        if not state["online"]:
            state.update(online=True, since=time.time(), slots={})
        ams = [dict(f) for f in st.get("filaments") or [] if str(f.get("slot")) != "Ext"]
        if not ams:
            return  # AMS not reported yet
        data = await asyncio.to_thread(filament.load)
        loaded = [{"printer": printer.name, "printer_id": pid, "filaments": ams}]
        reserved = {k: sum(x["qty"] for x in v) for k, v in filament.in_dryer(data).items()}
        filament.match(data, loaded, reserved)
        current = {str(f["slot"]): f.get("item_id") for f in ams if f.get("type") and f.get("item_id")}
        if state["slots"] and time.time() - state["since"] > self.AMS_SETTLE_S:
            for slot, old in state["slots"].items():
                if old and old not in current.values():
                    if await asyncio.to_thread(filament.unpark, pid, old):
                        log.info("%s: spool taken out of slot %s, moved back", printer.name, slot)
        state["slots"] = current

    async def set_power(self, pid, on: bool, force: bool = False):
        entity = self._power_entity(pid)
        if not entity:
            raise ha.HAError(t("Für diesen Drucker ist keine Steckdose eingerichtet"))
        printer = self.printers.get(pid)
        if not on and printer and not force:
            st = printer.snapshot()
            if st["state"] in ACTIVE_STATES:
                raise ha.PrinterBusy(t("{printer} druckt gerade – Ausschalten würde den Druck abbrechen", printer=printer.name))
        await ha.set_power(entity, on)
        self._auto_off.pop(pid, None)
        await asyncio.sleep(0.5)
        await self._refresh_power(pid)

    async def _check_auto_off(self, printer, cur):
        pid = printer.id
        ended = self._auto_off.get(pid)
        if ended is None:
            return
        minutes = float(self._pcfg(pid).get("auto_off_minutes") or 0)
        power = self.power.get(pid) or {}
        if minutes <= 0 or not power.get("on"):
            return
        if cur["state"] in ACTIVE_STATES:
            self._auto_off.pop(pid, None)
            return
        hottest = max((t["cur"] or 0 for t in cur["temps"] if t["label"] != "chamber"), default=0)
        if time.time() - ended < minutes * 60 or hottest >= 50:
            return
        self._auto_off.pop(pid, None)
        try:
            log.info("%s: switched off automatically", printer.name)
            await ha.set_power(self._power_entity(pid), False)
            await self._refresh_power(pid)
        except ha.HAError as exc:
            log.warning("%s: automatic switch-off failed: %s", printer.name, exc)

    async def _loop(self):
        while True:
            try:
                self._sync_cameras()
                for printer in list(self.printers.values()):
                    await self._evaluate(printer)
            except Exception:  # noqa: BLE001
                log.exception("Error in the status loop")
            await asyncio.sleep(2)

    async def _evaluate(self, printer):
        cur = printer.snapshot()
        if not cur["online"]:
            return  # keep jobs open while a printer is unreachable
        pid, state = printer.id, cur["state"]
        prev = self._prev.get(pid)
        self._prev[pid] = cur

        if pid in self._first:
            self._first.discard(pid)
            open_job = history.open_job(pid)
            if state in ACTIVE_STATES:
                if open_job:
                    self._jobs[pid] = open_job["id"]
                else:
                    started = time.time() - (cur.get("elapsed_s") or 0)
                    self._jobs[pid] = history.start_job(pid, printer.name, cur["filename"], started)
            elif open_job:
                history.end_job(open_job["id"], END_STATUS.get(state, "unknown"))
            # remember current HMS so old warnings don't trigger on startup
            self._hms_seen[pid] = {h["code"] for h in cur["hms"]}
            return

        await self._check_auto_off(printer, cur)
        self._maybe_load_meta(printer, cur)

        job = self._jobs.get(pid)
        if state in ACTIVE_STATES:
            if job is None:
                self._jobs[pid] = history.start_job(pid, printer.name, cur["filename"])
                self._job_slots[pid] = set()
            elif cur["filename"]:
                history.update_filename(job, cur["filename"])
            for f in cur.get("filaments") or []:
                if f.get("active"):
                    self._job_slots.setdefault(pid, set()).add(str(f.get("slot")))
        elif job is not None:
            del self._jobs[pid]
            self._auto_off[pid] = time.time()
            asyncio.create_task(self._finish_job(printer, job, cur, self._job_slots.pop(pid, set())))

        prev_state = prev["state"] if prev else None
        ncfg = self.cfg.get("notify", {})

        # errors
        if ncfg.get("on_error", True):
            if cur["error"] and cur["error"] != (prev or {}).get("error"):
                asyncio.create_task(self._notify(
                    printer, t("⚠️ {printer}: Fehler", printer=printer.name), self._describe(cur, cur["error"])))
            seen = self._hms_seen.setdefault(pid, set())
            current = {h["code"]: h for h in cur["hms"]}
            new = [h for code, h in current.items()
                   if code not in seen and h["severity"] in NOTIFY_HMS]
            self._hms_seen[pid] = set(current)
            if new:
                codes = ", ".join(h["code"] for h in new)
                asyncio.create_task(self._notify(
                    printer, t("⚠️ {printer}: Warnung", printer=printer.name),
                    self._describe(cur, f"HMS {codes}\n{new[0]['url']}")))

        if ncfg.get("on_pause") and state == "paused" and prev_state == "printing":
            asyncio.create_task(self._notify(
                printer, t("⏸️ {printer}: pausiert", printer=printer.name), self._describe(cur, t("Druck wurde pausiert."))))

    # -- job preview / filament ------------------------------------------
    def _maybe_load_meta(self, printer, cur):
        pid, key = printer.id, cur.get("filename")
        if not key or cur["state"] not in META_STATES or pid in self._meta_loading:
            return
        meta = self.job_meta.get(pid)
        if meta and meta["key"] == key:
            # retry a failed lookup every 5 minutes while printing
            if meta.get("thumb") or time.time() - meta["at"] < 120 \
                    or cur["state"] not in ACTIVE_STATES:
                return
        self._meta_loading.add(pid)
        asyncio.create_task(self._load_meta(printer, cur, key))

    async def _load_meta(self, printer, cur, key):
        pid = printer.id
        try:
            pending = self.pending_meta.get(pid)
            data = None
            if pending and pending["stem"] == file_stem(key):
                data = pending["meta"]
            if not (data and (data.get("thumb") or data.get("weight_g"))):
                fetched = await printer.fetch_job_meta(cur)
                if fetched:
                    data = {**(data or {}), **{k: v for k, v in fetched.items() if v}}
            self.job_meta[pid] = {"key": key, "at": time.time(), **(data or {})}
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: preview could not be loaded: %s", printer.name, exc)
            self.job_meta[pid] = {"key": key, "at": time.time()}
        finally:
            self._meta_loading.discard(pid)

    def set_pending_meta(self, pid, filename, meta):
        self.pending_meta[pid] = {"stem": file_stem(filename), "meta": meta}

    def _describe(self, st, text) -> str:
        parts = [text]
        if st.get("filename"):
            parts.append(t("Datei: {file}", file=st["filename"]))
        if st.get("progress") is not None:
            parts.append(t("Fortschritt: {progress} %", progress=st["progress"]))
        return "\n".join(parts)

    async def _finish_job(self, printer, job_id, st, slots=None):
        status = END_STATUS.get(st["state"], "unknown")
        image = await self.printer_snapshot(printer.id)
        meta = self.job_meta.get(printer.id) or {}
        if meta.get("key") != st.get("filename"):
            meta = {}
        share = 1.0 if status == "finished" else (st.get("progress") or 0) / 100
        grams = round(meta["weight_g"] * share, 1) if meta.get("weight_g") else None
        meters = round(meta["length_m"] * share, 2) if meta.get("length_m") else None
        cost, mats = costs.job_cost(self.cfg, meta.get("materials"), meta.get("weight_g"), share)
        deducted = []
        if (self.cfg.get("filament") or {}).get("deduct_usage") and (mats or grams):
            try:
                deducted = await self._deduct_usage(printer, st, mats, grams, slots or set())
            except Exception:  # noqa: BLE001
                log.exception("Filament usage")
        history.end_job(job_id, status, st.get("error"), image,
                        preview=meta.get("thumb"), preview_type=meta.get("thumb_type", "image/png"),
                        filament_g=grams, filament_m=meters, cost=cost, materials=mats, deducted=deducted)
        ncfg = self.cfg.get("notify", {})
        if status == "finished" and ncfg.get("on_finish"):
            await notify.send(self.cfg, t("✅ {printer}: fertig", printer=printer.name),
                              self._describe(st, t("Druck abgeschlossen.")), image)
        elif status == "cancelled" and ncfg.get("on_cancel", True):
            await notify.send(self.cfg, t("⏹️ {printer}: abgebrochen", printer=printer.name),
                              self._describe(st, t("Der Druck wurde abgebrochen.")), image)
        elif status == "failed" and ncfg.get("on_error", True) and not st.get("error"):
            # failed without an error text (otherwise the error was already reported)
            await notify.send(self.cfg, t("❌ {printer}: fehlgeschlagen", printer=printer.name),
                              self._describe(st, t("Der Druck ist fehlgeschlagen oder wurde abgebrochen.")), image)

    # -- maintenance reminders ------------------------------------------------
    MAINT_NAMES = {"clean": "Drucker reinigen", "lube": "Schmieren"}

    async def refresh_maintenance(self):
        self._maint_at = time.time()
        self.maint = await asyncio.to_thread(maintenance.status, self.cfg.get("printers", []))
        if not (self.cfg.get("notify") or {}).get("on_maintenance", True):
            return
        for pid, tasks in self.maint.items():
            printer = self.printers.get(pid)
            for task in tasks:
                if task["due"] and not task["notified"] and printer:
                    await asyncio.to_thread(maintenance.mark_notified, pid, task["id"])
                    task["notified"] = True
                    asyncio.create_task(notify.send(
                        self.cfg, t("🔧 {printer}: Wartung fällig", printer=printer.name),
                        t("{task} ist fällig ({hours} Druckstunden bzw. {days} Tage seit dem letzten Mal).",
                          task=t(self.MAINT_NAMES.get(task["id"], task["id"])),
                          hours=round(task["hours_since"]), days=round(task["days_since"]))))

    # -- filament usage ------------------------------------------------------
    async def _deduct_usage(self, printer, st, mats, grams, slots) -> list:
        """Subtract the print's filament from the spools that were used (optional setting).
        Per material: the active slots of that material family share its grams."""
        loaded_fils = [dict(f) for f in st.get("filaments") or [] if f.get("type")]
        if not loaded_fils:
            return []
        data = await asyncio.to_thread(filament.load)
        reserved = {k: sum(x["qty"] for x in v) for k, v in filament.in_dryer(data).items()}
        filament.match(data, [{"printer": printer.name, "printer_id": printer.id, "filaments": loaded_fils}], reserved)
        cands = [f for f in loaded_fils if f.get("item_id") and (not slots or str(f.get("slot")) in slots)]
        if not cands:
            return []
        uses = mats or [{"type": None, "g": grams}]
        done = []
        low = float((self.cfg.get("filament") or {}).get("low_warn_g") or 0)
        for m in uses:
            g = float(m.get("g") or 0)
            if g <= 0:
                continue
            if m.get("type"):
                fam = filament._family(m["type"])
                # only spools of the same material family; a different material is not guessed
                use = [f for f in cands if filament._family(f.get("type")) == fam]
            else:
                use = cands if len(cands) == 1 else []
            for f in use:
                rec = await asyncio.to_thread(filament.use_filament, f["item_id"], g / len(use), printer.id, f)
                if not rec:
                    continue
                rec["slot"] = f.get("slot")
                done.append(rec)
                if low and rec["before"] >= low > rec["left"] and (self.cfg.get("notify") or {}).get("on_low_filament", True):
                    asyncio.create_task(notify.send(
                        self.cfg, t("🧵 Filament knapp"),
                        t("{spool}: noch {left} g ({printer}, Slot {slot})", spool=rec["label"], left=round(rec["left"]),
                          printer=printer.name, slot=f.get("slot"))))
        if done:
            log.info("%s: filament used %s", printer.name, ", ".join(f"{d['label']} {d['g']} g" for d in done))
        return done

    # -- filament dryers ----------------------------------------------------
    async def _dryer_loop(self):
        while True:
            try:
                for d in await asyncio.to_thread(filament.due_dryers, time.time()):
                    await self._dryer_done(d)
            except Exception:  # noqa: BLE001
                log.exception("Dryers")
            await asyncio.sleep(20)

    async def _dryer_done(self, dryer):
        data = await asyncio.to_thread(filament.load)
        by_id = {i["id"]: i for i in data["items"]}
        lines = []
        for e in dryer["job"]["items"]:
            it = by_id.get(e["item_id"], {})
            loc = filament.location(data, it.get("location"))
            home = (loc.get("name") or t("Filamentlager")) if loc else ""
            name = " ".join(x for x in (it.get("material"), it.get("brand"), it.get("color_name")) if x) or t("Spule")
            lines.append(f"{e['qty']}× {name} → {home}")
        await asyncio.to_thread(filament.finish_drying, dryer["id"], True)
        if (self.cfg.get("notify") or {}).get("on_dryer", True):
            mins = round(dryer["job"].get("minutes") or 0)
            dur = f"{mins // 60} h {mins % 60} min" if mins % 60 and mins >= 60 else (f"{mins // 60} h" if mins >= 60 else f"{mins} min")
            msg = t("Trocknung fertig nach {duration}. Zurück an ihren Platz:", duration=dur) + "\n" + "\n".join(lines)
            try:
                await notify.send(self.cfg, t("🌀 {dryer} fertig", dryer=dryer["name"]), msg)
            except Exception:  # noqa: BLE001
                log.exception("Dryer notification")

    async def _notify(self, printer, title, message):
        image = await self.printer_snapshot(printer.id)
        await notify.send(self.cfg, title, message, image)
