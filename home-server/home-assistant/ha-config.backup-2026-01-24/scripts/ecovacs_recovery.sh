#!/bin/bash
# Ecovacs Integration Recovery Script
# Creates a new ecovacs config entry using the HA API
# Location: /config/scripts/ecovacs_recovery.sh

set -e

# Configuration - loaded from secrets
HA_URL="http://localhost:8123"
HA_TOKEN=$(cat /config/secrets.yaml | grep "ha_long_lived_token:" | cut -d' ' -f2)
ECOVACS_USER=$(cat /config/secrets.yaml | grep "ecovacs_username:" | cut -d'"' -f2)
ECOVACS_PASS=$(cat /config/secrets.yaml | grep "ecovacs_password:" | cut -d'"' -f2)
ECOVACS_COUNTRY=$(cat /config/secrets.yaml | grep "ecovacs_country:" | cut -d'"' -f2)

# Log file
LOG_FILE="/config/logs/ecovacs_recovery.log"
mkdir -p /config/logs

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
    echo "$1"
}

log "Starting ecovacs recovery..."

# Step 1: Start the config flow
log "Starting config flow..."
FLOW_RESPONSE=$(curl -s -X POST \
    "${HA_URL}/api/config/config_entries/flow" \
    -H "Authorization: Bearer ${HA_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"handler":"ecovacs"}')

FLOW_ID=$(echo "$FLOW_RESPONSE" | jq -r '.flow_id // empty')

if [ -z "$FLOW_ID" ]; then
    log "ERROR: Failed to start config flow"
    log "Response: $FLOW_RESPONSE"
    exit 1
fi

log "Config flow started: $FLOW_ID"

# Step 2: Submit credentials
log "Submitting credentials..."
SUBMIT_RESPONSE=$(curl -s -X POST \
    "${HA_URL}/api/config/config_entries/flow/${FLOW_ID}" \
    -H "Authorization: Bearer ${HA_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${ECOVACS_USER}\",\"password\":\"${ECOVACS_PASS}\",\"country\":\"${ECOVACS_COUNTRY}\"}")

RESULT=$(echo "$SUBMIT_RESPONSE" | jq -r '.type // empty')
ENTRY_ID=$(echo "$SUBMIT_RESPONSE" | jq -r '.result.entry_id // empty')

if [ "$RESULT" = "create_entry" ] && [ -n "$ENTRY_ID" ]; then
    log "SUCCESS: Integration created with entry_id: $ENTRY_ID"
    # Update the stored entry ID
    curl -s -X POST \
        "${HA_URL}/api/services/input_text/set_value" \
        -H "Authorization: Bearer ${HA_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"entity_id\":\"input_text.ecovacs_entry_id\",\"value\":\"${ENTRY_ID}\"}"
    exit 0
elif [ "$RESULT" = "abort" ]; then
    REASON=$(echo "$SUBMIT_RESPONSE" | jq -r '.reason // "unknown"')
    log "ABORTED: $REASON"
    if [ "$REASON" = "already_configured" ]; then
        log "Integration already exists - this is OK"
        exit 0
    fi
    exit 1
else
    log "ERROR: Unexpected response"
    log "Response: $SUBMIT_RESPONSE"
    exit 1
fi
