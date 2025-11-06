#!/bin/bash

###############################################################################
# CultoTranscript Development Shutdown Script
#
# This script stops all development services gracefully
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      CultoTranscript v2.0 Development Shutdown           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Stop React Dev Server
###############################################################################

echo -e "${YELLOW}[1/3]${NC} Stopping React dev server..."

# Try to read PID from file
if [ -f "$PROJECT_ROOT/.vite.pid" ]; then
    VITE_PID=$(cat "$PROJECT_ROOT/.vite.pid")
    if kill -0 $VITE_PID 2>/dev/null; then
        kill $VITE_PID
        echo -e "${GREEN}✓ React dev server stopped (PID: $VITE_PID)${NC}"
    else
        echo -e "${YELLOW}⚠ Vite process not running (PID: $VITE_PID)${NC}"
    fi
    rm "$PROJECT_ROOT/.vite.pid"
else
    # Fallback: kill any process on port 5173
    if lsof -ti:5173 > /dev/null 2>&1; then
        lsof -ti:5173 | xargs kill -9
        echo -e "${GREEN}✓ React dev server stopped (port 5173)${NC}"
    else
        echo -e "${YELLOW}⚠ No React dev server running on port 5173${NC}"
    fi
fi

echo ""

###############################################################################
# Stop Docker Containers
###############################################################################

echo -e "${YELLOW}[2/3]${NC} Stopping Docker containers..."

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

# Stop containers
$DOCKER_COMPOSE down

echo -e "${GREEN}✓ Docker containers stopped${NC}"
echo ""

###############################################################################
# Cleanup
###############################################################################

echo -e "${YELLOW}[3/3]${NC} Cleaning up..."

# Remove log files (optional)
if [ -f "$PROJECT_ROOT/vite.log" ]; then
    rm "$PROJECT_ROOT/vite.log"
    echo -e "${GREEN}✓ Removed vite.log${NC}"
fi

echo ""
echo -e "${GREEN}All services stopped successfully! 👋${NC}"
echo ""
