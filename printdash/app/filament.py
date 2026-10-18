"""Filament inventory (storage locations, brands, dryers) stored as JSON in the data directory."""
import copy
import json
import os
import re
import secrets
import threading

from .config import DATA_DIR
from .i18n import t

PATH = os.path.join(DATA_DIR, "filament.json")
CONDITIONS = ("neu", "angefangen")   # stored values; the UI translates them

# Storage locations are a free, ordered list. Older versions had three fixed
# ones ("lager", "ams", "schrank"); their keys stay valid as location ids.
OLD_LOCATIONS = (("lager", "Filamentlager", 40, False), ("ams", "AMS", 30, True),
                 ("schrank", "Schrank", 40, False))
MAX_LOCATIONS = 30


def new_location(name: str = "", **extra) -> dict:
    # printer_id: location that belongs to a printer's AMS (created automatically)
    loc = {"id": secrets.token_hex(4), "name": name, "temp_entity": "", "hum_entity": "",
           "bat_entity": "", "hum_max": 40, "in_printer": False, "printer_id": ""}
    loc.update(extra)
    return loc


DEFAULT = {
    # empty name = the UI shows a translated default ("Filament storage")
    "locations": [new_location("", id="storage")],
    "items": [],
    "brands": [],
    "dryers": [],
}

_lock = threading.Lock()
# held around every load → change → save, so two changes at the same moment
# (e.g. a dryer finishing while a spool is edited) cannot overwrite each other
_tx = threading.RLock()
HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")


def _hex(value, default="#cccccc") -> str:
    v = str(value or "").strip()
    if v and not v.startswith("#"):
        v = "#" + v
    return v if HEX.fullmatch(v) else default


def _transaction(fn):
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _tx:
            return fn(*args, **kwargs)
    return wrapper


def load() -> dict:
    with _tx:
        return _load()


def _load() -> dict:
    with _lock:
        if not os.path.exists(PATH):
            return copy.deepcopy(DEFAULT)
        with open(PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    out = copy.deepcopy(DEFAULT)
    out["locations"] = _locations_from(data.get("locations"))
    out["items"] = data.get("items") or []
    out["assign"] = data.get("assign") or {}
    out["dryers"] = data.get("dryers") or []
    out["slot_memory"] = data.get("slot_memory") or {}
    if "brands" in data:
        out["brands"] = data.get("brands") or []
    else:  # first start with brands: take over the brands already used in the inventory
        names = sorted({str(i.get("brand") or "").strip() for i in out["items"]} - {""}, key=str.lower)
        out["brands"] = [clean_brand({"name": n}) for n in names]
        save(out)  # persist once so the brand ids stay stable
    return out


def _locations_from(raw) -> list:
    """Location list from the stored data; converts the old fixed dict."""
    if isinstance(raw, dict):  # old format: {"lager": {...}, "ams": {...}, "schrank": {...}}
        out = []
        for key, name, hum_max, in_printer in OLD_LOCATIONS:
            old = raw.get(key) or {}
            loc = new_location(name, id=key, hum_max=hum_max, in_printer=in_printer)
            loc.update({k: v for k, v in old.items() if k in loc and k != "id"})
            out.append(loc)
        return out
    out = []
    for loc in raw or []:
        if isinstance(loc, dict) and loc.get("id"):
            base = new_location()
            base.update(loc)
            out.append(base)
    return out or copy.deepcopy(DEFAULT["locations"])


def location_ids(data: dict) -> list:
    return [loc["id"] for loc in data["locations"]]


def location(data: dict, loc_id: str) -> dict | None:
    return next((loc for loc in data["locations"] if loc["id"] == loc_id), None)


def default_location(data: dict, in_printer: bool = False) -> str:
    """First location (or the first one marked 'in the printer', e.g. the AMS)."""
    if in_printer:
        for loc in data["locations"]:
            if loc.get("in_printer"):
                return loc["id"]
    return data["locations"][0]["id"]


def save(data: dict) -> None:
    with _lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, PATH)


def _num(value, default=None, minimum=None):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        v = max(minimum, v)
    return int(v) if v.is_integer() else v


def clean_item(raw: dict, loc_ids: list) -> dict:
    """Validate one inventory entry coming from the browser."""
    location = raw.get("location") if raw.get("location") in loc_ids else loc_ids[0]
    condition = raw.get("condition") if raw.get("condition") in CONDITIONS else "neu"
    color = _hex(raw.get("color"))
    item = {
        "id": raw.get("id") or secrets.token_hex(4),
        "location": location,
        "brand": str(raw.get("brand") or "").strip()[:60],
        "material": str(raw.get("material") or "").strip().upper()[:30],
        "color": color,
        "color_name": str(raw.get("color_name") or "").strip()[:40],
        "count": int(_num(raw.get("count"), 1, 0)),
        "condition": condition,
        "spool_g": _num(raw.get("spool_g"), 1000, 0),
        "remaining_g": _num(raw.get("remaining_g"), None, 0) if condition == "angefangen" else None,
        "note": str(raw.get("note") or "").strip()[:200],
        "uid": str(raw.get("uid") or "").strip().upper()[:64],
        "dried_at": _num(raw.get("dried_at"), None, 0),
    }
    # spools parked in a printer's AMS remember where they came from
    if raw.get("return_to") in loc_ids and raw.get("return_to") != location:
        item["return_to"] = raw["return_to"]
    return item


def clean_brand(raw: dict) -> dict:
    """One brand with defaults for quick entry: spool weight, materials, colours."""
    mats = raw.get("materials") or []
    if isinstance(mats, str):
        mats = re.split(r"[,;]+", mats)
    materials = []
    for m in mats:
        m = str(m or "").strip().upper()[:30]
        if m and m not in materials:
            materials.append(m)
    colors = []
    for c in (raw.get("colors") or [])[:100]:
        if not isinstance(c, dict):
            continue
        hexv = _hex(c.get("color"))
        name = str(c.get("name") or "").strip()[:40]
        mat = str(c.get("material") or "").strip().upper()[:30]
        colors.append({"name": name, "color": hexv, "material": mat})
    return {
        "id": raw.get("id") or secrets.token_hex(4),
        "name": str(raw.get("name") or "").strip()[:60],
        "spool_g": _num(raw.get("spool_g"), 1000, 0),
        "materials": materials[:40],
        "colors": colors,
        "note": str(raw.get("note") or "").strip()[:200],
    }


@_transaction
def upsert_brand(raw: dict) -> dict:
    brand = clean_brand(raw)
    if not brand["name"]:
        raise ValueError(t("Bitte einen Namen angeben"))
    data = load()
    for b in data["brands"]:
        if b.get("id") != brand["id"] and b.get("name", "").lower() == brand["name"].lower():
            raise ValueError(t("Marke „{name}“ gibt es schon", name=brand["name"]))
    old = next((b for b in data["brands"] if b.get("id") == brand["id"]), None)
    if old:
        # renamed: keep the inventory in sync
        if old.get("name") and old["name"] != brand["name"]:
            for it in data["items"]:
                if it.get("brand") == old["name"]:
                    it["brand"] = brand["name"]
        data["brands"][data["brands"].index(old)] = brand
    else:
        data["brands"].append(brand)
    data["brands"].sort(key=lambda b: b["name"].lower())
    save(data)
    return brand


@_transaction
def delete_brand(brand_id: str) -> None:
    data = load()
    data["brands"] = [b for b in data["brands"] if b.get("id") != brand_id]
    save(data)


@_transaction
def upsert(raw: dict) -> dict:
    data = load()
    item = clean_item(raw, location_ids(data))
    if not (location(data, item["location"]) or {}).get("printer_id"):
        item.pop("return_to", None)  # only spools parked in an AMS have an origin
    for i, existing in enumerate(data["items"]):
        if existing.get("id") == item["id"]:
            data["items"][i] = item
            break
    else:
        data["items"].append(item)
    save(data)
    return item


@_transaction
def delete(item_id: str) -> None:
    data = load()
    data["items"] = [i for i in data["items"] if i.get("id") != item_id]
    save(data)


def _clean_location(loc: dict, values: dict) -> None:
    for field in ("name", "temp_entity", "hum_entity", "bat_entity"):
        if field in values:
            loc[field] = str(values[field] or "").strip()[:120]
    if "hum_max" in values:
        loc["hum_max"] = _num(values["hum_max"], loc.get("hum_max"), 0)


@_transaction
def add_location(values: dict) -> dict:
    data = load()
    if len(data["locations"]) >= MAX_LOCATIONS:
        raise ValueError(t("Zu viele Lagerorte"))
    loc = new_location()
    _clean_location(loc, values)
    if not loc["name"]:
        raise ValueError(t("Bitte einen Namen angeben"))
    data["locations"].append(loc)
    save(data)
    return loc


@_transaction
def set_location(key: str, values: dict) -> dict:
    data = load()
    loc = location(data, key)
    if not loc:
        raise ValueError(t("Unbekannter Ort"))
    _clean_location(loc, values)
    save(data)
    return loc


@_transaction
def order_locations(ids: list) -> list:
    data = load()
    pos = {i: n for n, i in enumerate(ids or [])}
    data["locations"].sort(key=lambda loc: pos.get(loc["id"], len(pos)))
    save(data)
    return data["locations"]


@_transaction
def delete_location(key: str, move_to: str | None = None) -> None:
    """Remove a location. Its spools go to `move_to` (required if there are any)."""
    data = load()
    if not location(data, key):
        raise ValueError(t("Unbekannter Ort"))
    if len(data["locations"]) <= 1:
        raise ValueError(t("Der letzte Lagerort kann nicht gelöscht werden"))
    items = [i for i in data["items"] if i.get("location") == key]
    if items:
        if not move_to or move_to == key or not location(data, move_to):
            raise ValueError(t("Bitte wählen, wohin die Spulen verschoben werden"))
        for it in items:
            it["location"] = move_to
    data["locations"] = [loc for loc in data["locations"] if loc["id"] != key]
    save(data)


# -- which stored spools are loaded in a printer ---------------------------------
def _base(material: str) -> str:
    """'PLA Basic' -> 'PLA', 'PETG HF' -> 'PETG', 'PETG CF' -> 'PETG-CF'."""
    tokens = [t for t in re.split(r"[\s_/-]+", str(material or "").upper()) if t]
    if not tokens:
        return ""
    if any(t in ("CF", "GF") for t in tokens[1:]):
        return f"{tokens[0]}-{'CF' if 'CF' in tokens[1:] else 'GF'}"
    return tokens[0]


def _rgb(color):
    c = str(color or "").lstrip("#")
    if len(c) < 6:
        return None
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _color_distance(a, b) -> float:
    ra, rb = _rgb(a), _rgb(b)
    if not ra or not rb:
        return 999.0
    return sum((x - y) ** 2 for x, y in zip(ra, rb)) ** 0.5


def _family(material: str) -> str:
    """'ABS-CF' -> 'ABS', 'PETG HF' -> 'PETG': printers often only know the plain type."""
    return _base(material).split("-")[0]


FAMILY_PENALTY = 25   # extra "colour distance" for ABS <-> ABS-CF instead of an exact match
MAX_DISTANCE = 70     # colours further apart than this are not considered the same spool


def slot_key(printer_id, slot) -> str:
    return f"{printer_id}|{slot}"


def slot_fingerprint(fil: dict) -> str:
    """Identifies what is in a slot; a manual choice is kept until this changes."""
    return f"{str(fil.get('type') or '').upper()}|{str(fil.get('color') or '').lower()}|{fil.get('uid') or ''}"


@_transaction
def set_assignment(printer_id: str, fil: dict, item_id: str) -> None:
    """Manual choice for a loaded slot ('' = automatic, 'none' = not in stock)."""
    data = load()
    assign = data.setdefault("assign", {})
    key = slot_key(printer_id, fil.get("slot"))
    if not item_id:
        assign.pop(key, None)
    else:
        assign[key] = {"item_id": item_id, "fingerprint": slot_fingerprint(fil)}
    save(data)


def match_loaded(items: list, loaded: list, assign: dict | None = None, reserved: dict | None = None,
                 printer_locations=None, printer_home: dict | None = None, memory: dict | None = None) -> dict:
    """Assign loaded printer slots to inventory items. Returns {item_id: [{printer, slot, how}]}.
    1) manual choice (as long as the same spool is in the slot)
    2) spool id (RFID serial)
    3) best colour within the material family; the exact material only gets a small head start,
       so 'ABS black' prefers ABS over ABS-CF, but 'ABS grey' takes a grey ABS-CF over a black ABS.
       Every spool is used at most 'count' times, so a second black ABS gets the ABS-CF."""
    assign = assign or {}
    result = {}
    reserved = reserved or {}
    capacity = {i["id"]: max(int(i.get("count") or 0) - reserved.get(i["id"], 0), 0) for i in items}
    printer_locs = set(printer_locations or ())
    printer_home = printer_home or {}
    by_id = {i["id"]: i for i in items}

    def take(item, printer, fil, how):
        result.setdefault(item["id"], []).append({"printer": printer, "slot": fil["slot"], "how": how})
        capacity[item["id"]] -= 1
        fil["item_id"] = item["id"]
        fil["how"] = how

    slots = [(p, f) for p in loaded for f in p["filaments"] if f.get("type")]
    # 1) manual
    for p, fil in slots:
        a = assign.get(slot_key(p.get("printer_id"), fil.get("slot")))
        if not a or a.get("fingerprint") != slot_fingerprint(fil):
            continue
        if a.get("item_id") == "none":
            fil["manual"] = True
            fil["item_id"] = None
            fil["how"] = "manual_none"
        elif a.get("item_id") in by_id:
            fil["manual"] = True
            take(by_id[a["item_id"]], p["printer"], fil, "manual")
    # 1b) the spool that was in this slot before (e.g. after filament was used from it)
    for p, fil in slots:
        if fil.get("manual") or fil.get("item_id"):
            continue
        m = (memory or {}).get(slot_key(p.get("printer_id"), fil.get("slot")))
        if m and m.get("fingerprint") == slot_fingerprint(fil) and m.get("item_id") in by_id \
                and capacity.get(m["item_id"], 0) > 0:
            take(by_id[m["item_id"]], p["printer"], fil, "memory")
    # 2) by identifier
    for p, fil in slots:
        if fil.get("manual") or fil.get("item_id"):
            continue
        uid = (fil.get("uid") or "").upper()
        if not uid:
            continue
        for item in items:
            if item.get("uid") and item["uid"] == uid and capacity[item["id"]] > 0:
                take(item, p["printer"], fil, "uid")
                break
    # 3) colour within the material family
    for p, fil in slots:
        if fil.get("item_id") or fil.get("manual"):
            continue
        base, fam = _base(fil.get("type")), _family(fil.get("type"))
        best = None
        for item in items:
            if capacity[item["id"]] <= 0 or _family(item.get("material")) != fam:
                continue
            dist = _color_distance(item.get("color"), fil.get("color"))
            if dist >= MAX_DISTANCE:
                continue
            exact = _base(item.get("material")) == base
            # tie-breakers: spools parked in this printer's AMS, then any location "in the printer"
            score = (dist + (0 if exact else FAMILY_PENALTY),
                     item.get("location") != printer_home.get(p.get("printer_id")),
                     item.get("location") not in printer_locs,
                     item.get("condition") != "angefangen")  # an opened spool rather than a new one
            if best is None or score < best[0]:
                best = (score, item, exact)
        if best:
            take(best[1], p["printer"], fil, "color" if best[2] else "family_color")
    return result


def match(data: dict, loaded: list, reserved: dict | None = None) -> dict:
    """match_loaded with the location hints of this inventory."""
    return match_loaded(
        data["items"], loaded, data.get("assign"), reserved,
        [loc["id"] for loc in data["locations"] if loc.get("in_printer")],
        {loc["printer_id"]: loc["id"] for loc in data["locations"] if loc.get("printer_id")},
        data.get("slot_memory"))


def item_label(item: dict) -> str:
    return " ".join(x for x in (item.get("material"), item.get("brand"), item.get("color_name")) if x) or t("Spule")


@_transaction
def use_filament(item_id: str, grams: float, printer_id: str | None = None, fil: dict | None = None) -> dict | None:
    """Subtract used filament from one spool of an entry. A new spool becomes "angefangen";
    of several equal spools one is split off. Returns {item_id, label, g, before, left}."""
    data = load()
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    if not item or not grams or grams <= 0 or int(item.get("count") or 0) <= 0:
        return None
    count = int(item["count"])
    opened = item.get("condition") == "angefangen" and item.get("remaining_g") is not None
    before = float(item["remaining_g"]) if opened else float(item.get("spool_g") or 1000)
    target = item
    if count > 1:
        target = {**item, "id": secrets.token_hex(4), "count": 1}
        item["count"] = count - 1
        data["items"].append(target)
    target["condition"] = "angefangen"
    target["remaining_g"] = round(max(0.0, before - grams), 1)
    if printer_id and fil:
        key = slot_key(printer_id, fil.get("slot"))
        a = (data.get("assign") or {}).get(key)
        if a and a.get("item_id") == item["id"]:
            a["item_id"] = target["id"]
        # remember which spool is in this slot, so the next print uses the same one
        data.setdefault("slot_memory", {})[key] = {"item_id": target["id"], "fingerprint": slot_fingerprint(fil)}
    save(data)
    return {"item_id": target["id"], "label": item_label(target), "g": round(grams, 1),
            "before": round(before, 1), "left": target["remaining_g"]}


# -- AMS of a printer: spools stay there while the printer is off ----------------------
def ams_location(data: dict, printer_id: str) -> dict | None:
    return next((loc for loc in data["locations"] if loc.get("printer_id") == printer_id), None)


@_transaction
def ensure_printer_locations(printers: list) -> list:
    """Create a storage location for every Bambu printer with "AMS vorhanden".
    An old unlinked AMS location (e.g. the former fixed "ams") is taken over instead."""
    data = load()
    created = []
    for p in printers:
        if p.get("type") != "bambu" or not p.get("has_ams") or not p.get("id"):
            continue
        if ams_location(data, p["id"]):
            continue
        free = next((loc for loc in data["locations"] if loc.get("in_printer") and not loc.get("printer_id")), None)
        if free:
            free["printer_id"] = p["id"]
            created.append(free)
            continue
        if len(data["locations"]) >= MAX_LOCATIONS:
            continue
        loc = new_location(f"AMS – {p.get('name') or 'Bambu'}", in_printer=True, printer_id=p["id"], hum_max=30)
        data["locations"].append(loc)
        created.append(loc)
    if created:
        save(data)
    return created


_TWIN_KEYS = ("brand", "material", "color_name", "condition", "uid", "spool_g", "remaining_g", "note")


def _is_twin(a: dict, b: dict) -> bool:
    return all((a.get(k) or "") == (b.get(k) or "") for k in _TWIN_KEYS) \
        and str(a.get("color") or "").lower() == str(b.get("color") or "").lower()


def _move_units(data: dict, item: dict, qty: int, to_loc: str, return_to: str | None) -> dict:
    """Move qty spools of item to another location; splits or merges entries as needed.
    Returns the entry that now holds the moved spools."""
    count = int(item.get("count") or 0)
    qty = max(0, min(qty, count))
    twin = next((i for i in data["items"] if i is not item and i.get("location") == to_loc
                 and (i.get("return_to") or None) == (return_to or None) and _is_twin(i, item)), None)
    if twin:
        twin["count"] = int(twin.get("count") or 0) + qty
        item["count"] = count - qty
        target = twin
    elif qty >= count:
        item["location"] = to_loc
        target = item
    else:
        target = {**item, "id": secrets.token_hex(4), "location": to_loc, "count": qty}
        item["count"] = count - qty
        data["items"].append(target)
    if return_to:
        target["return_to"] = return_to
    else:
        target.pop("return_to", None)
    if target is not item and not item.get("count"):
        # the old entry is empty now: remove it and point manual assignments to the new one
        data["items"] = [i for i in data["items"] if i is not item]
        for a in (data.get("assign") or {}).values():
            if a.get("item_id") == item["id"]:
                a["item_id"] = target["id"]
    return target


@_transaction
def move_item(item_id: str, to_loc: str, qty) -> dict:
    """Move some spools of an entry to another location (split / merge as needed)."""
    data = load()
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    dest = location(data, to_loc)
    if not item or not dest:
        raise ValueError(t("Unbekannter Ort") if item else t("Spule nicht gefunden"))
    count = int(item.get("count") or 0)
    qty = int(_num(qty, 1, 1) or 1)
    if item.get("location") == to_loc or count <= 0:
        return item
    if qty > count:
        raise ValueError(t("Es sind nur {n} Spulen vorhanden", n=count))
    origin = location(data, item.get("location")) or {}
    # into an AMS location: remember where the spools came from
    return_to = None
    if dest.get("printer_id"):
        return_to = item.get("return_to") if origin.get("printer_id") else origin.get("id")
    target = _move_units(data, item, qty, to_loc, return_to)
    save(data)
    return target


@_transaction
def park_in_ams(printer_id: str, slot_items: dict) -> int:
    """Printer was switched off: spools detected in its AMS move to its AMS location.
    slot_items = {slot: item_id}. Returns the number of spools moved."""
    data = load()
    loc = ams_location(data, printer_id)
    if not loc:
        return 0
    per_item = {}
    for slot, item_id in slot_items.items():
        if item_id and str(slot) != "Ext":
            per_item[item_id] = per_item.get(item_id, 0) + 1
    moved = 0
    by_id = {i["id"]: i for i in data["items"]}
    for item_id, n in per_item.items():
        item = by_id.get(item_id)
        if not item or item.get("location") == loc["id"]:
            continue
        origin = item.get("location")
        target = _move_units(data, item, n, loc["id"], origin)
        moved += n
        for slot, iid in slot_items.items():  # manual assignments follow the spool
            a = (data.get("assign") or {}).get(slot_key(printer_id, slot))
            if a and iid == item_id and a.get("item_id") == item_id:
                a["item_id"] = target["id"]
    if moved:
        save(data)
    return moved


@_transaction
def unpark(printer_id: str, item_id: str) -> bool:
    """A spool was taken out of the AMS while the printer runs: back to where it came from."""
    data = load()
    loc = ams_location(data, printer_id)
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    if not loc or not item or item.get("location") != loc["id"]:
        return False
    home = item.get("return_to")
    if not home or not location(data, home):
        return False
    _move_units(data, item, 1, home, None)
    save(data)
    return True


# -- filament dryers ---------------------------------------------------------------
MAX_DRYERS = 4

# rough drying guide (°C, hours); manufacturer data has priority
DRY_GUIDE = {
    "PLA": (50, 6), "PETG": (65, 6), "ABS": (70, 4), "ASA": (70, 4), "TPU": (55, 6),
    "PA": (80, 10), "PC": (80, 8), "PVA": (55, 8), "HIPS": (65, 4),
}


def dry_guide(material: str):
    fam = _family(material)
    return DRY_GUIDE.get(fam)


def _new_dryer(n: int) -> dict:
    return {"id": secrets.token_hex(3), "name": t("Trockner {n}", n=n), "job": None, "last": None}


@_transaction
def set_dryer_count(count: int) -> list:
    count = max(0, min(MAX_DRYERS, int(count)))
    data = load()
    dryers = data["dryers"]
    if count < len(dryers) and any(d.get("job") for d in dryers[count:]):
        raise ValueError(t("Ein Trockner, der entfernt würde, ist gerade in Betrieb"))
    while len(dryers) < count:
        dryers.append(_new_dryer(len(dryers) + 1))
    data["dryers"] = dryers[:count]
    save(data)
    return data["dryers"]


def _dryer(data: dict, dryer_id: str) -> dict:
    d = next((d for d in data["dryers"] if d["id"] == dryer_id), None)
    if not d:
        raise ValueError(t("Trockner nicht gefunden"))
    return d


@_transaction
def rename_dryer(dryer_id: str, name: str) -> dict:
    data = load()
    d = _dryer(data, dryer_id)
    d["name"] = str(name or "").strip()[:40] or d["name"]
    save(data)
    return d


def in_dryer(data: dict) -> dict:
    """{item_id: [{dryer, qty}]} for all running dryers."""
    out = {}
    for d in data.get("dryers") or []:
        for e in (d.get("job") or {}).get("items") or []:
            out.setdefault(e["item_id"], []).append({"dryer": d["name"], "dryer_id": d["id"], "qty": e["qty"]})
    return out


@_transaction
def start_drying(dryer_id: str, items: list, minutes: float, temp=None, now: float | None = None) -> dict:
    import time
    now = now or time.time()
    data = load()
    d = _dryer(data, dryer_id)
    minutes = _num(minutes, 0, 0)
    if not minutes:
        raise ValueError(t("Bitte eine Trocknungszeit angeben"))
    by_id = {i["id"]: i for i in data["items"]}
    busy = in_dryer({"dryers": [x for x in data["dryers"] if x["id"] != dryer_id]})
    clean = []
    for e in items or []:
        item = by_id.get(e.get("item_id"))
        qty = int(_num(e.get("qty"), 1, 0))
        if not item or qty <= 0:
            continue
        free = int(item.get("count") or 0) - sum(x["qty"] for x in busy.get(item["id"], []))
        if qty > free:
            raise ValueError(t("Von {spool} sind nur {free} verfügbar",
                               spool=f"{item.get('material')} {item.get('color_name') or ''}".strip(), free=max(free, 0)))
        clean.append({"item_id": item["id"], "qty": qty})
    if not clean:
        raise ValueError(t("Bitte mindestens eine Spule wählen"))
    d["job"] = {"items": clean, "start": now, "end": now + minutes * 60,
                "minutes": minutes, "temp": _num(temp, None, 0), "notified": False}
    save(data)
    return d


@_transaction
def extend_drying(dryer_id: str, minutes: float) -> dict:
    data = load()
    d = _dryer(data, dryer_id)
    if not d.get("job"):
        raise ValueError(t("Trockner läuft nicht"))
    minutes = _num(minutes, 0, 0)
    if not minutes:
        raise ValueError(t("Bitte eine Verlängerung in Minuten angeben"))
    d["job"]["end"] += minutes * 60
    d["job"]["minutes"] = round((d["job"]["end"] - d["job"]["start"]) / 60)
    d["job"]["notified"] = False
    save(data)
    return d


@_transaction
def finish_drying(dryer_id: str, done: bool = True, now: float | None = None) -> dict | None:
    """End a drying job: spools go back to where they came from.
    done=True marks them as dried (date shown in the inventory)."""
    import time
    now = now or time.time()
    data = load()
    d = _dryer(data, dryer_id)
    job = d.get("job")
    if not job:
        return None
    if done:
        ids = {e["item_id"] for e in job["items"]}
        for it in data["items"]:
            if it["id"] in ids:
                it["dried_at"] = now
    d["last"] = {"items": job["items"], "start": job["start"], "end": now, "done": done,
                 "minutes": job.get("minutes"), "temp": job.get("temp")}
    d["job"] = None
    save(data)
    return d


def due_dryers(now: float) -> list:
    return [d for d in load()["dryers"] if d.get("job") and d["job"]["end"] <= now]
