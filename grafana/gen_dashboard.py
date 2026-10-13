#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera grafana/dashboards/unab-ambiental.json (el dashboard aprovisionado).
Se versiona el generador porque es mas facil de revisar que 900 lineas de JSON.
Uso:  python grafana/gen_dashboard.py
"""
import json
import os

DS = {"type": "influxdb", "uid": "influx-ambiental"}
AQUI = os.path.dirname(os.path.abspath(__file__))
COLORES = {"nodo-mqtt": "#1F6FEB", "nodo-amqp": "#1E965A", "nodo-coap": "#DE7814"}
NOMBRES = {"nodo-mqtt": "nodo-mqtt (MQTT)", "nodo-amqp": "nodo-amqp (AMQP)", "nodo-coap": "nodo-coap (CoAP)"}


def serie(campo, fn="mean"):
    return ('from(bucket: "ambiental")\n'
            '  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
            '  |> filter(fn: (r) => r._measurement == "telemetria" and r._field == "%s")\n'
            '  |> aggregateWindow(every: v.windowPeriod, fn: %s, createEmpty: false)\n'
            '  |> keep(columns: ["_time", "_value", "nodo"])' % (campo, fn))


def actual(campo):
    return ('from(bucket: "ambiental")\n'
            '  |> range(start: -5m)\n'
            '  |> filter(fn: (r) => r._measurement == "telemetria" and r._field == "%s")\n'
            '  |> last()\n'
            '  |> keep(columns: ["_time", "_value", "nodo"])' % campo)


def overrides_nodo():
    return [{"matcher": {"id": "byFrameRefID", "options": "A"},
             "properties": [{"id": "displayName", "value": "${__field.labels.nodo}"}]}] + [
        {"matcher": {"id": "byName", "options": n},
         "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}},
                        {"id": "displayName", "value": NOMBRES[n]}]} for n, c in COLORES.items()]


def pasos(*p):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in p]}


def panel(pid, tipo, titulo, desc, x, y, w, h, consulta, defaults, opciones, overrides=None, **extra):
    p = {"id": pid, "type": tipo, "title": titulo, "description": desc, "datasource": DS,
         "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "targets": [{"refId": "A", "datasource": DS, "query": consulta}],
         "fieldConfig": {"defaults": defaults, "overrides": overrides if overrides is not None else overrides_nodo()},
         "options": opciones}
    p.update(extra)
    return p


def linea(umbral=None, modo="line", relleno=8):
    c = {"drawStyle": "line", "lineWidth": 1.5, "fillOpacity": relleno, "showPoints": "never", "spanNulls": 120000,
         "lineInterpolation": "linear", "axisPlacement": "auto"}
    if umbral:
        c["thresholdsStyle"] = {"mode": modo}
    return c


LEYENDA = {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["min", "mean", "max", "lastNotNull"]},
           "tooltip": {"mode": "multi", "sort": "desc"}}
GAUGE = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
         "showThresholdLabels": False, "showThresholdMarkers": True, "orientation": "auto"}
STAT = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "value",
        "graphMode": "none", "textMode": "value_and_name", "orientation": "horizontal", "justifyMode": "auto"}

TEXTO = """## Estación UNAB-Ambiental — toma continua de 4 días (Laboratorio 5)
**Qué mira el operador:** que la **temperatura no pase de 32 °C** ni la **humedad baje de 35 %** en ningún nodo, y que los tres nodos sigan
escribiendo **un dato cada 15 s** (un hueco se ve como una caída a 0 en *Muestras por minuto*). Las líneas rojas punteadas son los umbrales de alerta.

`nodo-mqtt → Mosquitto (MQTT 3.1.1)` · `nodo-amqp → RabbitMQ (AMQP 0-9-1)` · `nodo-coap → servidor CoAP (UDP)` → **ingestor → InfluxDB 2 → Grafana** (Grafana solo lee la TSDB). Hora: Bogotá (UTC−5).
"""

paneles = [
    {"id": 1, "type": "text", "title": "", "gridPos": {"x": 0, "y": 0, "w": 24, "h": 4},
     "options": {"mode": "markdown", "content": TEXTO}, "transparent": True},

    panel(2, "gauge", "Temperatura ahora", "Último valor de cada nodo (últimos 5 min). Rango del escenario 10–45 °C; alerta a 32 °C.",
          0, 4, 6, 6, actual("temperature"),
          {"unit": "celsius", "min": 10, "max": 45, "decimals": 1, "color": {"mode": "thresholds"},
           "thresholds": pasos(("blue", None), ("green", 18), ("orange", 30), ("red", 32))}, GAUGE,
          overrides=[{"matcher": {"id": "byFrameRefID", "options": "A"}, "properties": [{"id": "displayName", "value": "${__field.labels.nodo}"}]}]),
    panel(3, "gauge", "Humedad relativa ahora", "Último valor de cada nodo. Rango 0–100 %HR; alerta por debajo de 35 %.",
          6, 4, 6, 6, actual("humidity"),
          {"unit": "humidity", "min": 0, "max": 100, "decimals": 1, "color": {"mode": "thresholds"},
           "thresholds": pasos(("red", None), ("orange", 35), ("green", 45), ("blue", 90))}, GAUGE,
          overrides=[{"matcher": {"id": "byFrameRefID", "options": "A"}, "properties": [{"id": "displayName", "value": "${__field.labels.nodo}"}]}]),
    panel(4, "stat", "Iluminancia ahora", "Último valor de cada nodo. Rango del escenario 0–100 000 lux (noche ≈ 0, mediodía despejado ≈ 60 000).",
          12, 4, 4, 6, actual("illuminance"),
          {"unit": "lux", "min": 0, "max": 100000, "decimals": 0, "color": {"mode": "thresholds"},
           "thresholds": pasos(("#5a626e", None), ("#b8860b", 1000), ("orange", 20000))}, STAT,
          overrides=[{"matcher": {"id": "byFrameRefID", "options": "A"}, "properties": [{"id": "displayName", "value": "${__field.labels.nodo}"}]}]),
    panel(5, "stat", "Edad del último dato", "Edad del último punto de cada nodo en la TSDB. Verde < 45 s; rojo > 90 s = nodo caído (regla «Nodo sin datos»).",
          16, 4, 4, 6,
          'from(bucket: "ambiental")\n'
          '  |> range(start: v.timeRangeStart)\n'
          '  |> filter(fn: (r) => r._measurement == "telemetria" and r._field == "temperature")\n'
          '  |> last()\n'
          '  |> map(fn: (r) => ({_time: r._time, nodo: r.nodo, _value: float(v: uint(v: now()) - uint(v: r._time)) / 1000000000.0}))',
          {"unit": "s", "decimals": 0, "color": {"mode": "thresholds"},
           "thresholds": pasos(("green", None), ("orange", 45), ("red", 90))}, STAT,
          overrides=[{"matcher": {"id": "byFrameRefID", "options": "A"}, "properties": [{"id": "displayName", "value": "${__field.labels.nodo}"}]}]),
    panel(6, "stat", "Puntos en la ventana", "Cantidad de muestras de cada nodo dentro del rango de tiempo elegido (4 días × 5 760 por día = 23 040 esperadas por nodo).",
          20, 4, 4, 6,
          'from(bucket: "ambiental")\n'
          '  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
          '  |> filter(fn: (r) => r._measurement == "telemetria" and r._field == "temperature")\n'
          '  |> count()\n'
          '  |> keep(columns: ["_value", "nodo"])',
          {"unit": "none", "decimals": 0, "color": {"mode": "fixed", "fixedColor": "#1F6FEB"}}, STAT,
          overrides=[{"matcher": {"id": "byFrameRefID", "options": "A"}, "properties": [{"id": "displayName", "value": "${__field.labels.nodo}"}]}]),

    panel(10, "timeseries", "Temperatura (°C) — umbral de alerta 32 °C",
          "Promedio por intervalo de cada nodo. La línea roja es el umbral de la regla «Temperatura alta» (promedio de 2 min > 32 °C sostenido 1 min).",
          0, 10, 24, 9, serie("temperature"),
          {"unit": "celsius", "decimals": 1, "custom": dict(linea(True, relleno=0), axisSoftMin=16, axisSoftMax=34),
           "thresholds": pasos(("transparent", None), ("red", 32)), "color": {"mode": "palette-classic"}}, LEYENDA),
    panel(11, "timeseries", "Humedad relativa (%) — umbral de alerta 35 %",
          "Promedio por intervalo de cada nodo. La zona roja inferior es el umbral de la regla «Humedad baja».",
          0, 19, 12, 9, serie("humidity"),
          {"unit": "humidity", "decimals": 1, "min": 20, "max": 100, "custom": linea(True, relleno=0),
           "thresholds": pasos(("red", None), ("transparent", 35)), "color": {"mode": "palette-classic"}}, LEYENDA),
    panel(12, "timeseries", "Iluminancia (lux)",
          "Promedio por intervalo de cada nodo: se distinguen los días y las noches de la toma.",
          12, 19, 12, 9, serie("illuminance"),
          {"unit": "lux", "decimals": 0, "min": 0, "custom": linea(), "color": {"mode": "palette-classic"}}, LEYENDA),

    panel(20, "timeseries", "Muestras por minuto (huecos de la toma)",
          "Cuántas muestras por minuto llegaron a la TSDB desde cada nodo. Lo normal es 4 (una cada 15 s); 0 = hueco.",
          0, 28, 10, 8,
          'from(bucket: "ambiental")\n'
          '  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
          '  |> filter(fn: (r) => r._measurement == "telemetria" and r._field == "temperature")\n'
          '  |> aggregateWindow(every: v.windowPeriod, fn: count, createEmpty: true)\n'
          '  |> map(fn: (r) => ({r with _value: float(v: r._value) * 60000000000.0 / float(v: int(v: v.windowPeriod))}))\n'
          '  |> keep(columns: ["_time", "_value", "nodo"])',
          {"unit": "none", "decimals": 1, "min": 0, "max": 6,
           "custom": dict(linea(), lineInterpolation="stepAfter", fillOpacity=15), "color": {"mode": "palette-classic"}},
          {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["min", "mean"]}, "tooltip": {"mode": "multi", "sort": "desc"}},
          interval="1m"),
    panel(21, "timeseries", "Retardo dispositivo → TSDB (ms)",
          "Tiempo entre la marca de tiempo del nodo y la escritura en InfluxDB, por protocolo (promedio del intervalo).",
          10, 28, 7, 8,
          'from(bucket: "ambiental")\n'
          '  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
          '  |> filter(fn: (r) => r._measurement == "telemetria" and r._field == "lat_ms")\n'
          '  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)\n'
          '  |> keep(columns: ["_time", "_value", "nodo"])',
          {"unit": "ms", "decimals": 1, "min": 0, "custom": linea(relleno=0), "color": {"mode": "palette-classic"}},
          {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["mean", "max"]}, "tooltip": {"mode": "multi", "sort": "desc"}}),
    {"id": 22, "type": "alertlist", "title": "Alertas (estado actual)", "gridPos": {"x": 17, "y": 28, "w": 7, "h": 8},
     "description": "Reglas de Grafana Alerting de la carpeta UNAB-Ambiental y su estado: Normal, Pending o Firing.",
     "options": {"viewMode": "list", "groupMode": "default", "maxItems": 20, "sortOrder": 3, "dashboardAlerts": False,
                 "alertName": "", "alertInstanceLabelFilter": "", "folder": None,
                 "stateFilter": {"firing": True, "pending": True, "noData": True, "normal": True, "error": True}}},
]

dashboard = {
    "uid": "unab-ambiental",
    "title": "UNAB-Ambiental · Estación meteorológica (toma de 4 días)",
    "description": "Laboratorio 5: tres nodos (MQTT, AMQP, CoAP) -> InfluxDB -> Grafana. Temperatura, humedad e iluminancia con alertas por umbral.",
    "tags": ["lab5", "unab", "iot"],
    "timezone": "America/Bogota",
    "editable": False,
    "graphTooltip": 1,
    "schemaVersion": 39,
    "version": 1,
    "refresh": "30s",
    "time": {"from": "now-4d", "to": "now"},
    "timepicker": {"refresh_intervals": ["15s", "30s", "1m", "5m"]},
    "annotations": {"list": [
        {"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": False,
         "iconColor": "rgba(255, 96, 96, 1)", "name": "Alertas y anotaciones", "type": "dashboard"}]},
    "templating": {"list": []},
    "panels": paneles,
}

salida = os.path.join(AQUI, "dashboards", "unab-ambiental.json")
with open(salida, "w", encoding="utf-8", newline="\n") as f:
    json.dump(dashboard, f, ensure_ascii=False, indent=2)
print("OK", salida, len(paneles), "paneles")
