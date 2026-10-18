"""3D-PrintDash web server."""
import asyncio
import time
import base64
import logging
import os
import secrets
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config as config_store
from . import auth, backup, filament, ha, history, i18n, maintenance, notify, uploads
from .i18n import t
from .manager import Manager
from .printers import PrinterError
from .printers.moonraker import probe as probe_moonraker

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("printdash")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
INGRESS_IP = "172.30.32.2"  # Home Assistant ingress proxy
manager = Manager()


@asynccontextmanager
async def lifespan(app):
    uploads.cleanup()
    await manager.start()
    yield
    await manager.shutdown()


app = FastAPI(title="3D-PrintDash", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# -- password for direct (non-ingress) access -------------------------------
PUBLIC_PATHS = ("/login", "/api/login", "/static/style.css", "/static/i18n.js", "/static/lang/en.js")


def _password_hash() -> str:
    return manager.cfg.get("ui", {}).get("password") or ""


async def _authorized(headers, cookies, client_host) -> bool:
    stored = _password_hash()
    # The ingress proxy of Home Assistant connects from this fixed address; the
    # address is the real TCP peer (uvicorn runs without proxy headers).
    if not stored or client_host == INGRESS_IP:
        return True
    if auth.check_token(cookies.get(auth.COOKIE, ""), stored):
        return True
    # HTTP Basic still works for tools (e.g. a camera URL in another app)
    header = headers.get("authorization", "")
    if header.lower().startswith("basic "):
        if auth.blocked_for(client_host):
            return False
        try:
            _, _, given = base64.b64decode(header[6:]).decode().partition(":")
        except (ValueError, UnicodeDecodeError):
            return False
        ok = await asyncio.to_thread(auth.verify_cached, given, stored)
        if not ok:
            auth.record_fail(client_host)
        return ok
    return False


def _browser_lang(request) -> str:
    lang = (request.headers.get("x-pf-lang") or "").lower()
    return lang if lang in i18n.LANGUAGES else ""


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    host = request.client.host if request.client else None
    # language for messages from the server when "automatic" is set: remember the
    # browser language once (updated again whenever the settings are saved)
    lang = _browser_lang(request)
    ui = manager.cfg.setdefault("ui", {})
    if lang and not ui.get("language") and not ui.get("lang_hint"):
        ui["lang_hint"] = lang
        config_store.save(manager.cfg)
        i18n.set_lang(manager.cfg)
    if request.url.path in PUBLIC_PATHS or await _authorized(request.headers, request.cookies, host):
        return await call_next(request)
    if request.url.path == "/":
        return RedirectResponse("login", status_code=303)
    return JSONResponse({"detail": t("Anmeldung erforderlich")}, status_code=401)


@app.get("/login")
async def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"), headers={"Cache-Control": "no-cache"})


@app.post("/api/login")
async def login(body: dict, request: Request):
    stored = _password_hash()
    if not stored:
        return {"ok": True}
    ip = request.client.host if request.client else None
    wait = auth.blocked_for(ip)
    if wait:
        raise HTTPException(429, t("Zu viele Fehlversuche. Bitte in {min} min erneut versuchen.", min=max(1, round(wait / 60))))
    if not await asyncio.to_thread(auth.verify_password, str(body.get("password", "")), stored):
        auth.record_fail(ip)
        await asyncio.sleep(1.5)  # slow down guessing
        raise HTTPException(401, t("Falsches Passwort"))
    auth.reset_fails(ip)
    days = auth.SESSION_DAYS if body.get("remember", True) else None
    resp = JSONResponse({"ok": True})
    resp.set_cookie(auth.COOKIE, auth.make_token(stored), httponly=True, samesite="lax",
                    max_age=days * 86400 if days else None)
    return resp


@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE)
    return resp


def _printer(pid):
    printer = manager.printers.get(pid)
    if not printer:
        raise HTTPException(404, t("Drucker nicht gefunden"))
    return printer


def _camera(cid):
    cam = manager.cameras.get(cid)
    if not cam:
        raise HTTPException(404, t("Kamera nicht gefunden"))
    return cam


# -- pages & state -----------------------------------------------------------
@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"),
                        headers={"Cache-Control": "no-cache"})


@app.get("/api/state")
async def get_state(request: Request):
    st = manager.state()
    st["auth"] = {"enabled": bool(_password_hash()),
                  "ingress": bool(request.client and request.client.host == INGRESS_IP)}
    return st


@app.post("/api/printers/{pid}/command")
async def printer_command(pid: str, body: dict):
    printer = _printer(pid)
    try:
        await printer.command(body.get("action", ""))
    except PrinterError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@app.post("/api/printers/{pid}/power")
async def printer_power(pid: str, body: dict):
    _printer(pid)
    try:
        await manager.set_power(pid, bool(body.get("on")), bool(body.get("force")))
    except ha.PrinterBusy as exc:
        raise HTTPException(409, str(exc))
    except ha.HAError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "power": manager.power.get(pid)}


@app.get("/api/debug")
async def debug_raw():
    """Raw printer data, to help when a value is missing or wrong."""
    out = {}
    for printer in manager.printers.values():
        if hasattr(printer, "raw_status"):
            out[printer.name] = printer.raw_status()
        else:
            out[printer.name] = {"objects": getattr(printer, "objects", []),
                                 "status": getattr(printer, "status", {})}
    return out


@app.get("/api/ha/bambu")
async def ha_bambu_entities():
    if not ha.available():
        return {"available": False}
    try:
        return {"available": True, **(await ha.bambu_entities()), "images": await ha.bambu_images()}
    except ha.HAError as exc:
        return {"available": False, "error": str(exc)}


@app.get("/api/ha/entities")
async def ha_entities():
    if not ha.available():
        return {"available": False, "entities": []}
    try:
        return {"available": True, "entities": await ha.power_entities()}
    except ha.HAError as exc:
        return {"available": False, "entities": [], "error": str(exc)}


# -- uploads -------------------------------------------------------------------
@app.post("/api/uploads")
async def upload_file(request: Request, file: UploadFile = File(...)):
    limit_mb = uploads.MAX_SIZE // (1024 * 1024)
    if int(request.headers.get("content-length") or 0) > uploads.MAX_SIZE + 1024 * 1024:
        raise HTTPException(413, t("Datei zu gross (max. {mb} MB)", mb=limit_mb))
    await asyncio.to_thread(uploads.cleanup)
    token, path = uploads.new_path(file.filename)
    size = 0
    with open(path, "wb") as fh:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > uploads.MAX_SIZE:
                break
            fh.write(chunk)
    if size > uploads.MAX_SIZE:
        os.remove(path)
        raise HTTPException(413, t("Datei zu gross (max. {mb} MB)", mb=limit_mb))
    name = uploads.safe_name(file.filename)
    info = await asyncio.to_thread(uploads.inspect, path, name)
    info["token"] = token
    return info


@app.get("/api/uploads/{token}/thumb/{plate}")
async def upload_thumb(token: str, plate: int):
    found = uploads.find(token)
    img = uploads.thumbnail(found[0], plate) if found else None
    if not img:
        raise HTTPException(404)
    return Response(img, media_type="image/png")


@app.post("/api/printers/{pid}/print")
async def send_print(pid: str, body: dict):
    printer = _printer(pid)
    found = uploads.find(body.get("token", ""))
    if not found:
        raise HTTPException(404, t("Datei nicht mehr vorhanden, bitte erneut hochladen"))
    path, name = found
    ext = os.path.splitext(name)[1].lower()
    st = printer.snapshot()
    if ext not in st["file_types"]:
        raise HTTPException(400, t("{printer} kann keine {ext}-Dateien drucken", printer=printer.name, ext=ext))
    if body.get("start") and st["state"] in ("preparing", "printing", "paused"):
        raise HTTPException(409, t("{printer} druckt gerade", printer=printer.name))
    opts = {
        "start": bool(body.get("start")),
        "plate": int(body.get("plate") or 1),
        "use_ams": bool(body.get("use_ams")),
        "timelapse": bool(body.get("timelapse")),
        "bed_leveling": body.get("bed_leveling", True),
    }
    if ext == ".3mf" and opts["use_ams"]:
        info = await asyncio.to_thread(uploads.inspect, path, name)
        opts["ams_mapping"] = uploads.ams_mapping(info, opts["plate"], body.get("ams_map") or {})
    try:
        message = await printer.send_file(path, name, opts)
    except PrinterError as exc:
        raise HTTPException(502, str(exc))
    # remember preview + filament estimate so the job shows them right away
    try:
        if ext == ".3mf":
            meta = await asyncio.to_thread(uploads.job_meta_from_3mf, path, opts["plate"])
        else:
            meta = await asyncio.to_thread(uploads.job_meta_from_gcode, path)
        manager.set_pending_meta(pid, name, meta)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "message": message}


@app.get("/api/printers/{pid}/thumbnail")
async def printer_thumbnail(pid: str):
    meta = manager.job_meta.get(pid) or {}
    if not meta.get("thumb"):
        raise HTTPException(404)
    return Response(meta["thumb"], media_type=meta.get("thumb_type") or "image/png",
                    headers={"Cache-Control": "max-age=3600"})


# -- cameras -------------------------------------------------------------------
@app.websocket("/api/camera/{cid}/ws")
async def camera_ws(ws: WebSocket, cid: str):
    if not await _authorized(ws.headers, ws.cookies, ws.client.host if ws.client else None):
        await ws.close(code=4401)
        return
    cam = manager.cameras.get(cid)
    if not cam:
        await ws.close(code=4404)
        return
    await ws.accept()
    gen = cam.frames()
    try:
        async for frame in gen:
            await ws.send_bytes(frame)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await gen.aclose()


@app.get("/api/camera/{cid}/stream.mjpg")
async def camera_mjpeg(cid: str):
    cam = _camera(cid)

    async def body():
        gen = cam.frames()
        try:
            async for frame in gen:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
        finally:
            await gen.aclose()

    return StreamingResponse(body(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/camera/{cid}/snapshot.jpg")
async def camera_snapshot(cid: str):
    img = await _camera(cid).snapshot()
    if not img:
        raise HTTPException(504, t("Kein Bild verfügbar"))
    return Response(img, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# -- history -------------------------------------------------------------------
@app.get("/api/history")
async def get_history(printer_id: str | None = None, limit: int = 300):
    return await asyncio.to_thread(history.list_jobs, limit, printer_id)


@app.get("/api/history.csv")
async def history_csv(printer_id: str | None = None, lang: str | None = None):
    """All prints as a table for Excel & co. German: ';' as separator (what Excel expects there)."""
    import csv
    import io
    jobs = await asyncio.to_thread(history.list_jobs, 10 ** 7, printer_id)
    lang = lang if lang in i18n.LANGUAGES else i18n.lang()   # the browser's language (download link)
    de = lang == "de"
    t = (lambda s: s) if de else (lambda s: i18n.MESSAGES.get(lang, i18n.MESSAGES["en"]).get(s, s))  # noqa: E731
    currency = (manager.cfg.get("costs") or {}).get("currency") or ""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";" if de else ",")
    w.writerow([t("Drucker"), t("Datei"), t("Start"), t("Ende"), t("Dauer (h)"), t("Status"),
                t("Filament (g)"), t("Filament (m)"), t("Kosten") + (f" ({currency})" if currency else ""),
                t("Materialien"), t("Fehler")])
    fmt = lambda ts: time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else ""  # noqa: E731
    for j in reversed(jobs):
        mats = ", ".join(f"{m.get('type')} {round(m.get('g') or 0)} g" for m in j.get("materials") or [])
        w.writerow([j.get("printer_name") or "", j.get("filename") or "", fmt(j.get("started_at")), fmt(j.get("ended_at")),
                    round((j.get("duration_s") or 0) / 3600, 2), j.get("status") or "",
                    j.get("filament_g") if j.get("filament_g") is not None else "",
                    j.get("filament_m") if j.get("filament_m") is not None else "",
                    j.get("cost") if j.get("cost") is not None else "", mats, j.get("error") or ""])
    name = f"3d-printdash-history-{time.strftime('%Y-%m-%d')}.csv"
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/history/{job_id}/snapshot.jpg")
async def history_snapshot(job_id: int):
    path = history.snapshot_path(job_id)
    if not path:
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/history/{job_id}/preview")
async def history_preview(job_id: int):
    path = history.snapshot_path(job_id, "preview")
    if not path:
        raise HTTPException(404)
    return FileResponse(path)


@app.delete("/api/history/{job_id}")
async def delete_history(job_id: int):
    await asyncio.to_thread(history.delete_job, job_id)
    return {"ok": True}


# -- filament inventory --------------------------------------------------------
@app.get("/api/filament")
async def get_filament():
    data = filament.load()
    entities = [v for loc in data["locations"]
                for v in (loc.get("temp_entity"), loc.get("hum_entity"), loc.get("bat_entity"))]
    data["sensors"] = await ha.sensor_values(entities) if ha.available() else {}
    # what is loaded in the printers right now (AMS / toolheads)
    data["loaded"] = _loaded()
    data["in_dryer"] = filament.in_dryer(data)
    reserved = {k: sum(x["qty"] for x in v) for k, v in data["in_dryer"].items()}
    data["in_printer"] = filament.match(data, data["loaded"], reserved)
    data["dry_guide"] = filament.DRY_GUIDE
    data["now"] = time.time()
    return data


# -- dryers ---------------------------------------------------------------------
def _dryer_call(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.put("/api/filament/dryers")
async def set_dryers(body: dict):
    return await asyncio.to_thread(_dryer_call, filament.set_dryer_count, body.get("count", 0))


@app.put("/api/filament/dryers/{dryer_id}")
async def rename_dryer(dryer_id: str, body: dict):
    return await asyncio.to_thread(_dryer_call, filament.rename_dryer, dryer_id, body.get("name"))


@app.post("/api/filament/dryers/{dryer_id}/start")
async def start_dryer(dryer_id: str, body: dict):
    return await asyncio.to_thread(_dryer_call, filament.start_drying, dryer_id,
                                   body.get("items"), body.get("minutes"), body.get("temp"))


@app.post("/api/filament/dryers/{dryer_id}/extend")
async def extend_dryer(dryer_id: str, body: dict):
    return await asyncio.to_thread(_dryer_call, filament.extend_drying, dryer_id, body.get("minutes", 30))


@app.post("/api/filament/dryers/{dryer_id}/stop")
async def stop_dryer(dryer_id: str, body: dict):
    return await asyncio.to_thread(_dryer_call, filament.finish_drying, dryer_id, bool(body.get("done")))


def _loaded() -> list:
    return [{"printer": p["name"], "printer_id": p["id"], "filaments": [dict(f) for f in p["filaments"]]}
            for p in manager.state()["printers"] if p.get("filaments")]


@app.put("/api/filament/assign")
async def assign_filament(body: dict):
    """Manually tell which stored spool is in a printer slot."""
    pid, slot = body.get("printer_id"), str(body.get("slot"))
    printer = next((p for p in _loaded() if p["printer_id"] == pid), None)
    fil = next((f for f in (printer or {}).get("filaments", []) if str(f.get("slot")) == slot), None)
    if not fil or not fil.get("type"):
        raise HTTPException(404, t("In diesem Slot ist nichts geladen"))
    await asyncio.to_thread(filament.set_assignment, pid, fil, str(body.get("item_id") or ""))
    return {"ok": True}


@app.post("/api/filament/items")
async def save_filament_item(body: dict):
    return await asyncio.to_thread(filament.upsert, body)


@app.post("/api/filament/items/{item_id}/move")
async def move_filament_item(item_id: str, body: dict):
    return await asyncio.to_thread(_filament_call, filament.move_item, item_id, body.get("to"), body.get("qty", 1))


@app.delete("/api/filament/items/{item_id}")
async def delete_filament_item(item_id: str):
    await asyncio.to_thread(filament.delete, item_id)
    return {"ok": True}


@app.post("/api/filament/brands")
async def save_filament_brand(body: dict):
    try:
        return await asyncio.to_thread(filament.upsert_brand, body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.delete("/api/filament/brands/{brand_id}")
async def delete_filament_brand(brand_id: str):
    await asyncio.to_thread(filament.delete_brand, brand_id)
    return {"ok": True}


def _filament_call(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/filament/locations")
async def add_filament_location(body: dict):
    return await asyncio.to_thread(_filament_call, filament.add_location, body)


@app.put("/api/filament/locations")
async def order_filament_locations(body: dict):
    return await asyncio.to_thread(_filament_call, filament.order_locations, body.get("order") or [])


@app.put("/api/filament/locations/{key}")
async def save_filament_location(key: str, body: dict):
    return await asyncio.to_thread(_filament_call, filament.set_location, key, body)


@app.delete("/api/filament/locations/{key}")
async def delete_filament_location(key: str, move_to: str | None = None):
    await asyncio.to_thread(_filament_call, filament.delete_location, key, move_to)
    return {"ok": True}


@app.get("/api/ha/climate")
async def ha_climate():
    if not ha.available():
        return {"available": False, "temperature": [], "humidity": []}
    try:
        return {"available": True, **(await ha.climate_sensors())}
    except ha.HAError as exc:
        return {"available": False, "error": str(exc), "temperature": [], "humidity": []}


# -- settings ------------------------------------------------------------------
@app.get("/api/config")
async def get_config():
    return config_store.masked(manager.cfg)


@app.put("/api/config")
async def put_config(body: dict, request: Request):
    for p in body.get("printers", []):
        if p.get("type") not in ("bambu", "moonraker"):
            raise HTTPException(400, t("Unbekannter Druckertyp"))
    new_cfg = config_store.unmask(body, manager.cfg)
    new_cfg.setdefault("ui", {})
    if new_cfg["ui"].get("language") not in ("", None, *i18n.LANGUAGES):
        new_cfg["ui"]["language"] = ""
    if _browser_lang(request):
        new_cfg["ui"]["lang_hint"] = _browser_lang(request)
    pw = new_cfg.get("ui", {}).get("password") or ""
    if pw and not auth.is_hashed(pw):
        if len(pw) < 6:
            raise HTTPException(400, t("Passwort muss mindestens 6 Zeichen haben"))
        new_cfg["ui"]["password"] = await asyncio.to_thread(auth.hash_password, pw)
    changed = new_cfg.get("ui", {}).get("password") != manager.cfg.get("ui", {}).get("password")
    await manager.reload(new_cfg)
    await asyncio.to_thread(filament.ensure_printer_locations, new_cfg.get("printers", []))
    await manager.refresh_maintenance()
    resp = JSONResponse(config_store.masked(manager.cfg))
    # keep the person who just changed the password logged in
    if changed and new_cfg["ui"].get("password"):
        resp.set_cookie(auth.COOKIE, auth.make_token(new_cfg["ui"]["password"]), httponly=True,
                        samesite="lax", max_age=auth.SESSION_DAYS * 86400)
    return resp


# -- maintenance -----------------------------------------------------------------------
@app.post("/api/maintenance/{pid}/{task_id}/done")
async def maintenance_done(pid: str, task_id: str):
    _printer(pid)
    if task_id not in [t_[0] for t_ in maintenance.TASKS]:
        raise HTTPException(404)
    await asyncio.to_thread(maintenance.mark_done, pid, task_id)
    await manager.refresh_maintenance()
    return {"ok": True, "maintenance": manager.maint.get(pid, [])}


# -- backup / restore / import --------------------------------------------------------
@app.get("/api/backup")
async def download_backup():
    from starlette.background import BackgroundTask
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    await asyncio.to_thread(backup.create, path)
    name = f"3d-printdash-backup-{time.strftime('%Y-%m-%d')}.zip"
    return FileResponse(path, media_type="application/zip", filename=name,
                        background=BackgroundTask(os.remove, path))


@app.post("/api/backup/restore")
async def restore_backup(file: UploadFile = File(...)):
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        size = 0
        with open(path, "wb") as fh:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > backup.MAX_ZIP:
                    raise HTTPException(413, t("Sicherung ist zu gross"))
                fh.write(chunk)
        files = await asyncio.to_thread(backup.read_zip, path)
        return {"ok": True, **(await backup.restore(manager, files))}
    except backup.BackupError as exc:
        raise HTTPException(400, str(exc))
    finally:
        os.remove(path)


@app.post("/api/backup/import")
async def import_remote(body: dict):
    try:
        files, todo = await backup.fetch_remote(body.get("url", ""), body.get("password", ""))
        summary = await backup.restore(manager, files)
    except backup.BackupError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, **summary, "todo": todo}


@app.post("/api/probe/moonraker")
async def probe(body: dict):
    old = next((p for p in manager.cfg["printers"] if p.get("id") == body.get("id")), {})
    api_key = body.get("api_key") or ""
    if api_key == config_store.MASK:
        api_key = old.get("api_key", "")
    # the browser only knows the shortened IP (192.xx.xx.xx)
    url = config_store.unmask({"printers": [{"id": old.get("id"), "url": body.get("url", "")}]},
                              {"printers": [old]})["printers"][0]["url"] if old else body.get("url", "")
    result = await probe_moonraker(url, api_key)
    if result.get("camera"):
        for cam in result["camera"].get("webcams") or []:
            cam["stream_url"] = config_store.mask_ip(cam.get("stream_url"))
            cam["snapshot_url"] = config_store.mask_ip(cam.get("snapshot_url"))
    result["cameras"] = [config_store.mask_ip(c) for c in result.get("cameras") or []]
    return result


@app.get("/api/notify/services")
async def notify_services():
    base, _ = notify.ha_api()
    return {"available": bool(base), "services": await notify.list_ha_services()}


@app.post("/api/notify/test")
async def notify_test():
    image = None
    for cam in manager.cameras.values():
        image = await cam.snapshot(timeout=8)
        if image:
            break
    errors = await notify.send(manager.cfg, "🧪 3D-PrintDash",
                               t("Testbenachrichtigung. Alles funktioniert!"), image)
    if errors:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    return {"ok": True}
