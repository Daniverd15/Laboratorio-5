#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Renderiza como imagenes tipo terminal los LOGS REALES de ../mediciones
(no se edita ningun dato: solo se recortan lineas y se colorean las etiquetas).
Uso (requiere Pillow):  python informe/render_evidencias.py"""
import os
import re

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MED = os.path.join(RAIZ, "mediciones")
OUT = os.path.join(RAIZ, "evidencias")
FUENTES = ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
NEGRITA = ["C:/Windows/Fonts/consolab.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]
FONDO, TEXTO = (22, 24, 29), (212, 212, 212)
COLORES = [
    (r"FIRING|firing|Alerting|FORZA|\[PRUEBA\]|sin ACK|ERROR", (255, 110, 110)),
    (r"pending|Pending", (240, 200, 90)),
    (r"RESOLVED|resolved", (120, 220, 140)),
    (r"^#|^===", (255, 170, 80)),
    (r"\[RX-MQTT\]|\[MQTT\]|mqtt", (110, 170, 255)),
    (r"\[RX-AMQP\]|\[AMQP\]|amqp|basic\.publish", (120, 220, 140)),
    (r"\[RX-COAP\]|\[COAP\]|coap|CON POST", (245, 160, 80)),
    (r"\[TX\]", (190, 230, 190)),
    (r"healthy|inactive|Normal", (150, 200, 160)),
]


def fuente(lista, tam):
    for f in lista:
        if os.path.exists(f):
            return ImageFont.truetype(f, tam)
    return ImageFont.load_default()


def color_de(linea):
    for patron, col in COLORES:
        if re.search(patron, linea):
            return col
    return TEXTO


def limpia(l):
    return "".join(c if (c.isprintable() and ord(c) < 0x2500) else "." for c in l.replace("\t", "   "))


def render(titulo, comando, lineas, salida, ancho_car=150, tam=15):
    f, fb = fuente(FUENTES, tam), fuente(NEGRITA, tam)
    ancho_c, alto_l = f.getlength("M"), tam + 6
    lineas = [limpia(l) for l in lineas]
    lineas = [(l if len(l) <= ancho_car else l[:ancho_car - 1] + "…") for l in lineas]
    W = int(ancho_c * (ancho_car + 3)) + 24
    H = 56 + alto_l * (len(lineas) + 2) + 14
    img = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 34], fill=(38, 41, 50))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([12 + i * 22, 11, 24 + i * 22, 23], fill=c)
    d.text((90, 8), titulo, font=fb, fill=(230, 230, 230))
    y = 46
    d.text((12, y), "$ " + comando, font=fb, fill=(130, 220, 130))
    y += alto_l + 2
    for l in lineas:
        d.text((12, y), l, font=f, fill=color_de(l))
        y += alto_l
    img.save(os.path.join(OUT, salida))
    print("OK", salida, "%dx%d" % (W, H), len(lineas), "lineas")


def leer(nombre, patron=None):
    with open(os.path.join(MED, nombre), encoding="utf-8", errors="replace") as fh:
        L = [l.rstrip("\r\n") for l in fh]
    if patron:
        L = [l for l in L if re.search(patron, l)]
    return L


def transiciones(nombre):
    """De la vigilancia cada 10 s deja solo la primera linea de cada cambio de estado (y la ultima)."""
    out, previo = [], None
    L = leer(nombre)
    for l in L:
        estado = l.split()[3] if len(l.split()) > 3 else ""
        if estado != previo:
            out.append(l)
            previo = estado
    return out


def main():
    vm = "azureuser@vm-lab4-iot:~/lab5"
    render("Stack del Lab 5 en la VM de Azure (Docker Compose)  |  9 contenedores, 1 GB de RAM", "docker compose ps ; docker stats --no-stream ; free -m",
           [l for l in leer("01_compose_ps.txt") if l.strip()][:26], "01-stack-docker-compose.png", 150, 14)

    L = []
    for et, arch in [("nodo-mqtt  ->  Mosquitto (MQTT 3.1.1, QoS 1)", "02_log_nodo-mqtt.txt"), ("nodo-amqp  ->  RabbitMQ (AMQP 0-9-1, publisher confirms)", "02_log_nodo-amqp.txt"),
                     ("nodo-coap  ->  servidor CoAP del ingestor (CON POST, UDP 5683)", "02_log_nodo-coap.txt"), ("ingestor: los 3 protocolos escriben en InfluxDB (HTTP 204)", "02_log_ingestor.txt")]:
        L.append("=== " + et + " ===")
        L += leer(arch)[-(9 if "ingestor" in et else 4):]
    render("Las 3 variables por los 3 protocolos  |  " + vm, "docker compose logs --tail N nodo-mqtt nodo-amqp nodo-coap ingestor", L, "02-publicadores-mqtt-amqp-coap.png", 132, 15)

    L = ["# ./scripts/consulta.sh ultimos   (ultimos 5 puntos crudos de cada nodo; _time = marca de tiempo del dispositivo, UTC)"]
    L += [re.sub(r" {6,}", "   ", l) for l in leer("03_consulta_ultimos.txt") if l.strip() and not l.startswith("Result")]
    render("Consulta directa a la TSDB (InfluxDB 2, Flux), sin Grafana", "docker compose exec influxdb influx query '<flux>'", L, "03-consulta-tsdb.png", 150, 14)

    L = leer("04_rabbitmq.txt")
    L = [re.sub(r"\[\{\"product\".*?\"connection_name\",\"([^\"]+)\"\}\]", r"connection_name=\1 (pika 1.3.2)", l) for l in L]
    L += [""] + leer("05_mosquitto_sub.txt") + [""] + leer("06_coap_tcpdump.txt")
    render("Los brokers por dentro: RabbitMQ (AMQP 0-9-1), Mosquitto (MQTT) y CoAP en el cable", "rabbitmqctl list_* ; mosquitto_sub -v ; tcpdump udp port 5683",
           [l for l in L if l != "Timed out"], "04-brokers-amqp-mqtt-coap.png", 150, 14)

    render("Grafana aparte de la ingesta: datasource, contact point, politica y reglas (API HTTP)", "curl -s -u admin:*** http://localhost:3000/api/...",
           leer("07_grafana_api.txt"), "05-grafana-datasource-reglas.png", 178, 14)

    L = ["# 1) se fuerza el valor DESDE EL PUBLICADOR (./scripts/forzar.sh nodo-mqtt temperature 41 300)"] + leer("10_forzar_publicador.txt")
    L += ["", "# 2) estado de la regla en Grafana, leido cada 10 s (solo se muestran los cambios)   ./scripts/vigilar_alertas.sh"] + transiciones("11_alerta_temp_estados.txt")
    L += ["", "# 3) accion de la alerta: el webhook la recibe y la deja en el log   (docker compose logs alertas)"] + leer("12_alertas_contenedor.txt", "Temperatura alta")
    L += ["", "# 4) ...y la republica por MQTT para un actuador   (mosquitto_sub -t 'unab/ambiental/alertas/#')"] + leer("13_alertas_mqtt.txt", "temp-alta")
    render("Alerta de umbral disparada: Temperatura alta (> 32 °C, ventana 2 min, sostenida 1 min)", "./scripts/forzar.sh nodo-mqtt temperature 41 300", L, "16-alerta-disparo-log.png", 172, 14)

    L = ["# A) Hueco intencional: se detiene nodo-amqp ~3 min. La regla «Nodo sin datos» lo detecta y la consulta de huecos lo mide."]
    L += [l for l in leer("14_hueco_intencional.txt") if l.strip() and not l.startswith(("Result", "Table"))]
    L += ["", "# B) Ingestor detenido 73 s: nada se pierde (Mosquitto guarda la sesion QoS 1, RabbitMQ la cola durable, el nodo CoAP reintenta)."]
    R = [l for l in leer("15_resiliencia_ingestor.txt") if l.strip() and not l.startswith(("Result", "Table"))]
    corte = next(i for i, l in enumerate(R) if "ingestor al volver" in l)
    fin = next(i for i, l in enumerate(R) if "huecos > 30 s" in l)
    L += R[:corte + 1] + R[corte + 1:corte + 13] + ["   ..."] + R[fin:]
    render("Huecos de la toma: uno provocado y medido; una caida del ingestor que NO deja hueco", "docker compose stop nodo-amqp | ingestor ; ./scripts/consulta.sh huecos", L, "17-hueco-y-resiliencia.png", 150, 14)


if __name__ == "__main__":
    main()
