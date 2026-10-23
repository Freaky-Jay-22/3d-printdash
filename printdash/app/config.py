"""Persistent configuration stored as JSON in the data directory."""
import copy
import re
import json
import os
import secrets
import threading

DATA_DIR = os.environ.get("PRINTDASH_DATA") or os.environ.get("PRINTFARM_DATA") or "/data"
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

SECRET_FIELDS = {"access_code", "api_key", "password"}
URL_FIELDS = {"url", "camera_url"}          # may contain user:password@
IP_FIELDS = {"host", "url", "camera_url"}   # only the first part of an IP address is shown
PARTIAL_FIELDS = {"serial"}                 # only the first characters are shown
MASK = "********"

DEFAULT_CONFIG = {
    "printers": [],
    "cameras": [],
    # optional room sensors from Home Assistant, shown at the top of the overview (see rooms.py)
    "rooms": [],
    # timelapse videos: where they are stored (see timelapse.py); on/off is a printer setting
    "timelapse": {"storage": "data", "folder": "3d-printdash/timelapse", "fps": 25, "keep_days": 30},
    "notify": {
        "on_error": True,
        "on_finish": False,
        "on_cancel": True,
        "on_dryer": True,
        "on_pause": False,
        "on_low_filament": True,
        "on_maintenance": True,
        "with_snapshot": True,
        "ha_service": "",
    },
    "camera": {"fps": 10, "width": 1280},
    # deduct_usage: subtract the filament of each print from the loaded spool (optional)
    "filament": {"deduct_usage": False, "low_warn_g": 100},
    "costs": {
        "currency": "",  # "" = automatic (browser region)
        "default_price_per_kg": 25,
        "materials": {"PLA": 25, "PETG": 25, "PETG-CF": 40, "ABS": 25,
                      "ABS-CF": 45, "ASA": 30, "ASA-CF": 45, "TPU": 40},
    },
    # language "" = browser language; show_system = load bar at the bottom of the overview
    # theme "" = like the device, "light" / "dark"; accent "" = standard blue or a colour like "#22c55e"
    "ui": {"password": "", "language": "", "show_system": True, "theme": "", "accent": ""},
}

_lock = threading.Lock()


def new_id() -> str:
    return secrets.token_hex(4)


def _merge_defaults(cfg: dict) -> dict:
    out = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in cfg.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    # Telegram was removed: drop leftovers of older versions
    for old in ("telegram_token", "telegram_chat_id"):
        out["notify"].pop(old, None)
    return out


def load() -> dict:
    with _lock:
        if not os.path.exists(CONFIG_PATH):
            return copy.deepcopy(DEFAULT_CONFIG)
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return _merge_defaults(json.load(fh))


def save(cfg: dict) -> None:
    with _lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)


_URL_CRED = re.compile(r"^([a-zA-Z][\w+.-]*://[^:/@\s]*:)([^@\s]*)@")


def _mask_url(value):
    m = _URL_CRED.match(value) if isinstance(value, str) else None
    if not m or not m.group(2):
        return value
    return value[:m.start(2)] + MASK + value[m.end(2):]


def _unmask_url(value, old):
    """Put the stored password back into a URL the browser sent with the mask."""
    m = _URL_CRED.match(value) if isinstance(value, str) else None
    if not m or m.group(2) != MASK:
        return value
    o = _URL_CRED.match(old) if isinstance(old, str) else None
    return value[:m.start(2)] + (o.group(2) if o else "") + value[m.end(2):]


_IPV4 = re.compile(r"\b(\d{1,3})\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_IP_MASKED = re.compile(r"\b(\d{1,3})\.xx\.xx\.xx\b")


def mask_ip(value):
    """192.168.1.40 -> 192.xx.xx.xx (also inside URLs)."""
    return _IPV4.sub(r"\1.xx.xx.xx", value) if isinstance(value, str) else value


def _unmask_ip(value, old):
    """Put the stored IP back where the browser sent the shortened one."""
    if not isinstance(value, str) or not _IP_MASKED.search(value):
        return value
    olds = _IPV4.findall(old) if isinstance(old, str) else []
    full = _IPV4.search(old).group(0) if olds else None
    return _IP_MASKED.sub(lambda m: full if full and full.split(".")[0] == m.group(1) else m.group(0), value)


def mask_partial(value, keep: int = 3):
    v = str(value or "")
    return v[:keep] + "x" * max(0, len(v) - keep) if len(v) > keep else v


def redact(text) -> str:
    """Remove passwords from URLs in error messages (ffmpeg, httpx ...)."""
    text = re.sub(r"([a-zA-Z][\w+.-]*://)[^/@\s]+@", r"\1***@", str(text))
    return re.sub(r"(/bot)\d+:[\w-]+", r"\1***", text)


def masked(cfg: dict) -> dict:
    """Copy of the config with secrets hidden, for sending to the browser."""
    def walk(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k in SECRET_FIELDS and v:
                    v = MASK
                elif k in PARTIAL_FIELDS and isinstance(v, str):
                    v = mask_partial(v)
                else:
                    if k in URL_FIELDS:
                        v = _mask_url(v)
                    if k in IP_FIELDS:
                        v = mask_ip(v)
                    if not (k in URL_FIELDS or k in IP_FIELDS):
                        v = walk(v)
                out[k] = v
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node
    return walk(cfg)


def unmask(new: dict, old: dict) -> dict:
    """Replace masked secrets in `new` with the stored values from `old`."""
    def restore(new_node, old_node):
        if isinstance(new_node, dict):
            old_node = old_node if isinstance(old_node, dict) else {}
            for k, v in list(new_node.items()):
                if k in SECRET_FIELDS and v == MASK:
                    new_node[k] = old_node.get(k, "")
                elif k in PARTIAL_FIELDS:
                    old_v = old_node.get(k)
                    if old_v and v == mask_partial(old_v):
                        new_node[k] = old_v
                elif k in URL_FIELDS or k in IP_FIELDS:
                    if k in URL_FIELDS:
                        v = _unmask_url(v, old_node.get(k))
                    if k in IP_FIELDS:
                        v = _unmask_ip(v, old_node.get(k))
                    new_node[k] = v
                else:
                    restore(v, old_node.get(k))
        elif isinstance(new_node, list):
            old_by_id = {}
            if isinstance(old_node, list):
                old_by_id = {o.get("id"): o for o in old_node if isinstance(o, dict)}
            for item in new_node:
                if isinstance(item, dict):
                    restore(item, old_by_id.get(item.get("id"), {}))
    result = copy.deepcopy(new)
    restore(result, old)
    for coll in ("printers", "cameras", "rooms"):
        for item in result.get(coll, []):
            if not item.get("id"):
                item["id"] = new_id()
    return _merge_defaults(result)
