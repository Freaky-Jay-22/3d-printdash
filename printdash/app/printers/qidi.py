"""Qidi Box (Qidi Q2, Plus4 ...): which filament is loaded in which slot.

The Qidi firmware keeps the box slots in Klipper's save_variables:
  filament_slot<N>  filament id, e.g. "QFA02" (firmware 01.01.03 and later)
  color_slot<N>     ["RRGGBB"]
  slot<N>           1 = a spool is in the slot
  value_t<N>        tool T<N> -> "slot<M>"
  last_load_slot    the slot that was loaded into the nozzle last ("slot16" = external spool)
  box_count         number of boxes, 4 slots each
Filament ids come from the printer's filament list (filament-<nozzle>.json); the
table below is a copy of it, unknown ids fall back to the material family of their prefix.
"""
import re

# filament id -> (material, vendor, name)
FILAMENTS = {
    "QFA00": ("PLA", "QIDI", "PLA Basic"),
    "QFA01": ("PLA", "QIDI", "PLA Matte Basic"),
    "QFA02": ("PLA", "QIDI", "PLA Rapido"),
    "QFA03": ("PLA", "QIDI", "PLA Rapido Matte"),
    "QFA04": ("PLA", "QIDI", "PLA Rapido Metal"),
    "QFA05": ("PLA", "QIDI", "PLA Silk"),
    "QFA16": ("PLA", "QIDI", "WOOD Rapido"),
    "QFA50": ("PLA-CF", "QIDI", "PLA-CF"),
    "QFA90": ("PLA", "Generic", "PLA"),
    "QFA91": ("PLA", "Generic", "PLA+"),
    "QFA92": ("PLA", "Generic", "PLA Silk"),
    "QFB01": ("ASA", "QIDI", "ASA"),
    "QFB02": ("ASA-AERO", "QIDI", "ASA-Aero"),
    "QFB50": ("ABS-GF", "QIDI", "ABS-GF"),
    "QFB51": ("ASA-CF", "QIDI", "ASA-CF20 Core"),
    "QFB53": ("ABS", "QIDI", "ABS Odorless"),
    "QFB54": ("ABS", "QIDI", "ABS Rapido"),
    "QFB55": ("ABS", "QIDI", "ABS Rapido Metal"),
    "QFB91": ("ABS", "Generic", "ABS"),
    "QFC02": ("PC-ABS-FR", "QIDI", "PC/ABS-FR"),
    "QFC90": ("PC", "Generic", "PC"),
    "QFG00": ("PETG", "QIDI", "PETG Basic"),
    "QFG02": ("PETG", "QIDI", "PETG Rapido"),
    "QFG03": ("PETG", "QIDI", "PETG Tough"),
    "QFG04": ("PETG", "QIDI", "PETG Translucent"),
    "QFG50": ("PETG-CF", "QIDI", "PETG-CF"),
    "QFG51": ("PETG-GF", "QIDI", "PETG-GF"),
    "QFG90": ("PETG", "Generic", "PETG"),
    "QFL10": ("PLA", "HATCHBOX", "PLA"),
    "QFL11": ("PETG", "HATCHBOX", "PETG"),
    "QFL12": ("ABS", "HATCHBOX", "ABS"),
    "QFL20": ("PLA", "Polymaker", "PLA"),
    "QFL22": ("ABS", "Polymaker", "ABS"),
    "QFL24": ("PLA", "Polymaker", "PLA-HT"),
    "QFL30": ("PLA", "Bambu", "PLA"),
    "QFL31": ("PETG", "Bambu", "PETG"),
    "QFL32": ("ABS", "Bambu", "ABS"),
    "QFL60": ("PLA", "Overture", "PLA"),
    "QFL62": ("ABS", "Overture", "ABS"),
    "QFN04": ("PAHT-CF", "QIDI", "PAHT-CF"),
    "QFN05": ("PA6-CF", "QIDI", "PA6-CF"),
    "QFN12": ("PA12-CF", "QIDI", "PA12-CF"),
    "QFN14": ("PAHT-GF", "QIDI", "PAHT-GF"),
    "QFN20": ("UltraPA", "QIDI", "UltraPA"),
    "QFN21": ("UltraPA-CF25", "QIDI", "UltraPA-CF25"),
    "QFP01": ("PPS-CF", "QIDI", "PPS-CF"),
    "QFP02": ("PPS-GF", "QIDI", "PPS-GF"),
    "QFS01": ("PA-S", "QIDI", "Support For PET/PA"),
    "QFS03": ("PAHT-S", "QIDI", "Support For PAHT"),
    "QFT01": ("PET-CF", "QIDI", "PET-CF"),
    "QFT02": ("PET-GF", "QIDI", "PET-GF"),
    "QFU00": ("TPU-AERO", "QIDI", "TPU-Aero"),
    "QFU01": ("TPU", "QIDI", "TPU 95A-HF"),
    "QFU02": ("TPU-GF", "QIDI", "TPU-GF"),
    "QFU03": ("PEBA", "QIDI", "PEBA 95A"),
    "QFU91": ("TPU", "Generic", "TPU 95A"),
}
# material family by id prefix, for ids not in the table
PREFIX = {"QFA": "PLA", "QFB": "ABS", "QFC": "PC", "QFG": "PETG", "QFN": "PA", "QFP": "PPS",
          "QFS": "Support", "QFT": "PET", "QFU": "TPU"}
EXTERNAL_SLOT = 16


def detect(objects: list) -> bool:
    """A Qidi printer with a box: box_stepper objects plus save_variables."""
    return "save_variables" in objects and any(o.startswith("box_stepper ") for o in objects)


def _color(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", value.strip()):
        return "#" + value.strip().lstrip("#").lower()
    return None


def describe(fid) -> tuple:
    """(material, vendor, name) for a filament id; ("", "", "") when unknown or empty."""
    if not isinstance(fid, str) or not fid.strip():
        return "", "", ""
    fid = fid.strip().upper()
    if fid in FILAMENTS:
        return FILAMENTS[fid]
    return PREFIX.get(fid[:3], fid), "", ""


def filaments(variables: dict) -> list:
    """Loaded filament per box slot (and the external spool), in the app's format."""
    v = variables or {}
    if not v.get("enable_box", 1):
        return []
    try:
        boxes = max(0, min(4, int(v.get("box_count") or 0)))
    except (TypeError, ValueError):
        boxes = 0
    last = str(v.get("last_load_slot") or "")
    out = []
    for i in list(range(boxes * 4)) + [EXTERNAL_SLOT]:
        fid = v.get(f"filament_slot{i}")
        material, vendor, name = describe(fid)
        if i == EXTERNAL_SLOT and not material:
            continue   # no external spool set
        present = v.get(f"slot{i}") in (1, True, "1") or (i == EXTERNAL_SLOT and bool(material))
        if not present:
            material, vendor, name = "", "", ""
        out.append({
            "uid": None,
            "slot": "Ext" if i == EXTERNAL_SLOT else i + 1,
            "type": material,
            "color": _color(v.get(f"color_slot{i}")) if material else None,
            "vendor": vendor,
            "name": name,
            "active": bool(material) and last == f"slot{i}",
            "remain": None,
        })
    return out
