"""Fake Moonraker simulating a Snapmaker U1 (4 toolheads) for testing."""
import asyncio, glob, json, os, time
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse

app = FastAPI()
HERE = os.path.dirname(__file__)
FRAMES = [open(f, "rb").read() for f in sorted(glob.glob(os.path.join(HERE, "frames", "*.jpg")))]
S = {"state": "printing", "start": time.time() - 600, "light": 0.0, "file": "benchy_4color.gcode",
     "webhooks": "ready", "uploads": []}

@app.get("/printer/objects/list")
def objs():
    return {"result": {"objects": ["webhooks", "print_stats", "virtual_sdcard", "display_status", "toolhead",
            "heater_bed", "extruder", "extruder1", "extruder2", "extruder3", "led cavity_led", "neopixel toolhead_rgb", "output_pin beeper", "led status_led",
            "print_task_config", "filament_detect",
            "temperature_sensor cavity"]}}

@app.get("/server/webcams/list")
def cams():
    return {"result": {"webcams": [{"name": "cam", "enabled": True, "service": "mjpegstreamer-adaptive",
            "stream_url": "/webcam/?action=stream", "snapshot_url": "/webcam/?action=snapshot"}]}}

@app.get("/printer/info")
def info():
    return {"result": {"hostname": "snapmaker-u1", "state": "ready"}}

@app.post("/printer/objects/query")
async def query(req: Request):
    body = await req.json()
    elapsed = time.time() - S["start"]
    prog = min(1.0, elapsed / 3600)
    st = {
        "webhooks": {"state": S["webhooks"], "state_message": "MCU 'mcu' shutdown: Timer too close" if S["webhooks"] != "ready" else ""},
        "print_stats": {"state": S["state"], "filename": S["file"] if S["state"] != "standby" else "",
                         "print_duration": elapsed, "total_duration": elapsed + 30,
                         "message": "Filament runout" if S["state"] == "error" else "",
                         "info": {"current_layer": int(prog * 250), "total_layer": 250}},
        "virtual_sdcard": {"progress": prog}, "display_status": {"progress": prog},
        "toolhead": {"extruder": "extruder2"},
        "heater_bed": {"temperature": 59.8, "target": 60},
        "extruder": {"temperature": 150.2, "target": 150}, "extruder1": {"temperature": 30, "target": 0},
        "extruder2": {"temperature": 219.6, "target": 220}, "extruder3": {"temperature": 170, "target": 170},
        "led cavity_led": {"color_data": [[0.0, 0.0, 0.0, S["light"]]]},
        "print_task_config": {"filament_exist": [True, True, False, True], "filament_type": ["PLA", "PETG", "NONE", "PLA"],
            "filament_sub_type": ["Basic", "HF", "", "Silk"], "filament_vendor": ["Snapmaker", "Generic", "", "Polymaker"],
            "filament_color_rgba": ["E8312BFF", "1F7AE0FF", "00000000", "F2F2F2FF"]},
        "filament_detect": {"info": [{"MAIN_TYPE": "PLA", "ARGB_COLOR": 4293406507, "CARD_UID": "ab12cd34"}, {}, {}, {}], "state": [0, 0, 0, 0]},
        "temperature_sensor cavity": {"temperature": 33.1},
    }
    if S.get("cold"):
        for k in ("extruder", "extruder1", "extruder2", "extruder3", "heater_bed"):
            st[k] = {"temperature": 28.0, "target": 0}
    return {"result": {"status": {k: v for k, v in st.items() if k in body["objects"]}}}



@app.post("/printer/print/{action}")
def act(action: str):
    S["state"] = {"pause": "paused", "resume": "printing", "cancel": "cancelled"}[action]
    return {"result": "ok"}

@app.post("/printer/gcode/script")
async def gcode(req: Request):
    script = (await req.json())["script"]
    S.setdefault("gcode", []).append(script)
    if "VALUE=1" in script or "WHITE=1" in script: S["light"] = 1.0
    if "VALUE=0" in script or "WHITE=0" in script: S["light"] = 0.0
    return {"result": "ok"}

@app.post("/server/files/upload")
async def upload(file: UploadFile = File(...), root: str = Form("gcodes"), print: str = Form("false")):
    data = await file.read()
    S["uploads"].append((file.filename, len(data), print))
    if print == "true":
        S["state"], S["file"], S["start"] = "printing", file.filename, time.time()
    return {"result": {"item": {"path": file.filename}}}

# test hooks
@app.post("/_set")
async def set_(req: Request):
    S.update(await req.json()); return S

@app.get("/_state")
def get_():
    return S

@app.get("/webcam/")
async def webcam(action: str = "stream"):
    if action == "snapshot":
        from fastapi.responses import Response
        return Response(FRAMES[0], media_type="image/jpeg")
    async def gen():
        i = 0
        while True:
            f = FRAMES[i % len(FRAMES)]; i += 1
            yield b"--bd\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(f)).encode() + b"\r\n\r\n" + f + b"\r\n"
            await asyncio.sleep(0.2)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=bd")

@app.get("/api/services")
def ha_services():
    return [{"domain": "light", "services": {}}, {"domain": "notify", "services": {"mobile_app_pixel": {}, "notify": {}}}]

@app.post("/api/services/notify/{svc}")
async def ha_notify(svc: str, req: Request):
    S.setdefault("notified", []).append((svc, await req.json())); return []

# --- Snapmaker U1 stock camera simulation ---
from fastapi import WebSocket
from fastapi.responses import Response, JSONResponse
CAM = {"awake_until": 0, "i": 0, "calls": 0, "mode": "http"}

def _wake():
    CAM["awake_until"] = time.time() + 15; CAM["calls"] += 1

@app.post("/server/jsonrpc")
async def jsonrpc(req: Request):
    if CAM["mode"] != "http":
        return JSONResponse({"error": "not found"}, status_code=404)
    d = await req.json()
    if d["method"] == "camera.start_monitor":
        _wake(); return {"jsonrpc": "2.0", "result": "ok", "id": d["id"]}
    return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": d["id"]}

@app.websocket("/websocket")
async def ws_ep(ws: WebSocket):
    await ws.accept()
    while True:
        d = json.loads(await ws.receive_text())
        await ws.send_text(json.dumps({"jsonrpc": "2.0", "method": "notify_status_update", "params": []}))
        if d["method"] == "camera.start_monitor":
            _wake(); await ws.send_text(json.dumps({"jsonrpc": "2.0", "result": "ok", "id": d["id"]}))

@app.get("/server/files/camera/monitor.jpg")
def monitor():
    if time.time() < CAM["awake_until"]:
        CAM["i"] += 1
    return Response(FRAMES[CAM["i"] % len(FRAMES)], media_type="image/jpeg")

@app.get("/_cam")
def cam_state(mode: str = ""):
    if mode: CAM["mode"] = mode
    return CAM

# --- fake Home Assistant states/services for smart plugs ---
SENSORS = {"sensor.lager_batterie": ("14", "Lager Sensor Batterie", "battery", "%"),"sensor.lager_temperatur": ("19.8", "Lager Temperatur", "temperature", "°C"),
           "sensor.lager_feuchtigkeit": ("46", "Lager Feuchtigkeit", "humidity", "%"),
           "sensor.ams_temperatur": ("27.1", "AMS Temperatur", "temperature", "°C"),
           "sensor.ams_feuchtigkeit": ("18", "AMS Feuchtigkeit", "humidity", "%")}
PLUGS = {"switch.drucker_u1": "on", "light.steckdose_x1c": "on", "button.x1c_druck_pausieren": "unknown", "button.x1c_druck_fortsetzen": "unknown", "button.x1c_druck_stoppen": "unknown", "button.x1c_aktualisieren": "unknown", "light.x1c_kammerbeleuchtung": "on", "light.deckenlampe": "off", "image.x1c_00m00a000000000_titelbild": "2026-10-17"}

@app.get("/api/states")
def ha_states():
    return [{"entity_id": e, "state": v, "attributes": {"friendly_name": e.split(".")[1].replace("_", " ").title()}} for e, v in PLUGS.items()] + \
           [{"entity_id": "sensor.temp", "state": "21", "attributes": {}}] +            [{"entity_id": e, "state": v[0], "attributes": {"friendly_name": v[1], "device_class": v[2], "unit_of_measurement": v[3]}} for e, v in SENSORS.items()]

@app.get("/api/states/{entity}")
def ha_state(entity: str):
    if entity in SENSORS:
        v = SENSORS[entity]
        return {"entity_id": entity, "state": v[0], "attributes": {"unit_of_measurement": v[3]}}
    if entity not in PLUGS:
        return JSONResponse({"message": "Entity not found."}, status_code=404)
    return {"entity_id": entity, "state": PLUGS[entity], "attributes": {}}

@app.post("/api/services/{domain}/{service}")
async def ha_service(domain: str, service: str, req: Request):
    body = await req.json(); e = body["entity_id"]
    if domain == "notify":
        S.setdefault("notified", []).append((service, body)); return []
    if domain == "button":
        S.setdefault("pressed", []).append(e); return []
    PLUGS[e] = "on" if service == "turn_on" else "off"
    if e == "switch.drucker_u1":
        S["webhooks"] = "ready" if PLUGS[e] == "on" else "OFF"
    return []

@app.middleware("http")
async def power_cut(request, call_next):
    if S.get("webhooks") == "OFF" and request.url.path.startswith(("/printer", "/server")):
        return JSONResponse({}, status_code=503)
    return await call_next(request)

# --- metadata with thumbnails / versions ---
@app.get("/server/files/metadata")
def meta2(filename: str):
    return {"result": {"estimated_time": 4000, "filament_weight_total": 42.7, "filament_total": 14230.0,
            "thumbnails": [{"width": 32, "height": 32, "relative_path": ".thumbs/x-32x32.png"},
                           {"width": 300, "height": 300, "relative_path": ".thumbs/x-300x300.png"}]}}

@app.get("/server/files/gcodes/{path:path}")
def thumbfile(path: str):
    from fastapi.responses import Response
    if path.endswith(".gcode"):
        body = b"G1 X1" + bytes([10]) 
        body = body * 1000 + b"; filament used [mm] = 9000.0, 5230.0, 0, 0" + bytes([10]) + b"; filament used [g] = 27.1, 15.6, 0, 0" + bytes([10]) + b"; filament_type = PLA;PETG-CF;PLA;PLA" + bytes([10])
        return Response(body, media_type="text/plain")
    return Response(FRAMES[3] if "300" in path else b"small", media_type="image/jpeg")

@app.get("/machine/system_info")
def sysinfo():
    return {"result": {"system_info": {"distribution": {"name": "Snapmaker OS", "version": "1.2.3"}}}}

@app.get("/server/info")
def serverinfo():
    return {"result": {"moonraker_version": "v0.9.3-snap"}}


@app.post("/api/template")
async def ha_template(req: Request):
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(json.dumps([e for e in PLUGS if e.startswith(("button.x1c", "light.x1c", "image.x1c"))]))


@app.get("/api/image_proxy/{entity}")
def image_proxy(entity: str):
    from fastapi.responses import Response
    return Response(FRAMES[5], media_type="image/jpeg")
