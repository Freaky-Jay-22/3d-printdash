from .base import BasePrinter, PrinterError, ACTIVE_STATES  # noqa: F401
from .bambu import BambuPrinter
from .moonraker import MoonrakerPrinter
from .creality import CrealityPrinter

DRIVERS = {"bambu": BambuPrinter, "moonraker": MoonrakerPrinter, "creality": CrealityPrinter}


def create(cfg: dict) -> BasePrinter:
    return DRIVERS[cfg.get("type", "moonraker")](cfg)
