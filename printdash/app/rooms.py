"""Room climate: optional Home Assistant sensors of the room the printers stand in.

Each room in config["rooms"] names up to seven sensors (all optional) and limits:
  temp_entity, hum_entity, voc_entity, co2_entity, pm25_entity, pressure_entity, bat_entity
  hum_max, temp_max (red above), voc/co2/pm25 _warn (yellow from) and _max (red from)
The values are read every 10 s by the manager and shown at the top of the overview.
"""
from . import ha

SENSORS = ("temp", "hum", "voc", "co2", "pm25", "pressure", "bat")
# defaults: humidity in %, VOC in ppb, CO2 in ppm, fine dust PM2.5 in µg/m³
LIMITS = {"hum_max": 60, "temp_max": 0, "voc_warn": 250, "voc_max": 2000,
          "co2_warn": 1000, "co2_max": 1500, "pm25_warn": 15, "pm25_max": 35}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def limits(room: dict) -> dict:
    out = {}
    for key, default in LIMITS.items():
        v = _num(room.get(key))
        out[key] = default if v is None else v
    return out


def entities(room: dict) -> dict:
    return {k: (room.get(f"{k}_entity") or "").strip() for k in SENSORS}


def configured(rooms: list) -> list:
    return [r for r in rooms or [] if any(entities(r).values())]


def level(key: str, value, lim: dict) -> str:
    """"" (ok) | "warn" (yellow) | "bad" (red)"""
    if value is None:
        return ""
    if key == "hum":
        return "bad" if lim["hum_max"] and value > lim["hum_max"] else ""
    if key == "temp":
        return "bad" if lim["temp_max"] and value > lim["temp_max"] else ""
    if key == "bat":
        return "bad" if value < 20 else ""
    if key in ("voc", "co2", "pm25"):
        if lim[f"{key}_max"] and value >= lim[f"{key}_max"]:
            return "bad"
        if lim[f"{key}_warn"] and value >= lim[f"{key}_warn"]:
            return "warn"
    return ""


async def read(rooms: list) -> dict:
    """{room_id: {key: {value, unit}}} for all configured rooms (one request per sensor)."""
    rooms = configured(rooms)
    if not rooms or not ha.available():
        return {}
    wanted = [e for r in rooms for e in entities(r).values() if e]
    values = await ha.sensor_values(wanted)
    out = {}
    for r in rooms:
        vals = {}
        for key, eid in entities(r).items():
            if eid:
                v = values.get(eid) or {}
                vals[key] = {"value": _num(v.get("state")), "unit": v.get("unit")}
        out[r.get("id")] = vals
    return out


def view(rooms: list, data: dict) -> list:
    """What the overview shows: name, values with unit and level."""
    out = []
    for r in configured(rooms):
        lim = limits(r)
        vals = data.get(r.get("id")) or {}
        items = []
        for key in SENSORS:
            if not entities(r)[key]:
                continue
            v = vals.get(key) or {}
            items.append({"key": key, "value": v.get("value"), "unit": v.get("unit"),
                          "level": level(key, v.get("value"), lim)})
        out.append({"id": r.get("id"), "name": (r.get("name") or "").strip(), "items": items, "limits": lim})
    return out
