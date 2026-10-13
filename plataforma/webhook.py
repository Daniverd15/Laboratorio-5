#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accion de la alerta: receptor del webhook de Grafana Alerting.

1) deja cada notificacion en /datos/alertas.log (una linea JSON por alerta) y en el log del contenedor;
2) la republica por MQTT en unab/ambiental/alertas/<regla>/<nodo> (retenido), para que un actuador
   (ventilador, sirena, LED del ESP32) pueda reaccionar: Grafana decide, el broker distribuye.
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import paho.mqtt.client as mqtt

from sensor import log

ARCHIVO = os.environ.get("ALERTAS_LOG", "/datos/alertas.log")
cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="alertas")
cliente.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASS"])
cliente.reconnect_delay_set(1, 16)
cliente.connect_async(os.environ.get("MQTT_HOST", "mosquitto"), int(os.environ.get("MQTT_PORT", "1883")), keepalive=45)
cliente.loop_start()


class Receptor(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        try:
            aviso = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            self.send_response(400)
            self.end_headers()
            return
        for a in aviso.get("alerts", []):
            et = a.get("labels", {})
            reg = {"recibido": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "estado": a.get("status"),
                   "regla": et.get("alertname"), "nodo": et.get("nodo"), "severidad": et.get("severidad"),
                   "valores": a.get("values"), "inicio": a.get("startsAt"), "fin": a.get("endsAt"),
                   "resumen": a.get("annotations", {}).get("summary")}
            with open(ARCHIVO, "a", encoding="utf-8") as f:
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")
            log("ALERTA", "%s | %s | nodo=%s | valores=%s | %s" % (
                str(reg["estado"]).upper(), reg["regla"], reg["nodo"], reg["valores"], reg["resumen"]))
            cliente.publish("unab/ambiental/alertas/%s/%s" % (et.get("regla_id", "regla"), et.get("nodo", "todos")),
                            json.dumps(reg, ensure_ascii=False), qos=1, retain=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"webhook de alertas activo")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    log("ALERTA", "webhook escuchando en :8080/grafana -> %s + MQTT unab/ambiental/alertas/#" % ARCHIVO)
    ThreadingHTTPServer(("0.0.0.0", 8080), Receptor).serve_forever()
