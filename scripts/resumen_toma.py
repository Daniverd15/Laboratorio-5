#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resumen de la toma de datos: inicio, fin, puntos esperados/recibidos y huecos por nodo.

Lee la TSDB por su API HTTP (Flux) con el token de .env; no necesita librerias.
    python3 scripts/resumen_toma.py            # tabla legible
    python3 scripts/resumen_toma.py --json     # lo mismo en JSON (lo usa el informe)
Un "hueco" es cualquier intervalo de mas de 2 periodos (30 s) entre dos puntos seguidos de un nodo.
"""
import csv
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOGOTA = timezone(timedelta(hours=-5))


def env():
    e = dict(os.environ)
    try:
        with open(os.path.join(RAIZ, ".env"), encoding="utf-8") as f:
            for l in f:
                if "=" in l and not l.lstrip().startswith("#"):
                    k, v = l.strip().split("=", 1)
                    e.setdefault(k, v.split("#")[0].strip())
    except OSError:
        pass
    return e


E = env()
URL = E.get("INFLUX_URL_HOST", "http://127.0.0.1:8086")
PERIODO = float(E.get("PERIODO_S", "15"))
BASE = ('from(bucket:"ambiental") |> range(start:-30d) '
        '|> filter(fn:(r)=>r._measurement=="telemetria" and r._field=="temperature") |> group(columns:["nodo","protocolo"])')


def flux(q):
    req = urllib.request.Request(URL + "/api/v2/query?org=unab", data=json.dumps({"query": q, "type": "flux"}).encode(),
                                 headers={"Authorization": "Token " + E["INFLUX_TOKEN"], "Content-Type": "application/json",
                                          "Accept": "application/csv"})
    with urllib.request.urlopen(req, timeout=60) as r:
        texto = r.read().decode()
    filas = []
    for bloque in texto.split("\r\n\r\n"):
        filas += list(csv.DictReader(io.StringIO(bloque.strip())))
    return filas


def t(s):
    """RFC 3339 de InfluxDB (fraccion de longitud variable) -> datetime UTC; vale para Python 3.9+."""
    base, _, frac = s.rstrip("Z").partition(".")
    d = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return d + timedelta(seconds=float("0." + frac) if frac else 0)


def local(d):
    return d.astimezone(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")


def main():
    nodos = {}
    for f in flux(BASE + " |> count()"):
        nodos[f["nodo"]] = {"protocolo": f["protocolo"], "puntos": int(f["_value"])}
    for f in flux(BASE + " |> first()"):
        nodos[f["nodo"]]["inicio"] = f["_time"]
    for f in flux(BASE + " |> last()"):
        nodos[f["nodo"]]["fin"] = f["_time"]
    huecos = []
    for f in flux(BASE + " |> elapsed(unit:1s) |> filter(fn:(r)=>r.elapsed > %d)" % int(PERIODO * 2)):
        fin = t(f["_time"])
        seg = int(f["elapsed"])
        huecos.append({"nodo": f["nodo"], "desde": (fin - timedelta(seconds=seg)).strftime("%Y-%m-%dT%H:%M:%SZ"), "hasta": fin.strftime("%Y-%m-%dT%H:%M:%SZ"), "segundos": seg})
    huecos.sort(key=lambda h: h["desde"])
    for n, d in nodos.items():
        dur = (t(d["fin"]) - t(d["inicio"])).total_seconds()
        d["duracion_h"] = round(dur / 3600, 2)
        d["esperados"] = int(dur // PERIODO) + 1
        d["completitud_pct"] = round(100.0 * d["puntos"] / d["esperados"], 2)
        d["huecos"] = sum(1 for h in huecos if h["nodo"] == n)
        d["segundos_sin_datos"] = sum(h["segundos"] for h in huecos if h["nodo"] == n)
    inicio = min(t(d["inicio"]) for d in nodos.values())
    fin = max(t(d["fin"]) for d in nodos.values())
    res = {"corte_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "inicio_utc": inicio.isoformat(), "fin_utc": fin.isoformat(),
           "inicio_bogota": local(inicio), "fin_bogota": local(fin), "duracion_h": round((fin - inicio).total_seconds() / 3600, 2),
           "duracion_dias": round((fin - inicio).total_seconds() / 86400, 2), "periodo_s": PERIODO, "nodos": nodos, "huecos": huecos}
    if "--json" in sys.argv:
        print(json.dumps(res, indent=1))
        return
    print("TOMA DE DATOS  (hora de Bogota, UTC-5)   periodo de muestreo: %g s" % PERIODO)
    print("  inicio : %s\n  fin    : %s\n  ventana: %.2f h = %.2f dias" % (res["inicio_bogota"], res["fin_bogota"], res["duracion_h"], res["duracion_dias"]))
    print("\n%-10s %-9s %9s %9s %12s %7s %14s" % ("nodo", "protocolo", "puntos", "esperados", "completitud", "huecos", "s sin datos"))
    for n in sorted(nodos):
        d = nodos[n]
        print("%-10s %-9s %9d %9d %11.2f%% %7d %14d" % (n, d["protocolo"], d["puntos"], d["esperados"], d["completitud_pct"], d["huecos"], d["segundos_sin_datos"]))
    print("\nHUECOS (> %d s entre dos puntos seguidos): %d" % (PERIODO * 2, len(huecos)))
    for h in huecos:
        print("  %-10s %s -> %s  (%d s)" % (h["nodo"], local(t(h["desde"])), local(t(h["hasta"]))[11:], h["segundos"]))


if __name__ == "__main__":
    main()
