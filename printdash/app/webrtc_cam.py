"""Camera over WebRTC for Creality printers with newer firmware (K1 series from 1.3.5.22, K2).

The printer offers a small HTTP endpoint (port 8000, /call/webrtc_local). The client posts a
complete WebRTC offer and gets the answer back; both are JSON objects ({"type", "sdp"}) encoded
as base64 text. The video arrives as an RTP stream and is turned into JPEG images here, so the
rest of 3D-PrintDash sees the same frames as from any other camera.

The WebRTC library (aiortc) is only loaded when such a camera is actually used.
"""
import asyncio
import base64
import io
import json
import logging
import re
import time

import httpx

from .i18n import t

log = logging.getLogger("printdash.camera")


def available() -> bool:
    try:
        import aiortc  # noqa: F401
    except ImportError:
        return False
    return True


def encode_offer(sdp: str) -> str:
    return base64.b64encode(json.dumps({"type": "offer", "sdp": sdp}).encode()).decode()


def decode_answer(text: str) -> str:
    data = json.loads(base64.b64decode(text.strip()))
    sdp = data.get("sdp") if isinstance(data, dict) else None
    if not sdp:
        raise ValueError("no sdp")
    return clean_answer(sdp)


def clean_answer(sdp: str) -> str:
    """The printer may list a second format line for the same codec with Chrome-only options
    (x-google-…). Drop those so only one line per payload type is left."""
    lines = sdp.replace("\r\n", "\n").split("\n")
    fmtp = {}
    for line in lines:
        m = re.match(r"a=fmtp:(\d+) ", line)
        if m:
            fmtp.setdefault(m.group(1), []).append(line)
    keep = []
    for line in lines:
        m = re.match(r"a=fmtp:(\d+) ", line)
        if m and "x-google" in line and len(fmtp[m.group(1)]) > 1:
            continue
        keep.append(line)
    return "\r\n".join(keep)


def to_jpeg(frame, width: int, orient_fn) -> bytes:
    img = frame.to_image()  # PIL image, RGB
    if img.width > width:
        img = img.resize((width, max(2, round(img.height * width / img.width))))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    data = buf.getvalue()
    return orient_fn(data) if orient_fn else data


async def run(url: str, fps: int, width: int, publish, orient_fn=None, should_run=lambda: True,
              name: str = ""):
    """Connect, receive video and call publish(jpeg) about fps times per second until
    should_run() is false. Raises RuntimeError with a readable reason on problems."""
    try:
        from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
        from aiortc.mediastreams import MediaStreamError
    except ImportError as exc:
        raise RuntimeError(t("WebRTC ist in dieser Installation nicht verfügbar")) from exc

    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))  # local network only
    try:
        pc.addTransceiver("video", direction="recvonly")
        await pc.setLocalDescription(await pc.createOffer())  # waits for all candidates
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, content=encode_offer(pc.localDescription.sdp),
                                  headers={"Content-Type": "plain/text"})
        r.raise_for_status()
        try:
            answer = decode_answer(r.text)
        except (ValueError, KeyError) as exc:
            raise RuntimeError(t("Unerwartete Antwort der Kamera")) from exc
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type="answer"))
        track = next((t.receiver.track for t in pc.getTransceivers() if t.kind == "video"), None)
        if track is None:
            raise RuntimeError(t("Kamera sendet kein Video"))
        log.info("Camera %s: WebRTC connected", name)
        interval = 1 / max(1, fps)
        next_at = 0.0
        while should_run():
            try:
                frame = await asyncio.wait_for(track.recv(), 15)
            except asyncio.TimeoutError:
                raise RuntimeError(t("Keine Bilder vom Stream (Timeout)"))
            except MediaStreamError:
                raise RuntimeError(t("Stream beendet"))
            now = time.monotonic()
            if now < next_at:
                continue  # drop frames above the wanted frame rate
            next_at = now + interval
            await publish(await asyncio.to_thread(to_jpeg, frame, width, orient_fn))
    finally:
        await pc.close()
