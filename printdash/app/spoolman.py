"""Optional link to Spoolman (https://github.com/Donkie/Spoolman), a self-hosted spool manager.

Three ways to keep the filament inventory (setting filament.source):
- "own"      – 3D-PrintDash's own inventory (default, Spoolman is not used)
- "spoolman" – the spools come from Spoolman and are only shown here. 3D-PrintDash deducts nothing,
               Spoolman (or e.g. Moonraker) keeps track of the usage. Stored in its own file, so the
               own inventory stays untouched when switching back.
- "sync"     – both inventories are kept equal: spools from Spoolman appear here, spools added here are
               created in Spoolman, moves, edits and the usage after each print are written to Spoolman.

Everything runs in the local network over Spoolman's REST API (/api/v1). Every call is synchronous
(httpx) and is used from a worker thread.
"""
import logging
import os
import shutil
import threading
import time

import httpx

from . import config as config_store
from . import costs, filament
from .config import DATA_DIR
from .i18n import t

log = logging.getLogger("printdash.spoolman")

SOURCES = ("own", "spoolman", "sync")
TIMEOUT = 8.0
# densities for new filaments created in Spoolman (Spoolman needs one); g/cm³
DENSITY = {"PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.07, "TPU": 1.21, "PA": 1.14, "PC": 1.2,
           "PVA": 1.23, "HIPS": 1.04, "PP": 0.9}

_status = {"ok": None, "error": "", "version": "", "last": 0, "spools": 0}
_sync_lock = threading.Lock()


def settings(cfg: dict) -> dict:
    f = cfg.get("filament") or {}
    source = f.get("source") if f.get("source") in SOURCES else "own"
    url = str(f.get("spoolman_url") or "").strip().rstrip("/")
    if url.endswith("/api/v1"):
        url = url[:-7]
    if source != "own" and not url:
        source = "own"   # nothing to connect to
    return {"source": source, "url": url, "skip_klipper": bool(f.get("spoolman_skip_klipper")),
            "prices": "own" if f.get("spoolman_prices") == "own" else "spoolman"}


def status() -> dict:
    return dict(_status)


def apply_mode(cfg: dict) -> str:
    """Point the filament module at the right file for the chosen source."""
    s = settings(cfg)
    filament.set_mode(s["source"])
    return s["source"]


# -- REST helpers ----------------------------------------------------------------------
def _req(url: str, method: str, path: str, **kw):
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as c:
        r = c.request(method, f"{url}/api/v1{path}", **kw)
    if r.status_code >= 400:
        detail = ""
        try:
            detail = r.json().get("message") or r.json().get("detail") or ""
        except Exception:
            detail = r.text[:200]
        raise RuntimeError(f"Spoolman {method} {path}: HTTP {r.status_code} {detail}".strip())
    return r.json() if r.content else None


def check(url: str) -> dict:
    """Connection test for the settings page."""
    url = url.strip().rstrip("/")
    if url.endswith("/api/v1"):
        url = url[:-7]
    if not url:
        raise ValueError(t("Bitte die Adresse von Spoolman eintragen"))
    info = _req(url, "GET", "/info")
    spools = _req(url, "GET", "/spool")
    return {"version": info.get("version", ""), "spools": len([s for s in spools if not s.get("archived")])}


def _spools(url: str) -> list:
    return [s for s in (_req(url, "GET", "/spool") or []) if not s.get("archived")]


def use(cfg: dict, item_id: str, grams: float) -> bool:
    """After a print in sync mode: subtract the grams from the linked Spoolman spool."""
    s = settings(cfg)
    if s["source"] != "sync" or not grams:
        return False
    data = filament.load()
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    sid = (item or {}).get("spoolman_id")
    if not sid:
        return False
    try:
        spool = _req(s["url"], "PUT", f"/spool/{sid}/use", json={"use_weight": round(float(grams), 2)})
        _remember(sid, spool)
        return True
    except Exception as e:
        log.warning("Spoolman: could not subtract %.1f g from spool %s: %s", grams, sid, e)
        _status.update(ok=False, error=str(e))
        return False


# -- mapping between Spoolman spools and inventory entries -------------------------------
def _loc_name(loc: dict) -> str:
    return (loc.get("name") or "").strip() or t("Filamentlager")


def _find_loc(data: dict, name: str) -> str | None:
    """Location id for a Spoolman location name, or None."""
    name = (name or "").strip()
    if not name:
        return None
    for loc in data["locations"]:
        if _loc_name(loc).lower() == name.lower():
            return loc["id"]
    if name.lower() in ("filamentlager", "filament storage"):  # the unnamed default, in either language
        unnamed = next((loc for loc in data["locations"] if not (loc.get("name") or "").strip()), None)
        if unnamed:
            return unnamed["id"]
    return None


def _loc_for(data: dict, name: str, fallback: str) -> str:
    name = (name or "").strip()
    if not name:
        return fallback
    found = _find_loc(data, name)
    if found:
        return found
    if len(data["locations"]) >= filament.MAX_LOCATIONS:
        return fallback
    loc = filament.new_location(name, from_spoolman=True)
    data["locations"].append(loc)
    data.setdefault("_created", []).append(loc["id"])
    return loc["id"]


def _item_from_spool(sp: dict, old: dict | None, data: dict) -> dict:
    fil = sp.get("filament") or {}
    vendor = (fil.get("vendor") or {}).get("name") or ""
    color = fil.get("color_hex") or ""
    if not color and fil.get("multi_color_hexes"):
        color = str(fil["multi_color_hexes"]).split(",")[0]
    initial = sp.get("initial_weight") or fil.get("weight") or 1000
    used = float(sp.get("used_weight") or 0)
    remaining = sp.get("remaining_weight")
    started = used > 0.5 or (remaining is not None and float(remaining) < float(initial) - 0.5)
    first = data["locations"][0]["id"]
    # the place here only follows Spoolman when it was changed there; otherwise a spool parked here
    # in a printer's AMS (printer switched off) stays there
    seen = ((data.get("spoolman_seen") or {}).get(str(sp["id"])) or {}).get("location")
    here = filament.location(data, (old or {}).get("location"))
    return_to = (old or {}).get("return_to")
    if old and here and seen is not None and (sp.get("location") or "") == seen:
        where = old["location"]
    elif old and here and here.get("printer_id") and return_to:
        # parked in a printer's AMS (printer off) and moved or renamed in Spoolman:
        # it stays in the AMS and goes back to the new place later
        where = old["location"]
        return_to = _loc_for(data, sp.get("location"), return_to)
    else:
        where = _loc_for(data, sp.get("location"), (old or {}).get("location") or first)
    item = dict(old or {})
    if return_to:
        item["return_to"] = return_to
    item.update({
        "id": (old or {}).get("id") or os.urandom(4).hex(),
        "spoolman_id": sp["id"],
        "location": where,
        "brand": vendor[:60],
        "material": str(fil.get("material") or "").strip().upper()[:30],
        "color": filament._hex(color),
        "color_name": str(fil.get("name") or "").strip()[:40],
        "count": 1,
        "condition": "angefangen" if started else "neu",
        "spool_g": filament._num(initial, 1000, 0),
        "remaining_g": round(float(remaining), 1) if started and remaining is not None else None,
        "note": str(sp.get("comment") or (old or {}).get("note") or "").strip()[:200],
    })
    item.setdefault("uid", "")
    item.setdefault("dried_at", None)
    return item


def _remember(sid, spool: dict | None) -> None:
    """Keep the last state seen in Spoolman, to find out later what was changed here."""
    if not spool:
        return
    data = filament.load()
    data.setdefault("spoolman_seen", {})[str(sid)] = {"location": spool.get("location") or ""}
    filament.save(data)


def _vendor_id(url: str, name: str, cache: dict) -> int | None:
    name = (name or "").strip()
    if not name:
        return None
    if "vendors" not in cache:
        cache["vendors"] = _req(url, "GET", "/vendor") or []
    for v in cache["vendors"]:
        if (v.get("name") or "").strip().lower() == name.lower():
            return v["id"]
    v = _req(url, "POST", "/vendor", json={"name": name})
    cache["vendors"].append(v)
    return v["id"]


def _filament_id(url: str, item: dict, cache: dict) -> int:
    vid = _vendor_id(url, item.get("brand"), cache)
    color = (item.get("color") or "#cccccc").lstrip("#")[:6].lower()
    material = (item.get("material") or "").upper()
    name = item.get("color_name") or material or "Filament"
    if "filaments" not in cache:
        cache["filaments"] = _req(url, "GET", "/filament") or []
    for f in cache["filaments"]:
        if ((f.get("vendor") or {}).get("id") == vid and (f.get("material") or "").upper() == material
                and (f.get("color_hex") or "").lower()[:6] == color and (f.get("name") or "") == name):
            return f["id"]
    base = filament._base(material)
    body = {"name": name, "material": material, "color_hex": color, "density": DENSITY.get(base, 1.24),
            "diameter": 1.75, "weight": float(item.get("spool_g") or 1000)}
    price = _spool_price(cache.get("cfg"), material, body["weight"])
    if price:
        body["price"] = price
    if vid:
        body["vendor_id"] = vid
    f = _req(url, "POST", "/filament", json=body)
    cache["filaments"].append(f)
    return f["id"]


def _spool_price(cfg: dict | None, material: str, weight_g: float) -> float | None:
    """Price of a full spool from 3D-PrintDash's price list (per kg), as Spoolman stores it."""
    if not cfg:
        return None
    per_kg = costs.price_per_kg(cfg, material)
    return round(per_kg * float(weight_g or 1000) / 1000, 2) if per_kg else None


def _prices_both_ways(cfg: dict, url: str, spools: list, linked: set) -> None:
    """Prices, by the setting "spoolman_prices":
    - "spoolman": each material takes Spoolman's price per kg (average over its filaments with a price),
      also when a price was set here.
    - "own": the price list here applies, nothing is taken from Spoolman; in sync mode, Spoolman
      filaments without a price get the one from here (prices set in Spoolman are left alone).
    Materials from Spoolman are always added to the price list, so they can be seen and adjusted."""
    s = settings(cfg)
    seen, learned, materials = set(), {}, []
    for sp in spools:
        fil = sp.get("filament") or {}
        fid, weight, material = fil.get("id"), float(fil.get("weight") or 1000), (fil.get("material") or "").strip().upper()
        if material and material not in materials:
            materials.append(material)
        if not fid or fid in seen or not material:
            continue
        seen.add(fid)
        if s["prices"] == "spoolman":
            if fil.get("price") and weight > 0:
                learned.setdefault(material, []).append(float(fil["price"]) / weight * 1000)
        elif not fil.get("price") and s["source"] == "sync" and str(sp["id"]) in linked:
            price = _spool_price(cfg, material, weight)
            if price:
                try:
                    _req(url, "PATCH", f"/filament/{fid}", json={"price": price})
                except Exception as e:
                    log.warning("Spoolman: could not set the price of filament %s: %s", fid, e)
    c = cfg.setdefault("costs", {})
    before = dict(c["materials"]) if isinstance(c.get("materials"), dict) else None
    if learned:
        mats = dict(costs.settings(cfg)["materials"])  # the other materials keep their price
        for k, v in learned.items():
            price = round(sum(v) / len(v), 2)
            same = [x for x in mats if costs.normalize(x) == costs.normalize(k)]
            if same and len(same) == 1 and float(mats[same[0]] or 0) == price:
                continue
            for old in same:
                del mats[old]
            mats[k] = price
        c["materials"] = mats
    costs.add_materials(cfg, materials)
    if c.get("materials") != before:
        config_store.save(cfg)
        log.info("Spoolman: price list updated")


def _spool_body(item: dict, data: dict) -> dict:
    loc = filament.location(data, item.get("location")) or {}
    body = {"location": _loc_name(loc), "initial_weight": float(item.get("spool_g") or 1000),
            "comment": item.get("note") or ""}
    if item.get("condition") == "angefangen" and item.get("remaining_g") is not None:
        body["remaining_weight"] = float(item["remaining_g"])
    else:
        body["used_weight"] = 0
    return body


def _create_spool(url: str, item: dict, data: dict, cache: dict) -> dict:
    body = _spool_body(item, data)
    body["filament_id"] = _filament_id(url, item, cache)
    return _req(url, "POST", "/spool", json=body)


# -- what the user does here, mirrored to Spoolman (sync mode) ----------------------------
def push_item(cfg: dict, item: dict, old: dict | None) -> list:
    """An entry was added or edited here. Creates or updates the Spoolman spool(s) and links them.
    Several equal spools become one linked entry per spool. Returns the entries now stored."""
    s = settings(cfg)
    if s["source"] != "sync":
        return [item]
    url, cache = s["url"], {"cfg": cfg}
    data = filament.load()
    cur = next((i for i in data["items"] if i["id"] == item["id"]), None)
    if not cur:
        return [item]
    sid = cur.get("spoolman_id")
    if sid:
        body = _spool_body(cur, data)
        if not old or any((old.get(k) or "") != (cur.get(k) or "") for k in ("brand", "material", "color", "color_name")):
            body["filament_id"] = _filament_id(url, cur, cache)
        spool = _req(url, "PATCH", f"/spool/{sid}", json=body)
        data = filament.load()
        data.setdefault("spoolman_seen", {})[str(sid)] = {"location": spool.get("location") or ""}
        filament.save(data)
        return [cur]
    return _export_entry(url, cur, cache)


def _export_entry(url: str, cur: dict, cache: dict) -> list:
    """Create one Spoolman spool per spool of an entry and link them (entry is split into count 1)."""
    data = filament.load()
    cur = next((i for i in data["items"] if i["id"] == cur["id"]), None)
    if not cur or cur.get("spoolman_id"):
        return [cur] if cur else []
    count = max(1, int(cur.get("count") or 1))
    out = []
    for n in range(count):
        spool = _create_spool(url, cur, data, cache)
        entry = cur if n == 0 else {**cur, "id": os.urandom(4).hex()}
        entry["count"] = 1
        entry["spoolman_id"] = spool["id"]
        if n:
            data["items"].append(entry)
        data.setdefault("spoolman_seen", {})[str(spool["id"])] = {"location": spool.get("location") or ""}
        out.append(entry)
    filament.save(data)
    return out


def delete_item(cfg: dict, item: dict) -> None:
    """Deleted here → archived in Spoolman (not deleted, so nothing is lost there)."""
    s = settings(cfg)
    sid = item.get("spoolman_id")
    if s["source"] == "sync" and sid:
        try:
            _req(s["url"], "PATCH", f"/spool/{sid}", json={"archived": True})
        except Exception as e:
            log.warning("Spoolman: could not archive spool %s: %s", sid, e)


def _push_moves(url: str, data: dict) -> int:
    """Spools moved here (by hand or automatically into a printer's AMS): new location to Spoolman."""
    seen = data.get("spoolman_seen") or {}
    n = 0
    for it in data["items"]:
        sid = it.get("spoolman_id")
        if not sid:
            continue
        loc = filament.location(data, it.get("location"))
        name = _loc_name(loc) if loc else ""
        there = (seen.get(str(sid)) or {}).get("location", "")
        # same place under another name (e.g. "Filamentlager" / "Filament storage"): nothing to do
        if not name or there == name or _find_loc(data, there) == it.get("location"):
            continue
        try:
            _req(url, "PATCH", f"/spool/{sid}", json={"location": name})
            seen[str(sid)] = {"location": name}
            n += 1
        except httpx.TransportError:
            raise  # Spoolman not reachable: stop here, the comparison reports it
        except Exception as e:
            log.warning("Spoolman: could not move spool %s: %s", sid, e)
    data["spoolman_seen"] = seen
    return n


def _tidy_locations(data: dict, read_only: bool) -> None:
    """Locations that came from Spoolman and are empty now are removed. If one was renamed in
    Spoolman (one new, one emptied), the old one is renamed instead, so its sensors stay."""
    created = data.pop("_created", [])
    used = {i.get("location") for i in data["items"]} | {i.get("return_to") for i in data["items"]}

    def from_spoolman(loc):
        if loc.get("printer_id") or loc.get("in_printer") or not (loc.get("name") or "").strip():
            return False  # printer locations and the default storage always stay
        return bool(loc.get("from_spoolman")) or read_only  # show-only: all named locations come from Spoolman
    empty = [loc for loc in data["locations"] if from_spoolman(loc) and loc["id"] not in used and loc["id"] not in created]
    if len(created) == 1 and len(empty) == 1:
        old, new = empty[0], filament.location(data, created[0])
        if new:
            old["name"], old["from_spoolman"] = new["name"], True
            for it in data["items"]:
                if it.get("location") == new["id"]:
                    it["location"] = old["id"]
                if it.get("return_to") == new["id"]:
                    it["return_to"] = old["id"]
            data["locations"] = [loc for loc in data["locations"] if loc["id"] != new["id"]]
        return
    gone = {loc["id"] for loc in empty}
    if gone and len(data["locations"]) > len(gone):
        data["locations"] = [loc for loc in data["locations"] if loc["id"] not in gone]


def _brands_from(data: dict, items: list) -> None:
    """Brands used in Spoolman also appear under Filament → Brands, with their materials, colours
    and spool weight. Existing brands only get what is missing (nothing is changed or removed)."""
    by_name = {(b.get("name") or "").lower(): b for b in data.get("brands") or []}
    for name in sorted({i["brand"] for i in items if i.get("brand")}):
        own = [i for i in items if i.get("brand") == name]
        brand = by_name.get(name.lower())
        if not brand:
            weights = [i.get("spool_g") for i in own if i.get("spool_g")]
            brand = filament.clean_brand({"name": name, "spool_g": max(set(weights), key=weights.count) if weights else 1000})
            data.setdefault("brands", []).append(brand)
            by_name[name.lower()] = brand
        mats = brand.setdefault("materials", [])
        cols = brand.setdefault("colors", [])
        known = {((c.get("name") or "").lower(), c.get("material") or "", c.get("color") or "") for c in cols}
        for i in own:
            m = i.get("material") or ""
            if m and m not in mats and len(mats) < 40:
                mats.append(m)
            key = ((i.get("color_name") or "").lower(), m, i.get("color") or "")
            if (key[0] or key[2]) and key not in known and len(cols) < 100:
                cols.append({"name": i.get("color_name") or "", "color": i.get("color") or "", "material": m})
                known.add(key)


# -- regular comparison ------------------------------------------------------------------
def sync(cfg: dict) -> dict:
    """Bring the inventory in line with Spoolman. Called every minute and from the filament page."""
    s = settings(cfg)
    if s["source"] == "own":
        return status()
    if not _sync_lock.acquire(blocking=False):
        return status()
    try:
        with filament._tx:
            data = filament.load()
            if s["source"] == "sync":
                _push_moves(s["url"], data)
            spools = _spools(s["url"])
            by_sid = {str(i.get("spoolman_id")): i for i in data["items"] if i.get("spoolman_id")}
            keep, ids = [], set()
            for sp in spools:
                old = by_sid.get(str(sp["id"]))
                item = _item_from_spool(sp, old, data)
                keep.append(item)
                ids.add(str(sp["id"]))
                data.setdefault("spoolman_seen", {})[str(sp["id"])] = {"location": sp.get("location") or ""}
            # entries without a Spoolman spool stay (sync mode: they can be exported later)
            local = [i for i in data["items"] if not i.get("spoolman_id")] if s["source"] == "sync" else []
            data["items"] = local + keep
            data["spoolman_seen"] = {k: v for k, v in (data.get("spoolman_seen") or {}).items() if k in ids}
            _tidy_locations(data, read_only=s["source"] == "spoolman")
            _brands_from(data, keep)
            filament.save(data)
        try:
            _prices_both_ways(cfg, s["url"], spools, ids)
        except Exception as e:  # prices are a bonus, the comparison itself worked
            log.warning("Spoolman prices: %s", e)
        _status.update(ok=True, error="", last=time.time(), spools=len(spools))
    except Exception as e:
        if _status.get("ok") is not False or _status.get("error") != str(e):
            log.warning("Spoolman: %s", e)
        _status.update(ok=False, error=str(e), last=time.time())
    finally:
        _sync_lock.release()
    return status()


def export_local(cfg: dict) -> dict:
    """Sync mode, first start: put all entries that exist only here into Spoolman."""
    s = settings(cfg)
    if s["source"] != "sync":
        raise ValueError(t("Nur im Modus «Abgleich» möglich"))
    cache, n = {"cfg": cfg}, 0
    for it in [i for i in filament.load()["items"] if not i.get("spoolman_id") and int(i.get("count") or 0) > 0]:
        n += len(_export_entry(s["url"], it, cache))
    sync(cfg)
    return {"exported": n}


def adopt_spoolman(cfg: dict) -> dict:
    """Sync mode, first start: take over Spoolman's inventory; entries only here are removed
    (a backup of the old inventory is kept in the data folder)."""
    s = settings(cfg)
    if s["source"] != "sync":
        raise ValueError(t("Nur im Modus «Abgleich» möglich"))
    path = filament.path()
    if os.path.exists(path):
        shutil.copy(path, os.path.join(DATA_DIR, time.strftime("filament-backup-%Y%m%d-%H%M%S.json")))
    with filament._tx:
        data = filament.load()
        removed = sum(int(i.get("count") or 0) for i in data["items"] if not i.get("spoolman_id"))
        data["items"] = [i for i in data["items"] if i.get("spoolman_id")]
        filament.save(data)
    sync(cfg)
    return {"removed": removed}


def summary(cfg: dict, data: dict) -> dict:
    s = settings(cfg)
    st = status()
    return {"source": s["source"], "url": s["url"], "ok": st["ok"], "error": st["error"], "last": st["last"],
            "local_only": sum(int(i.get("count") or 0) for i in data.get("items", []) if not i.get("spoolman_id"))
            if s["source"] == "sync" else 0}

