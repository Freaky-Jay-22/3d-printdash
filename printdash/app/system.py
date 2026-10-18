"""Load and temperatures of the computer 3D-PrintDash runs on (the Home Assistant machine).

Read straight from the kernel: /proc (CPU, RAM) and /sys (temperature sensors). Containers
see the values of the whole machine there, so no extra setup is needed. Values the machine
does not offer (e.g. no sensors in a virtual machine) are simply left out.
"""
import glob
import os
import time

from .config import DATA_DIR

PROC = os.environ.get("PRINTDASH_PROC", "/proc")
SYS = os.environ.get("PRINTDASH_SYS", "/sys")

_last_cpu = None      # (busy, total) of the previous sample
_cache = {"at": 0.0, "data": None}

# hwmon driver names -> kind of sensor
CPU_DRIVERS = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "soc_thermal", "x86_pkg_temp", "cpu-thermal")
GPU_DRIVERS = ("amdgpu", "radeon", "nouveau", "i915", "xe")
DISK_DRIVERS = ("nvme", "drivetemp")


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def cpu_percent():
    """CPU load since the previous call (all cores together)."""
    global _last_cpu
    line = (_read(f"{PROC}/stat") or "").split("\n", 1)[0].split()
    if not line or line[0] != "cpu":
        return None
    vals = [int(x) for x in line[1:9]]
    idle = vals[3] + vals[4]          # idle + iowait
    total = sum(vals)
    busy = total - idle
    prev, _last_cpu = _last_cpu, (busy, total)
    if not prev or total <= prev[1]:
        return None
    return round(100 * (busy - prev[0]) / (total - prev[1]), 1)


def memory():
    info = {}
    for line in (_read(f"{PROC}/meminfo") or "").splitlines():
        key, _, rest = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            info[key] = int(rest.split()[0]) * 1024
    if "MemTotal" not in info:
        return None
    total = info["MemTotal"]
    used = total - info.get("MemAvailable", 0)
    return {"total": total, "used": used, "percent": round(100 * used / total, 1)}


def disk(path=None):
    try:
        st = os.statvfs(path or DATA_DIR)
    except OSError:
        return None
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    if not total:
        return None
    return {"total": total, "free": free, "percent": round(100 * (total - free) / total, 1)}


def _hwmon_temp(folder):
    """Main temperature of one hwmon device: CPU package / Tctl / Composite, else the first one."""
    temps = []
    for inp in sorted(glob.glob(f"{folder}/temp*_input")):
        raw = _read(inp)
        try:
            value = int(raw) / 1000
        except (TypeError, ValueError):
            continue
        if not -40 < value < 150:
            continue
        label = (_read(inp.replace("_input", "_label")) or "").lower()
        temps.append((label, value))
    if not temps:
        return None
    for want in ("package", "tctl", "tdie", "composite", "edge"):
        for label, value in temps:
            if want in label:
                return value
    return temps[0][1]


def temperatures():
    """[{kind: cpu|gpu|disk|board, name, temp}] – one entry per device, highest CPU first."""
    out = []
    for folder in sorted(glob.glob(f"{SYS}/class/hwmon/hwmon*")):
        name = (_read(f"{folder}/name") or "").lower()
        temp = _hwmon_temp(folder)
        if temp is None:
            continue
        if name in CPU_DRIVERS:
            kind = "cpu"
        elif name in GPU_DRIVERS:
            kind = "gpu"
        elif name in DISK_DRIVERS:
            kind = "disk"
        elif name in ("acpitz", "pch_cannonlake", "pch_skylake", "nct6775", "it87") or name.startswith("pch_"):
            kind = "board"
        else:
            continue  # wifi, battery … not interesting here
        out.append({"kind": kind, "name": name, "temp": round(temp, 1)})
    if not any(t["kind"] == "cpu" for t in out):
        # e.g. Raspberry Pi without hwmon: thermal zones
        for zone in sorted(glob.glob(f"{SYS}/class/thermal/thermal_zone*")):
            ztype = (_read(f"{zone}/type") or "").lower()
            raw = _read(f"{zone}/temp")
            if raw and any(w in ztype for w in ("cpu", "x86_pkg", "soc")):
                try:
                    out.append({"kind": "cpu", "name": ztype, "temp": round(int(raw) / 1000, 1)})
                    break
                except ValueError:
                    pass
    out.sort(key=lambda t: ({"cpu": 0, "gpu": 1, "disk": 2, "board": 3}[t["kind"]], -t["temp"]))
    # one CPU value is enough (several hwmon devices may report the same chip)
    seen_cpu = False
    result = []
    for t in out:
        if t["kind"] == "cpu":
            if seen_cpu:
                continue
            seen_cpu = True
        result.append(t)
    return result


def snapshot(max_age: float = 4.0) -> dict:
    """Cached system values (CPU load needs two samples, so the cache also paces the sampling)."""
    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < max_age:
        return _cache["data"]
    cpu = cpu_percent()
    data = {
        "cpu": cpu if cpu is not None else (_cache["data"] or {}).get("cpu"),
        "cores": os.cpu_count(),
        "memory": memory(),
        "disk": disk(),
        "temps": temperatures(),
    }
    _cache.update(at=now, data=data)
    return data
