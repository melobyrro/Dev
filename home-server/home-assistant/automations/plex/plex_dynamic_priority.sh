#!/bin/bash
# Plex Dynamic Resource Priority Service
# Monitors Plex activity and adjusts system resources accordingly

LOG_FILE="/tmp/plex_priority.log"
STATE_FILE="/tmp/plex_priority.state"
CHECK_INTERVAL=10

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_plex_sessions() {
    # Check if Plex has active playing sessions
    # Returns number of active sessions
    local token
    # Dynamically fetch token from inside the container
    token=$(docker exec plex grep -o 'PlexOnlineToken="[^"]*"' '/config/Library/Application Support/Plex Media Server/Preferences.xml' 2>/dev/null | cut -d'"' -f2)
    
    local sessions
    # Use token for authentication and ensure we only get the first size count (sessions count)
    sessions=$(docker exec plex curl -s -H "X-Plex-Token: $token" http://localhost:32400/status/sessions 2>/dev/null | grep -o 'size="[0-9]*"' | head -n 1 | cut -d'"' -f2)
    echo "${sessions:-0}"
}

get_system_load() {
    # Get 1-minute load average
    cut -d' ' -f1 /proc/loadavg
}

get_plex_pid() {
    docker inspect -f '{{.State.Pid}}' plex 2>/dev/null || echo ""
}

get_qbit_pid() {
    docker inspect -f '{{.State.Pid}}' qbittorrent 2>/dev/null || echo ""
}

set_priority_active() {
    # When Plex is active, give it priority
    local plex_pid=$1
    local qbit_pid=$2
    
    log "Plex active - setting high priority"
    
    # Process priority (niceness)
    sudo renice -n "$PLEX_NICENESS" -p "$plex_pid" 2>/dev/null && log "  Plex priority: $PLEX_NICENESS"
    if [ -n "$qbit_pid" ]; then
        sudo renice -n "$QBIT_NICENESS" -p "$qbit_pid" 2>/dev/null && log "  qBittorrent priority: $QBIT_NICENESS"
    fi
    
    # I/O priority
    if command -v ionice >/dev/null 2>&1; then
        sudo ionice -c"$PLEX_IONICE_CLASS" -n"$PLEX_IONICE_DATA" -p "$plex_pid" 2>/dev/null && log "  Plex I/O: class $PLEX_IONICE_CLASS"
        if [ -n "$qbit_pid" ]; then
            sudo ionice -c"$QBIT_IONICE_CLASS" -p "$qbit_pid" 2>/dev/null && log "  qBittorrent I/O: class $QBIT_IONICE_CLASS"
        fi
    fi
    
    # Try to limit qBittorrent via API if available
    limit_qbit_via_api "active"
}

set_priority_idle() {
    # When system is idle, restore normal priorities
    local plex_pid=$1
    local qbit_pid=$2
    
    log "System idle - restoring normal priorities"
    
    # Restore normal process priority
    sudo renice -n 0 -p "$plex_pid" 2>/dev/null && log "  Plex priority: 0 (normal)"
    if [ -n "$qbit_pid" ]; then
        sudo renice -n 0 -p "$qbit_pid" 2>/dev/null && log "  qBittorrent priority: 0 (normal)"
    fi
    
    # Restore normal I/O priority
    if command -v ionice >/dev/null 2>&1; then
        sudo ionice -c2 -n4 -p "$plex_pid" 2>/dev/null && log "  Plex I/O: best-effort"
        if [ -n "$qbit_pid" ]; then
            sudo ionice -c2 -n4 -p "$qbit_pid" 2>/dev/null && log "  qBittorrent I/O: best-effort"
        fi
    fi
    
    # Restore qBittorrent limits
    limit_qbit_via_api "idle"
}

limit_qbit_via_api() {
    # Try to control qBittorrent via API
    local mode=$1
    
    # This is a placeholder - in production, implement proper API calls
    # based on the Python script we created earlier
    if [ "$mode" = "active" ]; then
        log "  Would limit qBittorrent speeds (API control needed)"
    else
        log "  Would restore qBittorrent speeds (API control needed)"
    fi
}

monitor_system() {
    local plex_sessions
    local system_load
    local current_state="idle"
    local last_state="idle"
    
    log "Starting Plex Dynamic Priority Service"
    log "Check interval: ${CHECK_INTERVAL}s"
    
    while true; do
        # Load configuration
        if [ -f "/tmp/plex_priority.conf" ]; then
            source "/tmp/plex_priority.conf"
        fi
        
        # Defaults
        : "${PLEX_NICENESS:=-5}"
        : "${QBIT_NICENESS:=10}"
        : "${PLEX_IONICE_CLASS:=1}" # 1=Realtime, 2=Best-Effort, 3=Idle
        : "${PLEX_IONICE_DATA:=0}"
        : "${QBIT_IONICE_CLASS:=3}"
        : "${ENABLED:=true}"

        if [ "$ENABLED" != "true" ]; then
             if [ "$current_state" != "disabled" ]; then
                log "Service disabled via config - resetting priorities"
                plex_pid=$(get_plex_pid)
                qbit_pid=$(get_qbit_pid)
                set_priority_idle "$plex_pid" "$qbit_pid"
                current_state="disabled"
             fi
             sleep "$CHECK_INTERVAL"
             continue
        fi

        # Get current Plex sessions
        plex_sessions=$(get_plex_sessions)
        
        # Get system load
        system_load=$(get_system_load)
        
        # Get PIDs
        plex_pid=$(get_plex_pid)
        qbit_pid=$(get_qbit_pid)
        
        if [ -z "$plex_pid" ]; then
            log "Plex container not running, waiting..."
            sleep "$CHECK_INTERVAL"
            continue
        fi
        
        # Determine desired state
        if [ "$plex_sessions" -gt 0 ]; then
            desired_state="active"
            reason="Plex has $plex_sessions active session(s)"
        elif [ "$(echo "$system_load > 8" | bc 2>/dev/null || echo 0)" -eq 1 ]; then
            desired_state="active"
            reason="High system load: $system_load"
        else
            desired_state="idle"
            reason="System idle (load: $system_load)"
        fi
        
        # Apply state change if needed
        if [ "$desired_state" != "$current_state" ]; then
            log "State change: $current_state -> $desired_state ($reason)"
            
            if [ "$desired_state" = "active" ]; then
                set_priority_active "$plex_pid" "$qbit_pid"
            else
                set_priority_idle "$plex_pid" "$qbit_pid"
            fi
            
            current_state="$desired_state"
            echo "$current_state" > "$STATE_FILE"
        fi
        
        # Log status periodically
        if [ $(( $(date +%s) % 300 )) -lt "$CHECK_INTERVAL" ]; then
            log "Status: Plex sessions=$plex_sessions, Load=$system_load, State=$current_state"
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

# Start monitoring
monitor_system