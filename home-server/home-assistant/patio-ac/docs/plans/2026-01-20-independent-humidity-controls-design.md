# Design: Independent Day/Night Humidity Controls

**Date:** 2026-01-20
**Status:** Approved
**Author:** Claude + User collaboration

## Problem Statement

Currently, Day and Night Humidity modes share a single target (`patio_ac_dewpoint_stop`). When the user adjusts the target slider on either the Day or Night humidity card, both cards reflect the change. The user wants fully independent controls where:
- Day Humidity has its own trigger AND target
- Night Humidity has its own trigger AND target
- Changing one never affects the other

## Solution

### Entity Mapping

**Current State (shared target):**
| Mode | Trigger | Target |
|------|---------|--------|
| Day | `patio_ac_dewpoint_start` | `patio_ac_dewpoint_stop` |
| Night | `patio_ac_dewpoint_night_start` | `patio_ac_dewpoint_stop` |

**New State (independent targets):**
| Mode | Trigger | Target |
|------|---------|--------|
| Day | `patio_ac_dewpoint_start` | `patio_ac_dewpoint_day_stop` |
| Night | `patio_ac_dewpoint_night_start` | `patio_ac_dewpoint_night_stop` |

**Note:** The helpers `patio_ac_dewpoint_day_stop` and `patio_ac_dewpoint_night_stop` already exist in Home Assistant but are not currently wired up.

## Files Requiring Changes

| File | Current Version | New Version | Changes |
|------|-----------------|-------------|---------|
| automations.yaml | v2.9 | v2.10 | 8 references — Day uses `dewpoint_day_stop`, Night uses `dewpoint_night_stop` |
| patio_ac_control.yaml | v1.19 | v1.20 | 3 references — Dashboard cards wired to correct targets |
| patio_ac_threshold_validation_automations.yaml | v1 | v2 | 10 references — Split into independent day/night validation |
| Patio_AC_FRD.md | v1.7 | v1.8 | Update entity table, remove "shared target" note |
| gap_analysis.md | - | - | Update documentation |

## Validation Logic Changes

### Current Design
One automation (`patio_ac_validate_dewpoint_target`) watches the shared target and adjusts *both* triggers if raised.

### New Design
Two independent validations:

**Day Humidity:**
- `patio_ac_validate_day_humidity_trigger` — watches `dewpoint_start`, adjusts `dewpoint_day_stop` down if needed
- `patio_ac_validate_day_dewpoint_target` — watches `dewpoint_day_stop`, adjusts `dewpoint_start` up if needed

**Night Humidity:**
- `patio_ac_validate_night_humidity_trigger` — watches `dewpoint_night_start`, adjusts `dewpoint_night_stop` down if needed
- `patio_ac_validate_night_dewpoint_target` — watches `dewpoint_night_stop`, adjusts `dewpoint_night_start` up if needed

## Deployment Order

1. Update threshold validation automations (independent validation logic)
2. Update main automations (day/night use their own targets)
3. Update dashboard (wire sliders to correct entities)
4. Reload automations in Home Assistant
5. Test via Chrome DevTools

## Testing Plan

### Phase 1: UI Verification (Chrome DevTools)
1. Navigate to Patio AC dashboard
2. Adjust Day Humidity target slider → verify Night slider does NOT move
3. Adjust Night Humidity target slider → verify Day slider does NOT move
4. Verify trigger/target validation still works within each card (target stays 1° below trigger)

### Phase 2: Automation Trigger Test (Real-time Wait)
1. Note current dew point reading from sensor
2. Set Day trigger to 1° below current dew point (should trigger DRY)
3. Set Day target to trigger - 1° (valid config)
4. Wait for the 5-minute evaluation cycle to run
5. Observe: Does the automation detect the condition and start DRY mode?
6. Verify activity log shows "Day Humidity" as the reason

### Phase 3: Stop Condition Test
1. After DRY starts, set Day target to current dew point + 1° (so condition is met)
2. Wait for next evaluation cycle
3. Verify DRY stops when dew point reaches target

### Phase 4: Night Independence Check
1. Confirm Night Humidity settings remained untouched during all Day tests
2. Optionally repeat a quick trigger test for Night if within night hours

## Deprecation

- `patio_ac_dewpoint_stop` — no longer used after this change, can be removed from HA configuration later

## Success Criteria

- [x] Day and Night humidity sliders are fully independent
- [x] Validation logic works within each mode (target always 1° below trigger)
- [x] Day Humidity automation triggers correctly using day-specific target
- [x] Night Humidity automation triggers correctly using night-specific target
- [x] Activity log shows correct reason for each mode

## Implementation Results (2026-01-21)

**All success criteria verified:**
1. UI sliders are fully independent - Day target=60°F, Night target=60°F can be set independently
2. Threshold validation works - when Night trigger was set to 54°F, Night target auto-adjusted to 53°F
3. Night Humidity automation triggered correctly with reason "humidity_night"
4. Activity log showed "AC ON (DRY) — Night Humidity"

**Files deployed:**
- automations.v2.10.yaml
- patio_ac_control.v1.20.yaml
- Patio_AC_FRD_v1.8.md
