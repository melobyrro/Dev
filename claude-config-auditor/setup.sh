#!/bin/bash
# setup.sh - Set up the Claude Config Auditor local agent
# Run this on your Mac to install dependencies and load the launch agent

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="${SCRIPT_DIR}/com.byrro.claude-config-auditor.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/com.byrro.claude-config-auditor.plist"

echo "=== Claude Config Auditor Agent Setup ==="
echo ""

# Check Python 3
echo "Checking Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3."
    exit 1
fi
python3 --version

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install -r "${SCRIPT_DIR}/requirements.txt" --quiet

# Test the agent (dry run)
echo ""
echo "Testing agent (dry run)..."
python3 "${SCRIPT_DIR}/agent.py" --dry-run | head -50

# Copy plist to LaunchAgents
echo ""
echo "Installing launch agent..."
cp "${PLIST_SRC}" "${PLIST_DST}"

# Unload if already loaded
echo "Unloading existing agent (if any)..."
launchctl unload "${PLIST_DST}" 2>/dev/null || true

# Load the agent
echo "Loading agent..."
launchctl load "${PLIST_DST}"

# Check status
echo ""
echo "=== Agent Status ==="
launchctl list | grep claude-config-auditor || echo "Agent not in list (may not have run yet)"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "The agent will run:"
echo "  - Immediately on Mac login"
echo "  - Every 4 hours"
echo ""
echo "Log file: /tmp/claude-config-auditor.log"
echo ""
echo "Manual commands:"
echo "  Run now:    python3 ${SCRIPT_DIR}/agent.py"
echo "  Dry run:    python3 ${SCRIPT_DIR}/agent.py --dry-run"
echo "  View logs:  tail -f /tmp/claude-config-auditor.log"
echo "  Unload:     launchctl unload ${PLIST_DST}"
echo "  Reload:     launchctl load ${PLIST_DST}"
