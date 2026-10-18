"""On-demand camera streams.

Every camera (RTSP, RTSPS, HTTP MJPEG, or a JPEG snapshot URL) is turned into
a stream of JPEG frames. ffmpeg only runs while someone is watching (or a
snapshot is needed) and is stopped again shortly after the last viewer leaves.
"""
import asyncio
import logging
import ssl
import struct
import time
from urllib.parse import urlparse

import httpx

from .config import redact
from .i18n import t

log = logging.getLogger("printdash.camera")

SOI, EOI = b"\xff\xd8", b"\xff\xd9"
IDLE_STOP_SECONDS = 15


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

    def info(self) -> dict:
        return {
            "id": self.id, "name": self.name, "printer_id": self.printer_id,
            "active": self._task is not None and not self._task.done(),
            "error": self.error,
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
        return self._viewers > 0 or time.time() - self._last_viewer < IDLE_STOP_SECONDS

    async def _publish(self, frame: bytes):
        async with self._cond:
            self.frame = frame
            self.frame_at = time.time()
            self.seq += 1
            self.error = None
            self._cond.notify_all()

    async def _run(self):
        try:
            while self._should_run():
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
                    await self._publish(r.content)
                else:
                    same_count += 1
                    if self.frame is None or same_count == 1:
                        await self._publish(r.content)
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
                    await self._publish(frame)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    def _ffmpeg_args(self) -> list:
        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-fflags", "nobuffer", "-flags", "low_delay"]
        if self.url.startswith(("rtsp://", "rtsps://")):
            args += ["-rtsp_transport", "tcp", "-timeout", "10000000"]
        elif self.url.startswith(("http://", "https://")):
            args += ["-reconnect", "1", "-reconnect_streamed", "1", "-rw_timeout", "10000000"]
        args += ["-i", self.url, "-an",
                 "-vf", f"scale='min({self.width},iw)':-2",
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
        try:
            while self._should_run():
                try:
                    chunk = await asyncio.wait_for(proc.stdout.read(65536), 15)
                except asyncio.TimeoutError:
                    raise RuntimeError(t("Keine Bilder vom Stream (Timeout)"))
                if not chunk:
                    err = (await proc.stderr.read()).decode(errors="replace").strip()
                    raise RuntimeError(err.splitlines()[-1] if err else t("Stream beendet"))
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
            await self._kill()

    async def _kill(self):
        proc, self._proc = self._proc, None
        if proc and proc.returncode is None:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), 5)
            except (ProcessLookupError, asyncio.TimeoutError):
                pass
