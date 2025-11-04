#!/bin/bash
#
# Deploy Channel-Focused Update to Server
# Deploys the latest changes including date range filtering for bulk imports
#

set -e

SERVER="192.168.1.11"
USER="root"
PROJECT_PATH="/root/CultoTranscript"

echo "🚀 Deploying Channel-Focused Update to $SERVER..."

# Test SSH connection
echo "🔐 Testing SSH connection..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 $USER@$SERVER "echo 'SSH OK'" 2>/dev/null; then
    echo "❌ SSH connection failed!"
    echo ""
    echo "Please run this command to add your SSH key:"
    echo "  ssh-copy-id -i ~/.ssh/id_ed25519.pub $USER@$SERVER"
    echo ""
    echo "Or connect manually and verify access:"
    echo "  ssh $USER@$SERVER"
    exit 1
fi

echo "✅ SSH connection successful"

# Copy updated files
echo ""
echo "📦 Copying updated files..."

echo "  → app/web/main.py"
scp app/web/main.py $USER@$SERVER:$PROJECT_PATH/app/web/main.py

echo "  → app/web/routes/api.py"
scp app/web/routes/api.py $USER@$SERVER:$PROJECT_PATH/app/web/routes/api.py

echo "  → app/web/templates/index.html"
scp app/web/templates/index.html $USER@$SERVER:$PROJECT_PATH/app/web/templates/index.html

echo "  → app/web/templates/base.html"
scp app/web/templates/base.html $USER@$SERVER:$PROJECT_PATH/app/web/templates/base.html

echo "  → app/worker/main.py"
scp app/worker/main.py $USER@$SERVER:$PROJECT_PATH/app/worker/main.py

echo "  → DEPLOYMENT.md"
scp DEPLOYMENT.md $USER@$SERVER:$PROJECT_PATH/DEPLOYMENT.md

echo ""
echo "♻️  Restarting containers..."
ssh $USER@$SERVER "cd $PROJECT_PATH/docker && docker-compose restart web worker"

echo ""
echo "⏳ Waiting for services to start..."
sleep 3

echo ""
echo "📊 Checking container status..."
ssh $USER@$SERVER "cd $PROJECT_PATH/docker && docker-compose ps | grep -E '(web|worker)'"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Access the dashboard: http://$SERVER:8000"
echo ""
echo "📝 Test the new features:"
echo "  1. Dashboard should show channel header or setup form"
echo "  2. Two import options: single video and bulk with date range"
echo "  3. Navigation should say 'Todos os Vídeos' instead of 'Vídeos'"
echo ""
echo "📋 View logs with:"
echo "  ssh $USER@$SERVER 'cd $PROJECT_PATH/docker && docker-compose logs -f web worker'"
echo ""
