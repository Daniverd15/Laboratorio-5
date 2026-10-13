#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ingestor de la plataforma propia: MQTT + AMQP 0-9-1 + CoAP  ->  InfluxDB 2 (TSDB).

Un solo proceso con tres adaptadores:
  * MQTT : suscriptor paho (sesion persistente, QoS 1, ack manual)  <- Mosquitto
  * AMQP : consumidor pika de una cola durable (ack manual)         <- RabbitMQ
  * CoAP : servidor aiocoap, recurso POST /telemetria                <- nodo directo (sin broker)

Regla comun: el mensaje solo se confirma al emisor/broker (PUBACK, basic.ack, 2.04) DESPUES de
que InfluxDB acepto el punto. Si la TSDB esta caida, los datos esperan en el broker o en el nodo.
El punto se guarda con la marca de tiempo del dispositivo (campo ts, epoch ms), no con la de llegada;
como measurement+tags+timestamp identifican el punto, una reentrega no duplica datos.
"""
import asyncio
import json
import os
import threading
import time
import urllib.error
import urllib.request

import aiocoap
import aiocoap.resource as resource
import paho.mqtt.client as mqtt
import pika

from sensor import VARIABLES, log

INFLUX_URL = os.environ.get("INFLUX_URL", "http://influxdb:8086")
ORG = os.environ.get("INFLUX_ORG", "unab")
BUCKET = os.environ.get("INFLUX_BUCKET", "ambiental")
TOKEN = os.environ["INFLUX_TOKEN"]
RANGOS = {"temperature": (-20.0, 70.0), "humidity": (0.0, 100.0), "illuminance": (0.0, 200000.0)}
cuenta = {"mqtt": 0, "amqp": 0, "coap": 0, "rechazados": 0}


def escribir(muestra, protocolo):
    """Valida y escribe un punto. True si quedo en la TSDB; ValueError/KeyError si el mensaje es invalido."""
    nodo = str(muestra["nodo"])
    if not nodo.replace("-", "").replace("_", "").isalnum():
        raise ValueError("nodo invalido")
    ts = int(muestra["ts"])
    campos = []
    for v in VARIABLES:
        x = float(muestra[v])
        lo, hi = RANGOS[v]
        if not lo <= x <= hi:
            raise ValueError("%s=%s fuera de rango fisico" % (v, x))
        campos.append("%s=%s" % (v, x))
    campos.append("seq=%di" % int(muestra.get("seq", 0)))
    campos.append("lat_ms=%di" % max(0, int(time.time() * 1000) - ts))   # retardo dispositivo -> TSDB
    campos.append("forzado=%s" % ("true" if muestra.get("forzado") else "false"))
    linea = "telemetria,nodo=%s,protocolo=%s %s %d" % (nodo, protocolo, ",".join(campos), ts)
    req = urllib.request.Request(
        "%s/api/v2/write?org=%s&bucket=%s&precision=ms" % (INFLUX_URL, ORG, BUCKET),
        data=linea.encode(), method="POST", headers={"Authorization": "Token " + TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            ok = r.status == 204
    except urllib.error.HTTPError as e:
        log("TSDB", "InfluxDB rechazo el punto: %s %s" % (e.code, e.read()[:120]))
        ok = False
    except OSError as e:
        log("TSDB", "InfluxDB no responde: %s" % e)
        ok = False
    if ok:
        cuenta[protocolo] += 1
        log("RX-" + protocolo.upper(), "%s seq=%s T=%s H=%s L=%s -> InfluxDB 204" % (
            nodo, muestra.get("seq"), muestra["temperature"], muestra["humidity"], muestra["illuminance"]))
    return ok


def decodificar(cuerpo):
    m = json.loads(cuerpo.decode("utf-8"))
    if not isinstance(m, dict):
        raise ValueError("se esperaba un objeto JSON")
    return m


# --------------------------------------------------------------------------- MQTT
def adaptador_mqtt():
    topico = "unab/ambiental/+/telemetria"
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ingestor", protocol=mqtt.MQTTv311,
                    clean_session=False, manual_ack=True)
    c.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASS"])

    def on_connect(cl, userdata, flags, rc, props=None):
        log("MQTT", "CONNACK %s; SUBSCRIBE %s qos1 (sesion persistente)" % (rc, topico))
        cl.subscribe(topico, qos=1)

    def on_message(cl, userdata, msg):
        try:
            ok = escribir(decodificar(msg.payload), "mqtt")
        except (ValueError, KeyError, TypeError) as e:
            cuenta["rechazados"] += 1
            log("MQTT", "mensaje descartado en %s: %s" % (msg.topic, e))
            ok = True                      # invalido: se confirma para que no se reentregue eternamente
        if ok:
            cl.ack(msg.mid, msg.qos)       # sin ack el broker lo reentrega al reconectar
        else:
            time.sleep(2)
            cl.disconnect()                # fuerza reconexion -> el broker reenvia lo no confirmado

    c.on_connect, c.on_message = on_connect, on_message
    c.reconnect_delay_set(1, 16)
    while True:
        try:
            c.connect(os.environ.get("MQTT_HOST", "mosquitto"), int(os.environ.get("MQTT_PORT", "1883")), keepalive=45)
            c.loop_forever()
        except Exception as e:
            log("MQTT", "ERROR %s: %s" % (type(e).__name__, e))
        time.sleep(3)


# --------------------------------------------------------------------------- AMQP
def adaptador_amqp():
    exchange = os.environ.get("AMQP_EXCHANGE", "unab.ambiental")
    cola = os.environ.get("AMQP_QUEUE", "telemetria.tsdb")
    cred = pika.PlainCredentials(os.environ["AMQP_USER"], os.environ["AMQP_PASS"])
    params = pika.ConnectionParameters(os.environ.get("AMQP_HOST", "rabbitmq"), int(os.environ.get("AMQP_PORT", "5672")),
                                       os.environ.get("AMQP_VHOST", "/"), cred, heartbeat=30,
                                       client_properties={"connection_name": "ingestor"})

    def on_message(ch, method, props, body):
        try:
            ok = escribir(decodificar(body), "amqp")
        except (ValueError, KeyError, TypeError) as e:
            cuenta["rechazados"] += 1
            log("AMQP", "mensaje descartado rk=%s: %s" % (method.routing_key, e))
            ch.basic_reject(method.delivery_tag, requeue=False)
            return
        if ok:
            ch.basic_ack(method.delivery_tag)
        else:
            time.sleep(2)
            ch.basic_nack(method.delivery_tag, requeue=True)   # vuelve a la cola hasta que la TSDB responda

    while True:
        try:
            con = pika.BlockingConnection(params)
            ch = con.channel()
            ch.exchange_declare(exchange, exchange_type="topic", durable=True)
            ch.queue_declare(cola, durable=True)
            ch.queue_bind(cola, exchange, routing_key="telemetria.#")
            ch.basic_qos(prefetch_count=20)
            ch.basic_consume(cola, on_message, auto_ack=False)
            log("AMQP", "consumiendo cola durable '%s' (exchange %s, rk telemetria.#, prefetch 20)" % (cola, exchange))
            ch.start_consuming()
        except Exception as e:
            log("AMQP", "ERROR %s: %s; reintento en 3 s" % (type(e).__name__, e))
        time.sleep(3)


# --------------------------------------------------------------------------- CoAP
class Telemetria(resource.Resource):
    async def render_post(self, request):
        try:
            muestra = decodificar(request.payload)
            ok = await asyncio.get_running_loop().run_in_executor(None, escribir, muestra, "coap")
        except (ValueError, KeyError, TypeError) as e:
            cuenta["rechazados"] += 1
            log("COAP", "mensaje descartado: %s" % e)
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=str(e).encode())
        return aiocoap.Message(code=aiocoap.CHANGED if ok else aiocoap.SERVICE_UNAVAILABLE)


class Estado(resource.Resource):
    async def render_get(self, request):
        return aiocoap.Message(payload=json.dumps(cuenta).encode(), content_format=50)


async def main():
    threading.Thread(target=adaptador_mqtt, daemon=True, name="mqtt").start()
    threading.Thread(target=adaptador_amqp, daemon=True, name="amqp").start()
    raiz = resource.Site()
    raiz.add_resource([".well-known", "core"], resource.WKCResource(raiz.get_resources_as_linkheader))
    raiz.add_resource(["telemetria"], Telemetria())
    raiz.add_resource(["estado"], Estado())
    await aiocoap.Context.create_server_context(raiz, bind=("::", 5683))
    log("COAP", "servidor escuchando en udp/5683: POST /telemetria, GET /estado")
    while True:
        await asyncio.sleep(300)
        log("RESUMEN", "puntos escritos mqtt=%(mqtt)d amqp=%(amqp)d coap=%(coap)d rechazados=%(rechazados)d" % cuenta)


if __name__ == "__main__":
    asyncio.run(main())
