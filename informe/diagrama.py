#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagrama del Lab 5: 3 nodos (MQTT, AMQP, CoAP) -> ingestor -> InfluxDB -> Grafana (dashboard + alertas).
Uso: python informe/diagrama.py   (requiere Pillow)  ->  evidencias/00-arquitectura.png"""
import os

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(RAIZ, "evidencias", "00-arquitectura.png")
F = ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
FB = ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FM = ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]


def fnt(lista, n):
    for f in lista:
        if os.path.exists(f):
            return ImageFont.truetype(f, n)
    return ImageFont.load_default()


W, H = 1640, 760
img = Image.new("RGB", (W, H), (255, 255, 255))
d = ImageDraw.Draw(img)
t_tit, t_b, t_s, t_m = fnt(FB, 25), fnt(FB, 17), fnt(F, 15), fnt(FM, 14)
AZUL, VERDE, NARANJA, GRIS, MORADO, ROJO = (31, 111, 235), (30, 150, 90), (222, 120, 20), (90, 98, 110), (125, 70, 190), (200, 60, 60)


def caja(x, y, w, h, titulo, lineas, color, relleno=(247, 249, 252)):
    d.rounded_rectangle([x, y, x + w, y + h], 10, fill=relleno, outline=color, width=3)
    d.text((x + 12, y + 8), titulo, font=t_b, fill=color)
    for i, l in enumerate(lineas):
        d.text((x + 12, y + 36 + i * 20), l, font=t_s, fill=(40, 44, 52))


def flecha(x1, y1, x2, y2, texto, color, dy=-21, punta="der"):
    d.line([x1, y1, x2, y2], fill=color, width=4)
    if punta == "der":
        d.polygon([(x2, y2), (x2 - 14, y2 - 8), (x2 - 14, y2 + 8)], fill=color)
    elif punta == "izq":
        d.polygon([(x2, y2), (x2 + 14, y2 - 8), (x2 + 14, y2 + 8)], fill=color)
    elif punta == "abajo":
        d.polygon([(x2, y2), (x2 - 8, y2 - 14), (x2 + 8, y2 - 14)], fill=color)
    if texto:
        d.text(((x1 + x2) / 2 - d.textlength(texto, font=t_m) / 2, min(y1, y2) + dy), texto, font=t_m, fill=color)


d.text((20, 12), "Laboratorio 5 - Plataforma propia en una VM: protocolo -> TSDB -> Grafana", font=t_tit, fill=(25, 30, 40))
d.text((20, 48), "Todo corre con un solo docker-compose.yml (9 contenedores). Cada muestra lleva temperature, humidity, illuminance y la marca de tiempo del nodo (ts).", font=t_s, fill=GRIS)
d.rounded_rectangle([10, 80, W - 10, H - 46], 14, outline=(170, 178, 190), width=2)
d.text((24, 86), "VM Azure  Ubuntu 22.04  ·  Standard_B2ats_v2 (2 vCPU, 1 GB RAM + 2 GB swap)  ·  red interna de Docker", font=t_m, fill=GRIS)

filas = [
    (120, AZUL, "nodo-mqtt  (publicador)", ["paho-mqtt · MQTT 3.1.1 · QoS 1", "LWT + estado retenido"], "PUBLISH tcp/1883",
     "Mosquitto 2.0", ["broker MQTT, usuario/clave", "sesion persistente del ingestor"], "SUBSCRIBE qos1"),
    (290, VERDE, "nodo-amqp  (publicador)", ["pika · AMQP 0-9-1", "persistente + publisher confirms"], "basic.publish tcp/5672",
     "RabbitMQ 3.13", ["exchange topic unab.ambiental", "cola durable telemetria.tsdb"], "basic.consume"),
    (460, NARANJA, "nodo-coap  (publicador)", ["aiocoap · CoAP RFC 7252", "CON POST, reintento propio"], "CON POST /telemetria  udp/5683", None, None, None),
]
for y, col, tit, lin, etq, btit, blin, etq2 in filas:
    caja(30, y, 300, 110, tit, lin, col)
    if btit:
        flecha(330, y + 55, 560, y + 55, etq, col)
        caja(560, y, 290, 110, btit, blin, col)
        flecha(850, y + 55, 990, y + 55 if y == 290 else (y + 55), etq2, col)
    else:
        flecha(330, y + 55, 990, y + 55, etq, col)
        d.text((560, y + 66), "sin broker: el ACK 2.04 llega cuando el punto ya esta en la TSDB", font=t_s, fill=col)

# ingestor
d.rounded_rectangle([990, 120, 1210, 570], 12, fill=(250, 246, 255), outline=MORADO, width=3)
d.text((1004, 130), "ingestor (Python)", font=t_b, fill=MORADO)
for i, l in enumerate(["adaptador MQTT", "", "", "", "", "", "", "", "adaptador AMQP", "", "", "", "", "", "", "", "servidor CoAP"]):
    d.text((1004, 166 + i * 20.6), l, font=t_s, fill=(40, 44, 52))
d.text((1004, 214), "valida rangos y solo", font=t_s, fill=GRIS)
d.text((1004, 233), "confirma al emisor", font=t_s, fill=GRIS)
d.text((1004, 252), "si la TSDB acepto", font=t_s, fill=GRIS)

# TSDB
caja(1330, 120, 280, 150, "InfluxDB 2.7  (TSDB)", ["bucket ambiental, retencion 30 d", "measurement telemetria", "tags: nodo, protocolo", "timestamp = ts del dispositivo", "historial de la toma de 4 dias"], ROJO, (255, 248, 246))
flecha(1210, 195, 1330, 195, "write (LP)", MORADO)

# Grafana
caja(1330, 350, 280, 150, "Grafana OSS 11.6  (aparte)", ["solo LEE la TSDB (Flux)", "dashboard: ventana de 4 dias", "3 reglas: temp > 32 degC,", "humedad < 35 %, nodo sin datos", "puerto 3000 (lectura anonima)"], (200, 130, 0), (255, 251, 240))
d.line([1470, 350, 1470, 270], fill=(200, 130, 0), width=4)
d.polygon([(1470, 270), (1462, 284), (1478, 284)], fill=(200, 130, 0))
d.text((1482, 300), "consulta Flux", font=t_m, fill=(200, 130, 0))

# alertas
caja(1330, 580, 280, 110, "alertas (webhook)", ["accion: log de alertas (JSON)", "+ republica en MQTT", "unab/ambiental/alertas/#"], ROJO, (255, 248, 246))
flecha(1470, 500, 1470, 580, "", ROJO, punta="abajo")
d.text((1482, 530), "webhook HTTP", font=t_m, fill=ROJO)
d.text((30, 590), "forzar.sh escribe control/forzar.json: el publicador elegido", font=t_s, fill=GRIS)
d.text((30, 610), "envia el valor forzado y asi se dispara la alerta.", font=t_s, fill=GRIS)
d.text((20, H - 34), "Solo Grafana (tcp/3000) se publica a Internet; brokers y TSDB escuchan en 127.0.0.1. Las claves van en .env (no esta en el repositorio). Imagenes multi-arquitectura: sirve igual en la Raspberry Pi.", font=t_s, fill=GRIS)
img.save(OUT)
print("OK", OUT)
