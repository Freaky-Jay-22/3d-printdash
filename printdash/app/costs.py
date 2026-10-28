"""Filament prices per material and cost calculation."""
import re

DEFAULT_MATERIALS = {
    "PLA": 25, "PETG": 25, "PETG-CF": 40, "ABS": 25,
    "ABS-CF": 45, "ASA": 30, "ASA-CF": 45, "TPU": 40,
}


def settings(cfg: dict) -> dict:
    c = dict(cfg.get("costs") or {})
    # older versions had a single price
    if "default_price_per_kg" not in c:
        c["default_price_per_kg"] = c.get("filament_price_per_kg", 25)
    if not isinstance(c.get("materials"), dict):
        c["materials"] = dict(DEFAULT_MATERIALS)
    c.setdefault("currency", "")
    return c


def normalize(material: str) -> str:
    return re.sub(r"[\s_/]+", "-", str(material or "").strip().upper())


def price_per_kg(cfg: dict, material: str) -> float:
    c = settings(cfg)
    prices = {normalize(k): float(v or 0) for k, v in c["materials"].items()}
    norm = normalize(material)
    if norm in prices:
        return prices[norm]
    tokens = [t for t in norm.split("-") if t]
    if tokens:
        base = tokens[0]
        # "PETG CF", "PLA-CF Matte" ... -> "<BASE>-CF"
        if any(t in ("CF", "GF") or t.endswith("CF") for t in tokens[1:]):
            for suffix in ("CF", "GF"):
                if f"{base}-{suffix}" in prices and suffix in "-".join(tokens[1:]):
                    return prices[f"{base}-{suffix}"]
        if base in prices:  # "PLA Basic", "PETG HF", "PLA Silk" -> base material
            return prices[base]
    return float(c.get("default_price_per_kg") or 0)


def add_materials(cfg: dict, names) -> list:
    """Add materials that have no price of their own yet (e.g. new under brands).
    The start price is the one used so far (base material or default), so costs do not change.
    Returns [{name, price}] of what was added; cfg["costs"] is changed in place."""
    c = cfg.setdefault("costs", {})
    if not isinstance(c.get("materials"), dict):
        c["materials"] = dict(settings(cfg)["materials"])
    known = {normalize(k) for k in c["materials"]}
    added = []
    for name in names or []:
        key = str(name or "").strip().upper()
        if not key or normalize(key) in known:
            continue
        price = price_per_kg(cfg, key)
        c["materials"][key] = price
        known.add(normalize(key))
        added.append({"name": key, "price": price})
    return added


def has_price(cfg: dict, material: str) -> bool:
    """True when the material has its own entry in the price list (e.g. "SNAPSPEED PLA")."""
    norm = normalize(material)
    return bool(norm) and any(normalize(k) == norm for k in settings(cfg)["materials"])


def job_cost(cfg: dict, materials: list | None, total_g: float | None, share: float = 1.0,
             spools: dict | None = None):
    """Returns (cost, materials scaled by share). Uses the default price when the
    material split is unknown. spools: {type in the print file: material of the loaded spool};
    the spool's material is priced when it has its own price (print files only know "PLA")."""
    scaled = []
    cost = 0.0
    spools = spools or {}
    if materials:
        for m in materials:
            g = float(m.get("g") or 0) * share
            if g <= 0:
                continue
            kind = m.get("type") or ""
            spool = spools.get(kind)
            p = price_per_kg(cfg, spool if spool and has_price(cfg, spool) else kind)
            cost += g / 1000 * p
            name = m.get("type") or "?"
            same = next((x for x in scaled if x["type"] == name), None)
            if same:
                same["g"] = round(same["g"] + g, 1)
            else:
                scaled.append({"type": name, "g": round(g, 1)})
    elif total_g:
        cost = float(total_g) * share / 1000 * float(settings(cfg).get("default_price_per_kg") or 0)
    return (round(cost, 2) if cost else None), scaled


# density in g/cm³ per base material, for turning extruded length into grams
DENSITY = {"PLA": 1.24, "PETG": 1.27, "PET": 1.38, "ABS": 1.04, "ASA": 1.07, "TPU": 1.21, "PC": 1.20,
           "PA": 1.14, "PVA": 1.23, "HIPS": 1.04, "PP": 0.90, "PEBA": 1.01, "PPS": 1.35}


def density(material: str) -> float:
    m = normalize(material)
    for key in sorted(DENSITY, key=len, reverse=True):
        if m.startswith(key):
            return DENSITY[key]
    return 1.24


def grams_from_length(mm: float, material: str = "", diameter: float = 1.75) -> float:
    """Weight of a filament length: area of the strand × length × density."""
    area_mm2 = 3.14159265 * (diameter / 2) ** 2
    return mm * area_mm2 / 1000 * density(material)
