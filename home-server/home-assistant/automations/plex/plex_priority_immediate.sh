#!/bin/bash
# Immediate Plex Priority Adjustment
# Run this when Plex is buffering to give it priority

set -e

echo "=== Plex Priority Boost ==="
echo "Current time: $(date)"
echo ""

# 1. Check Plex status
echo "1. Checking Plex status..."
PLEX_PID=$(docker inspect -f '{{.State.Pid}}' plex 2>/dev/null || echo "")
if [ -z "$PLEX_PID" ]; then
    echo "   ✗ Plex container not found or not running"
    exit 1
fi
echo "   ✓ Plex PID: $PLEX_PID"

# 2. Check qBittorrent status
echo "2. Checking qBittorrent status..."
QBIT_PID=$(docker inspect -f '{{.State.Pid}}' qbittorrent 2>/dev/null || echo "")
if [ -z "$QBIT_PID" ]; then
    echo "   ⚠ qBittorrent not running"
    QBIT_PID=""
else
    echo "   ✓ qBittorrent PID: $QBIT_PID"
fi

# 3. Check system load
echo "3. System status:"
LOAD=$(uptime | awk -F'load average:' '{print $2}')
echo "   Load average: $LOAD"
FREE_MEM=$(free -h | awk '/^Mem:/ {print $4}')
echo "   Free memory: $FREE_MEM"
SWAP_USED=$(free -h | awk '/^Swap:/ {print $3}')
echo "   Swap used: $SWAP_USED"

# 4. Adjust process priorities (niceness)
# Lower niceness = higher priority (range: -20 to 19, default: 0)
echo "4. Adjusting process priorities..."

# Give Plex higher priority (niceness -5)
if renice -n -5 -p "$PLEX_PID" >/dev/null 2>&1; then
    echo "   ✓ Set Plex priority to -5 (higher)"
else
    echo "   ⚠ Could not adjust Plex priority (may need sudo)"
fi

# Give qBittorrent lower priority (niceness +10) if it's running
if [ -n "$QBIT_PID" ]; then
    if renice -n +10 -p "$QBIT_PID" >/dev/null 2>&1; then
        echo "   ✓ Set qBittorrent priority to +10 (lower)"
    else
        echo "   ⚠ Could not adjust qBittorrent priority"
    fi
fi

# 5. Adjust I/O priorities if available
echo "5. Adjusting I/O priorities..."
if command -v ionice >/dev/null 2>&1; then
    # Give Plex highest I/O priority (Real-time class)
    if ionice -c1 -n0 -p "$PLEX_PID" >/dev/null 2>&1; then
        echo "   ✓ Set Plex I/O to real-time priority"
    else
        echo "   ⚠ Could not set Plex I/O priority (may need sudo)"
    fi
    
    # Give qBittorrent lowest I/O priority (Idle class)
    if [ -n "$QBIT_PID" ]; then
        if ionice -c3 -p "$QBIT_PID" >/dev/null 2>&1; then
            echo "   ✓ Set qBittorrent I/O to idle priority"
        else
            echo "   ⚠ Could not set qBittorrent I/O priority"
        fi
    fi
else
    echo "   ⚠ ionice not available"
fi

# 6. Clear disk caches to free up memory (optional)
echo "6. Freeing up memory..."
if [ "$(id -u)" = "0" ]; then
    sync
    echo 3 > /proc/sys/vm/drop_caches
    echo "   ✓ Cleared disk caches"
else
    echo "   ⚠ Skipping cache clear (need root)"
fi

# 7. Check Plex transcode directory
echo "7. Checking Plex transcode space..."
TRANSCODE_DIR="/mnt/ByrroServer/docker-data/plex/transcode"
if [ -d "$TRANSCODE_DIR" ]; then
    TRANSCODE_FREE=$(df -h "$TRANSCODE_DIR" | awk 'NR==2 {print $4}')
    echo "   ✓ Transcode directory free: $TRANSCODE_FREE"
else
    echo "   ⚠ Transcode directory not found"
fi

# 8. Monitor Plex playback
echo "8. Monitoring Plex playback status..."
echo "   Run this command to check if buffering improves:"
echo "   docker exec plex tail -f '/config/Library/Application Support/Plex Media Server/Logs/Plex Media Server.log' | grep -i 'state='"
echo ""
echo "=== Priority boost complete ==="
echo ""
echo "To restore normal priorities, run:"
echo "  renice -n 0 -p $PLEX_PID"
if [ -n "$QBIT_PID" ]; then
    echo "  renice -n 0 -p $QBIT_PID"
fi
echo ""
echo "For automatic monitoring, consider setting up the Python script"
echo "that dynamically adjusts resources based on Plex activity."