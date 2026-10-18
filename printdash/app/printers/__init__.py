from .base import BasePrinter, PrinterError, ACTIVE_STATES  # noqa: F401
from .bambu import BambuPrinter
from .moonraker import MoonrakerPrinter

DRIVERS = {"bambu": BambuPrinter, "moonraker": MoonrakerPrinter}


def create(cfg: dict) -> BasePrinter:
    return DRIVERS[cfg.get("type", "moonraker")](cfg)
