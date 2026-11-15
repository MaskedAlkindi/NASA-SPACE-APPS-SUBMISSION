#!/usr/bin/env bash
# One-time setup of the HEALTH-01 online demo on a fresh Ubuntu 22.04/24.04 DigitalOcean droplet.
# Run as root from the repository folder:   bash deploy/digitalocean/setup.sh [your-domain.org]
# Works on a GPU droplet (Ollama + trainer on the GPU) and on a CPU droplet (Ollama on CPU, small model, no training).
set -euo pipefail
cd "$(dirname "$0")/../.."
DOMAIN="${1:-:80}"
EDITION="${EDITION:-serious}"          # serious = private, password-protected (default); notebook = public demo

echo "== Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

GPU=0
if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
  GPU=1
  echo "== NVIDIA GPU found: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"
  if ! docker info 2>/dev/null | grep -qi nvidia; then
    echo "== Installing NVIDIA container toolkit"
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' \
      > /etc/apt/sources.list.d/nvidia-container-toolkit.list
    apt-get update && apt-get install -y nvidia-container-toolkit
    nvidia-ctk runtime configure --runtime=docker && systemctl restart docker
  fi
else
  echo "== No NVIDIA GPU: CPU mode (Ollama on CPU, use a small model; fine-tuning disabled)"
fi

echo "== .env"
if [ ! -f .env ]; then
  cp .env.example .env
  rnd() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
  setkey() { if grep -q "^$1=" .env; then sed -i "s#^$1=.*#$1=$2#" .env; else echo "$1=$2" >> .env; fi; }
  setkey SECRET_KEY "$(rnd 48)"
  setkey POSTGRES_PASSWORD "$(rnd 24)"
  setkey DEMO_PASSCODE "$(rnd 10)"
  setkey DOMAIN "${DOMAIN}"
  setkey HMT_TRAINER_TOKEN "$(rnd 32)"
  setkey API_PORT "127.0.0.1:8000"      # only Caddy is exposed to the internet
  setkey WEB_PORT "127.0.0.1:8080"
  setkey MQTT_PORT "127.0.0.1:1883"     # sensors reach the broker over an SSH tunnel or VPN, not the open internet
  if [ "$EDITION" = serious ]; then
    setkey WEB_EDITION serious
    setkey WEB_NGINX_CONF nginx.serious.conf
    setkey SITE_PASSWORD "${SITE_PASSWORD:-staydetermined}"
  fi
  setkey OLLAMA_MODEL "$([ $GPU = 1 ] && echo qwen2.5:7b || echo qwen2.5:1.5b)"
  echo "   wrote .env (random demo passcode: see DEMO_PASSCODE in .env)"
fi

mkdir -p data/llm && chown -R 10001 data/llm

echo "== Firewall: SSH + web only"
if command -v ufw >/dev/null; then ufw allow OpenSSH; ufw allow 80/tcp; ufw allow 443/tcp; ufw --force enable; fi

FILES="-f docker-compose.yml -f deploy/digitalocean/docker-compose.do.yml"
if [ $GPU = 0 ]; then FILES="$FILES -f deploy/digitalocean/docker-compose.cpu.yml"; fi
echo "COMPOSE_FILES=\"$FILES\"" > deploy/digitalocean/.compose
echo "== Building and starting (first build takes several minutes)"
docker compose $FILES up -d --build

echo "== Downloading the assistant model into Ollama"
MODEL=$(grep '^OLLAMA_MODEL=' .env | tail -1 | cut -d= -f2)
docker compose $FILES exec -T ollama ollama pull "$MODEL"

echo "== Done. Open http://$( [ "$DOMAIN" = ":80" ] && curl -s ifconfig.me || echo "$DOMAIN" )/"
echo "   Update later with: bash deploy/digitalocean/update.sh"
