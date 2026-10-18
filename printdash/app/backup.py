"""Backup, restore and import from another installation.

A backup is a zip file with the data folder: config.json, filament.json,
maintenance.json, history.db and the images in snapshots/. Restoring first saves
the current state to /data/backups/ so nothing gets lost by accident.
"""
import asyncio
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import time
import zipfile

import httpx

from . import config as config_store
from . import filament, history
from .config import DATA_DIR
from .i18n import t

log = logging.getLogger("printdash.backup")

FILES = ("config.json", "filament.json", "maintenance.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
MAX_ZIP = 2 * 1024 ** 3          # 2 GB unpacked at most
KEEP_AUTO_BACKUPS = 5


class BackupError(Exception):
    pass


# -- create ------------------------------------------------------------------------
def create(path: str) -> str:
    """Write a backup zip to `path`."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("backup.json", json.dumps({"app": "3D-PrintDash", "created": time.time()}))
        for name in FILES:
            src = os.path.join(DATA_DIR, name)
            if os.path.exists(src):
                z.write(src, name)
        if os.path.exists(history.DB_PATH):
            # consistent copy even while the app writes to the database
            tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            tmp.close()
            try:
                with history._lock:
                    src, dst = sqlite3.connect(history.DB_PATH), sqlite3.connect(tmp.name)
                    with dst:
                        src.backup(dst)
                    src.close()
                    dst.close()
                z.write(tmp.name, "history.db")
            finally:
                os.remove(tmp.name)
        if os.path.isdir(history.SNAP_DIR):
            for name in sorted(os.listdir(history.SNAP_DIR)):
                full = os.path.join(history.SNAP_DIR, name)
                if os.path.isfile(full):
                    z.write(full, f"snapshots/{name}", compress_type=zipfile.ZIP_STORED)
    return path


def auto_backup(reason: str) -> str:
    """Safety copy before a restore; keeps the last few."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"{reason}-{time.strftime('%Y%m%d-%H%M%S')}.zip")
    create(path)
    old = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip"))
    for f in old[:-KEEP_AUTO_BACKUPS]:
        os.remove(os.path.join(BACKUP_DIR, f))
    return path


# -- restore -----------------------------------------------------------------------
_SNAP_NAME = re.compile(r"^snapshots/[\w.\-]+$")


def _check_zip(z: zipfile.ZipFile) -> list:
    names = z.namelist()
    if "config.json" not in names or "backup.json" not in names:
        raise BackupError(t("Das ist keine 3D-PrintDash-Sicherung"))
    try:
        if json.loads(z.read("backup.json")).get("app") != "3D-PrintDash":
            raise ValueError
    except ValueError as exc:
        raise BackupError(t("Das ist keine 3D-PrintDash-Sicherung")) from exc
    if sum(i.file_size for i in z.infolist()) > MAX_ZIP:
        raise BackupError(t("Sicherung ist zu gross"))
    use = []
    for n in names:
        if n in FILES or n == "history.db" or _SNAP_NAME.match(n):
            use.append(n)
    try:
        json.loads(z.read("config.json"))
        if "filament.json" in names:
            json.loads(z.read("filament.json"))
    except ValueError as exc:
        raise BackupError(t("Sicherung ist beschädigt: {error}", error=exc)) from exc
    if "history.db" in names:
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            tmp.write(z.read("history.db"))
            tmp.flush()
            try:
                con = sqlite3.connect(tmp.name)
                con.execute("SELECT count(*) FROM jobs").fetchone()
                con.close()
            except sqlite3.DatabaseError as exc:
                raise BackupError(t("Sicherung ist beschädigt: {error}", error=exc)) from exc
    return use


def _apply_files(files: dict) -> None:
    """files: {name: bytes}. Replaces the data folder content (except other files)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    for name in FILES:
        path = os.path.join(DATA_DIR, name)
        if name in files:
            tmp = path + ".restore"
            with open(tmp, "wb") as fh:
                fh.write(files[name])
            os.replace(tmp, path)
        elif os.path.exists(path) and name != "config.json":
            os.remove(path)  # not in the backup = did not exist there
    with history._lock:
        if "history.db" in files:
            tmp = history.DB_PATH + ".restore"
            with open(tmp, "wb") as fh:
                fh.write(files["history.db"])
            os.replace(tmp, history.DB_PATH)
        shutil.rmtree(history.SNAP_DIR, ignore_errors=True)
        os.makedirs(history.SNAP_DIR, exist_ok=True)
        for name, data in files.items():
            if name.startswith("snapshots/"):
                with open(os.path.join(history.SNAP_DIR, os.path.basename(name)), "wb") as fh:
                    fh.write(data)
    history.init()  # migrations for backups of older versions


def read_zip(path: str) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            return {n: z.read(n) for n in _check_zip(z)}
    except zipfile.BadZipFile as exc:
        raise BackupError(t("Das ist keine gültige Zip-Datei")) from exc


async def restore(manager, files: dict, keep_password: bool = True) -> dict:
    """Replace all data with `files` and restart the printers. Returns a short summary."""
    await asyncio.to_thread(auto_backup, "vor-wiederherstellung")
    cfg = json.loads(files["config.json"])
    if keep_password:
        # do not lock out the person doing the restore
        cfg.setdefault("ui", {})["password"] = (manager.cfg.get("ui") or {}).get("password", "")
    files = {**files, "config.json": json.dumps(cfg, indent=2, ensure_ascii=False).encode()}
    await asyncio.to_thread(_apply_files, files)
    new_cfg = config_store.load()
    await manager.reload(new_cfg)
    await asyncio.to_thread(filament.ensure_printer_locations, new_cfg.get("printers", []))
    data = await asyncio.to_thread(filament.load)
    jobs = await asyncio.to_thread(history.list_jobs, 10 ** 6)
    return {"printers": len(new_cfg.get("printers", [])), "spools": sum(int(i.get("count") or 0) for i in data["items"]),
            "jobs": len(jobs)}


# -- import from another running installation (also the former PrintFarm) -----------
MASK = config_store.MASK


def _needs_reentry(cfg: dict) -> list:
    """Masked values the other installation did not hand out -> cleared, listed for the user."""
    todo = []
    for p in cfg.get("printers", []):
        for key in ("access_code", "api_key"):
            if p.get(key) == MASK:
                p[key] = ""
                todo.append(f"{p.get('name') or p.get('id')}: {key}")
        for key in ("host", "url", "camera_url"):
            if isinstance(p.get(key), str) and "xx.xx.xx" in p[key]:
                todo.append(f"{p.get('name') or p.get('id')}: {key}")
        if isinstance(p.get("serial"), str) and re.search(r"x{4,}$", p["serial"]):
            todo.append(f"{p.get('name') or p.get('id')}: serial")
    for c in cfg.get("cameras", []):
        if isinstance(c.get("url"), str) and (MASK in c["url"] or "xx.xx.xx" in c["url"]):
            c["url"] = c["url"].replace(MASK, "")
            todo.append(f"{c.get('name') or c.get('id')}: url")
    cfg.get("notify", {}).pop("telegram_token", None)
    return todo


def _history_db(rows: list) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        path = tmp.name
    try:
        con = sqlite3.connect(path)
        con.execute("""CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, printer_id TEXT, printer_name TEXT,
            filename TEXT, started_at REAL, ended_at REAL, duration_s INTEGER, status TEXT, error TEXT, snapshot TEXT,
            preview TEXT, filament_g REAL, filament_m REAL, cost REAL, materials TEXT)""")
        cols = ("id", "printer_id", "printer_name", "filename", "started_at", "ended_at", "duration_s", "status",
                "error", "snapshot", "preview", "filament_g", "filament_m", "cost", "materials")
        for r in rows:
            vals = [r.get(c) for c in cols]
            m = r.get("materials")
            vals[-1] = json.dumps(m) if isinstance(m, list) and m else (m if isinstance(m, str) else None)
            con.execute(f"INSERT INTO jobs ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        con.commit()
        con.close()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.remove(path)


async def fetch_remote(url: str, password: str = "") -> tuple[dict, list]:
    """Read everything from another installation over its web interface."""
    url = (url or "").strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    try:
        async with httpx.AsyncClient(base_url=url, timeout=30, follow_redirects=True) as c:
            if password:
                r = await c.post("/api/login", json={"password": password, "remember": False})
                if r.status_code == 401:
                    raise BackupError(t("Falsches Passwort für die andere Installation"))
            r = await c.get("/api/config")
            if r.status_code == 401:
                raise BackupError(t("Die andere Installation verlangt ein Passwort"))
            r.raise_for_status()
            cfg = r.json()
            fil = (await c.get("/api/filament")).raise_for_status().json()
            rows = (await c.get("/api/history", params={"limit": 1000000})).raise_for_status().json()
            files = {}
            sem = asyncio.Semaphore(4)

            async def image(job, column, suffix):
                name = job.get(column)
                if not name:
                    return
                async with sem:
                    r = await c.get(f"/api/history/{job['id']}/{suffix}")
                if r.status_code == 200 and r.content:
                    files[f"snapshots/{os.path.basename(name)}"] = r.content

            await asyncio.gather(*(image(j, "snapshot", "snapshot.jpg") for j in rows),
                                 *(image(j, "preview", "preview") for j in rows))
    except httpx.HTTPError as exc:
        raise BackupError(t("Andere Installation nicht erreichbar: {error}", error=config_store.redact(exc))) from exc
    except ValueError as exc:
        raise BackupError(t("Unerwartete Antwort der anderen Installation")) from exc
    todo = _needs_reentry(cfg)
    keep = {"locations", "items", "brands", "assign", "dryers"}
    files["backup.json"] = json.dumps({"app": "3D-PrintDash", "created": time.time(), "imported_from": url}).encode()
    files["config.json"] = json.dumps(cfg, indent=2, ensure_ascii=False).encode()
    files["filament.json"] = json.dumps({k: v for k, v in fil.items() if k in keep}, indent=2, ensure_ascii=False).encode()
    files["history.db"] = _history_db(rows)
    return files, todo


def to_zip_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()
