# Observations and Recommended Improvements

**Date:** 2026-01-21
**Context:** Debugging session for Heat Guard mode reversion bug

## Issues Fixed This Session

| Issue | Fix | Version |
|-------|-----|---------|
| Event logger showed wrong mode (race condition) | Move reason update to AFTER mode change | v2.6 |
| Heat Guard COOL reverts to DRY (Tuya race condition) | Remove separate `climate.turn_on` call | v2.7 |

---

## Observations Needing Attention

### 1. Threshold Validation Allows Invalid Temperature Values

**Problem:** The threshold validation automations allow trigger/target values outside the AC's supported range.

**Evidence:**
- AC min_temp: 61°F, max_temp: 86°F
- Heat Guard trigger can be set to 50°F
- Heat Guard target auto-adjusts to 49°F (1° below trigger)
- But AC cannot set temperature to 49°F - it's below min_temp

**Impact:**
- Script's wait_template times out waiting for impossible temperature
- Script continues but behavior is undefined
- User sees settings that the AC can't actually achieve

**Recommendation:** Update threshold validation automations to clamp values within AC's supported range:
```yaml
# Example: Clamp target to AC min_temp
value: >
  {% set new_target = trigger_value - 1 %}
  {% set min_temp = state_attr('climate.150633095083490_climate', 'min_temp') | int(61) %}
  {{ [new_target, min_temp] | max }}
```

**Priority:** Medium - Prevents user confusion and script timeouts

---

### 2. Script Doesn't Handle Temperature Set Failures

**Problem:** If `climate.set_temperature` fails (e.g., value out of range), the script continues but wait_template times out.

**Current behavior:**
1. Script sets mode to COOL ✓
2. Script tries to set temperature to 49°F ✗ (silently fails)
3. wait_template waits for `cool|49` signature
4. Timeout after 5 seconds
5. Script continues but reason may not be set correctly

**Recommendation:** Add validation before calling set_temperature:
```yaml
- if:
  - condition: template
    value_template: >
      {% set min_t = state_attr('climate.150633095083490_climate', 'min_temp') | int(61) %}
      {% set max_t = state_attr('climate.150633095083490_climate', 'max_temp') | int(86) %}
      {{ mode in ['cool', 'dry'] and temperature >= min_t and temperature <= max_t }}
  then:
    - service: climate.set_temperature
      ...
```

**Priority:** Medium - Improves reliability

---

### 3. Input Number Ranges Don't Match AC Constraints

**Problem:** Helper ranges are set to 45-100°F, but AC only supports 61-86°F.

**Current configuration (from FRD):**
```yaml
input_number.patio_ac_heat_threshold:
  min: 45
  max: 100

input_number.patio_ac_heat_target:
  min: 45
  max: 100
```

**Recommendation:** Update helper min/max to match AC constraints:
```yaml
input_number.patio_ac_heat_threshold:
  min: 62  # At least 1° above AC min
  max: 100

input_number.patio_ac_heat_target:
  min: 61  # AC min_temp
  max: 99  # At least 1° below trigger max
```

**Note:** This requires updating `configuration.yaml` in Home Assistant.

**Priority:** Low - Nice to have, prevents invalid configurations

---

### 4. DRY Mode Temperature Handling

**Observation:** The expected signature for DRY mode is `dry|none` (no temperature check), but the script still calls `set_temperature` for DRY mode.

**Current code:**
```yaml
- if:
  - condition: template
    value_template: "{{ mode in ['cool', 'dry'] }}"
  then:
    - service: climate.set_temperature
```

**Question:** Does DRY mode on this Tuya AC actually use/respect temperature settings?

**Recommendation:** Test whether DRY mode uses temperature. If not, consider:
```yaml
- if:
  - condition: template
    value_template: "{{ mode == 'cool' }}"  # Only COOL uses temperature
  then:
    - service: climate.set_temperature
```

**Priority:** Low - Optimization, needs testing

---

## Testing Gaps Identified

### Manual Testing Needed

1. **Heat Guard full cycle:** Trigger → Run → Stop at target temperature
2. **Night Humidity with new independent targets:** Verify both day and night work independently
3. **Edge case:** What happens if AC is manually changed during automation run?

### Automated Testing Ideas

- Create a test automation that validates script behavior
- Log expected vs actual states after each script run
- Alert on signature mismatches

---

## Files That May Need Updates

| File | Change | Priority |
|------|--------|----------|
| `configuration.v2.8.yaml` | Update input_number min/max ranges | Low |
| `scripts.v2.7.yaml` | Add temperature range validation | Medium |
| `patio_ac_threshold_validation_automations.yaml` | Clamp to AC min/max | Medium |
| `Patio_AC_FRD_v1.8.md` | Document AC temperature constraints | Low |

---

## Summary

The critical bugs (mode reversion, event logger race condition) are fixed. The remaining items are **improvements** that would make the system more robust:

1. **Should fix:** Temperature validation against AC's actual limits
2. **Nice to have:** Better error handling in scripts
3. **Documentation:** Update FRD with AC hardware constraints
