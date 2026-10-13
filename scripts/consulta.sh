#!/usr/bin/env bash
# Consulta directa a la TSDB (sin Grafana) con el cliente influx del propio contenedor.
#   ./scripts/consulta.sh ultimos      # ultimos 5 puntos crudos de cada nodo
#   ./scripts/consulta.sh resumen      # conteo, primer y ultimo punto, min/media/max por nodo (toda la toma)
#   ./scripts/consulta.sh huecos       # intervalos de mas de 30 s sin datos (lo normal es 15 s)
#   ./scripts/consulta.sh "<flux>"     # cualquier consulta Flux
set -euo pipefail
cd "$(dirname "$0")/.."
Q=${1:-ultimos}
case "$Q" in
  ultimos) FLUX='from(bucket:"ambiental") |> range(start:-10m) |> filter(fn:(r)=>r._measurement=="telemetria" and (r._field=="temperature" or r._field=="humidity" or r._field=="illuminance" or r._field=="seq"))
  |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value") |> group(columns:["nodo"]) |> sort(columns:["_time"]) |> tail(n:5)
  |> keep(columns:["_time","nodo","protocolo","seq","temperature","humidity","illuminance"])' ;;
  resumen) FLUX='d = from(bucket:"ambiental") |> range(start:-30d) |> filter(fn:(r)=>r._measurement=="telemetria" and r._field=="temperature") |> group(columns:["nodo","protocolo"])
d |> count() |> rename(columns:{_value:"puntos"}) |> keep(columns:["nodo","protocolo","puntos"]) |> group() |> yield(name:"1_puntos_por_nodo")
d |> first() |> rename(columns:{_time:"primer_punto"}) |> keep(columns:["nodo","primer_punto"]) |> group() |> yield(name:"2_inicio_de_la_toma")
d |> last() |> rename(columns:{_time:"ultimo_punto"}) |> keep(columns:["nodo","ultimo_punto"]) |> group() |> yield(name:"3_fin_de_la_toma")
v = from(bucket:"ambiental") |> range(start:-30d) |> filter(fn:(r)=>r._measurement=="telemetria" and (r._field=="temperature" or r._field=="humidity" or r._field=="illuminance")) |> group(columns:["_field"])
v |> min() |> keep(columns:["_field","_value"]) |> group() |> yield(name:"4_minimo")
v |> mean() |> keep(columns:["_field","_value"]) |> group() |> yield(name:"5_media")
v |> max() |> keep(columns:["_field","_value"]) |> group() |> yield(name:"6_maximo")' ;;
  huecos) FLUX='from(bucket:"ambiental") |> range(start:-30d) |> filter(fn:(r)=>r._measurement=="telemetria" and r._field=="temperature") |> group(columns:["nodo"])
  |> elapsed(unit:1s) |> filter(fn:(r)=>r.elapsed > 30)
  |> map(fn:(r)=>({nodo:r.nodo, hueco_termina:r._time, segundos_sin_datos:r.elapsed})) |> group() |> sort(columns:["hueco_termina"])' ;;
  *) FLUX="$Q" ;;
esac
docker compose exec -T influxdb sh -c 'influx query --org unab --token "$DOCKER_INFLUXDB_INIT_ADMIN_TOKEN" "$0"' "$FLUX"
