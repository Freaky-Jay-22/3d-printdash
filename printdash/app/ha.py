"""Minimal Home Assistant REST client (used for smart plugs).

As an add-on the Supervisor token is used automatically. With docker compose,
set HA_URL and HA_TOKEN (long-lived access token).
"""
import re

import httpx

from .notify import ha_api
from .i18n import t

POWER_DOMAINS = ("switch", "light", "input_boolean")


class HAError(Exception):
    pass


class PrinterBusy(HAError):
    """Switching off is refused because the printer is printing."""


async def _request(method: str, path: str, **kw):
    base, token = ha_api()
    if not base:
        raise HAError(t("Home Assistant nicht verbunden"))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.request(method, f"{base}{path}",
                                     headers={"Authorization": f"Bearer {token}"}, **kw)
    except httpx.HTTPError as exc:
        raise HAError(t("Home Assistant nicht erreichbar: {error}", error=exc)) from exc
    if r.status_code == 404:
        raise HAError(t("Entität nicht gefunden"))
    if r.status_code >= 400:
        raise HAError(t("Home Assistant: Fehler {code}", code=r.status_code))
    return r.json()


async def _request_text(method: str, path: str, **kw) -> str:
    base, token = ha_api()
    if not base:
        raise HAError(t("Home Assistant nicht verbunden"))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.request(method, f"{base}{path}",
                                     headers={"Authorization": f"Bearer {token}"}, **kw)
    except httpx.HTTPError as exc:
        raise HAError(t("Home Assistant nicht erreichbar: {error}", error=exc)) from exc
    if r.status_code >= 400:
        raise HAError(t("Home Assistant: Fehler {code}", code=r.status_code))
    return r.text


def available() -> bool:
    return ha_api()[0] is not None


async def power_entities() -> list:
    """Switch-like entities for the settings dropdown."""
    states = await _request("GET", "/states")
    out = []
    for s in states:
        domain = s["entity_id"].split(".", 1)[0]
        if domain in POWER_DOMAINS:
            out.append({
                "entity_id": s["entity_id"],
                "name": s.get("attributes", {}).get("friendly_name") or s["entity_id"],
                "state": s.get("state"),
            })
    # plugs first (switch domain), then by name
    out.sort(key=lambda e: (not e["entity_id"].startswith("switch."), e["name"].lower()))
    return out


async def get_state(entity_id: str) -> dict:
    return await _request("GET", f"/states/{entity_id}")


async def set_power(entity_id: str, on: bool):
    domain = entity_id.split(".", 1)[0]
    if domain not in POWER_DOMAINS:
        raise HAError(t("{entity} ist keine schaltbare Entität", entity=entity_id))
    await _request("POST", f"/services/{domain}/turn_{'on' if on else 'off'}",
                   json={"entity_id": entity_id})


# -- Bambu Lab integration (ha-bambulab) entities ------------------------------
# Entity ids depend on the HA language (e.g. German: button.x1c_druck_pausieren),
# so entities are found via the integration and classified by keywords.
KEYWORDS = {
    "pause": ("pause", "pausier"),
    "resume": ("resume", "fortsetz", "weiter", "continue"),
    "stop": ("stop", "abbrech", "cancel", "beend"),
    "light": ("chamber", "kammer"),
}


def _classify(entity: dict) -> str | None:
    text = f"{entity['entity_id']} {entity['name']}".lower()
    domain = entity["entity_id"].split(".", 1)[0]
    if domain == "light":
        return "light" if any(k in text for k in KEYWORDS["light"]) else None
    if domain != "button":
        return None
    for key in ("resume", "pause", "stop"):  # "resume" first: may contain "pause" in names
        if any(k in text for k in KEYWORDS[key]):
            return key
    return None


async def bambu_entities() -> dict:
    """Buttons/lights of the HA Bambu Lab integration plus a best guess per function."""
    ids = None
    try:
        rendered = await _request_text("POST", "/template",
                                       json={"template": "{{ integration_entities('bambu_lab') | tojson }}"})
        import json as _json
        ids = set(_json.loads(rendered))
    except (HAError, ValueError):
        ids = None
    states = await _request("GET", "/states")
    buttons, lights = [], []
    for s in states:
        eid = s["entity_id"]
        if ids is not None and eid not in ids:
            continue
        item = {"entity_id": eid, "name": s.get("attributes", {}).get("friendly_name") or eid,
                "state": s.get("state")}
        if eid.startswith("button."):
            buttons.append(item)
        elif eid.startswith("light."):
            lights.append(item)
    guess = {}
    for item in buttons + lights:
        key = _classify(item)
        if key and key not in guess:
            guess[key] = item["entity_id"]
    return {"buttons": buttons, "lights": lights, "guess": guess,
            "filtered": ids is not None}


async def press(entity_id: str):
    domain = entity_id.split(".", 1)[0]
    services = {"button": "press", "input_button": "press", "script": "turn_on",
                "switch": "turn_on", "scene": "turn_on"}
    if domain not in services:
        raise HAError(t("{entity} kann nicht ausgelöst werden (erwartet button.…, script.… o. ä.)", entity=entity_id))
    await _request("POST", f"/services/{domain}/{services[domain]}", json={"entity_id": entity_id})


async def set_light(entity_id: str, on: bool):
    domain = entity_id.split(".", 1)[0]
    if domain not in ("light", "switch"):
        raise HAError(t("{entity} ist kein Licht", entity=entity_id))
    await _request("POST", f"/services/{domain}/turn_{'on' if on else 'off'}",
                   json={"entity_id": entity_id})


# -- cover image (print preview) of the Bambu Lab integration ------------------
COVER_WORDS = ("cover", "titelbild", "vorschau", "preview")


async def bambu_images() -> list:
    """image.* entities of the Bambu Lab integration (cover image first)."""
    try:
        import json as _json
        rendered = await _request_text("POST", "/template",
                                       json={"template": "{{ integration_entities('bambu_lab') | tojson }}"})
        ids = set(_json.loads(rendered))
    except (HAError, ValueError):
        ids = None
    states = await _request("GET", "/states")
    out = []
    for s in states:
        eid = s["entity_id"]
        if not eid.startswith("image.") or (ids is not None and eid not in ids):
            continue
        name = s.get("attributes", {}).get("friendly_name") or eid
        out.append({"entity_id": eid, "name": name,
                    "cover": any(w in f"{eid} {name}".lower() for w in COVER_WORDS)})
    out.sort(key=lambda x: not x["cover"])
    return out


async def get_image(entity_id: str) -> tuple[bytes, str] | None:
    """Current picture of an image entity via the HA image proxy."""
    base, token = ha_api()
    if not base:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{base}/image_proxy/{entity_id}",
                                 headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        return None
    if r.status_code != 200 or not r.content:
        return None
    return r.content, r.headers.get("content-type", "image/png")



# -- print weight of the Bambu Lab integration (cloud prints) ------------------------
WEIGHT_WORDS = ("print_weight", "print weight", "gewicht_des_drucks", "gewicht des drucks", "druckgewicht")
_TRAY = re.compile(r"ams\s*(\d+)\s*tray\s*(\d+)", re.I)


async def bambu_print_weight(serial: str = "") -> dict | None:
    """Filament weight of the current print from the HA Bambu Lab integration.
    The integration knows it for prints sent through the Bambu cloud (the print file is
    then not on the printer's SD card). Returns {"weight_g", "slots": {slot: g}} or None."""
    import json as _json
    template = ("{% set ns = namespace(o=[]) %}{% for e in integration_entities('bambu_lab') %}"
                "{% if e.startswith('sensor.') and state_attr(e, 'device_class') == 'weight' %}"
                "{% set d = device_id(e) %}"
                "{% set ns.o = ns.o + [{'id': e, 'serial': (device_attr(d, 'serial_number') if d else '') or ''}] %}"
                "{% endif %}{% endfor %}{{ ns.o | tojson }}")
    try:
        found = _json.loads(await _request_text("POST", "/template", json={"template": template}))
    except (HAError, ValueError):
        return None
    serial = (serial or "").strip().lower()

    def rank(c):
        sid = str(c.get("serial") or "").lower()
        mine = (serial and sid == serial) or (serial and serial in c["id"].lower())
        named = any(w in c["id"].lower() for w in WEIGHT_WORDS)
        return (not mine, not named)
    found.sort(key=rank)
    for c in found:
        sid = str(c.get("serial") or "").lower()
        if serial and sid and sid != serial and serial not in c["id"].lower():
            continue  # sensor of another printer
        try:
            st = await get_state(c["id"])
        except HAError:
            continue
        attrs = st.get("attributes") or {}
        slots = {}
        for key, value in attrs.items():
            m = _TRAY.search(str(key))
            try:
                g = float(value)
            except (TypeError, ValueError):
                continue
            if m and g > 0:
                slots[(int(m.group(1)) - 1) * 4 + int(m.group(2))] = g
            elif "ext" in str(key).lower() and g > 0:
                slots["Ext"] = g
        try:
            total = float(st.get("state"))
        except (TypeError, ValueError):
            total = 0
        if not (total > 0 or slots) or not (any(w in c["id"].lower() for w in WEIGHT_WORDS) or slots):
            continue
        return {"weight_g": round(total or sum(slots.values()), 2), "slots": slots, "entity": c["id"]}
    return None


# -- climate sensors for the filament tab ----------------------------------------
async def climate_sensors() -> dict:
    """Temperature, humidity and battery sensors.
    Battery is checked first so 'Feuchtigkeitssensor Batterie' is not listed as humidity;
    the battery list additionally offers every other %-sensor, in case one is mis-tagged."""
    states = await _request("GET", "/states")
    temps, hums, bats, other_pct = [], [], [], []
    vocs, co2s, pms, press = [], [], [], []
    for s in states:
        eid = s["entity_id"]
        if not eid.startswith("sensor."):
            continue
        attrs = s.get("attributes", {})
        dc = attrs.get("device_class")
        unit = attrs.get("unit_of_measurement")
        name = attrs.get("friendly_name") or eid
        text = f"{eid} {name}".lower()
        item = {"entity_id": eid, "name": name, "state": s.get("state"), "unit": unit}
        is_battery = dc == "battery" or (unit == "%" and any(w in text for w in ("batt", "akku")))
        if is_battery:
            bats.append(item)
        elif dc == "temperature" or unit in ("°C", "°F"):
            temps.append(item)
        elif dc == "humidity" or (unit == "%" and any(w in text for w in ("humid", "feucht"))):
            hums.append(item)
            other_pct.append(item)
        elif dc in ("volatile_organic_compounds", "volatile_organic_compounds_parts") or unit == "ppb" \
                or "voc" in text:
            vocs.append(item)
        elif dc == "carbon_dioxide" or "co2" in text:
            co2s.append(item)
        elif dc in ("pm25", "pm1", "pm10") or any(w in text for w in ("pm2", "pm1", "feinstaub", "particulate")):
            pms.append(item)
        elif dc in ("atmospheric_pressure", "pressure") or unit in ("hPa", "mbar", "kPa", "inHg", "psi"):
            press.append(item)
        elif unit == "%":
            other_pct.append(item)
    key = lambda x: x["name"].lower()  # noqa: E731
    temps.sort(key=key)
    hums.sort(key=key)
    bats.sort(key=key)
    other_pct.sort(key=key)
    for lst in (vocs, co2s, pms, press):
        lst.sort(key=key)
    return {"temperature": temps, "humidity": hums, "battery": bats + other_pct,
            "voc": vocs, "co2": co2s, "pm25": pms, "pressure": press}


async def sensor_values(entity_ids: list) -> dict:
    out = {}
    for eid in {e for e in entity_ids if e}:
        try:
            s = await _request("GET", f"/states/{eid}")
            out[eid] = {"state": s.get("state"),
                        "unit": s.get("attributes", {}).get("unit_of_measurement")}
        except HAError as exc:
            out[eid] = {"state": None, "error": str(exc)}
    return out
