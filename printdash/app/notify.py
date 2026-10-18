"""Notifications through Home Assistant (notify service, e.g. the companion app)."""
from .i18n import t
import logging
import os
import time

import httpx

log = logging.getLogger("printdash.notify")

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
MEDIA_DIR = "/media/printdash"


def ha_api():
    """(base_url, token) for the Home Assistant API, or (None, None)."""
    if SUPERVISOR_TOKEN:
        return "http://supervisor/core/api", SUPERVISOR_TOKEN
    url, token = os.environ.get("HA_URL"), os.environ.get("HA_TOKEN")
    if url and token:
        return url.rstrip("/") + "/api", token
    return None, None


async def list_ha_services() -> list:
    base, token = ha_api()
    if not base:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base}/services", headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            for domain in r.json():
                if domain.get("domain") == "notify":
                    return sorted(domain.get("services", {}).keys())
    except httpx.HTTPError as exc:
        log.warning("Cannot read Home Assistant services: %s", exc)
    return []


def _save_media(image: bytes) -> str | None:
    """Store the image where the HA companion app can load it (/media/local/...)."""
    if not os.path.isdir("/media"):
        return None
    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        # keep the folder small
        files = sorted(os.listdir(MEDIA_DIR))
        for old in files[:-50]:
            os.remove(os.path.join(MEDIA_DIR, old))
        name = f"{int(time.time() * 1000)}.jpg"
        with open(os.path.join(MEDIA_DIR, name), "wb") as fh:
            fh.write(image)
        return f"/media/local/printdash/{name}"
    except OSError as exc:
        log.warning("Could not save image: %s", exc)
        return None


async def send(cfg: dict, title: str, message: str, image: bytes | None = None) -> list:
    """Send to every configured channel. Returns list of error strings."""
    errors = []
    ncfg = cfg.get("notify", {})
    if not ncfg.get("with_snapshot", True):
        image = None

    service = (ncfg.get("ha_service") or "").strip()
    if service:
        base, token = ha_api()
        if not base:
            errors.append(t("Home Assistant nicht erreichbar (nur als Add-on oder mit HA_URL/HA_TOKEN)"))
        else:
            service = service.removeprefix("notify.")
            data = {"title": title, "message": message}
            media = _save_media(image) if image else None
            if media:
                data["data"] = {"image": media}
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    r = await client.post(
                        f"{base}/services/notify/{service}", json=data,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    r.raise_for_status()
            except httpx.HTTPStatusError as exc:
                errors.append(t("Home Assistant: Fehler {code} beim Senden über notify.{service}", code=exc.response.status_code, service=service))
            except httpx.HTTPError as exc:
                errors.append(t("Home Assistant nicht erreichbar ({error})", error=exc.__class__.__name__))

    if not service:
        errors.append(t("Kein Benachrichtigungsdienst eingerichtet (Einstellungen → Benachrichtigungen)"))
    for e in errors:
        log.warning("Notification: %s", e)
    return errors
