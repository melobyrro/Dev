# Fix: Tuya Mode Reversion Race Condition

**Date:** 2026-01-21
**Status:** Implemented & Verified
**Version:** scripts.v2.7.yaml

## Problem Statement

When Heat Guard automation turned on the AC, the mode would briefly flash to COOL but immediately revert to DRY (the device's last-used mode). This happened within ~250ms, making the AC run in the wrong mode.

## Root Cause Analysis

The script used a two-step power-on sequence:

```yaml
# Old approach (buggy)
- if AC is off:
  - climate.turn_on        # Powers on in LAST mode (DRY)
  - delay 1 second
- climate.set_hvac_mode    # Sets COOL
```

### What Happened

1. `climate.turn_on` sends "power on" command to Tuya device
2. Device powers on in its last-used mode (DRY)
3. Tuya cloud syncs this state
4. `climate.set_hvac_mode` sends "change to COOL"
5. Device changes to COOL
6. **Tuya cloud "corrects" the state back to DRY** (race condition)

### Evidence from State History

```
05:48:10.690 - dry (mode=3)  ← climate.turn_on → device powers on in last mode
05:48:11.454 - cool (mode=2) ← climate.set_hvac_mode → changed to COOL
05:48:11.702 - dry (mode=3)  ← REVERTED! Only 248ms later
```

## Solution

Remove the separate `climate.turn_on` call. The `climate.set_hvac_mode` service handles both power-on AND mode setting atomically on Tuya devices.

```yaml
# New approach (v2.7)
# No separate turn_on - set_hvac_mode handles it
- climate.set_hvac_mode    # Powers on AND sets mode atomically
- delay 1 second
- climate.set_temperature  # Set temperature after mode is stable
```

## Changes Made

**File:** `scripts.v2.7.yaml`

1. **Removed** the entire conditional block that called `climate.turn_on` + delay
2. **Added** 1-second delay before `climate.set_temperature` to let mode stabilize
3. **Kept** the v2.6 fix (reason set AFTER mode change for event logger)

## Verification Results

After deploying v2.7, the AC correctly goes from OFF directly to COOL:

```
05:56:21 - OFF
05:56:46 - COOL (mode=2)  ← No intermediate DRY!
05:57:39 - COOL (mode=2)  ← Stays in COOL
05:58:48 - COOL (mode=2)  ← Still COOL
```

## Related Changes

This fix builds on v2.6 which addressed a separate issue:

| Version | Fix |
|---------|-----|
| v2.6 | Move reason update to AFTER mode change (event logger race condition) |
| v2.7 | Remove separate climate.turn_on (Tuya mode reversion race condition) |

## Files Updated

- `scripts.v2.7.yaml` - Production script with both fixes
- `scripts.v2.6.yaml` - Archived (superseded by v2.7)

## Notes

- This is a **Tuya-specific behavior** - other climate integrations may not have this issue
- The `climate.set_hvac_mode` service is the correct way to power on and set mode atomically
- Always test climate control changes thoroughly - cloud-based devices can have unexpected behaviors
