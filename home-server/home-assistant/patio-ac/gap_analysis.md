# Patio AC Control System - Gap Analysis

**Date**: 2026-01-19 (Updated)
**FRD Version**: 1.7
**Analysis Scope**: Automations, Scripts, Sensors, Dashboard

---

## Summary

| Category | Status | Issues |
|----------|--------|--------|
| Authority Model | PASS | Manual detection and blocking works correctly |
| Heat Guard | PASS | Enable/disable, trigger/target, misconfiguration guard all work |
| Day Humidity | PASS | Enable/disable, dew point logic works |
| Night Humidity | PASS | Enable/disable, dew point logic works |
| Safety/Emergency | PASS | Emergency RH stop works correctly |
| **Threshold Validation** | **PASS** | Bidirectional validation enforces 1° gap (added 2026-01-19) |
| Day/Night Cutoff | **FAIL** | Missing hard cutoff automation |
| Allow Seamless Handoff | **FAIL** | Helper exists but unused |
| Runtime Accounting | PASS | All runtime buckets exist and track correctly |
| Graphs | PASS | Two graphs with correct series |
| Dashboard Sensor | **WARN** | Activity log uses deprecated input_text pattern |

---

## Critical Gaps

### 1. Day/Night Schedule Cutoff (FR-SCHED-02) - CRITICAL

**Requirement**: After night start (default 22:00), Day Humidity must be ineligible and Active Logic must not display Day Humidity past the cutoff.

**Current Implementation**:
- Day Humidity automation has `condition: time after: day_start, before: night_start`
- Night Humidity automation has `condition: time after: night_start, before: day_start`

**Gap**: If Day Humidity is running (reason=humidity_day) when night start time arrives:
- No automation exists to STOP Day Humidity
- Day Humidity will continue until dew point drops below target
- The system violates FR-SCHED-02

**Fix Required**: Add automation `patio_ac_day_night_boundary` that:
1. Triggers at `input_datetime.patio_ac_night_start` and `input_datetime.patio_ac_day_start`
2. If reason is `humidity_day` and time is after night_start → stop DRY, set reason to idle
3. If reason is `humidity_night` and time is after day_start → stop DRY, set reason to idle
4. Optionally check Allow Seamless Handoff to enable smooth transition

---

### 2. Allow Seamless Handoff (FR-SCHED) - INCOMPLETE

**Requirement**: The FRD mentions this setting should control Day/Night transitions.

**Current Implementation**:
- `input_boolean.patio_ac_allow_seamless_handoff` exists in configuration
- It is shown in the dashboard Global Configuration section
- **No automations reference or use this helper**

**Gap**: The feature is incomplete - the UI control exists but does nothing.

**Fix Required**: The day/night boundary automation should use this:
- If `allow_seamless_handoff = ON`: At boundary, check if new ruleset is eligible and transition directly
- If `allow_seamless_handoff = OFF`: At boundary, stop current and return to Idle

---

### 3. Activity Log Sensor Mismatch - WARNING

**Current Dashboard v1.15** references:
```yaml
{% set events = state_attr('sensor.patio_ac_activity', 'events') %}
```

**Current Configuration** has:
- `input_text.patio_ac_event_1` through `input_text.patio_ac_event_10` (deprecated pattern from v1.14)

**Gap**: The dashboard references a sensor that may not exist or has wrong structure.

**Fix**: Either:
1. Create `sensor.patio_ac_activity` with `events` attribute (template sensor)
2. Or revert dashboard to use the input_text pattern from v1.14

---

## Passing Requirements

### Authority Model (FR-AUTH)
- Manual classification works via user_id detection in `patio_ac_manual_override_detect`
- Manual blocks automation starts (conditions check `reason == 'idle'`)
- Manual is ungoverned (daily limit enforcer excludes manual)
- Resume Automation button clears manual state

### Heat Guard (FR-HG)
- Enable/disable via `input_boolean.patio_ac_heat_guard_enabled`
- Trigger/target with misconfiguration guard
- Max duration: 0-1440 minutes in 30-minute steps
- Uses COOL mode only

### Threshold Validation (FR-RANGE-02) - Added 2026-01-19
- **Bidirectional validation** enforces minimum 1° gap between trigger and target
- Lower trigger → target follows down automatically
- Raise target → trigger follows up automatically
- Implemented via 5 automations:
  - `patio_ac_validate_heat_guard_trigger`
  - `patio_ac_validate_heat_guard_target`
  - `patio_ac_validate_day_humidity_trigger`
  - `patio_ac_validate_night_humidity_trigger`
  - `patio_ac_validate_dewpoint_target`
- **Tested**: Confirmed working via Chrome DevTools on 2026-01-19
- **Source file**: `patio_ac_threshold_validation_automations.yaml`

### Humidity Domains (FR-DH, FR-NH)
- Enable/disable for both Day and Night
- Dew point trigger/target logic
- Misconfiguration guard (target >= trigger)
- Uses DRY mode only
- Shared target `input_number.patio_ac_dewpoint_stop`

### Safety/Emergency (FR-SE)
- Emergency RH stop triggers and forces AC OFF
- Sets reason to `humidity_emergency` which maps to "Safety/Emergency"

### Runtime Accounting (FR-RT)
- Total-by-mode: `sensor.patio_ac_runtime_dry_total`, `sensor.patio_ac_runtime_cool_total`
- Automation buckets: `sensor.patio_ac_runtime_*_automation`
- Manual buckets: `sensor.patio_ac_runtime_*_manual`
- Overall: `sensor.patio_ac_runtime_total_all`
- Binary sensors correctly track mode + authority combination

### Graphs (FR-GRAPH)
- Graph 1: Humidity + Dew Point + Dry Runtime + Cool Runtime (4 series)
- Graph 2: Temperature + Dry Runtime + Cool Runtime (3 series)
- Entity IDs match FRD requirements

### Global Configuration (FR-GC)
- Last evaluated: `sensor.patio_ac_last_evaluated` (timestamp)
- Next evaluation: `sensor.patio_ac_next_evaluation` (countdown)
- Logical grouping with sections
- Explanation toggle with comprehensive documentation

### Reason Friendly Sensor (FR-ENT-STATE)
- `sensor.patio_ac_reason_friendly` correctly maps all internal reasons:
  - idle → Idle
  - manual → Manual
  - heat_guard → Heat Guard
  - humidity_day → Day Humidity
  - humidity_night → Night Humidity
  - humidity_emergency → Safety/Emergency
  - safety_lock → Safety/Emergency

---

## Recommendations

### Priority 1 - Fix Day/Night Cutoff
Create new automation to enforce schedule boundaries.

### Priority 2 - Implement Seamless Handoff
Connect the existing UI control to actual behavior.

### Priority 3 - Fix Activity Log
Align dashboard to actual sensor structure.

### Priority 4 - Dashboard Polish
- Improve chart colors for better distinction
- Add chart legends
- Ensure mobile responsive layout works (already done in v1.15)

---

## Proposed Automation: Day/Night Boundary Handler

```yaml
- id: patio_ac_day_night_boundary
  alias: "Patio AC - Day/Night Boundary Handler"
  description: "Enforce schedule cutoff and handle seamless handoff"
  mode: single
  trigger:
    - platform: time
      at: input_datetime.patio_ac_night_start
      id: night_start
    - platform: time
      at: input_datetime.patio_ac_day_start
      id: day_start
  condition:
    - condition: template
      value_template: "{{ states('input_select.patio_ac_reason') in ['humidity_day', 'humidity_night'] }}"
  action:
    - variables:
        current_reason: "{{ states('input_select.patio_ac_reason') }}"
        is_night_start: "{{ trigger.id == 'night_start' }}"
        is_day_start: "{{ trigger.id == 'day_start' }}"
        wrong_ruleset: >
          {{ (is_night_start and current_reason == 'humidity_day') or
             (is_day_start and current_reason == 'humidity_night') }}
        seamless: "{{ is_state('input_boolean.patio_ac_allow_seamless_handoff', 'on') }}"
    - choose:
        - conditions:
            - condition: template
              value_template: "{{ wrong_ruleset }}"
          sequence:
            - choose:
                - conditions:
                    - condition: template
                      value_template: "{{ seamless }}"
                  sequence:
                    # Seamless: Switch to new ruleset if eligible
                    - variables:
                        dp: "{{ states('sensor.patio_dew_point') | float(0) }}"
                        new_trigger: >
                          {% if is_night_start %}
                            {{ states('input_number.patio_ac_dewpoint_night_start') | float(0) }}
                          {% else %}
                            {{ states('input_number.patio_ac_dewpoint_start') | float(0) }}
                          {% endif %}
                        new_enabled: >
                          {% if is_night_start %}
                            {{ is_state('input_boolean.patio_ac_night_humidity_enabled', 'on') }}
                          {% else %}
                            {{ is_state('input_boolean.patio_ac_day_humidity_enabled', 'on') }}
                          {% endif %}
                        eligible: "{{ new_enabled and dp >= new_trigger }}"
                        new_reason: "{{ 'humidity_night' if is_night_start else 'humidity_day' }}"
                    - choose:
                        - conditions:
                            - condition: template
                              value_template: "{{ eligible }}"
                          sequence:
                            - action: input_select.select_option
                              target:
                                entity_id: input_select.patio_ac_reason
                              data:
                                option: "{{ new_reason }}"
                      default:
                        # Not eligible for new ruleset, stop
                        - action: script.patio_ac_control
                          data:
                            action: "off"
                            reason: "{{ current_reason }}"
              default:
                # Non-seamless: Just stop
                - action: script.patio_ac_control
                  data:
                    action: "off"
                    reason: "{{ current_reason }}"
```
