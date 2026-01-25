# Kia EV9 Climate Schedule & Button Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix broken dashboard buttons, fix climate schedules not triggering, and make smart mode always-on with configurable rate.

**Architecture:** The root cause is that after OTP self-healing recovery, the device_id changes but the `input_text.ev9_device_id` helper is never updated. Dashboard buttons also use hardcoded device_ids. Smart mode should be always-on (no toggle) with a configurable "minutes per degree" rate.

**Tech Stack:** Home Assistant, YAML automations/scripts/helpers, shell scripts, Lovelace JSON dashboard

---

## Root Cause Analysis

### Finding 1: Integration Completely Broken
User reports ALL buttons fail with "unknown error":
- `script/ev9_start_climate_with_timer` - unknown error
- `script/ev9_stop_climate_cancel_timer` - unknown error
- `lock/lock` - unknown error

This confirms the kia_uvo integration is unavailable or the device_id helper has an invalid value.

### Finding 2: Device ID Not Updated After OTP Recovery
After v2.4 self-healing OTP automation recreates the kia_uvo integration:
- The integration gets a **NEW device_id**
- `input_text.ev9_device_id` helper still has the **OLD device_id**
- All automations/scripts calling kia_uvo services fail

**Evidence**: Neither `ev9_recovery_with_otp.sh` nor `ev9_submit_otp.sh` update the helper.

### Finding 3: Dashboard Buttons Use Hardcoded Device ID
In `lovelace.kia_ev9.v2.0.json`:
- Start Charge: `device_id: "7f6b71f10dc261408a02149c68aa3e23"` (hardcoded)
- Stop Charge: `device_id: "7f6b71f10dc261408a02149c68aa3e23"` (hardcoded)
- Refresh: `device_id: "7f6b71f10dc261408a02149c68aa3e23"` (hardcoded)
- Stop Climate: `device_id: "7f6b71f10dc261408a02149c68aa3e23"` (hardcoded)

### Finding 4: Smart Mode Should Be Always-On
User feedback:
- Smart mode should ALWAYS be enabled for schedules
- No per-schedule toggle needed
- Instead of toggle, make the rate configurable (e.g., "0.5 minutes per degree")

Current formula: `extra_time = temp_diff * 0.5` (max 20 min)
New approach: `extra_time = temp_diff * rate` where `rate` is configurable via helper

---

## Task 0: Diagnose Current Integration State (FIRST)

Before making code changes, verify the current state of the integration.

**Step 1: Check if kia_uvo integration exists**

SSH to HA and run:
```bash
curl -s http://localhost:8123/api/config/config_entries/entry \
  -H "Authorization: Bearer $HA_TOKEN" | \
  grep -o '"entry_id":"[^"]*","domain":"kia_uvo"'
```

**Step 2: Get the actual device_id from the integration**

```bash
curl -s http://localhost:8123/api/config/device_registry/devices \
  -H "Authorization: Bearer $HA_TOKEN" | \
  grep -B5 -A5 '"manufacturer":"Kia"'
```

**Step 3: Check current helper value**

```bash
curl -s http://localhost:8123/api/states/input_text.ev9_device_id \
  -H "Authorization: Bearer $HA_TOKEN"
```

**Step 4: Compare and fix if mismatch**

If the device_id from Step 2 differs from helper in Step 3, manually update:
```bash
curl -X POST http://localhost:8123/api/services/input_text/set_value \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"input_text.ev9_device_id","value":"NEW_DEVICE_ID_HERE"}'
```

**Step 5: Verify lock entity exists**

```bash
curl -s http://localhost:8123/api/states/lock.ev9_door_lock \
  -H "Authorization: Bearer $HA_TOKEN"
```

---

## Task 1: Update OTP Submit Script to Auto-Update Device ID

**Files:**
- Modify: `scripts/ev9_submit_otp.sh`

**Step 1: Read current script**

Review `scripts/ev9_submit_otp.sh:1-42`.

**Step 2: Add device_id extraction after successful OTP**

Replace lines 34-41 with:

```bash
if echo "$response" | grep -q '"type":"create_entry"'; then
    # Extract the new device_id from the response
    new_device_id=$(echo "$response" | grep -o '"device_id":"[^"]*"' | head -1 | cut -d'"' -f4)

    if [ -n "$new_device_id" ]; then
        log "New device_id: $new_device_id"

        # Update the helper via HA API
        update_response=$(curl -s -X POST \
            -H "Authorization: Bearer $HA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"entity_id\":\"input_text.ev9_device_id\",\"value\":\"${new_device_id}\"}" \
            "${HA_URL}/api/services/input_text/set_value")

        log "Updated input_text.ev9_device_id helper to: $new_device_id"
    else
        log "WARNING: Could not extract device_id from response, attempting to query device registry"

        # Fallback: Query device registry for Kia device
        sleep 5  # Wait for integration to initialize
        new_device_id=$(curl -s \
            -H "Authorization: Bearer $HA_TOKEN" \
            "${HA_URL}/api/config/device_registry/devices" | \
            grep -o '"id":"[^"]*"[^}]*"manufacturer":"Kia"' | \
            head -1 | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

        if [ -n "$new_device_id" ]; then
            log "Found device_id from registry: $new_device_id"
            curl -s -X POST \
                -H "Authorization: Bearer $HA_TOKEN" \
                -H "Content-Type: application/json" \
                -d "{\"entity_id\":\"input_text.ev9_device_id\",\"value\":\"${new_device_id}\"}" \
                "${HA_URL}/api/services/input_text/set_value" > /dev/null
        else
            log "ERROR: Could not find device_id - manual update required"
        fi
    fi

    log "Integration created successfully!"
    echo "SUCCESS"
    exit 0
else
    echo "ERROR: OTP submission failed: $response"
    exit 1
fi
```

**Step 3: Verify syntax**

```bash
bash -n scripts/ev9_submit_otp.sh
```

**Step 4: Commit**

```bash
git add scripts/ev9_submit_otp.sh
git commit -m "fix(ev9): auto-update device_id helper after OTP recovery"
```

---

## Task 2: Create Wrapper Scripts for Dashboard Buttons

**Files:**
- Create: `scripts.v2.5.yaml` (copy from `scripts.v2.1.yaml`)

**Step 1: Copy current scripts**

```bash
cp scripts.v2.1.yaml scripts.v2.5.yaml
```

**Step 2: Update version header**

```yaml
# Kia EV9 Scripts
# Version: 2.5
# Last Updated: 2026-01-22
#
# CHANGES from v2.1:
# - Added charging control wrapper scripts (ev9_start_charge, ev9_stop_charge, ev9_force_update)
#   These scripts use the centralized device_id helper, allowing dashboard buttons to work
#   even after integration recreation
```

**Step 3: Add wrapper scripts at end of file**

```yaml
# ============================================================
# CHARGING CONTROL WRAPPERS (v2.5)
# Dashboard buttons cannot use templates, so these scripts
# provide indirection via the ev9_device_id helper.
# ============================================================

ev9_start_charge:
  alias: "EV9: Start Charging"
  description: "Start EV charging using centralized device_id"
  icon: mdi:ev-station
  mode: single
  sequence:
    - service: kia_uvo.start_charge
      data:
        device_id: "{{ states('input_text.ev9_device_id') }}"
    - service: python_script.shift_event_log
      data:
        entity_prefix: input_text.ev9_event
        max_events: 10
        new_event: "{{ now().strftime('%H:%M') }} - CHARGE_START: Manual start"

ev9_stop_charge:
  alias: "EV9: Stop Charging"
  description: "Stop EV charging using centralized device_id"
  icon: mdi:ev-station
  mode: single
  sequence:
    - service: kia_uvo.stop_charge
      data:
        device_id: "{{ states('input_text.ev9_device_id') }}"
    - service: python_script.shift_event_log
      data:
        entity_prefix: input_text.ev9_event
        max_events: 10
        new_event: "{{ now().strftime('%H:%M') }} - CHARGE_STOP: Manual stop"

ev9_force_update:
  alias: "EV9: Force Data Refresh"
  description: "Force vehicle data update using centralized device_id"
  icon: mdi:refresh
  mode: single
  sequence:
    - service: kia_uvo.force_update
      data:
        device_id: "{{ states('input_text.ev9_device_id') }}"
    - service: python_script.shift_event_log
      data:
        entity_prefix: input_text.ev9_event
        max_events: 10
        new_event: "{{ now().strftime('%H:%M') }} - DATA_REFRESH: Manual refresh"
```

**Step 4: Commit**

```bash
git add scripts.v2.5.yaml
git commit -m "feat(ev9): add charging wrapper scripts for dashboard buttons"
```

---

## Task 3: Update Dashboard to Use Scripts

**Files:**
- Create: `lovelace.kia_ev9.v2.3.json` (copy from `lovelace.kia_ev9.v2.0.json`)

**Step 1: Copy dashboard**

```bash
cp lovelace.kia_ev9.v2.0.json lovelace.kia_ev9.v2.3.json
```

**Step 2: Update Start Charge button (around line 109-114)**

Change:
```json
"service": "kia_uvo.start_charge",
"data": {
  "device_id": "7f6b71f10dc261408a02149c68aa3e23"
}
```

To:
```json
"service": "script.ev9_start_charge"
```

**Step 3: Update Stop Charge button (around line 122-130)**

Change:
```json
"service": "kia_uvo.stop_charge",
"data": {
  "device_id": "7f6b71f10dc261408a02149c68aa3e23"
},
```

To:
```json
"service": "script.ev9_stop_charge",
```

**Step 4: Update Refresh button (around line 137-143)**

Change:
```json
"service": "kia_uvo.force_update",
"data": {
  "device_id": "7f6b71f10dc261408a02149c68aa3e23"
}
```

To:
```json
"service": "script.ev9_force_update"
```

**Step 5: Update Stop Climate button (around line 254-262)**

Change:
```json
"service": "kia_uvo.stop_climate",
"data": {
  "device_id": "7f6b71f10dc261408a02149c68aa3e23"
},
```

To:
```json
"service": "script.ev9_stop_climate_cancel_timer",
```

**Step 6: Commit**

```bash
git add lovelace.kia_ev9.v2.3.json
git commit -m "fix(ev9): dashboard buttons use scripts instead of hardcoded device_id"
```

---

## Task 4: Add Smart Mode Rate Helper (Always-On Smart Mode)

**Files:**
- Create: `helpers.v2.5.yaml` (copy from `helpers.v2.4.yaml`)

**Step 1: Copy helpers**

```bash
cp helpers.v2.4.yaml helpers.v2.5.yaml
```

**Step 2: Update version header**

```yaml
# Kia EV9 Helper Entities
# Version: 2.5
# Last Updated: 2026-01-22
#
# CHANGES from v2.4:
# - Added input_number.ev9_smart_mode_rate for configurable smart mode rate
# - Removed input_boolean.ev9_smart_precondition (smart mode is now always-on)
#
# Smart mode formula: extra_time = |target_temp - outside_temp| * rate
# Default rate: 0.5 (i.e., 10°F difference = 5 min extra lead time)
```

**Step 3: Add smart mode rate helper**

Add to `input_number` section:

```yaml
  # Smart Mode Rate (v2.5)
  # Minutes of extra lead time per degree of temperature difference
  # Example: rate=0.5, 20°F diff = 10 min extra lead time
  ev9_smart_mode_rate:
    name: "EV9 Smart Mode Rate"
    icon: mdi:thermometer-chevron-up
    min: 0.1
    max: 1.0
    step: 0.1
    unit_of_measurement: "min/°F"
    mode: slider
```

**Step 4: Remove global smart mode toggle (optional cleanup)**

Comment out or remove:
```yaml
  # DEPRECATED in v2.5 - smart mode is always on
  # ev9_smart_precondition:
  #   name: "EV9 Smart Pre-conditioning"
  #   icon: mdi:thermometer-auto
```

**Step 5: Commit**

```bash
git add helpers.v2.5.yaml
git commit -m "feat(ev9): add configurable smart mode rate, always-on smart mode"
```

---

## Task 5: Update Automation for Always-On Smart Mode

**Files:**
- Create: `automations.v2.5.yaml` (copy from `automations.v2.4.yaml`)

**Step 1: Copy automations**

```bash
cp automations.v2.4.yaml automations.v2.5.yaml
```

**Step 2: Update version header**

```yaml
# CHANGES from v2.4:
# - Smart mode is now always-on (removed toggle check)
# - Rate is configurable via input_number.ev9_smart_mode_rate (default 0.5 min/°F)
# - Formula: extra_time = temp_diff * rate (capped at 20 min)
```

**Step 3: Update condition template (lines 640-663)**

Change from:
```jinja
{% set smart_mode = is_state('input_boolean.ev9_smart_precondition', 'on') %}
...
{% if smart_mode %}
  {% set temp_diff = (sched_temp - current_temp) | abs %}
  {% set extra_time = [[(temp_diff * 0.5) | round(0) | int, 20] | min, 0] | max %}
  {% set lead_time = base_lead + extra_time %}
{% else %}
  {% set lead_time = base_lead %}
{% endif %}
```

To:
```jinja
{% set smart_rate = states('input_number.ev9_smart_mode_rate') | float(0.5) %}
...
{# Smart mode is always on #}
{% set temp_diff = (sched_temp - current_temp) | abs %}
{% set extra_time = [[(temp_diff * smart_rate) | round(0) | int, 20] | min, 0] | max %}
{% set lead_time = base_lead + extra_time %}
```

**Step 4: Update action variables (lines 685-718)**

Change:
```yaml
smart_mode: "{{ is_state('input_boolean.ev9_smart_precondition', 'on') }}"
```

To:
```yaml
smart_rate: "{{ states('input_number.ev9_smart_mode_rate') | float(0.5) }}"
```

And change:
```yaml
extra_time: "{{ [[((target_temp | float - current_temp | float) | abs * 0.5) | round(0) | int, 20] | min, 0] | max if smart_mode else 0 }}"
```

To:
```yaml
extra_time: "{{ [[((target_temp | float - current_temp | float) | abs * smart_rate) | round(0) | int, 20] | min, 0] | max }}"
```

**Step 5: Update notification message (lines 746-751)**

Change from checking `smart_mode` boolean to always showing smart mode info:
```yaml
message: >
  Schedule {{ matched_schedule }} triggered.
  Smart mode: Started {{ actual_lead }} min early (base: {{ base_lead }} + {{ extra_time }} min for {{ temp_diff | round(0) }}°F diff @ {{ smart_rate }} min/°F)
  Outside: {{ current_temp }}°F -> Target: {{ target_temp }}°F ({{ climate_mode }})
  Departure in {{ actual_lead }} minutes.
```

**Step 6: Commit**

```bash
git add automations.v2.5.yaml
git commit -m "feat(ev9): always-on smart mode with configurable rate"
```

---

## Task 6: Update Dashboard Config Tab

**Files:**
- Modify: `lovelace.kia_ev9.v2.3.json` (continue from Task 3)

**Step 1: Find pre-conditioning settings section**

Locate the Config tab's climate settings area.

**Step 2: Remove global smart mode toggle**

Remove or comment out any entity card for `input_boolean.ev9_smart_precondition`.

**Step 3: Add smart mode rate slider**

Add to the pre-conditioning settings:
```json
{
  "entity": "input_number.ev9_smart_mode_rate",
  "name": "Smart Mode Rate",
  "icon": "mdi:thermometer-chevron-up"
}
```

**Step 4: Add explanation markdown**

```json
{
  "type": "markdown",
  "content": "**Smart Mode (Always On)**: Lead time adjusts based on outside temperature. Rate = extra minutes per °F difference. Example: 0.5 rate + 20°F diff = 10 min extra."
}
```

**Step 5: Commit**

```bash
git add lovelace.kia_ev9.v2.3.json
git commit -m "feat(ev9): dashboard shows smart mode rate, removes toggle"
```

---

## Task 7: Manual Testing Checklist

**Test 0: Fix Current Integration (Do First!)**

1. SSH to HA: `ssh byrro@192.168.1.11`
2. Run diagnostic commands from Task 0
3. If device_id mismatch found, manually update helper
4. Verify buttons work before proceeding

**Test 1: Device ID Auto-Update**

1. Note current `input_text.ev9_device_id` value
2. Manually trigger OTP recovery (or wait for watchdog)
3. After recovery, check helper updated automatically
4. Expected: Helper has new device_id

**Test 2: Dashboard Buttons**

1. Go to https://home.byrroserver.com/kia-ev9/main
2. Test each button:
   - Refresh → no error
   - Start Climate → climate starts
   - Stop Climate → climate stops
   - Lock → vehicle locks
   - Unlock → vehicle unlocks
3. Expected: All work without "unknown error"

**Test 3: Climate Schedule**

1. Set Schedule 1 time to 5 minutes from now
2. Enable Schedule 1 and today's day
3. Set temperature to differ from outside temp by ~20°F
4. Wait for trigger
5. Expected: Climate starts `base_lead + extra_time` minutes before departure

**Test 4: Smart Mode Rate**

1. Set `ev9_smart_mode_rate` to 0.5
2. Trigger schedule with 20°F diff → should add 10 min
3. Change rate to 1.0
4. Trigger schedule with 20°F diff → should add 20 min (capped)
5. Expected: Rate parameter correctly affects lead time

---

## Deployment Steps

1. **Run Task 0 first** - Fix current integration state manually

2. **Deploy shell script** (Task 1):
   ```bash
   scp scripts/ev9_submit_otp.sh byrro@192.168.1.11:/mnt/ByrroServer/docker-data/homeassistant/config/scripts/
   ```

3. **Deploy helpers** (Task 4):
   - Create `input_number.ev9_smart_mode_rate` via HA UI or YAML
   - Optionally remove `input_boolean.ev9_smart_precondition`

4. **Deploy scripts** (Task 2):
   - Merge scripts.v2.5.yaml into HA scripts.yaml
   - Reload: Developer Tools → YAML → Scripts

5. **Deploy automations** (Task 5):
   - Merge automations.v2.5.yaml into HA automations.yaml
   - Reload: Developer Tools → YAML → Automations

6. **Deploy dashboard** (Tasks 3, 6):
   - Import lovelace.kia_ev9.v2.3.json via HA UI

7. **Run test checklist** (Task 7)

---

## Version Summary

| Component | Before | After |
|-----------|--------|-------|
| helpers | v2.4 | v2.5 |
| automations | v2.4 | v2.5 |
| scripts | v2.1 | v2.5 |
| dashboard | v2.0 | v2.3 |
| shell scripts | v2.4 | v2.5 |

---

## Key Files to Modify

| File | Changes |
|------|---------|
| `scripts/ev9_submit_otp.sh` | Add device_id extraction and helper update |
| `scripts.v2.5.yaml` | Add 3 wrapper scripts |
| `lovelace.kia_ev9.v2.3.json` | Change 4 buttons to use scripts, add rate slider |
| `helpers.v2.5.yaml` | Add `ev9_smart_mode_rate`, deprecate toggle |
| `automations.v2.5.yaml` | Remove smart mode check, use configurable rate |
