# Kia EV9 Integration - Project Instructions

> **Inherits from:** [/Dev/CLAUDE.md](../../../CLAUDE.md) — Read root file for universal dev workflow (git sync, Chrome MCP, Tasks, /done)

## Overview

This project integrates a **2024 Kia EV9** electric vehicle with Home Assistant using the [kia_uvo HACS integration](https://github.com/Hyundai-Kia-Connect/kia_uvo). The integration provides vehicle status monitoring, climate control, charging management, and location tracking.

## File Structure

```
kia-ev9/
├── CLAUDE.md                       # This file - project instructions
├── requirements.md                 # Functional requirements document (v1.1)
├── helpers.v{X}.{Y}.yaml           # Input helpers for configurable settings
├── automations.v{X}.{Y}.yaml       # Vehicle automations
├── scripts.v{X}.{Y}.yaml           # HA scripts for vehicle control
├── lovelace.kia-ev9.v{X}.{Y}.yaml  # Dashboard cards
├── qa_tests.py                     # Automated test suite (10 tests)
├── scripts/                        # Shell scripts for HA
│   ├── ev9_recovery_with_otp.sh    # Multi-step config flow with OTP request
│   └── ev9_submit_otp.sh           # Submit OTP to complete config flow
├── docs/plans/                     # Design documents
│   ├── 2026-01-21-connection-watchdog-design.md
│   └── 2026-01-21-email-otp-automation-design.md
└── .archive/                       # Old versions
```

## Current Versions

| Component | Current Version | Last Updated |
|-----------|-----------------|--------------|
| Requirements | v1.3 | 2026-01-19 |
| Helpers | v2.8 | 2026-01-24 |
| Automations | v2.7 | 2026-01-24 |
| Scripts | v2.5 | 2026-01-22 |
| Dashboard | v2.8 | 2026-01-24 |

## Change History

See [CHANGELOG.md](./CHANGELOG.md) for version history.

**Latest:** v2.8 (2026-01-24) - Car Status Visibility Enhancement

---

## Actual Entity IDs (Discovered 2025-01-19)

### Primary Sensors
| Entity ID | Description | Unit |
|-----------|-------------|------|
| `sensor.ev9_ev_battery_level` | EV battery state of charge | % |
| `sensor.ev9_ev_range` | EV driving range | mi |
| `sensor.ev9_total_driving_range` | Total driving range | mi |
| `sensor.ev9_ev_charging_power` | Current charging power | kW |
| `sensor.ev9_estimated_charge_duration` | Time to full charge | min |
| `sensor.ev9_car_battery_level` | 12V battery level | % |
| `sensor.ev9_odometer` | Total miles driven | mi |
| `sensor.ev9_set_temperature` | Climate set temperature | °F |
| `sensor.ev9_last_updated_at` | Last data sync | timestamp |
| `sensor.ev9_next_service` | Distance to next service | mi |
| `sensor.ev9_fuel_level` | Fuel level (shows 0 for EV) | % |
| `sensor.ev9_dtc_count` | Diagnostic trouble codes | count |
| `sensor.ev9_data` | All vehicle data (JSON) | - |

### Binary Sensors
| Entity ID | Description |
|-----------|-------------|
| `binary_sensor.ev9_ev_battery_charge` | Is charging |
| `binary_sensor.ev9_ev_battery_plug` | Is plugged in |
| `binary_sensor.ev9_locked` | Vehicle locked |
| `binary_sensor.ev9_air_conditioner` | Climate/AC running |
| `binary_sensor.ev9_engine` | Engine/motor running |
| `binary_sensor.ev9_defrost` | Defrost active |
| `binary_sensor.ev9_steering_wheel_heater` | Steering wheel heater on |
| `binary_sensor.ev9_back_window_heater` | Rear defroster on |
| `binary_sensor.ev9_side_mirror_heater` | Mirror heaters on |
| `binary_sensor.ev9_trunk` | Trunk open |
| `binary_sensor.ev9_hood` | Hood open |
| `binary_sensor.ev9_front_left_door` | Front left door open |
| `binary_sensor.ev9_front_right_door` | Front right door open |
| `binary_sensor.ev9_back_left_door` | Back left door open |
| `binary_sensor.ev9_back_right_door` | Back right door open |
| `binary_sensor.ev9_tire_pressure_all` | Tire pressure warning |
| `binary_sensor.ev9_smart_key_battery_warning` | Key fob battery low |
| `binary_sensor.ev9_washer_fluid_warning` | Washer fluid low |
| `binary_sensor.ev9_fuel_low_level` | Fuel low (N/A for EV) |

### Controls
| Entity ID | Description | Range |
|-----------|-------------|-------|
| `lock.ev9_door_lock` | Lock/unlock vehicle | - |
| `number.ev9_ac_charging_limit` | AC charge limit | 50-100% (step 10) |
| `number.ev9_dc_charging_limit` | DC charge limit | 50-100% (step 10) |

### Device Tracker
| Entity ID | Description |
|-----------|-------------|
| `device_tracker.ev9_location` | GPS location |

### Services
| Service | Description |
|---------|-------------|
| `kia_uvo.start_climate` | Start climate control |
| `kia_uvo.stop_climate` | Stop climate control |
| `kia_uvo.start_charge` | Start charging |
| `kia_uvo.stop_charge` | Stop charging |
| `kia_uvo.update` | Force data refresh |

---

## Helper Entities (Configurable via Dashboard)

### Departure Schedule Helpers
For pre-conditioning automation with UI-configurable times:

```yaml
# input_datetime: Departure times per day
input_datetime:
  ev9_departure_monday: ...
  ev9_departure_tuesday: ...
  # (see helpers.v1.0.yaml for full list)

# input_boolean: Enable/disable per day
input_boolean:
  ev9_precondition_monday: ...
  ev9_precondition_tuesday: ...
  # (see helpers.v1.0.yaml for full list)

# input_number: Lead time before departure
input_number:
  ev9_precondition_lead_time: 5-30 min
  ev9_low_battery_threshold: 10-50%
```

---

## Deployment Process

### Initial Setup (Completed)
- [x] Install HACS
- [x] Install kia_uvo integration from HACS
- [x] Add integration with Kia Connect credentials
- [x] Verify entities created

### Next Steps
1. Deploy helper entities to HA
2. Create automations
3. Build dashboard cards

### Configuration Changes
1. SSH to Docker VM: `ssh byrro@192.168.1.11`
2. HA Config path: `/mnt/ByrroServer/docker-data/homeassistant/config/`
3. Reload after changes:
   ```bash
   curl -X POST http://192.168.1.11:8123/api/services/homeassistant/reload_all \
     -H "Authorization: Bearer $HA_TOKEN"
   ```

---

## Testing Checklist

- [x] Integration connects successfully
- [x] All expected sensors populate
- [x] Lock/unlock commands work (verified 2026-01-20)
- [x] Climate control starts/stops (verified via qa_tests.py)
- [x] Location tracking updates
- [x] Automations trigger correctly (qa_tests.py passes 10/10)
- [x] Dashboard cards render properly
- [x] Walk-Away auto-lock works (with skip-if-locked logic)
- [x] Timeout auto-lock works (with skip-if-locked logic)
- [x] Theft detection entities exist
- [x] Event log rotation works
- [x] Self-healing OTP automation works (verified 2026-01-22)

### Running Tests

The `qa_tests.py` script runs 10 automated tests against the live Home Assistant instance:

```bash
cd /Users/andrebyrro/Dev/home-server/home-assistant/kia-ev9
python qa_tests.py
```

**Tests included:**
1. Health Check - Verifies critical entities exist
2. Log Rotation - Tests event log shift logic
3. Climate Logic - Tests timer and logging
4. Walk-Away Automation - Simulates auto-lock trigger
5. Schedule Toggles - Tests enable/disable
6. Theft Detection Entities - Verifies v2.2 entities
7. Theft Automations Loaded - Checks automation state
8. Theft Toggle & Thresholds - Tests config helpers
9. Movement Sensor Logic - Tests distance calculation
10. Kia Integration Freshness - Checks data staleness

**Note**: Tests 3 and 4 interact with the real Kia API, so a 10-second cooldown is added between them to avoid rate limiting.

---

## Troubleshooting

### Common Issues
1. **Auth fails**: Re-authenticate in Kia Connect app first, then retry
2. **No data**: Check if Kia Connect servers are responding
3. **Stale data**: Use `kia_uvo.update` service to force refresh
4. **Rate limits**: Don't poll more than once per 30 minutes

### Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.kia_uvo: debug
    hyundai_kia_connect_api: debug
```

---

## Known Issues

### `binary_sensor.ev9_locked` vs `lock.ev9_door_lock`

These two entities both represent vehicle lock status but can become desynced:

| Entity | Type | States | Use Case |
|--------|------|--------|----------|
| `binary_sensor.ev9_locked` | Binary Sensor | on/off | Read-only status display |
| `lock.ev9_door_lock` | Lock | locked/unlocked | Control AND reliable status |

**Issue discovered 2026-01-20**: Using HA's `set_state()` API on `binary_sensor.ev9_locked` during testing caused it to become "detached" from the kia_uvo integration. The raw Kia API showed `doorLock: true` but the binary_sensor showed `off`.

**Recommendation**: Always use `lock.ev9_door_lock` for automation conditions. It's the control entity and maintains accurate state sync with the Kia API.

### Kia API Rate Limiting

The Kia Connect API enforces rate limits:
- **Error**: "Another remote command is being executed"
- **Cause**: Commands sent too quickly in succession
- **Workaround**: Wait 10+ seconds between API commands
- **Note**: The climate test in qa_tests.py adds a 10-second cooldown before the walk-away test

### Kia API Intermittent Failures

Occasional `KeyError: 'payload'` errors occur when fetching vehicle data. This is a known Kia Connect API issue that typically recovers on its own within minutes.

### IMAP Integration `imap.fetch` Service

When using the IMAP integration's `imap.fetch` service to retrieve email content:

| Parameter | Correct | Wrong |
|-----------|---------|-------|
| Entry reference | `entry: <entry_id>` | `entry_id: <entry_id>` |

**Error if wrong**: `extra keys not allowed @ data['entry_id']`

**Example correct usage**:
```yaml
- action: imap.fetch
  data:
    entry: 01KFHWR9EMN3GVQ03WVFSXHNRY  # NOT entry_id
    uid: '{{ trigger.event.data.uid }}'
  response_variable: fetched_email
```

**Note**: The IMAP entry ID can be found in HA → Settings → Integrations → IMAP → three-dot menu → "Show device info" → look at the URL.

---

## Kia API Reference

### Available Charging Data

The Kia Connect API provides these charging-related fields via `sensor.ev9_data`:

| Field | Path | Description |
|-------|------|-------------|
| Battery Level | `evStatus.batteryStatus` | Current SOC (%) |
| Charging Status | `evStatus.batteryCharge` | true/false |
| Plugged In | `evStatus.batteryPlugin` | 0 = unplugged, 1 = plugged |
| Charging Power | `evStatus.realTimePower` | Current power (kW) |
| Charging Current | `evStatus.chargingCurrent` | Amperage |
| Battery Conditioning | `evStatus.batteryConditioning` | true if battery is being conditioned |
| Time to Full | `evStatus.remainTime2.atc.value` | Minutes remaining |

### NOT Available from API

The following data is **NOT** provided by the Kia Connect API:
- **Throttle reason**: Why charging speed reduced (no thermal management feedback)
- **Battery temperature**: Actual pack temperature
- **Cell voltages**: Individual cell data
- **Charging curve position**: Where on the charge curve
- **Preconditioning status**: Whether battery is actively heating/cooling

### Interpreting Charging Behavior

When charging appears throttled:
1. Check `batteryConditioning` - if true, battery is being thermally managed
2. Check ambient temperature vs battery behavior
3. High SOC (>80%) naturally reduces charge rate
4. The API won't tell you WHY it's throttled, only that power is reduced

---

## Related Documentation

- [kia_uvo GitHub](https://github.com/Hyundai-Kia-Connect/kia_uvo)
- [Home Assistant Community Thread](https://community.home-assistant.io/t/kia-uvo-integration/297927)
- [Kia Connect App](https://www.kia.com/us/en/owners/kia-connect)
