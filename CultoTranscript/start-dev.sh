#!/bin/bash

###############################################################################
# CultoTranscript Development Startup Script
#
# This script starts all development services in the correct order:
# 1. Docker containers (FastAPI, PostgreSQL, Redis)
# 2. React dev server (Vite)
# 3. Runs smoke tests to verify everything is working
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      CultoTranscript v2.0 Development Startup            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Step 1: Check Prerequisites
###############################################################################

echo -e "${YELLOW}[1/6]${NC} Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "  Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found${NC}"
    echo "  Please install Node.js: https://nodejs.org/"
    exit 1
fi

# Check npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}✗ npm not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker found:${NC} $(docker --version)"
echo -e "${GREEN}✓ Node.js found:${NC} $(node --version)"
echo -e "${GREEN}✓ npm found:${NC} $(npm --version)"
echo ""

###############################################################################
# Step 2: Start Docker Containers
###############################################################################

echo -e "${YELLOW}[2/6]${NC} Starting Docker containers..."

cd "$PROJECT_ROOT"

# Check if docker compose or docker-compose
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose --version &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}✗ Neither 'docker compose' nor 'docker-compose' found${NC}"
    exit 1
fi

echo "  Using: $DOCKER_COMPOSE"

# Stop any existing containers
echo "  Stopping existing containers..."
$DOCKER_COMPOSE down > /dev/null 2>&1 || true

# Start containers with build
echo "  Building and starting containers..."
$DOCKER_COMPOSE up -d --build

# Wait for services to be ready
echo "  Waiting for services to start..."
sleep 5

# Check if culto_web is running
if ! $DOCKER_COMPOSE ps | grep -q "culto_web.*Up"; then
    echo -e "${RED}✗ culto_web container failed to start${NC}"
    echo "  Check logs with: $DOCKER_COMPOSE logs culto_web"
    exit 1
fi

echo -e "${GREEN}✓ Docker containers running${NC}"
echo ""

###############################################################################
# Step 3: Wait for FastAPI to be Ready
###############################################################################

echo -e "${YELLOW}[3/6]${NC} Waiting for FastAPI server..."

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ FastAPI server ready${NC}"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 1
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "\n${RED}✗ FastAPI server failed to start after ${MAX_RETRIES}s${NC}"
    echo "  Check logs with: $DOCKER_COMPOSE logs culto_web"
    exit 1
fi

echo ""

###############################################################################
# Step 4: Test SSE Endpoint
###############################################################################

echo -e "${YELLOW}[4/6]${NC} Testing SSE endpoint..."

# Test health endpoint
SSE_HEALTH=$(curl -s http://localhost:8000/api/v2/events/health)
if echo "$SSE_HEALTH" | grep -q '"status":"healthy"'; then
    echo -e "${GREEN}✓ SSE endpoint healthy${NC}"
    echo "  $SSE_HEALTH"
else
    echo -e "${RED}✗ SSE endpoint not responding correctly${NC}"
    echo "  Response: $SSE_HEALTH"
fi

echo ""

###############################################################################
# Step 5: Start React Dev Server
###############################################################################

echo -e "${YELLOW}[5/6]${NC} Starting React dev server..."

cd "$PROJECT_ROOT/UI"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "  Installing npm dependencies..."
    npm install
fi

# Kill any existing Vite server on port 5173
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

# Start Vite in background
echo "  Starting Vite dev server on port 5173..."
npm run dev > "$PROJECT_ROOT/vite.log" 2>&1 &
VITE_PID=$!

# Wait for Vite to be ready
echo "  Waiting for Vite server..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ React dev server ready${NC}"
        echo -e "  ${BLUE}→ http://localhost:5173${NC}"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 1
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "\n${RED}✗ Vite server failed to start after ${MAX_RETRIES}s${NC}"
    echo "  Check logs in: vite.log"
    kill $VITE_PID 2>/dev/null || true
    exit 1
fi

echo ""

###############################################################################
# Summary
###############################################################################

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                  All Services Running!                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Services:${NC}"
echo -e "  ${BLUE}→${NC} FastAPI Backend:  ${GREEN}http://localhost:8000${NC}"
echo -e "  ${BLUE}→${NC} React Frontend:   ${GREEN}http://localhost:5173${NC}"
echo -e "  ${BLUE}→${NC} API Docs:         ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  ${BLUE}→${NC} SSE Stream:       ${GREEN}http://localhost:8000/api/v2/events/stream${NC}"
echo ""
echo -e "${GREEN}Docker Containers:${NC}"
$DOCKER_COMPOSE ps
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo -e "  ${BLUE}View FastAPI logs:${NC}    $DOCKER_COMPOSE logs -f culto_web"
echo -e "  ${BLUE}View React logs:${NC}       tail -f $PROJECT_ROOT/vite.log"
echo -e "  ${BLUE}Run tests:${NC}             cd Tests && npm test"
echo -e "  ${BLUE}Stop all services:${NC}     $DOCKER_COMPOSE down && kill $VITE_PID"
echo ""
echo -e "${GREEN}Vite PID:${NC} $VITE_PID (save this to kill later)"
echo -e "${BLUE}To stop React server:${NC} kill $VITE_PID"
echo ""
echo -e "${GREEN}Ready for development! 🚀${NC}"
echo ""

# Save PID for cleanup script
echo "$VITE_PID" > "$PROJECT_ROOT/.vite.pid"
