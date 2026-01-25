# Entity Rename Audit

**Date:** 2026-01-22
**Auditor:** Claude Code (Packages Migration)

## Summary

Audit of Home Assistant entity IDs to identify hardware-based names that should be renamed to semantic names.

## Patio AC Climate Entity

| Current (Production) | New (Staging) | References Updated |
|---------------------|---------------|-------------------|
| `climate.150633095083490_climate` | `climate.patio_ac` | 88 |

### Files Updated in Staging

| File | References |
|------|------------|
| automations.yaml | 20 |
| automations.v2.9.yaml | 20 |
| scripts.v2.5.yaml | 13 |
| configuration.yaml | 12 |
| scripts.yaml | 11 |
| patio_ac_template.yaml | 8 |
| scripts_debug.yaml | 4 |

### Production Action Required

**IMPORTANT:** The actual entity rename must be done in production via Home Assistant UI:

1. Open Home Assistant: http://192.168.1.11:8123
2. Navigate: Settings → Devices & Services → Entities
3. Search: `150633095083490`
4. Click the climate entity
5. Click the gear icon (settings)
6. Change "Entity ID" from `climate.150633095083490_climate` to `climate.patio_ac`
7. Click "Update"

**This must be done BEFORE deploying the staging config to production.**

## Kia EV9 Entities

All EV9 entity IDs are already semantic:

| Entity | Status |
|--------|--------|
| `lock.ev9_door_lock` | ✅ Good |
| `device_tracker.ev9_location` | ✅ Good |
| `sensor.ev9_ev_battery_level` | ✅ Good |
| `binary_sensor.ev9_ev_battery_charge` | ✅ Good |
| `binary_sensor.ev9_ev_battery_plug` | ✅ Good |

## Other Projects

All other entity IDs audited are semantic:

| Entity | Status |
|--------|--------|
| `sensor.patio_dew_point` | ✅ Good |
| `sensor.patio_temp_sensor_temperature` | ✅ Good |
| `binary_sensor.daikin_running` | ✅ Good |
| `input_boolean.dawarich_on_trip` | ✅ Good |

## Conclusion

Only **one** hardware-based entity ID was found and has been updated in staging:
- `climate.150633095083490_climate` → `climate.patio_ac`

All other entity IDs follow semantic naming conventions.

## Verification Commands

```bash
# Check for any remaining hardware IDs (should return 0)
grep -r 'climate.150633095083490_climate' /config/*.yaml | wc -l

# Verify new entity ID is used
grep -r 'climate.patio_ac' /config/*.yaml | wc -l
```
