#!/usr/bin/env bash
# Prepara una VM Ubuntu 22.04 limpia (o una Raspberry Pi OS 64 bits) para el Lab 5:
# Docker Engine + plugin compose, 2 GB de swap (la VM B2ats_v2 solo tiene 1 GB de RAM) y hora sincronizada.
# Uso:  sudo ./scripts/instalar_vm.sh
set -euo pipefail

echo "[1/4] Docker Engine + compose (script oficial get.docker.com)"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
usermod -aG docker "${SUDO_USER:-$USER}" || true
systemctl enable --now docker

echo "[2/4] Swap de 2 GB (RabbitMQ + InfluxDB + Grafana no caben holgados en 1 GB)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
sysctl -w vm.swappiness=20 >/dev/null
grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=20' >> /etc/sysctl.conf

echo "[3/4] Hora real (la TSDB guarda la marca de tiempo del dispositivo)"
timedatectl set-ntp true || true
systemctl restart systemd-timesyncd 2>/dev/null || true

echo "[4/4] Rotacion de logs de Docker (4 dias de toma no deben llenar el disco)"
mkdir -p /etc/docker
if [ ! -f /etc/docker/daemon.json ]; then
  printf '{\n  "log-driver": "json-file",\n  "log-opts": {"max-size": "10m", "max-file": "3"}\n}\n' > /etc/docker/daemon.json
  systemctl restart docker
fi
docker --version && docker compose version
free -m | sed -n '1,3p'
timedatectl | grep -E 'Local time|synchronized'
