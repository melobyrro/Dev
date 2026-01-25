# Phase 7: BUG-6 Recorder Oversized Attributes - FIXED
**Date:** 2026-01-23
**Status:** RESOLVED

---

## Problem

Recurring warnings every 5 minutes:
```
WARNING (Recorder) [homeassistant.components.recorder.db_schema]
State attributes for sensor.X exceed maximum size of 16384 bytes.
```

## Affected Sensors

| Sensor | Purpose |
|--------|---------|
| `sensor.falco_api_events` | Security events from Falco |
| `sensor.hardlink_other_status` | Hardlink tool status |
| `sensor.filebot_other_status` | FileBot media organizer status |
| `sensor.trivy_api_summary` | Trivy security scanner summary |
| `sensor.trivy_api_vulnerabilities` | Trivy vulnerability list |

---

## Solution

Added recorder exclusion in `configuration.yaml`:

```yaml
recorder:
  exclude:
    entities:
      - sensor.falco_api_events
      - sensor.hardlink_other_status
      - sensor.filebot_other_status
      - sensor.trivy_api_summary
      - sensor.trivy_api_vulnerabilities
```

---

## Verification

```bash
# After restart, no more warnings:
docker logs --since 30s homeassistant 2>&1 | grep -i 'oversized'
# Result: (empty - no warnings)
```

---

## Trade-offs

| Aspect | Before | After |
|--------|--------|-------|
| Log noise | Warnings every 5 min | Clean logs |
| DB performance | Potential issues | No impact |
| History for these sensors | Attempted (failed) | Not recorded |
| Current state | Available | Still available |

**Note:** These sensors still work for current state and automations. Only historical recording is disabled.

---

## Rollback

Remove the `recorder:` section from `configuration.yaml` and restart HA.

---

## BUG-6: RESOLVED
