import json, ssl, time, paho.mqtt.client as mqtt
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fakeprinter")
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
c.tls_set_context(ctx)
def on_msg(cl, u, m):
    d = json.loads(m.payload); print("printer got:", d, flush=True)
    if "pushing" in d:
        cl.publish("device/SER123/report", json.dumps({"print":{"command":"push_status","gcode_state":"RUNNING","mc_percent":10,"mc_remaining_time":30,"subtask_name":"Test","nozzle_temper":200,"nozzle_target_temper":200,"bed_temper":60,"bed_target_temper":60,"chamber_temper":34,"layer_num":31,"total_layer_num":180,"lights_report":[{"node":"chamber_light","mode":"on"}],"ams":{"tray_now":"0","ams":[{"id":"0","temp":"26.4","humidity":"2","humidity_raw":"21","tray":[{"id":"0","tray_type":"PLA","tray_color":"F72323FF","remain":64},{"id":"1","tray_type":"PLA","tray_color":"FFFFFFFF","remain":90},{"id":"2","tray_type":"PETG","tray_color":"1F7AE0FF","remain":30},{"id":"3"}]}]}}}))
    if d.get("print",{}).get("command")=="pause":
        cl.publish("device/SER123/report", json.dumps({"print":{"command":"pause","result":"failed","reason":"no permission"}}))
c.on_message = on_msg
c.on_connect = lambda cl,u,f,rc,p: cl.subscribe("device/SER123/request")
c.connect("127.0.0.1", 8883); c.loop_forever()
