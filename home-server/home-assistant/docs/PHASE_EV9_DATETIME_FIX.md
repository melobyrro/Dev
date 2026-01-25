# EV9 Datetime Comparison Fix
**Date:** 2026-01-23
**Status:** RESOLVED

---

## Problem

Recurring warnings every minute:
```
WARNING [homeassistant.components.automation.ev9_timeout_lock_check]
EV9: Timeout Lock Check: Error in 'condition' evaluation

ERROR [homeassistant.components.template.template_entity]
TemplateError('TypeError: can't subtract offset-naive and offset-aware datetimes')
```

---

## Root Cause

The `as_datetime()` function returns an offset-naive datetime, while `now()` returns an offset-aware datetime. Subtracting them directly causes a TypeError.

**Affected Code:**
```jinja
{% set unlocked_time = as_datetime(unlocked_since) %}
{% set elapsed_min = ((now() - unlocked_time).total_seconds() / 60) | int %}
```

---

## Solution

Wrapped `as_datetime()` with `as_local()` to convert to an offset-aware datetime:

```jinja
{% set unlocked_time = as_local(as_datetime(unlocked_since)) %}
{% set elapsed_min = ((now() - unlocked_time).total_seconds() / 60) | int %}
```

**Files Modified:**
1. `configuration.yaml` - Template sensor `sensor.ev9_timeout_countdown`
2. `automations.yaml` - Automation `ev9_timeout_lock_check`

---

## Verification

```bash
# No more warnings after fix
docker logs --since 2m homeassistant 2>&1 | grep -E 'ev9_timeout|offset-naive'
# Result: (empty - no warnings)
```

---

## Related

This is a common issue in Home Assistant when comparing datetime objects. The fix ensures timezone consistency.

---

## EV9 Datetime Fix: RESOLVED
