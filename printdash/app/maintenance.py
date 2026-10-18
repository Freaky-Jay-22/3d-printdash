"""Maintenance reminders per printer: cleaning and lubrication.

Each task is due after a number of print hours (from the history) and/or days since it
was last marked as done. Intervals are printer settings (0 = off):
  maint_clean_h, maint_clean_d, maint_lube_h, maint_lube_d
The time of the last "done" lives in /data/maintenance.json.
"""
import json
import os
import threading
import time

from . import history
from .config import DATA_DIR

PATH = os.path.join(DATA_DIR, "maintenance.json")
# id, default hours, default days
TASKS = (("clean", 100, 0), ("lube", 300, 0))
_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, PATH)


def intervals(pcfg: dict) -> list:
    out = []
    for tid, dh, dd in TASKS:
        h = pcfg.get(f"maint_{tid}_h")
        d = pcfg.get(f"maint_{tid}_d")
        h = dh if h is None or h == "" else float(h or 0)
        d = dd if d is None or d == "" else float(d or 0)
        if h > 0 or d > 0:
            out.append((tid, h, d))
    return out


def status(printers: list, now: float | None = None) -> dict:
    """{printer_id: [{id, hours, days, hours_since, days_since, progress, due, done_at}]}.
    A task seen for the first time starts counting now (old history does not make it due)."""
    now = now or time.time()
    out = {}
    with _lock:
        data = _load()
        changed = False
        for p in printers:
            pid = p.get("id")
            if not pid:
                continue
            tasks = []
            for tid, h, d in intervals(p):
                rec = data.setdefault(pid, {}).setdefault(tid, {})
                if "done" not in rec:
                    rec["done"] = now
                    changed = True
                hours_since = history.print_seconds(pid, rec["done"], now) / 3600
                days_since = (now - rec["done"]) / 86400
                prog = max(hours_since / h if h else 0, days_since / d if d else 0)
                tasks.append({"id": tid, "hours": h, "days": d, "hours_since": round(hours_since, 1),
                              "days_since": round(days_since, 1), "progress": round(prog, 3),
                              "due": prog >= 1, "done_at": rec["done"], "notified": rec.get("notified", False)})
            out[pid] = tasks
        if changed:
            _save(data)
    return out


def mark_done(printer_id: str, task_id: str, now: float | None = None) -> None:
    with _lock:
        data = _load()
        data.setdefault(printer_id, {})[task_id] = {"done": now or time.time(), "notified": False}
        _save(data)


def mark_notified(printer_id: str, task_id: str) -> None:
    with _lock:
        data = _load()
        data.setdefault(printer_id, {}).setdefault(task_id, {"done": time.time()})["notified"] = True
        _save(data)
