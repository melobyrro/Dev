#!/usr/bin/env python3
"""
Home Assistant Automation Monitor
Queries HA automations from database and adds them to the schedule summary JSON
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Configuration
SCHEDULE_SUMMARY_PATH = "/home/byrro/docker/monitoring/trivy/reports/schedule-summary.json"
LOCAL_TZ_NAME = os.environ.get("WATCHTOWER_LOCAL_TZ", "America/New_York")
HA_CONFIG_PATH = "/mnt/ByrroServer/docker-data/homeassistant/config"

# HA Automation metadata - maps automation ID to details
HA_AUTOMATION_KNOWLEDGE = {
    "patio_ac_manual_override_detector": {
        "purpose": "Patio AC: Manual Override Detection",
        "detail": "Detects when user manually controls the AC and disables automations for 2 hours.",
        "category": "homeassistant",
        "group": "Manual Override",
        "triggers": "State change on climate entity (non-automation context)",
        "actions": "Enable override flag, start 2h timer, cancel running timers",
    },
    "patio_ac_humidity_guard": {
        "purpose": "Patio AC: Humidity Guard",
        "detail": "Dehumidifies when humidity exceeds 65% during normal hours (8am-10pm).",
        "category": "homeassistant",
        "group": "Primary Control",
        "triggers": "Humidity > 65% for 10 minutes",
        "actions": "Set AC to DRY mode for max 45 minutes",
    },
    "patio_ac_heat_spike_guard": {
        "purpose": "Patio AC: Heat Spike Guard",
        "detail": "Cools when temperature exceeds 90°F AND humidity > 60%.",
        "category": "homeassistant",
        "group": "Primary Control",
        "triggers": "Temp > 90°F for 10 min AND humidity > 60%",
        "actions": "Set AC to COOL at 85°F for max 60 minutes",
    },
    "patio_ac_quiet_hours_dehumidify": {
        "purpose": "Patio AC: Quiet Hours Dehumidify",
        "detail": "Dehumidifies only (no cooling) during quiet hours (10pm-8am).",
        "category": "homeassistant",
        "group": "Primary Control",
        "triggers": "Humidity > 70% for 15 min (10pm-8am only)",
        "actions": "Set AC to DRY mode for max 30 minutes (no cooling)",
    },
    "patio_ac_humidity_guard_early_stop": {
        "purpose": "Patio AC: Humidity Early Stop",
        "detail": "Stops dehumidify early when humidity goal is met to save energy.",
        "category": "homeassistant",
        "group": "Early Stop",
        "triggers": "Humidity < 60% for 2 min (while humidity guard active)",
        "actions": "Turn off AC, cancel timer",
    },
    "patio_ac_heat_spike_early_stop": {
        "purpose": "Patio AC: Heat Spike Early Stop",
        "detail": "Stops cooling early when temperature goal is met to save energy.",
        "category": "homeassistant",
        "group": "Early Stop",
        "triggers": "Temp < 85°F for 2 min (while heat spike active)",
        "actions": "Turn off AC, cancel timer",
    },
    "patio_ac_quiet_hours_early_stop": {
        "purpose": "Patio AC: Quiet Hours Early Stop",
        "detail": "Stops quiet hours dehumidify early when humidity goal is met.",
        "category": "homeassistant",
        "group": "Early Stop",
        "triggers": "Humidity < 65% for 2 min (while quiet hours active)",
        "actions": "Turn off AC, cancel timer",
    },
    "patio_ac_timer_expiration_handler": {
        "purpose": "Patio AC: Timer Expiration Handler",
        "detail": "Ensures AC turns off when time-box expires (prevents over-running).",
        "category": "homeassistant",
        "group": "Safety & Cleanup",
        "triggers": "Any timer finishes (humidity/heat spike/quiet hours)",
        "actions": "Turn off AC if still running",
    },
    "patio_ac_safety_monitor": {
        "purpose": "Patio AC: Safety Monitor (CRITICAL)",
        "detail": "Emergency shutdown if AC enters heat or auto mode. Checks every 5 minutes.",
        "category": "homeassistant",
        "group": "Safety & Cleanup",
        "triggers": "AC state = heat/auto OR every 5 minutes",
        "actions": "Emergency shutdown, enable override, block all automations",
    },
    "patio_ac_manual_override_reset": {
        "purpose": "Patio AC: Manual Override Reset",
        "detail": "Re-enables automations after 2-hour manual override holdoff expires.",
        "category": "homeassistant",
        "group": "Safety & Cleanup",
        "triggers": "2-hour holdoff timer finishes",
        "actions": "Disable override flag, re-enable automations",
    },
}


def format_local(dt):
    """Format datetime in local timezone."""
    try:
        local_tz = ZoneInfo(LOCAL_TZ_NAME)
        local_dt = dt.astimezone(local_tz)
        return local_dt.strftime("%Y-%m-%d %H:%M %Z")
    except:
        return str(dt)


def query_ha_automations():
    """Query Home Assistant automations from entity registry."""
    try:
        entity_registry_path = f"{HA_CONFIG_PATH}/.storage/core.entity_registry"

        with open(entity_registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        # Filter for patio_ac automations
        automations = [
            entity for entity in registry.get("data", {}).get("entities", [])
            if entity.get("entity_id", "").startswith("automation.patio_ac")
        ]

        return automations

    except FileNotFoundError:
        print(f"Error: Entity registry not found", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error reading entity registry: {e}", file=sys.stderr)
        return []


def get_automation_states():
    """Get current states of automations from database."""
    try:
        # Query the database for automation states
        query = """
        SELECT sm.entity_id, s.state, sa.shared_attrs
        FROM states s
        JOIN states_meta sm ON s.metadata_id = sm.metadata_id
        JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
        WHERE sm.entity_id LIKE 'automation.patio_ac%'
        AND s.state_id IN (
            SELECT MAX(state_id)
            FROM states s2
            WHERE s2.metadata_id = s.metadata_id
        )
        """

        result = subprocess.run(
            ["sudo", "sqlite3", f"{HA_CONFIG_PATH}/home-assistant_v2.db", query],
            capture_output=True,
            text=True,
            timeout=10
        )

        states = {}
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    entity_id, state, attrs_json = line.split("|", 2)
                    try:
                        attrs = json.loads(attrs_json)
                    except:
                        attrs = {}
                    states[entity_id] = {
                        "state": state,
                        "attributes": attrs
                    }

        return states

    except Exception as e:
        print(f"Error querying database: {e}", file=sys.stderr)
        return {}


def parse_automation_data(automations, states):
    """Parse automation data into schedule format."""
    parsed = []

    for auto in automations:
        entity_id = auto.get("entity_id", "")
        automation_id = entity_id.replace("automation.", "")

        # Get metadata from knowledge base
        knowledge = HA_AUTOMATION_KNOWLEDGE.get(automation_id, {})

        # Get current state
        state_info = states.get(entity_id, {})
        state = state_info.get("state", "unknown")
        attributes = state_info.get("attributes", {})

        # Parse last triggered time
        last_triggered = attributes.get("last_triggered")
        last_run_formatted = ""
        if last_triggered:
            try:
                # Parse ISO format timestamp
                dt = datetime.fromisoformat(last_triggered.replace("Z", "+00:00"))
                last_run_formatted = format_local(dt)
            except:
                last_run_formatted = str(last_triggered) if last_triggered else ""

        # Determine if automation is enabled
        enabled = state == "on"
        flags = []
        if not enabled:
            flags.append("disabled")
        if knowledge.get("group") == "Safety & Cleanup":
            flags.append("critical")

        # Get friendly name from attributes or auto data
        friendly_name = attributes.get("friendly_name") or auto.get("name") or automation_id

        parsed_entry = {
            "entity_id": entity_id,
            "name": friendly_name,
            "state": state,
            "enabled": enabled,
            "purpose": knowledge.get("purpose", automation_id.replace("_", " ").title()),
            "detail": knowledge.get("detail", "Home Assistant automation."),
            "category": knowledge.get("category", "homeassistant"),
            "group": knowledge.get("group", "Unknown"),
            "triggers": knowledge.get("triggers", "See automation configuration"),
            "actions": knowledge.get("actions", "See automation configuration"),
            "last_triggered": last_triggered or None,
            "last_run": last_run_formatted or None,
            "flags": flags,
        }

        parsed.append(parsed_entry)

    # Sort by group, then by entity_id
    group_order = ["Manual Override", "Primary Control", "Early Stop", "Safety & Cleanup", "Unknown"]
    parsed.sort(key=lambda x: (group_order.index(x.get("group", "Unknown")), x.get("entity_id", "")))

    return parsed


def update_schedule_summary(ha_automations):
    """Add HA automations to the schedule summary JSON."""
    try:
        # Read existing summary
        with open(SCHEDULE_SUMMARY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Add HA automations section
        data["homeassistant_automations"] = ha_automations

        # Update summary counts
        if "summary" not in data:
            data["summary"] = {}

        data["summary"]["homeassistant_automations"] = len(ha_automations)
        data["summary"]["ha_enabled"] = sum(1 for a in ha_automations if a.get("enabled"))
        data["summary"]["ha_disabled"] = sum(1 for a in ha_automations if not a.get("enabled"))

        # Write back
        with open(SCHEDULE_SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"✓ Added {len(ha_automations)} Home Assistant automations to schedule summary")
        return True

    except FileNotFoundError:
        print(f"Error: Schedule summary not found at {SCHEDULE_SUMMARY_PATH}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error updating schedule summary: {e}", file=sys.stderr)
        return False


def main():
    print("Querying Home Assistant automations...")

    # Get automation list from entity registry
    automations = query_ha_automations()

    if not automations:
        print("No automations found in entity registry")
        sys.exit(1)

    print(f"Found {len(automations)} automations in registry")

    # Get current states from database
    states = get_automation_states()
    print(f"Retrieved states for {len(states)} automations")

    # Parse and combine data
    parsed = parse_automation_data(automations, states)

    if update_schedule_summary(parsed):
        print("✓ Schedule summary updated successfully")
        sys.exit(0)
    else:
        print("✗ Failed to update schedule summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
