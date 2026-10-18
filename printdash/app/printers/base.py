"""Common printer interface and the normalized state every driver produces."""
import time

# Normalized states used everywhere in the app
STATES = (
    "offline", "idle", "preparing", "printing", "paused",
    "finished", "failed", "cancelled", "error",
)
ACTIVE_STATES = ("preparing", "printing", "paused")


class PrinterError(Exception):
    """Error with a message that can be shown to the user as-is."""


class BasePrinter:
    type = "base"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.id = cfg["id"]
        self.name = cfg.get("name") or self.id
        self._cmd_message = None
        self._cmd_message_at = 0.0

    # -- lifecycle -------------------------------------------------------
    async def start(self):
        raise NotImplementedError

    async def stop(self):
        raise NotImplementedError

    # -- state -----------------------------------------------------------
    def snapshot(self) -> dict:
        raise NotImplementedError

    def base_state(self) -> dict:
        msg = self._cmd_message if time.time() - self._cmd_message_at < 20 else None
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "online": False,
            "state": "offline",
            "progress": None,
            "remaining_s": None,
            "elapsed_s": None,
            "filename": None,
            "layer": None,
            "total_layers": None,
            "temps": [],
            "light": None,
            "error": None,
            "hms": [],
            "filaments": [],
            "cmd_message": msg,
            "file_types": [],
            "versions": [],
            "ams": [],
        }

    def set_cmd_message(self, text):
        self._cmd_message = text
        self._cmd_message_at = time.time()

    # -- actions ---------------------------------------------------------
    async def command(self, action: str):
        """action: pause | resume | stop | light_on | light_off"""
        raise NotImplementedError

    async def send_file(self, path: str, filename: str, opts: dict):
        raise NotImplementedError

    async def fetch_job_meta(self, st: dict) -> dict | None:
        """Preview image and filament estimate for the current job:
        {"thumb": bytes, "thumb_type": str, "weight_g": float, "length_m": float}"""
        return None

    def camera_sources(self) -> list:
        """List of {id, name, url, mode} for built-in cameras."""
        return []
