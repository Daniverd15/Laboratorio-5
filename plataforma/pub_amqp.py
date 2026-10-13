#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publicador AMQP 0-9-1 (pika) -> RabbitMQ.

Exchange 'unab.ambiental' (topic, durable), routing key 'telemetria.<nodo>'.
Mensajes persistentes (delivery_mode=2) + publisher confirms + mandatory: el publicador
solo da por enviada una muestra cuando el broker la confirma Y existe una cola que la reciba.
"""
import collections
import os
import time

import pika

from sensor import Sensor, cuerpo, log

NODO = os.environ.get("NODO", "nodo-amqp")
HOST = os.environ.get("AMQP_HOST", "rabbitmq")
PORT = int(os.environ.get("AMQP_PORT", "5672"))
PERIODO = float(os.environ.get("PERIODO_S", "15"))
EXCHANGE = os.environ.get("AMQP_EXCHANGE", "unab.ambiental")
RK = "telemetria.%s" % NODO


def conectar():
    cred = pika.PlainCredentials(os.environ["AMQP_USER"], os.environ["AMQP_PASS"])
    con = pika.BlockingConnection(pika.ConnectionParameters(
        HOST, PORT, os.environ.get("AMQP_VHOST", "/"), cred, heartbeat=30,
        blocked_connection_timeout=20, client_properties={"connection_name": NODO}))
    ch = con.channel()
    ch.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
    ch.confirm_delivery()
    log("AMQP", "conexion 0-9-1 abierta con %s:%d, exchange=%s (topic, durable), confirms ON" % (HOST, PORT, EXCHANGE))
    return con, ch


def main():
    sensor = Sensor(NODO, offset_temp=float(os.environ.get("OFFSET_TEMP", "0")))
    pendientes = collections.deque(maxlen=5000)
    con = ch = None
    espera = 1
    prox = time.time()
    while True:
        pendientes.append(sensor.leer())
        try:
            if con is None or con.is_closed:
                con, ch = conectar()
                espera = 1
            while pendientes:
                m = pendientes[0]
                ch.basic_publish(EXCHANGE, RK, cuerpo(m), mandatory=True, properties=pika.BasicProperties(
                    content_type="application/json", content_encoding="utf-8", delivery_mode=2,
                    message_id="%s-%d" % (NODO, m["seq"]), timestamp=m["ts"] // 1000, app_id=NODO))
                pendientes.popleft()
                log("TX", "basic.publish %s rk=%s seq=%d T=%.2f H=%.1f L=%.1f%s -> basic.ack" % (
                    EXCHANGE, RK, m["seq"], m["temperature"], m["humidity"], m["illuminance"],
                    " FORZADO" if "forzado" in m else ""))
        except pika.exceptions.UnroutableError:
            log("AMQP", "mensaje sin cola destino (el ingestor aun no enlazo la cola); se reintenta")
        except Exception as e:  # conexion caida, nack, bloqueo del broker...
            log("AMQP", "ERROR %s: %s; %d muestra(s) en cola, reintento" % (type(e).__name__, e, len(pendientes)))
            try:
                if con is not None:
                    con.close()
            except Exception:
                pass
            con = None
            espera = min(espera * 2, 16)
        prox += PERIODO
        dormir = max(0.0, prox - time.time())
        if con is not None and con.is_open:
            try:
                con.sleep(dormir)          # atiende los heartbeats mientras espera
            except Exception:
                con = None
        else:
            time.sleep(dormir)


if __name__ == "__main__":
    main()
