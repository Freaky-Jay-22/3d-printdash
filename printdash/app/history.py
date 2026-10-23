"""Print history in SQLite."""
import json
import os
import sqlite3
import threading
import time

from .config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "history.db")
SNAP_DIR = os.path.join(DATA_DIR, "snapshots")

_lock = threading.Lock()


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    os.makedirs(SNAP_DIR, exist_ok=True)
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                printer_id TEXT, printer_name TEXT, filename TEXT,
                started_at REAL, ended_at REAL, duration_s INTEGER,
                status TEXT, error TEXT, snapshot TEXT
            )""")
        cols = {r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()}
        for col, typ in (("preview", "TEXT"), ("filament_g", "REAL"), ("filament_m", "REAL"),
                         ("cost", "REAL"), ("materials", "TEXT"), ("deducted", "TEXT"),
                         ("timelapse", "TEXT")):
            if col not in cols:
                c.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")


def start_job(printer_id, printer_name, filename, started_at=None) -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO jobs (printer_id, printer_name, filename, started_at, status) "
            "VALUES (?, ?, ?, ?, 'running')",
            (printer_id, printer_name, filename, started_at or time.time()),
        )
        return cur.lastrowid


def open_job(printer_id):
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT * FROM jobs WHERE printer_id=? AND status='running' "
            "ORDER BY id DESC LIMIT 1", (printer_id,)).fetchone()
        return dict(row) if row else None


def update_filename(job_id, filename):
    with _lock, _conn() as c:
        c.execute("UPDATE jobs SET filename=? WHERE id=? AND (filename IS NULL OR filename<>?)",
                  (filename, job_id, filename))


def end_job(job_id, status, error=None, snapshot: bytes | None = None,
            preview: bytes | None = None, preview_type: str = "image/png",
            filament_g=None, filament_m=None, cost=None, materials=None, deducted=None):
    snap_name = prev_name = None
    if snapshot:
        snap_name = f"{job_id}.jpg"
        with open(os.path.join(SNAP_DIR, snap_name), "wb") as fh:
            fh.write(snapshot)
    if preview:
        prev_name = f"{job_id}_preview.{'jpg' if 'jpeg' in (preview_type or '') else 'png'}"
        with open(os.path.join(SNAP_DIR, prev_name), "wb") as fh:
            fh.write(preview)
    now = time.time()
    with _lock, _conn() as c:
        row = c.execute("SELECT started_at FROM jobs WHERE id=?", (job_id,)).fetchone()
        duration = int(now - row["started_at"]) if row else None
        c.execute(
            "UPDATE jobs SET ended_at=?, duration_s=?, status=?, error=?, snapshot=?, "
            "preview=?, filament_g=?, filament_m=?, cost=?, materials=?, deducted=? WHERE id=?",
            (now, duration, status, error, snap_name, prev_name, filament_g, filament_m,
             cost, json.dumps(materials) if materials else None,
             json.dumps(deducted) if deducted else None, job_id),
        )


def list_jobs(limit=300, printer_id=None):
    sql, args = "SELECT * FROM jobs", []
    if printer_id:
        sql += " WHERE printer_id=?"
        args.append(printer_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _lock, _conn() as c:
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    for r in rows:
        # the browser only needs to know whether a video exists (not where it is stored)
        r["timelapse"] = bool(r.get("timelapse") and os.path.exists(r["timelapse"]))
        for col in ("materials", "deducted"):
            try:
                r[col] = json.loads(r[col]) if r.get(col) else []
            except ValueError:
                r[col] = []
    return rows


def snapshot_path(job_id, column="snapshot"):
    assert column in ("snapshot", "preview")
    with _lock, _conn() as c:
        row = c.execute(f"SELECT {column} FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row and row[column]:
        path = os.path.join(SNAP_DIR, row[column])
        if os.path.exists(path):
            return path
    return None


def set_timelapse(job_id, path: str | None):
    with _lock, _conn() as c:
        c.execute("UPDATE jobs SET timelapse=? WHERE id=?", (path, job_id))


def timelapse_path(job_id) -> str | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT timelapse FROM jobs WHERE id=?", (job_id,)).fetchone()
    path = row["timelapse"] if row else None
    return path if path and os.path.exists(path) else None


def delete_timelapse(job_id) -> bool:
    """Delete the video of a print (wherever it is stored); the history entry stays."""
    with _lock, _conn() as c:
        row = c.execute("SELECT timelapse FROM jobs WHERE id=?", (job_id,)).fetchone()
        path = row["timelapse"] if row else None
        c.execute("UPDATE jobs SET timelapse=NULL WHERE id=?", (job_id,))
    if path and os.path.exists(path):
        os.remove(path)
        return True
    return False


def timelapse_videos() -> list:
    """All prints that have a video: id, printer, file, start, size."""
    with _lock, _conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id, printer_name, filename, started_at, status, timelapse FROM jobs "
            "WHERE timelapse IS NOT NULL ORDER BY id DESC").fetchall()]
    out = []
    for r in rows:
        try:
            r["size"] = os.path.getsize(r["timelapse"])
        except OSError:
            continue  # file is gone (deleted by hand or cleaned up)
        r.pop("timelapse")
        out.append(r)
    return out


def delete_job(job_id):
    for column in ("snapshot", "preview"):
        path = snapshot_path(job_id, column)
        if path:
            os.remove(path)
    # a video inside 3D-PrintDash goes with the entry; videos on a NAS / media folder stay
    video = timelapse_path(job_id)
    if video and os.path.abspath(video).startswith(os.path.abspath(DATA_DIR) + os.sep):
        os.remove(video)
    with _lock, _conn() as c:
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))


def print_seconds(printer_id, since: float, now: float | None = None) -> float:
    """Printing time of a printer since a point in time (running print included)."""
    now = now or time.time()
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT started_at, ended_at, status FROM jobs WHERE printer_id=? "
            "AND (ended_at IS NULL OR ended_at > ?) AND started_at IS NOT NULL", (printer_id, since)).fetchall()
    total = 0.0
    for r in rows:
        end = r["ended_at"] if r["ended_at"] else (now if r["status"] == "running" else None)
        if end is None:
            continue
        total += max(0.0, min(end, now) - max(r["started_at"], since))
    return total
