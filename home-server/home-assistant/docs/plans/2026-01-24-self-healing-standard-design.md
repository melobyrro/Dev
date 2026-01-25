# Self-Healing Integration Standard Design

**Date:** 2026-01-24
**Status:** Approved
**Author:** Claude + Andre

---

## Overview

This design establishes a standard pattern for self-healing cloud integrations in Home Assistant, plus a centralized health monitoring dashboard.

### Components

1. **Jose Self-Healing** - Automated recovery for Dreame vacuum integration
2. **Integration Health Dashboard** - Centralized monitoring for all integrations

---

## 1. Jose Self-Healing Architecture

### State Machine

Jose uses a simplified 3-stage state machine (compared to EV9's 5-stage, since no OTP is required):

```
idle → recovering → (idle|failed)
```

### Components

**1.1 Watchdog Automation** (`jose_connection_watchdog`)
- **Trigger**: `sensor.jose_battery` unavailable for 2 hours
- **Cooldown**: 4 hours between attempts (prevents spam during Dreame outages)
- **Action**: Calls recovery shell script

**1.2 Recovery Shell Script** (`jose_recovery.sh`)
- Reads credentials from `secrets.yaml`
- Deletes existing Dreame config entry via HA API
- Creates new config entry with stored credentials
- Returns success/failure

**1.3 Helpers**

| Helper | Purpose |
|--------|---------|
| `input_boolean.jose_watchdog_enabled` | Master toggle |
| `input_text.jose_recovery_state` | State: idle/recovering/failed |
| `input_text.jose_last_recovery_attempt` | Timestamp for cooldown |
| `input_text.jose_last_recovery_result` | SUCCESS/FAILED + details |

**1.4 Verification**
- After script runs, wait 2 minutes for integration init
- Check if `sensor.jose_battery` is available
- If yes → SUCCESS notification
- If no → FAILED notification (manual intervention needed)

### secrets.yaml Addition

```yaml
dreame_username: "your_email@example.com"
dreame_password: "your_password"
```

---

## 2. Integration Health Dashboard

### Purpose

A centralized view showing health status of all integrations, with proactive alerts before things break.

### Dashboard Location

New tab on Homelab dashboard or standalone at `/system-health/`

### Layout: Three Sections

**2.1 Status Grid** (Top)

Quick visual health check using colored chips:
- 🟢 Green = Online (entity available, updated < 30 min)
- 🟡 Yellow = Stale (entity available but not updated > 30 min)
- 🔴 Red = Offline (entity unavailable)

**2.2 Details Table** (Middle)

| Integration | Watchdog Entity | Last Updated | Recovery Mode | Last Recovery |
|-------------|-----------------|--------------|---------------|---------------|
| Kia EV9 | `sensor.ev9_ev_battery_level` | 3 min ago | Auto (OTP) | SUCCESS 01-22 |
| Jose | `sensor.jose_battery` | 5 min ago | Auto | Never |
| Daikin | `sensor.daikin_*` | 1 min ago | Manual | — |
| Midea AC | `climate.patio_*` | Now | Manual | — |

**2.3 Recovery Controls** (Bottom)
- Manual "Reload Integration" buttons for each
- Link to HA Settings → Integrations
- Recent recovery event log (last 5 events across all integrations)

### Template Sensor

```yaml
template:
  - sensor:
      - name: "Integration Health Summary"
        state: >
          {% set integrations = [
            ('ev9', 'sensor.ev9_ev_battery_level'),
            ('jose', 'sensor.jose_battery'),
            ('daikin', 'climate.living_room'),
            ('midea', 'climate.patio_ac')
          ] %}
          {% set offline = integrations | selectattr('1', 'is_state', 'unavailable') | list | count %}
          {{ 'healthy' if offline == 0 else offline ~ ' offline' }}
```

---

## 3. Shared Components (Reusable Standard)

### Purpose

Create a pattern that any future cloud integration can adopt.

### Standard Package Structure

```
packages/
  {integration}_recovery.yaml    # Watchdog + helpers
scripts/
  {integration}_recovery.sh      # Shell script for API calls
```

### Standardized Helper Naming Convention

| Helper | Pattern | Example (Jose) |
|--------|---------|----------------|
| Watchdog toggle | `input_boolean.{name}_watchdog_enabled` | `input_boolean.jose_watchdog_enabled` |
| Recovery state | `input_text.{name}_recovery_state` | `input_text.jose_recovery_state` |
| Last attempt | `input_text.{name}_last_recovery_attempt` | `input_text.jose_last_recovery_attempt` |
| Last result | `input_text.{name}_last_recovery_result` | `input_text.jose_last_recovery_result` |

### Standardized Automation ID Pattern

| Automation | Pattern |
|------------|---------|
| Watchdog | `{name}_connection_watchdog` |
| OTP receiver (if needed) | `{name}_otp_received` |
| OTP timeout (if needed) | `{name}_otp_timeout` |

### Recovery State Values (Standard)

| State | Meaning |
|-------|---------|
| `idle` | Normal operation |
| `recovering` | Recovery in progress |
| `awaiting_otp` | Waiting for OTP (cloud auth only) |
| `completing` | OTP received, finalizing |
| `failed` | Recovery failed, manual intervention needed |

### Event Log Message Prefixes (Standard)

All recovery events use `WATCHDOG_` prefix:
- `WATCHDOG_START` - Recovery initiated
- `WATCHDOG_SUCCESS` - Recovered successfully
- `WATCHDOG_FAILED` - Recovery failed
- `WATCHDOG_TIMEOUT` - OTP/response timeout
- `WATCHDOG_OTP_REQUESTED` - OTP email sent (if applicable)
- `WATCHDOG_OTP_RECEIVED` - OTP extracted (if applicable)

---

## 4. File Organization

### New Files

```
home-assistant/
├── ha-config/
│   ├── packages/
│   │   ├── jose_recovery.yaml          # Jose watchdog + helpers
│   │   └── integration_health.yaml     # Health dashboard sensors
│   ├── scripts/
│   │   └── jose_recovery.sh            # Jose recovery script
│   └── dashboards/
│       └── system_health.yaml          # Health dashboard (optional)
│
├── jose/
│   ├── CLAUDE.md                       # Add recovery docs
│   └── requirements.md                 # Add watchdog requirements
│
└── docs/
    └── plans/
        └── 2026-01-24-self-healing-standard-design.md  # This file
```

### configuration.yaml Addition

```yaml
shell_command:
  jose_recovery: "bash /config/scripts/jose_recovery.sh '{{ token }}' /config/secrets.yaml"
```

---

## 5. Implementation Plan

### Phase 1: Jose Self-Healing

| Step | Task | Files |
|------|------|-------|
| 1.1 | Add Dreame credentials to secrets.yaml | `secrets.yaml` |
| 1.2 | Create recovery shell script | `scripts/jose_recovery.sh` |
| 1.3 | Create recovery package (helpers + automation) | `packages/jose_recovery.yaml` |
| 1.4 | Add shell_command to configuration.yaml | `configuration.yaml` |
| 1.5 | Test: Manually trigger watchdog, verify recovery | — |
| 1.6 | Update jose/CLAUDE.md with recovery docs | `jose/CLAUDE.md` |

### Phase 2: Integration Health Dashboard

| Step | Task | Files |
|------|------|-------|
| 2.1 | Create health sensor package | `packages/integration_health.yaml` |
| 2.2 | Add offline alert automation | `packages/integration_health.yaml` |
| 2.3 | Create dashboard view (or add tab) | `dashboards/system_health.yaml` |
| 2.4 | Test: Verify all integrations appear correctly | — |

### Phase 3: Documentation

| Step | Task | Files |
|------|------|-------|
| 3.1 | Save this design document | `docs/plans/2026-01-24-self-healing-standard-design.md` |
| 3.2 | Update root CLAUDE.md with self-healing standard | `CLAUDE.md` |

---

## 6. Validation Checklist

- [ ] Jose watchdog triggers after 2 hours unavailable
- [ ] Recovery script successfully recreates integration
- [ ] 4-hour cooldown prevents recovery spam
- [ ] Health dashboard shows all integrations
- [ ] Alert fires when any integration offline >30 min
- [ ] EV9 existing self-healing still works

---

## Appendix: Comparison with EV9 Pattern

| Aspect | EV9 | Jose |
|--------|-----|------|
| Auth method | OAuth + OTP | Username/Password |
| State machine | 5-stage | 3-stage |
| OTP handling | Email via IMAP | Not needed |
| Recovery time | ~7 minutes | ~3 minutes |
| Complexity | High | Low |
