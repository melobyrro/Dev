#!/bin/bash
# EV9 Submit OTP Script
# Version: 2.5
#
# Submits OTP code to complete the Kia UVO config flow
# After successful creation, extracts new device_id and updates the helper
#
# Usage: ev9_submit_otp.sh <secrets_file>
# Reads flow_id from input_text.ev9_recovery_flow_id
# Reads OTP code from input_text.ev9_otp_code
# Output: "SUCCESS" or "ERROR: message"
#
# CHANGES from v2.4:
# - Auto-updates input_text.ev9_device_id after successful integration creation
# - Queries device registry as fallback if device_id not in response

HA_URL="http://localhost:8123"
SECRETS_FILE="${1:-/config/secrets.yaml}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Get HA token from secrets file
get_ha_token() {
    grep "^ha_long_lived_token:" "$SECRETS_FILE" | cut -d" " -f2 | tr -d '"' | tr -d "'"
}

# Get helper state via HA API
get_helper_state() {
    local entity_id="$1"
    curl -s "http://localhost:8123/api/states/${entity_id}" \
        -H "Authorization: Bearer $HA_TOKEN" | \
        grep -o '"state":"[^"]*"' | cut -d'"' -f4
}

HA_TOKEN=$(get_ha_token)

if [ -z "$HA_TOKEN" ]; then
    echo "ERROR: Could not read HA token from secrets file"
    exit 1
fi

# Read flow_id and OTP from helpers
FLOW_ID=$(get_helper_state "input_text.ev9_recovery_flow_id")
OTP_CODE=$(get_helper_state "input_text.ev9_otp_code")

if [ -z "$FLOW_ID" ] || [ -z "$OTP_CODE" ]; then
    echo "ERROR: Missing flow_id or OTP code from helpers"
    exit 1
fi

log "Submitting OTP code to flow: $FLOW_ID"

response=$(curl -s -X POST \
    -H "Authorization: Bearer $HA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"otp\":\"${OTP_CODE}\"}" \
    "${HA_URL}/api/config/config_entries/flow/${FLOW_ID}")

log "Response: $response"

if echo "$response" | grep -q '"type":"create_entry"'; then
    log "Integration created successfully!"

    # Extract the new device_id from the response
    # The response contains "result" with device info
    new_device_id=$(echo "$response" | grep -o '"device_id":"[^"]*"' | head -1 | cut -d'"' -f4)

    if [ -n "$new_device_id" ]; then
        log "New device_id from response: $new_device_id"
    else
        log "WARNING: Could not extract device_id from response, querying device registry..."

        # Wait for integration to initialize
        sleep 5

        # Query device registry for Kia device using template API
        new_device_id=$(curl -s -X POST \
            -H "Authorization: Bearer $HA_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"template": "{{ device_id(\"sensor.ev9_ev_battery_level\") }}"}' \
            "${HA_URL}/api/template")

        if [ -n "$new_device_id" ] && [ "$new_device_id" != "None" ]; then
            log "Found device_id from template: $new_device_id"
        else
            log "ERROR: Could not find device_id - manual update required"
            echo "SUCCESS"
            exit 0
        fi
    fi

    # Update the device_id helper
    log "Updating input_text.ev9_device_id to: $new_device_id"
    update_response=$(curl -s -X POST \
        -H "Authorization: Bearer $HA_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"entity_id\":\"input_text.ev9_device_id\",\"value\":\"${new_device_id}\"}" \
        "${HA_URL}/api/services/input_text/set_value")

    log "Helper update response: $update_response"

    echo "SUCCESS"
    exit 0
else
    echo "ERROR: OTP submission failed: $response"
    exit 1
fi
