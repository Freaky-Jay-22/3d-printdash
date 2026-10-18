"""Staging area for uploaded print files and .3mf inspection (plates, filaments)."""
import json
import os
import re
import secrets
import time
import xml.etree.ElementTree as ET
import zipfile

from .config import DATA_DIR
from .i18n import t

UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
MAX_AGE = 24 * 3600
MAX_SIZE = 500 * 1024 * 1024  # largest accepted print file


def cleanup():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    now = time.time()
    for name in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, name)
        try:
            if now - os.path.getmtime(path) > MAX_AGE:
                os.remove(path)
        except OSError:
            pass


def safe_name(name: str) -> str:
    name = os.path.basename(name or "datei")
    name = re.sub(r"[^\w.\-() ]+", "_", name).strip() or "datei"
    return name[:120]


def new_path(filename: str) -> tuple[str, str]:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    token = secrets.token_hex(8)
    return token, os.path.join(UPLOAD_DIR, f"{token}__{safe_name(filename)}")


def find(token: str) -> tuple[str, str] | None:
    if not re.fullmatch(r"[0-9a-f]{16}", token or ""):
        return None
    for name in os.listdir(UPLOAD_DIR):
        if name.startswith(token + "__"):
            return os.path.join(UPLOAD_DIR, name), name.split("__", 1)[1]
    return None


def inspect(path: str, filename: str) -> dict:
    info = {"name": filename, "size": os.path.getsize(path), "kind": "gcode", "plates": [],
            "project_filaments": 0}
    if not filename.lower().endswith(".3mf"):
        return info
    info["kind"] = "3mf"
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            try:
                settings = json.loads(z.read("Metadata/project_settings.config"))
                info["project_filaments"] = len(settings.get("filament_colour") or [])
            except (KeyError, ValueError):
                pass
            plates = {}
            if "Metadata/slice_info.config" in names:
                root = ET.fromstring(z.read("Metadata/slice_info.config"))
                for plate in root.iter("plate"):
                    meta = {m.get("key"): m.get("value") for m in plate.iter("metadata")}
                    idx = int(meta.get("index", len(plates) + 1))
                    plates[idx] = {
                        "index": idx,
                        "prediction_s": int(float(meta.get("prediction") or 0)) or None,
                        "weight_g": float(meta.get("weight") or 0) or None,
                        "filaments": [
                            {"id": int(f.get("id")), "type": f.get("type"),
                             "color": f.get("color"), "used_g": f.get("used_g")}
                            for f in plate.iter("filament")
                        ],
                    }
            for n in names:
                m = re.fullmatch(r"Metadata/plate_(\d+)\.gcode", n)
                if m:
                    idx = int(m.group(1))
                    plates.setdefault(idx, {"index": idx, "filaments": [],
                                            "prediction_s": None, "weight_g": None})
            for idx, plate in plates.items():
                plate["sliced"] = f"Metadata/plate_{idx}.gcode" in names
                plate["thumb"] = f"Metadata/plate_{idx}.png" in names
            info["plates"] = [plates[k] for k in sorted(plates)]
            ids = [f["id"] for p in info["plates"] for f in p["filaments"]]
            info["project_filaments"] = max([info["project_filaments"], *ids, 0])
    except zipfile.BadZipFile:
        info["error"] = t("Keine gültige .3mf-Datei")
    return info


def thumbnail(path: str, plate: int) -> bytes | None:
    try:
        with zipfile.ZipFile(path) as z:
            return z.read(f"Metadata/plate_{int(plate)}.png")
    except (KeyError, zipfile.BadZipFile, ValueError):
        return None


def ams_mapping(info: dict, plate: int, choice: dict) -> list | None:
    """Build Bambu's ams_mapping list: index = project filament, value = AMS slot (0-based)."""
    count = info.get("project_filaments") or 0
    if not count:
        return None
    mapping = [-1] * count
    plate_info = next((p for p in info["plates"] if p["index"] == plate), None)
    for fil in (plate_info or {}).get("filaments", []):
        fid = fil["id"]
        slot = choice.get(str(fid), choice.get(fid, fid))
        try:
            mapping[fid - 1] = 254 if str(slot).lower() == "ext" else int(slot) - 1
        except (ValueError, IndexError, TypeError):
            pass
    return mapping


def job_meta_from_3mf(path: str, plate: int = 1) -> dict:
    """Preview image + filament estimate (per material) of one plate of a sliced .3mf."""
    info = inspect(path, os.path.basename(path))
    pl = next((p for p in info["plates"] if p["index"] == plate), None) or \
        (info["plates"][0] if info["plates"] else {})
    materials = []
    for f in pl.get("filaments", []):
        try:
            g = float(f.get("used_g") or 0)
        except ValueError:
            g = 0
        if g > 0:
            materials.append({"type": f.get("type") or "?", "g": round(g, 2)})
    used_g = sum(m["g"] for m in materials)
    meta = {"weight_g": pl.get("weight_g") or used_g or None, "length_m": None,
            "materials": materials, "estimated_s": pl.get("prediction_s"),
            "thumb": None, "thumb_type": "image/png"}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            for cand in (f"Metadata/plate_{pl.get('index', plate)}.png",
                         f"Metadata/plate_{plate}.png", "Metadata/thumbnail.png"):
                if cand in names:
                    meta["thumb"] = z.read(cand)
                    break
            if "Metadata/slice_info.config" in names:
                root = ET.fromstring(z.read("Metadata/slice_info.config"))
                for p in root.iter("plate"):
                    idx = {m.get("key"): m.get("value") for m in p.iter("metadata")}.get("index")
                    if str(idx) == str(pl.get("index", plate)):
                        meters = sum(float(f.get("used_m") or 0) for f in p.iter("filament"))
                        meta["length_m"] = round(meters, 2) or None
    except (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError):
        pass
    return meta


def _numbers(text: str) -> list:
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text or "")]


def parse_gcode_text(text: str) -> dict:
    """Filament info from slicer comments (OrcaSlicer, PrusaSlicer, Bambu Studio, Cura)."""
    meta = {"weight_g": None, "length_m": None, "materials": []}
    grams = []
    m = re.search(r"^;\s*filament used \[g\]\s*=\s*([^\n]+)", text, re.I | re.M)
    if m:
        grams = _numbers(m.group(1))
    m = re.search(r"^;\s*total filament (?:weight|used) \[g\]\s*[:=]\s*([\d.]+)", text, re.I | re.M)
    total_g = float(m.group(1)) if m else (sum(grams) if grams else None)
    if total_g:
        meta["weight_g"] = round(total_g, 1)
    m = re.search(r"^;\s*filament used \[mm\]\s*=\s*([^\n]+)", text, re.I | re.M)
    if m:
        meta["length_m"] = round(sum(_numbers(m.group(1))) / 1000, 2) or None
    m = re.search(r"^;\s*filament_type\s*=\s*([^\n]+)", text, re.I | re.M)
    types = [t.strip() for t in re.split(r"[;,]", m.group(1))] if m else []
    if grams and types:
        # per extruder/filament slot; slots with 0 g were not used
        for i, g in enumerate(grams):
            if g > 0:
                meta["materials"].append({"type": types[i] if i < len(types) else types[-1],
                                          "g": round(g, 2)})
    elif total_g and types:
        used = [t for t in types if t]
        if len(set(used)) == 1:
            meta["materials"] = [{"type": used[0], "g": round(total_g, 2)}]
    return meta


def job_meta_from_gcode(path: str) -> dict:
    """Thumbnail + filament estimate from slicer comments in a .gcode file."""
    import base64
    meta = {"weight_g": None, "length_m": None, "materials": [], "thumb": None,
            "thumb_type": "image/png"}
    try:
        with open(path, "rb") as fh:
            head = fh.read(2_000_000)
            fh.seek(max(0, os.path.getsize(path) - 400_000))
            tail = fh.read()
    except OSError:
        return meta
    text = (head + b"\n" + tail).decode(errors="replace")
    thumbs = re.findall(r"; thumbnail(?:_PNG)? begin (\d+)x(\d+) \d+\n(.*?); thumbnail(?:_PNG)? end",
                        text, flags=re.S)
    if thumbs:
        w, h, data = max(thumbs, key=lambda t: int(t[0]) * int(t[1]))
        try:
            meta["thumb"] = base64.b64decode("".join(line.lstrip("; ").strip() for line in data.splitlines()))
        except ValueError:
            pass
    meta.update(parse_gcode_text(text))
    return meta
