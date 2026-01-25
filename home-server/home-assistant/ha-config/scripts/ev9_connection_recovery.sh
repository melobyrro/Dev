#!/bin/bash
# EV9 Connection Recovery Script
# Version: 1.0
#
# This script attempts to recover the Kia UVO integration:
# 1. Tries to reload the existing integration
# 2. If reload fails, deletes and recreates the integration
#
# Usage: ev9_connection_recovery.sh <ha_token> <secrets_file>
# Output: Writes result to /tmp/ev9_recovery_result.txt

set -e

HA_URL="http://localhost:8123"
HA_TOKEN="$1"
SECRETS_FILE="${2:-/config/secrets.yaml}"
RESULT_FILE="/tmp/ev9_recovery_result.txt"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Parse YAML value from secrets file
get_secret() {
    local key="$1"
    grep "^${key}:" "$SECRETS_FILE" | sed 's/^[^:]*: *//' | tr -d '"' | tr -d "'"
}

# Make API request
api_request() {
    local method="$1"
    local endpoint="$2"
    local data="$3"

    if [ -n "$data" ]; then
        curl -s -X "$method" \
            -H "Authorization: Bearer $HA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "${HA_URL}${endpoint}"
    else
        curl -s -X "$method" \
            -H "Authorization: Bearer $HA_TOKEN" \
            -H "Content-Type: application/json" \
            "${HA_URL}${endpoint}"
    fi
}

# Check if sensor is available
check_sensor() {
    local state
    state=$(api_request "GET" "/api/states/sensor.ev9_ev_battery_level" | grep -o '"state":"[^"]*"' | cut -d'"' -f4)
    if [ "$state" != "unavailable" ] && [ "$state" != "unknown" ] && [ -n "$state" ]; then
        return 0
    else
        return 1
    fi
}

# Find kia_uvo config entry ID
find_entry_id() {
    api_request "GET" "/api/config/config_entries/entry" | \
        grep -o '"entry_id":"[^"]*","domain":"kia_uvo"' | \
        head -1 | \
        sed 's/"entry_id":"\([^"]*\)".*/\1/'
}

# Reload integration
reload_integration() {
    local entry_id="$1"
    log "Attempting to reload integration (entry_id: $entry_id)"
    local result
    result=$(api_request "POST" "/api/config/config_entries/entry/${entry_id}/reload")
    log "Reload response: $result"
}

# Delete integration
delete_integration() {
    local entry_id="$1"
    log "Deleting integration (entry_id: $entry_id)"
    api_request "DELETE" "/api/config/config_entries/entry/${entry_id}"
}

# Create new integration
create_integration() {
    local username password pin
    username=$(get_secret "kia_username")
    password=$(get_secret "kia_password")
    pin=$(get_secret "kia_pin")

    if [ -z "$username" ] || [ -z "$password" ] || [ -z "$pin" ]; then
        log "ERROR: Could not read credentials from secrets file"
        return 1
    fi

    log "Creating new kia_uvo integration"

    # Step 1: Initialize the config flow
    local flow_response
    flow_response=$(api_request "POST" "/api/config/config_entries/flow" \
        '{"handler":"kia_uvo","show_advanced_options":false}')

    local flow_id
    flow_id=$(echo "$flow_response" | grep -o '"flow_id":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$flow_id" ]; then
        log "ERROR: Could not start config flow. Response: $flow_response"
        return 1
    fi

    log "Config flow started (flow_id: $flow_id)"

    # Step 2: Submit credentials
    # Region: 3 = USA, Brand: 1 = Kia
    local create_response
    create_response=$(api_request "POST" "/api/config/config_entries/flow/${flow_id}" \
        "{\"username\":\"${username}\",\"password\":\"${password}\",\"pin\":\"${pin}\",\"region\":3,\"brand\":1}")

    log "Create response: $create_response"

    # Check if it succeeded (should have "type": "create_entry")
    if echo "$create_response" | grep -q '"type":"create_entry"'; then
        return 0
    else
        return 1
    fi
}

# Main recovery logic
main() {
    log "=== EV9 Connection Recovery Started ==="

    # Check if already working
    if check_sensor; then
        log "Sensor is already available - no recovery needed"
        echo "SKIPPED: Sensor already available" > "$RESULT_FILE"
        exit 0
    fi

    # Find existing entry
    local entry_id
    entry_id=$(find_entry_id)

    if [ -n "$entry_id" ]; then
        log "Found existing kia_uvo entry: $entry_id"

        # Try reload first
        reload_integration "$entry_id"

        log "Waiting 5 minutes for reload to take effect..."
        sleep 300

        if check_sensor; then
            log "SUCCESS: Reload restored connection"
            echo "SUCCESS: Reload restored connection at $(date '+%H:%M')" > "$RESULT_FILE"
            exit 0
        fi

        log "Reload did not restore connection, proceeding to recreate"

        # Delete the broken entry
        delete_integration "$entry_id"
        sleep 10
    else
        log "No existing kia_uvo entry found"
    fi

    # Create new integration
    if create_integration; then
        log "Integration created, waiting 2 minutes for initialization..."
        sleep 120

        if check_sensor; then
            log "SUCCESS: Recreation restored connection"
            echo "SUCCESS: Recreation restored connection at $(date '+%H:%M')" > "$RESULT_FILE"
            exit 0
        else
            log "FAILED: Recreation completed but sensor still unavailable"
            echo "FAILED: Recreation completed but sensor still unavailable at $(date '+%H:%M')" > "$RESULT_FILE"
            exit 1
        fi
    else
        log "FAILED: Could not create integration"
        echo "FAILED: Could not create integration at $(date '+%H:%M')" > "$RESULT_FILE"
        exit 1
    fi
}

main
