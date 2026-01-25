#!/bin/bash
# EV9 Connection Recovery with OTP Script
# Version: 2.4
#
# This script handles the multi-step config flow for Kia UVO integration:
# 1. Deletes existing kia_uvo entry if present
# 2. Starts new config flow
# 3. Submits region (USA) and brand (Kia)
# 4. Submits credentials
# 5. Requests OTP via EMAIL
# 6. Returns flow_id for OTP submission by automation
#
# Usage: ev9_recovery_with_otp.sh <ha_token> <secrets_file>
# Output: flow_id on success, "ERROR: message" on failure

set -e

HA_URL="http://localhost:8123"
SECRETS_FILE="${2:-/config/secrets.yaml}"

# Get HA token - from argument, or fall back to secrets.yaml
HA_TOKEN="$1"
if [ -z "$HA_TOKEN" ] || [[ "$HA_TOKEN" == *"{{"* ]]; then
    # Token not provided or is a literal template variable, read from secrets
    HA_TOKEN=$(grep "^ha_long_lived_token:" "$SECRETS_FILE" | sed 's/^[^:]*: *//' | tr -d '"' | tr -d "'")
    if [ -z "$HA_TOKEN" ]; then
        echo "ERROR: No HA token provided and ha_long_lived_token not found in secrets.yaml"
        exit 1
    fi
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
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

# Find kia_uvo config entry ID
find_entry_id() {
    api_request "GET" "/api/config/config_entries/entry" | \
        grep -o '"entry_id":"[^"]*","domain":"kia_uvo"' | \
        head -1 | \
        sed 's/"entry_id":"\([^"]*\)".*/\1/'
}

# Delete integration
delete_integration() {
    local entry_id="$1"
    log "Deleting integration (entry_id: $entry_id)"
    api_request "DELETE" "/api/config/config_entries/entry/${entry_id}"
}

# Main flow
main() {
    log "=== EV9 Recovery with OTP Started ==="

    # Get credentials
    local username password pin
    username=$(get_secret "kia_username")
    password=$(get_secret "kia_password")
    pin=$(get_secret "kia_pin")

    if [ -z "$username" ] || [ -z "$password" ] || [ -z "$pin" ]; then
        echo "ERROR: Could not read credentials from secrets file"
        exit 1
    fi

    # Find and delete existing entry
    local entry_id
    entry_id=$(find_entry_id)

    if [ -n "$entry_id" ]; then
        log "Found existing kia_uvo entry: $entry_id"
        delete_integration "$entry_id"
        sleep 5
    else
        log "No existing kia_uvo entry found"
    fi

    # Step 1: Start config flow
    log "Starting config flow..."
    local flow_response
    flow_response=$(api_request "POST" "/api/config/config_entries/flow" \
        '{"handler":"kia_uvo","show_advanced_options":false}')

    local flow_id
    flow_id=$(echo "$flow_response" | grep -o '"flow_id":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$flow_id" ]; then
        echo "ERROR: Could not start config flow"
        exit 1
    fi

    log "Config flow started (flow_id: $flow_id)"

    # Step 2: Submit region (3=USA) and brand (1=Kia)
    log "Submitting region and brand..."
    local step2_response
    step2_response=$(api_request "POST" "/api/config/config_entries/flow/${flow_id}" \
        '{"region":3,"brand":1}')

    if ! echo "$step2_response" | grep -q '"step_id":"credentials_password"'; then
        echo "ERROR: Region/brand step failed: $step2_response"
        exit 1
    fi

    # Step 3: Submit credentials
    log "Submitting credentials..."
    local step3_response
    step3_response=$(api_request "POST" "/api/config/config_entries/flow/${flow_id}" \
        "{\"username\":\"${username}\",\"password\":\"${password}\",\"pin\":\"${pin}\"}")

    if ! echo "$step3_response" | grep -q '"step_id":"select_otp_method"'; then
        echo "ERROR: Credentials step failed: $step3_response"
        exit 1
    fi

    # Step 4: Request OTP via EMAIL
    log "Requesting OTP via EMAIL..."
    local step4_response
    step4_response=$(api_request "POST" "/api/config/config_entries/flow/${flow_id}" \
        '{"method":"EMAIL"}')

    if ! echo "$step4_response" | grep -q '"step_id":"enter_otp"'; then
        echo "ERROR: OTP request failed: $step4_response"
        exit 1
    fi

    log "OTP requested successfully. Waiting for email..."

    # Return flow_id for automation to use when OTP arrives
    echo "$flow_id"
}

main
