#!/usr/bin/env bash
# Fuerza un valor en un publicador durante N segundos (para disparar una alerta de Grafana).
# El publicador lee ./control/forzar.json en cada muestra; al vencer "hasta" vuelve solo a lo normal.
#
#   ./scripts/forzar.sh nodo-mqtt temperature 41 240     # 41 degC durante 4 minutos en el nodo MQTT
#   ./scripts/forzar.sh '*' humidity 28 180              # todos los nodos
#   ./scripts/forzar.sh off                              # cancela
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p control
if [ "${1:-}" = "off" ]; then
  echo '{}' > control/forzar.json
  echo "$(date -u +%FT%TZ) forzado cancelado"
  exit 0
fi
NODO=${1:?nodo (nodo-mqtt|nodo-amqp|nodo-coap|*)}
VAR=${2:?variable (temperature|humidity|illuminance)}
VALOR=${3:?valor}
SEG=${4:-240}
HASTA=$(( $(date +%s) + SEG ))
printf '{"%s": {"%s": %s, "hasta": %s}}\n' "$NODO" "$VAR" "$VALOR" "$HASTA" > control/forzar.json
echo "$(date -u +%FT%TZ) FORZANDO $VAR=$VALOR en $NODO durante ${SEG}s (hasta $(date -u -d @"$HASTA" +%TZ))"
