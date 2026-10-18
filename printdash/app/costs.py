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


def job_cost(cfg: dict, materials: list | None, total_g: float | None, share: float = 1.0):
    """Returns (cost, materials scaled by share). Uses the default price when the
    material split is unknown."""
    scaled = []
    cost = 0.0
    if materials:
        for m in materials:
            g = float(m.get("g") or 0) * share
            if g <= 0:
                continue
            p = price_per_kg(cfg, m.get("type") or "")
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
