"""Timelapse videos of prints.

While a print runs, one camera image is saved per layer (or every 30 s when the
printer does not report layers). When the print ends, ffmpeg turns the images into
an MP4 video. The images are collected inside the data folder; the finished video
goes to the chosen storage:

  data   – inside 3D-PrintDash (/data/timelapse)
  media  – Home Assistant media folder (/media/<folder>), e.g. a NAS added under
           Settings → System → Storage → "Add network storage" with usage "Media"
  share  – Home Assistant share folder (/share/<folder>), same with usage "Share"

Settings (config["timelapse"]): storage, folder, fps, keep_days.
Per printer: timelapse (on/off), timelapse_camera ("" = automatic).
A single print can also be started or stopped by hand (button on the printer card);
that choice is kept as a small marker file next to the images, so it survives a restart.
"""
import asyncio
import glob
import logging
import os
import re
import shutil
import time

from .config import DATA_DIR

log = logging.getLogger("printdash.timelapse")

FRAMES_DIR = os.path.join(DATA_DIR, "timelapse_frames")
ROOTS = {
    "data": os.path.join(DATA_DIR, "timelapse"),
    "media": os.environ.get("PRINTDASH_MEDIA", "/media"),
    "share": os.environ.get("PRINTDASH_SHARE", "/share"),
}
DEFAULTS = {"storage": "data", "folder": "3d-printdash/timelapse", "fps": 25, "keep_days": 30}
MIN_GAP_S = 5          # never more than one image every 5 s
FALLBACK_GAP_S = 30    # printers without layer information
MIN_FRAMES = 10        # fewer images make no useful video
MAX_FRAMES = 3000

_encode_lock = asyncio.Lock()


def settings(cfg: dict) -> dict:
    s = {**DEFAULTS, **(cfg.get("timelapse") or {})}
    if s["storage"] not in ROOTS:
        s["storage"] = "data"
    try:
        s["fps"] = max(5, min(60, int(s.get("fps") or 25)))
    except (TypeError, ValueError):
        s["fps"] = 25
    try:
        s["keep_days"] = max(0, int(s.get("keep_days") or 0))
    except (TypeError, ValueError):
        s["keep_days"] = 0
    return s


def clean_folder(folder: str) -> str:
    """Relative sub folder without '..' or absolute parts."""
    parts = [p for p in re.split(r"[\\/]+", str(folder or "")) if p not in ("", ".", "..")]
    return "/".join(re.sub(r"[^\w .\-]", "_", p) for p in parts)


def target_dir(cfg: dict, storage: str | None = None, folder: str | None = None) -> str:
    s = settings(cfg)
    storage = storage if storage in ROOTS else s["storage"]
    root = ROOTS[storage]
    if storage == "data":
        return root
    sub = clean_folder(s["folder"] if folder is None else folder) or "3d-printdash/timelapse"
    return os.path.join(root, sub)


def storage_info(cfg: dict, storage: str | None = None, folder: str | None = None) -> dict:
    """Where videos go, whether that works, and the free space there."""
    path = target_dir(cfg, storage, folder)
    storage = storage if storage in ROOTS else settings(cfg)["storage"]
    root = ROOTS[storage]
    info = {"storage": storage, "path": path, "root_exists": os.path.isdir(root),
            "writable": False, "free": None, "total": None, "videos": 0, "videos_bytes": 0}
    if storage == "data" or os.path.isdir(root):
        try:
            os.makedirs(path, exist_ok=True)
            test = os.path.join(path, ".write_test")
            with open(test, "w") as fh:
                fh.write("ok")
            os.remove(test)
            info["writable"] = True
        except OSError:
            pass
    probe = path if os.path.isdir(path) else root
    try:
        st = os.statvfs(probe)
        info["free"], info["total"] = st.f_bavail * st.f_frsize, st.f_blocks * st.f_frsize
    except OSError:
        pass
    for f in glob.glob(os.path.join(path, "*.mp4")):
        try:
            info["videos_bytes"] += os.path.getsize(f)
            info["videos"] += 1
        except OSError:
            pass
    return info


# -- collecting images -------------------------------------------------------------
class Recorder:
    """Remembers per running job when the last image was taken."""

    def __init__(self):
        self._last = {}  # job id -> (layer, time)

    def frame_dir(self, job_id) -> str:
        return os.path.join(FRAMES_DIR, str(int(job_id)))

    def count(self, job_id) -> int:
        d = self.frame_dir(job_id)
        return len(glob.glob(os.path.join(d, "*.jpg"))) if os.path.isdir(d) else 0

    def due(self, job_id, layer) -> bool:
        last_layer, last_t = self._last.get(job_id, (None, 0.0))
        now = time.time()
        if now - last_t < MIN_GAP_S:
            return False
        if layer is not None:
            return layer != last_layer
        return now - last_t >= FALLBACK_GAP_S

    def add(self, job_id, layer, image: bytes) -> int:
        d = self.frame_dir(job_id)
        os.makedirs(d, exist_ok=True)
        n = self.count(job_id)
        self._last[job_id] = (layer, time.time())
        if n >= MAX_FRAMES:
            return n
        with open(os.path.join(d, f"{n + 1:05d}.jpg"), "wb") as fh:
            fh.write(image)
        return n + 1

    def mode(self, job_id) -> str | None:
        """"on" / "off" when chosen by hand for this print, else None (printer setting decides)."""
        d = self.frame_dir(job_id)
        for m in ("on", "off"):
            if os.path.exists(os.path.join(d, f".{m}")):
                return m
        return None

    def set_mode(self, job_id, on: bool):
        d = self.frame_dir(job_id)
        os.makedirs(d, exist_ok=True)
        for m in ("on", "off"):
            try:
                os.remove(os.path.join(d, f".{m}"))
            except FileNotFoundError:
                pass
        open(os.path.join(d, ".on" if on else ".off"), "w").close()
        if on:
            self._last.pop(job_id, None)  # take the first image right away

    def forget(self, job_id):
        self._last.pop(job_id, None)
        shutil.rmtree(self.frame_dir(job_id), ignore_errors=True)


def _safe_name(text: str) -> str:
    stem = os.path.splitext(os.path.basename(str(text or "")))[0]
    stem = re.sub(r"\.gcode$", "", stem, flags=re.I)
    return re.sub(r"[^\w\-]+", "_", stem).strip("_")[:60] or "print"


async def encode(cfg: dict, recorder: Recorder, job_id, printer_name: str, filename: str) -> str | None:
    """Turn the collected images into an MP4 in the chosen storage. Returns the path."""
    d = recorder.frame_dir(job_id)
    frames = sorted(glob.glob(os.path.join(d, "*.jpg")))
    if len(frames) < MIN_FRAMES:
        recorder.forget(job_id)
        return None
    s = settings(cfg)
    out_dir = target_dir(cfg)
    stamp = time.strftime("%Y%m%d-%H%M")
    name = f"{stamp}_{_safe_name(printer_name)}_{_safe_name(filename)}_{int(job_id)}.mp4"
    async with _encode_lock:
        try:
            await asyncio.to_thread(os.makedirs, out_dir, exist_ok=True)
        except OSError as exc:
            log.warning("Timelapse folder %s not available (%s), using the internal folder", out_dir, exc)
            out_dir = ROOTS["data"]
            os.makedirs(out_dir, exist_ok=True)
        tmp = os.path.join(d, "video.mp4")
        args = ["nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-framerate", str(s["fps"]), "-i", os.path.join(d, "%05d.jpg"),
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,tpad=stop_mode=clone:stop_duration=1.5",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
                "-threads", "2", "-movflags", "+faststart", tmp]
        if not shutil.which("nice"):
            args = args[3:]
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        if proc.returncode != 0 or not os.path.exists(tmp):
            log.warning("Timelapse video for job %s failed: %s", job_id, (err or b"").decode(errors="replace")[-300:])
            return None
        dest = os.path.join(out_dir, name)
        try:
            await asyncio.to_thread(shutil.move, tmp, dest)
        except OSError as exc:
            log.warning("Timelapse could not be saved to %s (%s), keeping it internally", out_dir, exc)
            os.makedirs(ROOTS["data"], exist_ok=True)
            dest = os.path.join(ROOTS["data"], name)
            await asyncio.to_thread(shutil.move, tmp, dest)
    recorder.forget(job_id)
    log.info("Timelapse saved: %s (%d images)", dest, len(frames))
    return dest


def cleanup(cfg: dict, keep_paths: set | None = None) -> int:
    """Delete videos older than keep_days in all storages (only files 3D-PrintDash made)."""
    keep_days = settings(cfg)["keep_days"]
    removed = 0
    if keep_days > 0:
        limit = time.time() - keep_days * 86400
        dirs = {ROOTS["data"], target_dir(cfg)}
        for d in dirs:
            for f in glob.glob(os.path.join(d, "*_*.mp4")):
                if not re.search(r"_\d+\.mp4$", f):
                    continue
                try:
                    if os.path.getmtime(f) < limit:
                        os.remove(f)
                        removed += 1
                except OSError:
                    pass
    # leftovers of images from jobs that no longer run (e.g. after a crash)
    if os.path.isdir(FRAMES_DIR):
        for d in glob.glob(os.path.join(FRAMES_DIR, "*")):
            try:
                if keep_paths is not None and os.path.basename(d) in keep_paths:
                    continue
                if time.time() - os.path.getmtime(d) > 3 * 86400:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
    return removed
