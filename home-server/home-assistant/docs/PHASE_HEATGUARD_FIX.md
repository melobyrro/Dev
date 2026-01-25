# Patio AC Heat Guard Bug Fix
**Date:** 2026-01-23
**Status:** RESOLVED

---

## Problem

The Patio AC was turning on in COOL mode every 5 minutes even when the temperature was well below the 95°F heat guard threshold (e.g., at 70°F).

**Symptom:** AC turned on unexpectedly, user had to manually turn it off.

---

## Root Cause

The `patio_ac_heat_guard_on` automation (line 791 of `patio_ac.yaml`) had multiple triggers:
- `numeric_state`: temp above threshold (correct)
- `time_pattern: /5 minutes`: periodic catch-up (problematic without condition)
- `state` changes on settings

The CONDITIONS block only checked:
1. `reason == "idle"`
2. `heat_guard_enabled == on`
3. Runtime limit not exceeded

**MISSING:** Temperature check in conditions!

When the 5-minute periodic trigger fired, it would activate the AC regardless of temperature because the condition block didn't verify the temperature was actually above the threshold.

---

## Solution

Added a `numeric_state` condition to the condition block:

```yaml
    - condition: numeric_state
      entity_id: sensor.patio_temp_sensor_temperature
      above: input_number.patio_ac_heat_threshold
```

This ensures the AC only activates when the temperature is at or above the threshold, regardless of which trigger fired.

---

## Files Modified

| File | Change |
|------|--------|
| `packages/patio_ac/patio_ac.yaml` | Added temperature condition to `patio_ac_heat_guard_on` automation (lines 820-822) |

---

## Verification

1. HA container restarted successfully
2. No configuration errors
3. Current temperature ~70°F, threshold 95°F
4. AC should remain off during 5-minute intervals

**Test procedure:**
1. Ensure reason is "idle" and heat guard is enabled
2. Wait 5+ minutes
3. Confirm AC does not turn on
4. Check automation traces in HA UI to verify condition blocked the trigger

---

## Backup/Rollback

**Backup created:**
`/mnt/ByrroServer/backups/homeassistant/patio_ac.yaml.pre-heatguard-fix-*`

**Rollback:**
```bash
# Find the backup
ls -la /mnt/ByrroServer/backups/homeassistant/patio_ac.yaml.pre-heatguard-fix-*

# Restore
cp /mnt/ByrroServer/backups/homeassistant/patio_ac.yaml.pre-heatguard-fix-YYYYMMDD-HHMMSS \
   /mnt/ByrroServer/docker-data/homeassistant/config/packages/patio_ac/patio_ac.yaml
docker restart homeassistant
```

---

## Related

- The 5-minute `time_pattern` trigger is a valid catch-up mechanism for:
  - Missed `numeric_state` transitions
  - Delayed sensor updates
  - HA restarts while temperature was already high
- The fix preserves this catch-up behavior while adding the necessary safety check.

---

## Heat Guard Fix: RESOLVED
