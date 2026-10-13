#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publicador CoAP (RFC 7252, aiocoap) -> servidor CoAP de la plataforma.

POST confirmable (CON) a coap://<host>:5683/telemetria con Content-Format 50 (application/json).
No hay broker: el ACK '2.04 Changed' del servidor ES la confirmacion, y solo llega cuando la
muestra ya quedo escrita en la TSDB.
"""
import asyncio
import collections
import os
import time

import aiocoap

from sensor import Sensor, cuerpo, log

NODO = os.environ.get("NODO", "nodo-coap")
URI = os.environ.get("COAP_URI", "coap://ingestor:5683/telemetria")
PERIODO = float(os.environ.get("PERIODO_S", "15"))


async def main():
    sensor = Sensor(NODO, offset_temp=float(os.environ.get("OFFSET_TEMP", "0")))
    pendientes = collections.deque(maxlen=5000)
    ctx = await aiocoap.Context.create_client_context()
    log("COAP", "cliente listo, destino %s (mensajes CON sobre UDP)" % URI)
    prox = time.time()
    while True:
        pendientes.append(sensor.leer())
        while pendientes:
            m = pendientes[0]
            req = aiocoap.Message(code=aiocoap.POST, uri=URI, payload=cuerpo(m), content_format=50, mtype=aiocoap.CON)
            try:
                resp = await asyncio.wait_for(ctx.request(req).response, timeout=20)
            except Exception as e:
                log("COAP", "sin ACK (%s: %s); %d muestra(s) en cola para reenviar" % (type(e).__name__, e, len(pendientes)))
                break
            if not resp.code.is_successful():
                log("COAP", "respuesta %s; se reintenta en el siguiente ciclo" % resp.code)
                break
            pendientes.popleft()
            log("TX", "CON POST /telemetria seq=%d T=%.2f H=%.1f L=%.1f%s -> ACK %s" % (
                m["seq"], m["temperature"], m["humidity"], m["illuminance"],
                " FORZADO" if "forzado" in m else "", resp.code))
        prox += PERIODO
        await asyncio.sleep(max(0.0, prox - time.time()))


if __name__ == "__main__":
    asyncio.run(main())
