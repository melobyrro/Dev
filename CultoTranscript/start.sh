#!/bin/bash
#
# CultoTranscript - Quick Start Script
#

set -e

echo "🚀 CultoTranscript - Starting services..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it before continuing."
    echo "   Run: nano .env"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Navigate to docker directory
cd docker

# Start services
echo "📦 Starting Docker containers..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to initialize (30 seconds)..."
sleep 30

# Check service health
echo "🔍 Checking service status..."
docker-compose ps

echo ""
echo "✅ CultoTranscript is running!"
echo ""
echo "🌐 Access the application:"
echo "   http://localhost:8000"
echo ""
echo "🔐 Default login password: admin123"
echo "   (Change in .env: INSTANCE_PASSWORD)"
echo ""
echo "📊 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
