# -*- coding: utf-8 -*-
"""Modelo del sensor del escenario UNAB-Ambiental (estacion tipo Hobo MX-100).

Lo usan los tres publicadores (MQTT, AMQP, CoAP), de modo que la unica diferencia
entre nodos es el protocolo. Genera las 3 variables del laboratorio:
    temperature [degC], humidity [%HR], illuminance [lux]
con ciclo dia/noche en hora de Bucaramanga (UTC-5) y permite FORZAR un valor
desde el publicador (archivo de control) para disparar la alerta de Grafana.
"""
import json
import math
import os
import random
import time

UTC_OFFSET_H = -5                      # Colombia no tiene horario de verano
CONTROL = os.environ.get("CONTROL_FILE", "/control/forzar.json")
VARIABLES = ("temperature", "humidity", "illuminance")


class Sensor:
    def __init__(self, nodo, offset_temp=0.0, semilla=None):
        self.nodo = nodo
        self.offset_temp = offset_temp
        self.rnd = random.Random(semilla if semilla is not None else nodo)
        self.deriva = 0.0              # deriva lenta de temperatura (frentes, nubes)
        self.nubes = 0.75              # fraccion de luz que deja pasar el cielo
        self.seq = 0

    def _hora_local(self, t):
        return ((t / 3600.0) + UTC_OFFSET_H) % 24

    def _forzado(self, t):
        """{"nodo-mqtt": {"temperature": 41.0, "hasta": 1760000000}}  ("*" = todos los nodos)."""
        try:
            with open(CONTROL, encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError):
            return {}
        regla = datos.get(self.nodo) or datos.get("*") or {}
        if regla.get("hasta", 0) < t:
            return {}
        return {k: float(v) for k, v in regla.items() if k in VARIABLES}

    def leer(self, t=None):
        t = time.time() if t is None else t
        h = self._hora_local(t)
        self.deriva = max(-1.5, min(1.5, self.deriva + self.rnd.gauss(0, 0.04)))
        self.nubes = max(0.25, min(1.0, self.nubes + self.rnd.gauss(0, 0.03)))

        # Temperatura: minimo ~03:00, maximo ~15:00 (19..28 degC en Bucaramanga)
        temp = 23.5 + 4.5 * math.sin(2 * math.pi * (h - 9) / 24) + self.offset_temp + self.deriva + self.rnd.gauss(0, 0.08)
        # Humedad relativa: inversa a la temperatura
        hum = max(30.0, min(99.0, 76.0 - 3.6 * (temp - 23.5 - self.offset_temp) + self.rnd.gauss(0, 0.6)))
        # Iluminancia: sol entre 05:45 y 18:00, atenuado por nubes; de noche solo alumbrado
        if 5.75 <= h <= 18.0:
            lux = 62000.0 * math.sin(math.pi * (h - 5.75) / 12.25) ** 1.4 * self.nubes + self.rnd.uniform(0, 40)
        else:
            lux = self.rnd.uniform(0.5, 6.0)

        m = {"temperature": round(temp, 2), "humidity": round(hum, 1), "illuminance": round(lux, 1)}
        forzado = self._forzado(t)
        m.update(forzado)
        self.seq += 1
        # ts = marca de tiempo REAL del dispositivo (epoch ms, UTC): es la que se guarda en la TSDB
        muestra = {"nodo": self.nodo, "seq": self.seq, "ts": int(t * 1000)}
        muestra.update(m)
        if forzado:
            muestra["forzado"] = sorted(forzado)
        return muestra


def cuerpo(muestra):
    return json.dumps(muestra, separators=(",", ":")).encode("utf-8")


def log(etiqueta, texto):
    print("%s [%s] %s" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), etiqueta, texto), flush=True)
