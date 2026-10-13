#!/usr/bin/env bash
# Imprime cada 10 s el estado de las reglas de Grafana (Normal -> Pending -> Alerting -> Normal).
# Sirve de evidencia en texto del disparo:  ./scripts/vigilar_alertas.sh 60 | tee evidencia.log
#   $1 = numero de lecturas (por defecto 60 = 10 minutos)
set -euo pipefail
cd "$(dirname "$0")/.."
N=${1:-60}
for _ in $(seq "$N"); do
  curl -s http://localhost:3000/api/prometheus/grafana/api/v1/rules | python3 -c '
import json, sys, time
ahora = time.strftime("%H:%M:%SZ", time.gmtime())
for g in json.load(sys.stdin)["data"]["groups"]:
    for r in g["rules"]:
        inst = " ".join("%s=%s(%s)" % (a["labels"].get("nodo", "-"), a["state"], (a.get("value") or "")[:60].replace("\n", " ")) for a in sorted(r.get("alerts", []), key=lambda a: a["labels"].get("nodo", "")))
        print("%s %-18s %-8s %s" % (ahora, r["name"], r["state"], inst))
'
  echo
  sleep 10
done
