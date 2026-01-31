# Patio AC Control System — Requirements

**Version:** 2.0
**Last Updated:** 2026-01-31
**Owner:** Andre

---

## 1) Purpose

Automated climate control for the patio AC unit with:
- Heat guard protection (high temperature triggers)
- Humidity-based control (day/night modes)
- Manual override capability
- Compressor protection timers

---

## 2) Inputs

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.patio_temperature` | Sensor | Current patio temperature |
| `sensor.patio_humidity` | Sensor | Current patio humidity |
| `sensor.outdoor_dew_point` | Sensor | Outdoor dew point for comfort logic |
| `climate.patio_ac` | Climate | The AC unit (abstracted from hardware ID) |

---

## 3) Outputs

| Entity | Type | Description |
|--------|------|-------------|
| `input_select.patio_ac_reason` | Helper | Current state reason (Idle, Heat Guard, Humidity Day/Night, Manual) |
| `sensor.patio_ac_last_evaluated` | Sensor | Last automation evaluation timestamp |
| `sensor.patio_ac_event_log` | Sensor | Activity log |
| `sensor.patio_ac_*_runtime` | Sensors | Runtime tracking (cool/dry, auto/manual) |

---

## 4) Controls

| Control | Entity | Description |
|---------|--------|-------------|
| Manual Override | `input_boolean.patio_ac_manual_override` | Force manual control |
| Heat Guard Threshold | `input_number.patio_ac_heat_guard_temp` | Temperature trigger for heat protection |
| Humidity Day Start | `input_number.patio_ac_humidity_day_start` | RH% to start day dehumidification |
| Humidity Day Stop | `input_number.patio_ac_humidity_day_stop` | RH% to stop day dehumidification |
| Humidity Night Start | `input_number.patio_ac_humidity_night_start` | RH% to start night dehumidification |
| Humidity Night Stop | `input_number.patio_ac_humidity_night_stop` | RH% to stop night dehumidification |
| Compressor Protection | `input_datetime.patio_ac_compressor_protection_until` | Minimum off time |

---

## 5) Safety and Guardrails

| Guardrail | Description |
|-----------|-------------|
| Heat Guard Priority | Heat protection overrides ALL other states |
| Compressor Protection | Enforced minimum off-time between cycles |
| Min Run Time | Prevents short-cycling |
| HAL Compliance | Uses `climate.patio_ac` (virtual), not hardware ID |
| Timeout Safety | All waits have explicit timeouts with fallback |

---

## 6) UI Contract

**Dashboard:** `patio-ac/dashboards/patio_ac.v1.21.yaml`
**Lovelace Path:** `/lovelace/patio-ac`

### Tab Structure
| Tab | Content |
|-----|---------|
| Overview | Status, current state, primary controls |
| Automations | (To be added per Section 4.9) |
| Settings | Thresholds, timers, advanced configuration |

### Observe → Understand → Act
- **Observe:** Current temp/humidity, AC state, runtime stats
- **Understand:** Current reason (Heat Guard, Humidity, etc.), threshold values
- **Act:** Manual override toggle, run controls

---

## 7) Acceptance Tests

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Heat Guard Trigger | Set temp above threshold | AC activates with reason "Heat Guard" |
| Humidity Day | Set RH above day start | AC activates in dry mode during day hours |
| Manual Override | Toggle manual override | AC responds to manual controls only |
| Compressor Protection | Turn off AC, try immediate restart | Restart blocked until protection timer expires |

---

## 8) Rollback

**Git revert:** `git revert <commit>` for config changes
**Restore:** Backup `ha-config/packages/patio_ac.yaml` from `.archive/`

---

## 9) File Locations

| File | Path | Purpose |
|------|------|---------|
| Package (Code) | `ha-config/packages/patio_ac.yaml` | All automations, scripts, helpers, sensors |
| Dashboard | `patio-ac/dashboards/patio_ac.v1.21.yaml` | Lovelace UI |
| Requirements | `patio-ac/REQUIREMENTS.md` | This file |
| Archive | `patio-ac/.archive/` | Old versions |
