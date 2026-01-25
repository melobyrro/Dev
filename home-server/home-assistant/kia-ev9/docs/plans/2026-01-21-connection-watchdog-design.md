# Kia EV9 Connection Watchdog Design

**Date**: 2026-01-21
**Status**: Approved
**Version**: 2.3

## Overview

Automated self-healing system that detects when the Kia UVO integration loses connection and automatically recovers it without manual intervention.

## Problem Statement

The Kia Connect API occasionally fails with `KeyError: 'payload'` errors, causing the integration to enter a `setup_retry` state. While HA attempts automatic retries, extended outages (24+ hours) require manual deletion and recreation of the integration with credentials.

## Solution

A watchdog automation that:
1. Detects prolonged unavailability (2+ hours)
2. Attempts a gentle reload first
3. If reload fails, automatically recreates the integration using stored credentials
4. Notifies the user of recovery attempts and outcomes

## Detection Logic

### Trigger
- `sensor.ev9_ev_battery_level` becomes `unavailable` for 2 hours

### Why Battery Level Sensor?
- Core sensor that always has a value when connected
- Goes unavailable early when integration fails
- Simple state-based trigger

### Cooldown
- 4-hour cooldown between recovery attempts
- Prevents retry spam during extended Kia server outages
- Tracked via `input_text.ev9_last_recovery_attempt`

## Recovery Flow

```
[2 hours unavailable]
    |
    v
[Send "Recovery Starting" notification]
    |
    v
[Try reload integration via API]
    |
    v
[Wait 5 minutes]
    |
    v
[Check if sensor is available now]
    |
    +-- YES --> [Log SUCCESS, notify "Reload worked"]
    |
    +-- NO --> [Delete integration entry]
                    |
                    v
               [Wait 10 seconds]
                    |
                    v
               [Create new integration with stored credentials]
                    |
                    v
               [Wait 2 minutes]
                    |
                    v
               [Check if sensor is available]
                    |
                    +-- YES --> [Log SUCCESS, notify "Recreated successfully"]
                    |
                    +-- NO --> [Log FAILED, notify "Manual intervention needed"]
```

## API Calls

| Action | Endpoint | Method |
|--------|----------|--------|
| Reload | `/api/config/config_entries/entry/{entry_id}/reload` | POST |
| Delete | `/api/config/config_entries/entry/{entry_id}` | DELETE |
| Create (init flow) | `/api/config/config_entries/flow` | POST |
| Create (submit) | `/api/config/config_entries/flow/{flow_id}` | POST |

## Implementation Components

### 1. Python Script: `python_scripts/ev9_connection_recovery.py`

Core recovery logic that:
- Reads credentials from secrets.yaml
- Finds the kia_uvo config entry (if exists)
- Attempts reload, checks result, recreates if needed
- Returns structured result for automation

### 2. Automation: `ev9_connection_watchdog`

- Triggers on sensor unavailable for 2 hours
- Checks cooldown and master toggle
- Calls Python script via `pyscript` or `shell_command`
- Sends notifications based on result

### 3. New Helpers

```yaml
input_boolean.ev9_connection_watchdog_enabled  # Master toggle (default: on)
input_text.ev9_last_recovery_attempt           # Timestamp of last attempt
input_text.ev9_last_recovery_result            # SUCCESS/FAILED + details
```

### 4. Secrets Addition

```yaml
# In secrets.yaml
kia_username: "andre.byrro@gmail.com"
kia_password: "your_kia_password_here"
kia_pin: "8560"
```

## Security Considerations

- Credentials stored in `secrets.yaml` (git-ignored)
- Python script reads secrets via HA config path
- Credentials never logged or included in notifications
- Standard HA security model applies

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Kia servers down extended period | Cooldown prevents retry spam; notifies once per 4 hours |
| Integration deleted manually | Script detects missing entry, creates fresh |
| Recreation fails (bad credentials) | Notifies "Manual intervention needed" with error |
| HA restarts during recovery | Re-evaluates on next trigger; cooldown prevents duplicate |
| Sensor briefly unavailable (<2h) | No action - must be unavailable for full 2 hours |

## Event Log Integration

All recovery events logged via `python_script.shift_event_log`:
- `WATCHDOG_START` - Recovery process initiated
- `WATCHDOG_RELOAD` - Reload attempted
- `WATCHDOG_RECREATE` - Full recreation attempted
- `WATCHDOG_SUCCESS` - Recovery completed successfully
- `WATCHDOG_FAILED` - Recovery failed, manual intervention needed

## Dashboard Updates

Add to Config tab "Automation Health" section:
- Watchdog enabled toggle
- Last recovery attempt timestamp
- Last recovery result

## File Changes

| File | Change |
|------|--------|
| `helpers.v2.3.yaml` | Add 3 new helpers |
| `automations.v2.3.yaml` | Add watchdog automation |
| `python_scripts/ev9_connection_recovery.py` | New recovery script |
| `lovelace.kia-ev9.v2.3.yaml` | Add watchdog status to dashboard |
| `secrets.yaml` | Add Kia credentials |
| `CLAUDE.md` | Document v2.3 changes |

## Notification Examples

### Recovery Starting
```
Title: EV9 Connection Recovery
Message: Kia integration has been unavailable for 2+ hours.
         Attempting automatic recovery...
```

### Reload Succeeded
```
Title: EV9 Connection Restored
Message: Integration reloaded successfully.
         Vehicle data should update shortly.
```

### Recreation Succeeded
```
Title: EV9 Connection Restored
Message: Integration was recreated successfully.
         Vehicle data should update in 2-3 minutes.
```

### Recovery Failed
```
Title: EV9 Connection FAILED
Message: Automatic recovery failed after reload and recreation attempts.
         Manual intervention required.
         Error: [error details]
Push: critical, time-sensitive
```

## Testing Plan

1. Verify helpers created correctly
2. Manually set sensor to unavailable (via dev tools) to test trigger
3. Test reload path by temporarily breaking token
4. Test recreation path by deleting integration
5. Verify cooldown prevents rapid retries
6. Verify notifications arrive correctly
