# Jose (Vacuum) - Project Instructions

> **Inherits from:** [/Dev/CLAUDE.md](../../../CLAUDE.md) — Read root file for universal dev workflow (git sync, Chrome MCP, Tasks, /done)

## Overview

Jose is a **Dreame robot vacuum** integrated with Home Assistant via the **Ecovacs integration**. This project includes a dashboard, error logging, and **self-healing connection recovery**.

## File Structure

```
jose/
├── CLAUDE.md                       # This file - project instructions
├── requirements.md                 # Functional requirements document
├── lovelace.jose_vacuum.json       # Dashboard layout
├── jose_vacuum_package.yaml        # Error logging automation (local copy)
├── ecovacs_recovery_package.yaml   # Recovery package (local copy)
├── ecovacs_recovery.sh             # Recovery script (local copy)
└── sources.md                      # Reference links

ha-config/packages/
├── jose_vacuum_package.yaml        # ACTIVE: Error logging
├── ecovacs_recovery_package.yaml   # ACTIVE: Self-healing watchdog
└── integration_health.yaml         # ACTIVE: Health monitoring

ha-config/scripts/
└── ecovacs_recovery.sh             # ACTIVE: Integration recreation script
```

## Current Versions

| Component | Current Version | Last Updated |
|-----------|-----------------|--------------|
| Requirements | v1.0 | 2026-01-23 |
| Dashboard | v1.0 | 2026-01-23 |
| Recovery Package | v1.1 | 2026-01-24 |
| Health Monitoring | v1.0 | 2026-01-24 |

---

## Self-Healing System (v1.1)

### How It Works

Jose has a **tiered recovery system** that automatically reconnects when the Ecovacs cloud integration goes offline:

```
Tier 1: Reload (after 10 min offline)
    ↓ (if failed, wait 1 hour)
Tier 2: Delete + Recreate (after reload fails)
    ↓ (if failed, wait 1 hour)
Tier 3+: Notify only (cloud may be down)
```

### State Machine

```
idle → recovering → (idle|failed)
```

### Recovery Helpers

| Helper | Purpose |
|--------|---------|
| `input_boolean.ecovacs_recovery_enabled` | Master toggle for watchdog |
| `input_text.jose_recovery_state` | Current state: idle/recovering/failed |
| `input_text.jose_last_recovery_result` | Last recovery result with timestamp |
| `input_number.ecovacs_recovery_attempts` | Counter for tiered recovery |
| `input_datetime.ecovacs_last_recovery` | Timestamp for cooldown tracking |
| `input_text.ecovacs_entry_id` | Stored config entry ID |

### Event Log Messages

All recovery events use the `WATCHDOG_` prefix:

| Event | Meaning |
|-------|---------|
| `WATCHDOG_START` | Recovery initiated |
| `WATCHDOG_RELOAD` | Attempting config entry reload |
| `WATCHDOG_RELOAD_FAILED` | Reload didn't restore connectivity |
| `WATCHDOG_RECREATE` | Full integration recreation starting |
| `WATCHDOG_SUCCESS` | Recovery completed successfully |
| `WATCHDOG_FAILED` | Recovery failed, manual intervention needed |
| `WATCHDOG_RETRY` | Repeated attempt (cloud likely down) |

### Required secrets.yaml Entries

```yaml
# Dreame/Ecovacs credentials
dreame_username: "your_email@example.com"
dreame_password: "your_password"
ecovacs_country: "us"

# HA API token for recovery script
ha_long_lived_token: "your_long_lived_token"
```

### Manual Recovery

If auto-recovery fails, manually recreate the integration:

1. Go to Settings → Integrations
2. Find Ecovacs, click three dots → Delete
3. Click "Add Integration" → Ecovacs
4. Enter your Dreame credentials
5. The watchdog will auto-update the entry ID on next HA restart

---

## Entity Inventory

### Primary Entities

| Entity ID | Type | Description |
|-----------|------|-------------|
| `vacuum.jose` | Vacuum | Main control entity |
| `sensor.jose_battery` | Sensor | Battery level (watchdog target) |
| `sensor.jose_error` | Sensor | Current error message |
| `sensor.jose_area` | Sensor | Area cleaned this session |
| `sensor.jose_duration` | Sensor | Duration of current session |

### Recovery Entities

| Entity ID | Type | Description |
|-----------|------|-------------|
| `input_boolean.ecovacs_recovery_enabled` | Toggle | Enable/disable watchdog |
| `sensor.jose_integration_status` | Sensor | online/stale/offline |

---

## Dashboard

**URL**: `/jose-vacuum/jose`

### Layout (2-column, responsive)

**Left Column (Act)**:
- Primary vacuum controls (Start/Stop/Home/Locate)
- Status grid (Battery, Station, Mop, Error)
- Session metrics
- Quick actions
- Error history

**Right Column (Observe)**:
- Lifetime statistics
- Consumables gauges
- Live map

---

## Automations

| Automation | ID | Purpose |
|------------|-----|---------|
| Jose: Connection Watchdog | `jose_connection_watchdog` | Tiered recovery on disconnect |
| Jose: Reset Recovery Counter | `jose_reset_recovery_counter` | Reset on successful reconnect |
| Jose: Update Entry ID | `jose_update_entry_id` | Store entry ID on HA start |
| Jose Vacuum Log Errors | `jose_vacuum_log_error_messages` | Error FIFO logging |

---

## Troubleshooting

### Integration Goes Offline Frequently

1. Check Ecovacs cloud status (try native app)
2. Verify secrets.yaml credentials are correct
3. Check `/config/logs/ecovacs_recovery.log` for errors
4. Ensure `input_boolean.ecovacs_recovery_enabled` is ON

### Recovery Script Fails

1. SSH to HA and test manually:
   ```bash
   bash /config/scripts/ecovacs_recovery.sh
   ```
2. Check log output for API errors
3. Verify `ha_long_lived_token` is valid
4. Ensure credentials work in native Ecovacs/Dreame app

### Entry ID Issues

The entry ID is auto-updated on HA startup. If you manually recreated the integration:
1. Restart Home Assistant
2. Or manually update `input_text.ecovacs_entry_id` with the new ID

---

## Related Documentation

- [Ecovacs Integration](https://www.home-assistant.io/integrations/ecovacs/)
- [Self-Healing Standard](../docs/plans/2026-01-24-self-healing-standard-design.md)
- [Integration Health Dashboard](../ha-config/packages/integration_health.yaml)
