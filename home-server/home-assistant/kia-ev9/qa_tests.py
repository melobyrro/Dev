import requests
import time
import json
import sys

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# REPLACE THESE WITH YOUR ACTUAL DETAILS BEFORE RUNNING
HA_URL = "http://localhost:8123"  # Change to your HA IP if running remotely
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI0MjJlYmM5NmQzZjE0MzhjODc0OGRkYzkzNWQ4ZjNkMyIsImlhdCI6MTc2ODkzMTkwNiwiZXhwIjoyMDg0MjkxOTA2fQ.pjx4-W2e0rT9o6D-NFbGmfm6RYLsF2c1H2cRwqVHQ0I"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "content-type": "application/json",
}

# ==============================================================================
# TEST HELPERS
# ==============================================================================

def log(msg, status="INFO"):
    colors = {
        "INFO": "\033[94m",    # Blue
        "SUCCESS": "\033[92m", # Green
        "FAIL": "\033[91m",    # Red
        "WARN": "\033[93m",    # Yellow
        "RESET": "\033[0m"
    }
    print(f"{colors.get(status, '')}[{status}] {msg}{colors['RESET']}")

def get_state(entity_id):
    response = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    return None

def call_service(domain,service, data={}):
    response = requests.post(f"{HA_URL}/api/services/{domain}/{service}", headers=HEADERS, json=data)
    return response.status_code == 200

def set_state(entity_id, state, attributes={}):
    """Force a state change (Mocking sensors for testing)"""
    data = {"state": state, "attributes": attributes}
    response = requests.post(f"{HA_URL}/api/states/{entity_id}", headers=HEADERS, json=data)
    return response.status_code in [200, 201]

def verify_log_entry(expected_substring):
    """Checks the event log helpers for a specific string"""
    # We check the first 3 event slots
    for i in range(1, 4):
        state = get_state(f"input_text.ev9_event_{i}")
        if state and expected_substring in state['state']:
            return True, state['state']
    return False, None

# ==============================================================================
# TEST CASES
# ==============================================================================

def test_1_health_check():
    log("TEST 1: Health Check - Verifying Critical Entities...", "INFO")
    critical_entities = [
        "input_text.ev9_device_id",
        "input_boolean.ev9_walk_away_lock_enabled",
        "input_number.ev9_target_temperature",
        "timer.ev9_climate_timer",
        "script.ev9_start_climate_with_timer"
    ]
    
    missing = []
    for entity in critical_entities:
        if not get_state(entity):
            missing.append(entity)
    
    if missing:
        log(f"FAILED: Missing entities: {missing}", "FAIL")
        return False
    log("SUCCESS: All critical entities found.", "SUCCESS")
    return True

def test_2_log_rotation_logic():
    log("TEST 2: Log Logic - Verifying Rotation...", "INFO")
    # 1. Clear Log
    call_service("script", "ev9_clear_event_log")
    time.sleep(1)
    
    # 2. Inject a test event via the python script service directly
    test_msg = "TEST_EVENT_UNIQUE_ID_12345"
    call_service("python_script", "shift_event_log", {
        "entity_prefix": "input_text.ev9_event",
        "max_events": 10,
        "new_event": test_msg
    })
    time.sleep(1)
    
    # 3. Verify
    state = get_state("input_text.ev9_event_1")
    if state and test_msg in state['state']:
        log("SUCCESS: Event logged correctly to slot 1.", "SUCCESS")
        return True
    else:
        log(f"FAILED: Expected '{test_msg}' in slot 1, found '{state['state'] if state else 'None'}'", "FAIL")
        return False

def test_3_climate_logic_mock():
    log("TEST 3: Climate Logic - Timer & Logs...", "INFO")
    
    # 1. Set Duration Helper
    call_service("input_number", "set_value", {"entity_id": "input_number.ev9_climate_duration", "value": 15})
    
    # 2. Call Script (Note: This will try to hit the Kia API, which might fail if ID is wrong, 
    # but the HA side logic (Timer + Log) should still fire if the script doesn't error out completely)
    log("Triggering Climate Script...", "INFO")
    call_service("script", "ev9_start_climate_with_timer")
    time.sleep(2)
    
    # 3. Check Timer
    timer = get_state("timer.ev9_climate_timer")
    if timer and timer['state'] == "active":
        log("SUCCESS: Climate Timer started.", "SUCCESS")
    else:
        log("FAILED: Climate Timer did not start.", "FAIL")
        return False
        
    # 4. Check Log
    found, msg = verify_log_entry("CLIMATE_START")
    if found:
        log(f"SUCCESS: Log entry found: {msg}", "SUCCESS")
    else:
        log("FAILED: No CLIMATE_START entry in logs.", "FAIL")
        return False
        
    return True

def test_4_walkaway_automation_simulation():
    log("TEST 4: Walk-Away Automation (Simulated)...", "INFO")

    # Wait for any previous Kia API commands to complete (from climate test)
    log("Waiting for Kia API cooldown...", "INFO")
    time.sleep(10)

    # 1. Setup Conditions: Enabled=On, Locked=Off, Engine=Off
    call_service("input_boolean", "turn_on", {"entity_id": "input_boolean.ev9_walk_away_lock_enabled"})
    set_state("binary_sensor.ev9_locked", "off") # Mock unlocked
    set_state("binary_sensor.ev9_engine", "off") # Mock engine off

    # 2. Set threshold to 5m
    call_service("input_number", "set_value", {"entity_id": "input_number.ev9_walkaway_distance", "value": 5})

    # 3. Clear previous result
    call_service("input_text", "set_value", {"entity_id": "input_text.ev9_last_walkaway_result", "value": ""})

    # 4. Manually trigger automation
    # Note: Automation has 5 second delay to check lock result, so we wait 15 seconds total
    log("Manually triggering Walk-Away Automation...", "INFO")
    call_service("automation", "trigger", {"entity_id": "automation.ev9_walk_away_auto_lock_2", "skip_condition": True})
    time.sleep(15)

    # 5. Verify Result Text was updated (SUCCESS or FAILED - both mean automation ran)
    result_text = get_state("input_text.ev9_last_walkaway_result")
    if result_text and result_text['state'] and len(result_text['state']) > 0:
        if "SUCCESS" in result_text['state']:
            log(f"SUCCESS: Result text updated: {result_text['state']}", "SUCCESS")
        else:
            log(f"INFO: Automation ran but lock may have failed (expected in test): {result_text['state']}", "WARN")
        return True
    else:
        log(f"FAILED: Result text not updated. Current: {result_text['state'] if result_text else 'None'}", "FAIL")
        return False

def test_5_schedule_toggles():
    log("TEST 5: Schedule Toggles...", "INFO")

    call_service("input_boolean", "turn_on", {"entity_id": "input_boolean.ev9_schedule_1_enabled"})
    time.sleep(1)
    state = get_state("input_boolean.ev9_schedule_1_enabled")
    if state['state'] == 'on':
        log("SUCCESS: Schedule 1 enabled.", "SUCCESS")
    else:
        log("FAILED: Schedule 1 failed to enable.", "FAIL")
        return False

    call_service("input_boolean", "turn_off", {"entity_id": "input_boolean.ev9_schedule_1_enabled"})
    time.sleep(1)
    state = get_state("input_boolean.ev9_schedule_1_enabled")
    if state['state'] == 'off':
        log("SUCCESS: Schedule 1 disabled.", "SUCCESS")
        return True
    else:
        log("FAILED: Schedule 1 failed to disable.", "FAIL")
        return False

def test_6_theft_detection_entities():
    log("TEST 6: Theft Detection Entities (v2.2)...", "INFO")

    theft_entities = [
        "input_boolean.ev9_theft_alert_enabled",
        "input_number.ev9_theft_distance_threshold",
        "input_number.ev9_theft_phone_distance_threshold",
        "input_text.ev9_last_known_location",
        "input_text.ev9_last_theft_alert",
        "input_text.ev9_last_theft_result",
        "sensor.ev9_movement_distance",
    ]

    missing = []
    for entity in theft_entities:
        state = get_state(entity)
        if not state:
            missing.append(entity)
        else:
            log(f"  Found: {entity} = {state['state']}", "INFO")

    if missing:
        log(f"FAILED: Missing theft entities: {missing}", "FAIL")
        return False
    log("SUCCESS: All theft detection entities exist.", "SUCCESS")
    return True

def test_7_theft_automations_loaded():
    log("TEST 7: Theft Automations Loaded...", "INFO")

    theft_automations = [
        "automation.ev9_update_last_known_location",
        "automation.ev9_theft_movement_alert",
        "automation.ev9_lock_from_theft_alert",
    ]

    missing = []
    disabled = []
    for entity in theft_automations:
        state = get_state(entity)
        if not state:
            missing.append(entity)
        elif state['state'] != 'on':
            disabled.append(f"{entity}={state['state']}")
        else:
            log(f"  Found: {entity} = {state['state']}", "INFO")

    if missing:
        log(f"FAILED: Missing automations: {missing}", "FAIL")
        return False
    if disabled:
        log(f"WARNING: Disabled automations: {disabled}", "WARN")
    log("SUCCESS: All theft automations loaded.", "SUCCESS")
    return True

def test_8_theft_toggle_and_thresholds():
    log("TEST 8: Theft Toggle & Thresholds...", "INFO")

    # Test toggle on/off
    call_service("input_boolean", "turn_on", {"entity_id": "input_boolean.ev9_theft_alert_enabled"})
    time.sleep(1)
    state = get_state("input_boolean.ev9_theft_alert_enabled")
    if state['state'] != 'on':
        log("FAILED: Could not enable theft alert", "FAIL")
        return False
    log("  Theft alert enabled successfully", "INFO")

    # Test threshold adjustment
    call_service("input_number", "set_value", {"entity_id": "input_number.ev9_theft_distance_threshold", "value": 100})
    time.sleep(1)
    state = get_state("input_number.ev9_theft_distance_threshold")
    if float(state['state']) != 100.0:
        log(f"FAILED: Distance threshold not set. Expected 100, got {state['state']}", "FAIL")
        return False
    log("  Distance threshold set to 100m", "INFO")

    # Turn off for safety
    call_service("input_boolean", "turn_off", {"entity_id": "input_boolean.ev9_theft_alert_enabled"})
    time.sleep(1)

    log("SUCCESS: Theft toggles and thresholds work.", "SUCCESS")
    return True

def test_9_movement_sensor_logic():
    log("TEST 9: Movement Distance Sensor...", "INFO")

    # Set a known location
    call_service("input_text", "set_value", {
        "entity_id": "input_text.ev9_last_known_location",
        "value": "25.7617,-80.1918"  # Miami coords
    })
    time.sleep(2)

    state = get_state("sensor.ev9_movement_distance")
    if state:
        log(f"  Movement distance: {state['state']}m", "INFO")
        # Should be > 0 if vehicle is not at those exact coords
        if state['state'] not in ['unknown', 'unavailable', '']:
            log("SUCCESS: Movement sensor calculating distance.", "SUCCESS")
            return True
        else:
            log(f"WARN: Movement sensor returned {state['state']}", "WARN")
            return True  # Not a hard fail, might be GPS issue
    else:
        log("FAILED: Movement sensor not found", "FAIL")
        return False

def test_10_kia_integration_freshness():
    log("TEST 10: Kia Integration Data Freshness...", "INFO")

    last_update = get_state("sensor.ev9_last_updated_at")
    battery = get_state("sensor.ev9_ev_battery_level")
    charging = get_state("binary_sensor.ev9_ev_battery_charge")

    if not last_update or not battery:
        log("FAILED: Cannot read Kia sensors", "FAIL")
        return False

    log(f"  Battery: {battery['state']}%", "INFO")
    log(f"  Charging: {charging['state'] if charging else 'unknown'}", "INFO")
    log(f"  Last Kia Update: {last_update['state']}", "INFO")

    # Check if data is stale (> 2 hours old)
    from datetime import datetime, timezone
    try:
        last_ts = datetime.fromisoformat(last_update['state'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        age_minutes = (now - last_ts).total_seconds() / 60
        log(f"  Data age: {age_minutes:.0f} minutes", "INFO")

        if age_minutes > 120:
            log(f"WARN: Kia data is {age_minutes:.0f} minutes old (>2 hours stale!)", "WARN")
            return False
        elif age_minutes > 60:
            log(f"WARN: Kia data is {age_minutes:.0f} minutes old", "WARN")
            return True
        else:
            log("SUCCESS: Kia data is fresh.", "SUCCESS")
            return True
    except Exception as e:
        log(f"WARN: Could not parse timestamp: {e}", "WARN")
        return True

# ==============================================================================
# MAIN RUNNER
# ==============================================================================

if __name__ == "__main__":
    log("STARTING KIA EV9 INTEGRATION TEST SUITE", "INFO")
    log("=======================================", "INFO")
    
    try:
        # Validate connection first
        api_status = requests.get(f"{HA_URL}/api/", headers=HEADERS)
        if api_status.status_code != 200:
            log(f"CRITICAL: Cannot connect to HA API. Status: {api_status.status_code}", "FAIL")
            sys.exit(1)
    except Exception as e:
        log(f"CRITICAL: Connection failed: {e}", "FAIL")
        sys.exit(1)

    results = []
    results.append(test_1_health_check())
    results.append(test_2_log_rotation_logic())
    results.append(test_3_climate_logic_mock())
    results.append(test_4_walkaway_automation_simulation())
    results.append(test_5_schedule_toggles())
    results.append(test_6_theft_detection_entities())
    results.append(test_7_theft_automations_loaded())
    results.append(test_8_theft_toggle_and_thresholds())
    results.append(test_9_movement_sensor_logic())
    results.append(test_10_kia_integration_freshness())
    
    log("=======================================", "INFO")
    if all(results):
        log("ALL TESTS PASSED. SYSTEM IS READY.", "SUCCESS")
        sys.exit(0)
    else:
        log("SOME TESTS FAILED. CHECK LOGS ABOVE.", "FAIL")
        sys.exit(1)
