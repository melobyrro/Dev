#!/bin/bash
# deploy.sh - Deploy n8n stack to Docker VM
# Run this from your Mac to copy files and start the stack

set -e

REMOTE_HOST="byrro@192.168.1.11"
REMOTE_DIR="/home/byrro/docker/n8n"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== n8n Claude Config Auditor Deployment ==="
echo ""

# Check SSH connectivity
echo "Checking SSH connectivity..."
if ! ssh -q "${REMOTE_HOST}" exit; then
    echo "ERROR: Cannot connect to ${REMOTE_HOST}"
    exit 1
fi

# Create remote directory
echo "Creating remote directory..."
ssh "${REMOTE_HOST}" "mkdir -p ${REMOTE_DIR}"

# Copy files
echo "Copying files..."
scp "${LOCAL_DIR}/docker-compose.yml" "${REMOTE_HOST}:${REMOTE_DIR}/"
scp "${LOCAL_DIR}/init.sql" "${REMOTE_HOST}:${REMOTE_DIR}/"
scp "${LOCAL_DIR}/README.md" "${REMOTE_HOST}:${REMOTE_DIR}/"

# Check if .env exists on remote
if ssh "${REMOTE_HOST}" "test -f ${REMOTE_DIR}/.env"; then
    echo ".env already exists on remote, skipping..."
else
    echo ""
    echo "=== IMPORTANT: Create .env file on the remote server ==="
    echo ""
    echo "SSH to ${REMOTE_HOST} and run:"
    echo ""
    echo "cd ${REMOTE_DIR}"
    echo "cat > .env << 'EOF'"
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
    echo "N8N_USER=admin"
    echo "N8N_PASSWORD=$(openssl rand -hex 16)"
    echo "EOF"
    echo "chmod 600 .env"
    echo ""
    read -p "Press Enter after creating .env file..."
fi

# Create byrro-net network if it doesn't exist
echo "Ensuring byrro-net network exists..."
ssh "${REMOTE_HOST}" "docker network create byrro-net 2>/dev/null || true"

# Start the stack
echo "Starting Docker stack..."
ssh "${REMOTE_HOST}" "cd ${REMOTE_DIR} && docker compose up -d"

# Wait for services
echo "Waiting for services to be healthy..."
sleep 10

# Check status
echo ""
echo "=== Container Status ==="
ssh "${REMOTE_HOST}" "docker ps --filter 'name=n8n' --format 'table {{.Names}}\t{{.Status}}'"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Access n8n at: http://192.168.1.11:5678"
echo "2. Login with credentials from .env file"
echo "3. Import workflows from ${LOCAL_DIR}/workflows/"
echo "4. Configure PostgreSQL credential (see README.md)"
echo "5. Activate all workflows"
