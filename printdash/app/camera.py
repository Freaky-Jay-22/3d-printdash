"""On-demand camera streams.

Every camera (RTSP, RTSPS, HTTP MJPEG, or a JPEG snapshot URL) is turned into
a stream of JPEG frames. ffmpeg only runs while someone is watching (or a
snapshot is needed) and is stopped again shortly after the last viewer leaves.
"""
import asyncio
import collections
import io
import logging
import re
import ssl
import subprocess
import struct
import time
from urllib.parse import urlparse

import httpx

from .config import redact
from .i18n import t

log = logging.getLogger("printdash.camera")

SOI, EOI = b"\xff\xd8", b"\xff\xd9"
IDLE_STOP_SECONDS = 15
# compatibility mode (setting per Bambu printer, for cameras that start slowly or lag):
# keep the stream open longer, start faster, keep the delay low, less CPU load
COMPAT_IDLE_STOP_SECONDS = 60
COMPAT_MAX_WIDTH = 960
COMPAT_MAX_FPS = 5
# measurement: what the printer really sends (logged once per connection, nothing personal)
MEASURE_SECONDS = 30
_SHOWINFO = re.compile(r"\bn:\s*\d+.*?pts_time:\s*([-\d.]+).*?iskey:\s*(\d)")
_STREAM = re.compile(r"Stream #\d+:\d+.*?Video:\s*(\w+)[^,]*,.*?(\d{2,5}x\d{2,5})(?:.*?([\d.]+) fps)?")
_LEVEL = re.compile(r"\[(?:info|verbose)\]\s")
_measure_ok: bool | None = None

ROTATIONS = (0, 90, 180, 270)   # clockwise, like Fluidd / Mainsail


def clean_orient(raw) -> dict | None:
    """{rotate, flip_h, flip_v} or None when the image stays as it is."""
    if not isinstance(raw, dict):
        return None
    try:
        rotate = int(raw.get("rotate") or 0) % 360
    except (TypeError, ValueError):
        rotate = 0
    out = {"rotate": rotate if rotate in ROTATIONS else 0,
           "flip_h": bool(raw.get("flip_h")), "flip_v": bool(raw.get("flip_v"))}
    return out if (out["rotate"] or out["flip_h"] or out["flip_v"]) else None


def orient_filters(orient: dict | None) -> list:
    """ffmpeg filters: mirror first, then rotate clockwise (same order as Fluidd / Mainsail)."""
    if not orient:
        return []
    out = []
    if orient.get("flip_h"):
        out.append("hflip")
    if orient.get("flip_v"):
        out.append("vflip")
    out += {90: ["transpose=1"], 180: ["hflip", "vflip"], 270: ["transpose=2"]}.get(orient.get("rotate"), [])
    return out


_pil_warned = False


def orient_jpeg(data: bytes, orient: dict | None) -> bytes:
    """Mirror / rotate a single JPEG image (cameras that deliver still images)."""
    global _pil_warned
    if not orient:
        return data
    try:
        from PIL import Image
    except ImportError:
        if not _pil_warned:
            _pil_warned = True
            log.warning("Pillow is missing: still image cameras cannot be rotated or mirrored")
        return data
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        if orient.get("flip_h"):
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if orient.get("flip_v"):
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        # Pillow rotates counter-clockwise
        turn = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                270: Image.Transpose.ROTATE_90}.get(orient.get("rotate"))
        if turn is not None:
            img = img.transpose(turn)
        out = io.BytesIO()
        img.convert("RGB").save(out, "JPEG", quality=85)
        return out.getvalue()
    except Exception:  # noqa: BLE001 – a broken image is shown as it came
        return data


def measure_available() -> bool:
    """showinfo without checksums costs almost nothing; older ffmpeg versions lack the option."""
    global _measure_ok
    if _measure_ok is None:
        try:
            out = subprocess.run(["ffmpeg", "-hide_banner", "-h", "filter=showinfo"],
                                 capture_output=True, text=True, timeout=10).stdout
            _measure_ok = "checksum" in out
        except (OSError, subprocess.SubprocessError):
            _measure_ok = False
    return _measure_ok


class StreamMeter:
    """Reads ffmpeg's info lines: when the stream was ready, codec/size/fps of the
    printer's stream, how often a full image (keyframe) arrives."""

    def __init__(self, started: float, own_clock: bool = False):
        self.started = started
        self.own_clock = own_clock  # printer timestamps are replaced by the arrival time
        self.ready_at = None      # stream opened and analysed
        self.first_at = None      # first decoded image
        self.codec = self.size = self.fps = None
        self.frames = 0
        self.keys = []            # arrival time of full images (keyframes)
        self.last_pts = None
        self.jumps = 0            # printer timestamps going backwards or skipping ahead
        self._stuck = False
        self.done = False

    def feed(self, line: str, now: float) -> bool:
        """Returns True when the measurement is complete."""
        if self.done:
            return False
        if self.ready_at is None and "Input #0" in line:
            self.ready_at = now
        if self.codec is None and "Video:" in line:
            m = _STREAM.search(line)
            if m:
                self.codec, self.size, self.fps = m.group(1), m.group(2), m.group(3)
        m = _SHOWINFO.search(line)
        if m:
            if self.first_at is None:
                self.first_at = now
            self.frames += 1
            if m.group(2) == "1":
                self.keys.append(now)
            try:
                pts = float(m.group(1))
            except ValueError:
                pts = None
            if pts is not None:
                if self.last_pts is not None:
                    diff = pts - self.last_pts
                    # forward jump, or time going backwards (ffmpeg then squeezes the
                    # following timestamps together, so they hardly move)
                    stuck = diff < 0.002
                    if diff > 2 or (stuck and not self._stuck):
                        self.jumps += 1
                    self._stuck = stuck
                self.last_pts = pts
            if now - self.first_at >= MEASURE_SECONDS:
                self.done = True
                return True
        return False

    def summary(self, now: float) -> str | None:
        if self.first_at is None:
            return None
        span = max(0.1, now - self.first_at)
        parts = []
        if self.codec or self.size:
            parts.append(" ".join(x for x in (self.size, self.codec) if x))
        if self.fps:
            parts.append(f"announced {self.fps} fps")
        parts.append(f"received {self.frames / span:.1f} images/s")
        if len(self.keys) >= 2:
            gaps = [b - a for a, b in zip(self.keys, self.keys[1:]) if b > a]
            if gaps:
                parts.append(f"full image every {sum(gaps) / len(gaps):.1f} s")
        else:
            parts.append(f"only 1 full image in {span:.0f} s")
        parts.append("printer timestamps ignored" if self.own_clock else f"timestamp jumps: {self.jumps}")
        if self.ready_at is not None:
            parts.append(f"stream ready after {self.ready_at - self.started:.1f} s")
        parts.append(f"first image after {self.first_at - self.started:.1f} s")
        return ", ".join(parts)


class CameraHub:
    def __init__(self, cam: dict, fps: int = 10, width: int = 1280):
        self.id = cam["id"]
        self.name = cam.get("name") or self.id
        self.url = cam["url"]
        self.mode = cam.get("mode", "ffmpeg")
        self.printer_id = cam.get("printer_id")
        self.fps = max(1, min(int(fps or 10), 30))
        self.width = int(width or 1280)
        self.frame: bytes | None = None
        self.frame_at = 0.0
        self.seq = 0
        self.error: str | None = None
        self._viewers = 0
        self._last_viewer = 0.0
        self._cond = asyncio.Condition()
        self._task: asyncio.Task | None = None
        self._proc = None
        # optional async callable that must be called regularly to keep the
        # camera producing images (Snapmaker U1 stock firmware)
        self.keepalive = cam.get("keepalive")
        self.auth = cam.get("auth")  # Bambu P1/A1 camera: LAN access code
        self.compat = bool(cam.get("compat"))
        self.orient = clean_orient(cam.get("orient"))  # mirror / rotate the image
        self.auto_orient = clean_orient(cam.get("auto_orient"))  # what the printer itself reports
        if self.compat:
            self.fps = min(self.fps, COMPAT_MAX_FPS)
            self.width = min(self.width, COMPAT_MAX_WIDTH)
        self._attempt_at = 0.0   # start of the current connection attempt
        self._first_logged = False

    def info(self) -> dict:
        return {
            "id": self.id, "name": self.name, "printer_id": self.printer_id,
            "active": self._task is not None and not self._task.done(),
            "error": self.error,
            "orient": self.orient,
            "auto_orient": self.auto_orient,
        }

    # -- viewers ---------------------------------------------------------
    def _ensure_running(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def frames(self):
        """Async generator yielding each new JPEG frame while subscribed."""
        self._viewers += 1
        self._ensure_running()
        last = -1
        try:
            while True:
                async with self._cond:
                    await self._cond.wait_for(lambda: self.seq != last)
                    last, frame = self.seq, self.frame
                if frame:
                    yield frame
        finally:
            self._viewers -= 1
            self._last_viewer = time.time()

    async def snapshot(self, timeout: float = 10) -> bytes | None:
        if self.frame and time.time() - self.frame_at < 3:
            return self.frame
        self._last_viewer = time.time()
        self._ensure_running()
        start_seq = self.seq
        try:
            async with self._cond:
                await asyncio.wait_for(
                    self._cond.wait_for(lambda: self.seq != start_seq and self.frame),
                    timeout,
                )
        except asyncio.TimeoutError:
            return self.frame  # may be an older image, or None
        return self.frame

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self._kill()

    # -- worker ----------------------------------------------------------
    def _should_run(self) -> bool:
        idle = COMPAT_IDLE_STOP_SECONDS if self.compat else IDLE_STOP_SECONDS
        return self._viewers > 0 or time.time() - self._last_viewer < idle

    async def _publish(self, frame: bytes):
        if not self._first_logged and self._attempt_at:
            self._first_logged = True
            log.info("Camera %s: first image after %.1f s%s", self.name, time.time() - self._attempt_at,
                     " (compatibility mode)" if self.compat else "")
        async with self._cond:
            self.frame = frame
            self.frame_at = time.time()
            self.seq += 1
            self.error = None
            self._cond.notify_all()

    async def _run(self):
        try:
            while self._should_run():
                self._attempt_at = time.time()
                self._first_logged = False
                try:
                    if self.mode == "snapshot":
                        await self._run_snapshot()
                    elif self.mode == "bambu_jpeg":
                        await self._run_bambu_jpeg()
                    else:
                        await self._run_ffmpeg()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    # ffmpeg/httpx messages often contain the URL, incl. the password
                    self.error = redact(exc)
                    log.warning("Camera %s: %s", self.name, self.error)
                if self._should_run():
                    await asyncio.sleep(3)
        finally:
            await self._kill()

    async def _run_snapshot(self):
        interval = 1 / min(self.fps, 2)
        last_keepalive = 0.0
        last_image = None
        same_count = 0
        sep = "&" if "?" in self.url else "?"
        async with httpx.AsyncClient(timeout=8, verify=False) as client:
            while self._should_run():
                if self.keepalive and time.time() - last_keepalive > 8:
                    last_keepalive = time.time()
                    try:
                        await self.keepalive()
                    except Exception as exc:  # noqa: BLE001
                        raise RuntimeError(t("Kamera lässt sich nicht aktivieren: {error}", error=exc)) from exc
                    await asyncio.sleep(0.5)
                r = await client.get(f"{self.url}{sep}_t={int(time.time() * 1000)}")
                r.raise_for_status()
                if not r.content.startswith(SOI):
                    raise RuntimeError(t("Antwort ist kein JPEG-Bild"))
                # only publish changed images; warn if the camera stops updating
                if r.content != last_image:
                    last_image = r.content
                    same_count = 0
                    await self._publish(await self._oriented(r.content))
                else:
                    same_count += 1
                    if self.frame is None or same_count == 1:
                        await self._publish(await self._oriented(r.content))
                    if same_count * interval > 30:
                        self.error = t("Bild aktualisiert sich nicht mehr")
                await asyncio.sleep(interval)

    async def _run_bambu_jpeg(self):
        """Bambu P1/A1 camera: TLS on port 6000, login packet, then JPEG frames
        each with a 16-byte header (little-endian payload size in the first 4 bytes)."""
        u = urlparse(self.url)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(u.hostname, u.port or 6000, ssl=ctx), 10)
        try:
            login = struct.pack("<IIII", 0x40, 0x3000, 0, 0)
            login += b"bblp".ljust(32, b"\0") + str(self.auth or "").encode()[:32].ljust(32, b"\0")
            writer.write(login)
            await writer.drain()
            while self._should_run():
                try:
                    header = await asyncio.wait_for(reader.readexactly(16), 15)
                except asyncio.TimeoutError:
                    raise RuntimeError(t("Keine Bilder vom Stream (Timeout)"))
                except asyncio.IncompleteReadError:
                    raise RuntimeError(t("Kamera hat die Verbindung beendet (Zugangscode und „LAN Only Liveview“ prüfen)"))
                size = int.from_bytes(header[0:4], "little")
                if not 0 < size < 10_000_000:
                    raise RuntimeError(t("Antwort ist kein JPEG-Bild"))
                frame = await asyncio.wait_for(reader.readexactly(size), 15)
                if frame.startswith(SOI) and frame.endswith(EOI):
                    await self._publish(await self._oriented(frame))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _oriented(self, frame: bytes) -> bytes:
        if not self.orient:
            return frame
        return await asyncio.to_thread(orient_jpeg, frame, self.orient)

    def _measuring(self) -> bool:
        return self.url.startswith(("rtsp://", "rtsps://")) and measure_available()

    def _ffmpeg_args(self) -> list:
        measure = self._measuring()
        level = "repeat+level+info" if measure else "error"
        args = ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", level, "-nostdin",
                "-fflags", "nobuffer", "-flags", "low_delay"]
        if self.compat:
            # start after a short look at the stream instead of up to 5 s, no reordering delay
            args += ["-probesize", "500000", "-analyzeduration", "1000000", "-max_delay", "0"]
        if self.url.startswith(("rtsp://", "rtsps://")):
            args += ["-rtsp_transport", "tcp", "-timeout", "10000000"]
            if self.compat:
                # some printers (e.g. P2S) send broken timestamps, which stalls the frame rate
                # conversion: use the arrival time instead
                args += ["-reorder_queue_size", "0", "-use_wallclock_as_timestamps", "1"]
        elif self.url.startswith(("http://", "https://")):
            args += ["-reconnect", "1", "-reconnect_streamed", "1", "-rw_timeout", "10000000"]
        args += ["-i", self.url, "-an",
                 "-vf", ",".join((["showinfo=checksum=0"] if measure else []) + orient_filters(self.orient)
                                 + [f"scale='min({self.width},iw)':-2"]),
                 "-r", str(self.fps), "-q:v", "6", "-f", "mjpeg", "pipe:1"]
        return args

    async def _run_ffmpeg(self):
        self._proc = await asyncio.create_subprocess_exec(
            *self._ffmpeg_args(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        proc = self._proc
        buf = b""
        last_frame = time.time()
        errors = collections.deque(maxlen=5)
        meter = (StreamMeter(self._attempt_at or time.time(), own_clock=self.compat)
                 if self._measuring() else None)

        async def read_stderr():
            # must always be drained, otherwise ffmpeg blocks once the pipe is full
            while True:
                raw = await proc.stderr.readline()
                if not raw:
                    return
                line = raw.decode(errors="replace").rstrip()
                if meter is not None:
                    now = time.time()
                    if meter.feed(line, now):
                        log.info("Camera %s: measurement: %s", self.name, meter.summary(now))
                    if _LEVEL.search(line):
                        continue
                if line:
                    errors.append(re.sub(r"\[(?:error|fatal|warning|panic)\]\s*", "", line))

        err_task = asyncio.create_task(read_stderr())
        try:
            while self._should_run():
                try:
                    chunk = await asyncio.wait_for(proc.stdout.read(65536), 15)
                except asyncio.TimeoutError:
                    raise RuntimeError(t("Keine Bilder vom Stream (Timeout)"))
                if not chunk:
                    try:
                        await asyncio.wait_for(err_task, 3)
                    except asyncio.TimeoutError:
                        pass
                    raise RuntimeError(errors[-1] if errors else t("Stream beendet"))
                buf += chunk
                while True:
                    start = buf.find(SOI)
                    if start < 0:
                        buf = b""
                        break
                    end = buf.find(EOI, start + 2)
                    if end < 0:
                        buf = buf[start:]
                        break
                    await self._publish(buf[start:end + 2])
                    last_frame = time.time()
                    buf = buf[end + 2:]
                if len(buf) > 8_000_000:
                    buf = b""
                if time.time() - last_frame > 20:
                    raise RuntimeError(t("Keine Bilder vom Stream"))
        finally:
            if meter is not None and not meter.done:
                summary = meter.summary(time.time())
                if summary:  # stream ended before the measurement was complete
                    log.info("Camera %s: measurement (stopped early): %s", self.name, summary)
                    meter.done = True
            await self._kill()
            err_task.cancel()

    async def _kill(self):
        proc, self._proc = self._proc, None
        if proc and proc.returncode is None:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), 5)
            except (ProcessLookupError, asyncio.TimeoutError):
                pass
