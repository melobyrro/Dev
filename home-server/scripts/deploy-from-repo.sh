#!/bin/bash
# deploy-from-repo.sh
# Deploys configs from the Dev repo to their container paths on the VM
# Run this ON the VM after git pull, or call from Mac via SSH

set -e

REPO="/home/byrro/Dev/home-server"
HA_CONFIG="/mnt/ByrroServer/docker-data/homeassistant/config"

echo "=== GitOps Deploy Script ==="
echo "Timestamp: $(date)"

# Step 1: Pull latest from GitHub
echo ""
echo "=== Step 1: Pulling latest from GitHub ==="
cd /home/byrro/Dev
git pull --rebase
echo "Current commit: $(git log --oneline -1)"

# Step 2: Deploy Home Assistant config
echo ""
echo "=== Step 2: Deploying Home Assistant config ==="
rsync -av --delete \
    --exclude='.storage' \
    --exclude='*.db' \
    --exclude='*.db-shm' \
    --exclude='*.db-wal' \
    --exclude='*.log' \
    --exclude='*.log.*' \
    --exclude='secrets.yaml' \
    --filter='P SERVICE_ACCOUNT.json' \
    --exclude='.HA_VERSION' \
    --exclude='home-assistant.log' \
    --exclude='home-assistant.log.1' \
    --exclude='home-assistant.log.fault' \
    --exclude='__pycache__' \
    --exclude='deps' \
    --exclude='tts' \
    --exclude='custom_components' \
    --exclude='.cloud' \
    "$REPO/home-assistant/ha-config/" "$HA_CONFIG/"

# Step 3: Deploy Docker composes (without overwriting data)
echo ""
echo "=== Step 3: Deploying Docker composes ==="
rsync -av \
    --exclude='data/' \
    --exclude='*-data/' \
    --exclude='*.db' \
    --exclude='.env' \
    "$REPO/docker/" "/home/byrro/docker/"

# Step 4: Deploy container configs to docker-data
echo ""
echo "=== Step 4: Deploying container configs ==="
DOCKER_DATA="/mnt/ByrroServer/docker-data"

# Caddy
rsync -av "$REPO/docker/caddy/Caddyfile" "$DOCKER_DATA/caddy/"

# Homepage
rsync -av "$REPO/docker/homepage/"*.yaml "$DOCKER_DATA/homepage/"

# Loki
rsync -av "$REPO/docker/loki/config.yml" "$DOCKER_DATA/loki/"

# Promtail
rsync -av "$REPO/docker/promtail/promtail-config.yml" "$DOCKER_DATA/promtail/"

# Step 5: Deploy scripts
echo ""
echo "=== Step 5: Deploying scripts ==="
rsync -av \
    --exclude='__pycache__' \
    "$REPO/scripts/" "/home/byrro/scripts/"

# Step 6: Restart Home Assistant (optional - comment out if not desired)
echo ""
echo "=== Step 6: Restarting Home Assistant ==="
docker restart homeassistant

echo ""
echo "=== Deploy complete! ==="
echo "Timestamp: $(date)"
