#!/bin/bash
#
# Deploy delete video feature to server
#

set -e

SERVER="192.168.1.11"
USER="root"

echo "🚀 Deploying delete video feature..."

# Copy updated API routes
echo "📦 Copying API routes..."
scp app/web/routes/api.py $USER@$SERVER:/root/CultoTranscript/app/web/routes/api.py

# Copy updated dashboard template
echo "📦 Copying dashboard template..."
scp app/web/templates/index.html $USER@$SERVER:/root/CultoTranscript/app/web/templates/index.html

# Restart web service
echo "♻️  Restarting web service..."
ssh $USER@$SERVER "cd /root/CultoTranscript/docker && docker-compose restart web"

echo "✅ Deployment complete!"
echo "🌐 Check http://192.168.1.11:8000"
