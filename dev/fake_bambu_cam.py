"""Fake camera of a Bambu P1/A1 printer (TLS port 6000, login packet, JPEG frames).

Usage (needs cert.pem/key.pem, see README):  python3 fake_bambu_cam.py [port] [access_code]
"""
import asyncio
import glob
import os
import ssl
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
CODE = sys.argv[2] if len(sys.argv) > 2 else "12345678"
FRAMES = [open(f, "rb").read() for f in sorted(glob.glob(os.path.join(HERE, "frames", "*.jpg")))]


async def client(reader, writer):
    try:
        login = await reader.readexactly(80)
        size, kind = struct.unpack("<II", login[:8])
        user = login[16:48].rstrip(b"\0").decode()
        code = login[48:80].rstrip(b"\0").decode()
        if size != 0x40 or kind != 0x3000 or user != "bblp" or code != CODE:
            print("login refused", user, code, flush=True)
            writer.close()
            return
        print("client logged in", flush=True)
        i = 0
        while True:
            frame = FRAMES[i % len(FRAMES)]
            writer.write(struct.pack("<IIII", len(frame), 0, 1, 0) + frame)
            await writer.drain()
            i += 1
            await asyncio.sleep(0.5)
    except (asyncio.IncompleteReadError, ConnectionError):
        pass
    finally:
        writer.close()


async def main():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(HERE, "cert.pem"), os.path.join(HERE, "key.pem"))
    server = await asyncio.start_server(client, "127.0.0.1", PORT, ssl=ctx)
    print(f"fake Bambu camera on port {PORT}", flush=True)
    async with server:
        await server.serve_forever()

asyncio.run(main())
