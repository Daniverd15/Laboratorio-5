#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publicador MQTT 3.1.1 (paho) -> Mosquitto.  QoS 1, usuario/clave y LWT.

Topico: unab/ambiental/<nodo>/telemetria     Estado (retenido): unab/ambiental/<nodo>/estado
Las muestras que no se pudieron publicar se guardan en memoria y se reenvian con su
marca de tiempo original, para que una caida corta del broker no deje un hueco en la TSDB.
"""
import collections
import os
import time

import paho.mqtt.client as mqtt

from sensor import Sensor, cuerpo, log

NODO = os.environ.get("NODO", "nodo-mqtt")
HOST = os.environ.get("MQTT_HOST", "mosquitto")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
PERIODO = float(os.environ.get("PERIODO_S", "15"))
TOPICO = "unab/ambiental/%s/telemetria" % NODO
ESTADO = "unab/ambiental/%s/estado" % NODO


def on_connect(cl, userdata, flags, rc, props=None):
    log("MQTT", "CONNACK %s -> %s:%d" % (rc, HOST, PORT))
    cl.publish(ESTADO, "online", qos=1, retain=True)


def on_disconnect(cl, userdata, flags, rc, props=None):
    log("MQTT", "DESCONECTADO (%s)" % rc)


def main():
    sensor = Sensor(NODO, offset_temp=float(os.environ.get("OFFSET_TEMP", "0")))
    pendientes = collections.deque(maxlen=5000)
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=NODO, protocol=mqtt.MQTTv311)
    c.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASS"])
    c.will_set(ESTADO, "offline", qos=1, retain=True)
    c.on_connect, c.on_disconnect = on_connect, on_disconnect
    c.reconnect_delay_set(1, 16)
    c.connect_async(HOST, PORT, keepalive=45)
    c.loop_start()

    prox = time.time()
    while True:
        pendientes.append(sensor.leer())
        while pendientes:
            m = pendientes[0]
            publicado = False
            if c.is_connected():
                info = c.publish(TOPICO, cuerpo(m), qos=1)
                try:
                    info.wait_for_publish(timeout=5)
                    publicado = info.is_published()
                except (ValueError, RuntimeError):
                    pass
            if not publicado:
                log("MQTT", "sin PUBACK; %d muestra(s) en cola para reenviar" % len(pendientes))
                break
            pendientes.popleft()
            log("TX", "PUBLISH qos1 %s seq=%d T=%.2f H=%.1f L=%.1f%s -> PUBACK" % (
                TOPICO, m["seq"], m["temperature"], m["humidity"], m["illuminance"],
                " FORZADO" if "forzado" in m else ""))
        prox += PERIODO
        time.sleep(max(0.0, prox - time.time()))


if __name__ == "__main__":
    main()
