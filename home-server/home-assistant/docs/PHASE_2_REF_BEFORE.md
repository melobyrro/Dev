# Phase 2: REF BEFORE - Entity ID Standardization
**Date:** 2026-01-23
**Target:** Replace `climate.150633095083490_climate` with `climate.patio_ac`

---

## Entity Registry Status

| Entity ID | In Registry | Status |
|-----------|-------------|--------|
| `climate.patio_ac` | YES (2 refs) | ACTIVE - Already renamed |
| `climate.150633095083490_climate` | NO | Deprecated - needs cleanup |

**Finding:** Entity rename already completed in HA. Only YAML/dashboard references remain.

---

## Reference Counts (Before)

### Active Files (excluding backups)
- **Total active references:** 446

### YAML Files with Old ID
| File | Purpose |
|------|---------|
| `configuration.yaml` | Main config |
| `automations.v2.9.yaml` | Legacy automations |
| `scripts.v2.5.yaml` | Legacy scripts |
| `scripts_debug.yaml` | Debug scripts |
| `patio_ac_template.yaml` | Template sensors |
| `dashboards/patio_ac_control.v1.8.yaml` | Legacy dashboard |
| `dashboards/patio_ac_control.v1.10.yaml` | Legacy dashboard |
| `dashboards/patio_ac_control.v1.11.yaml` | Legacy dashboard |

### Active Dashboard Storage Files
| Dashboard | References |
|-----------|------------|
| `lovelace.patio_ac` | 1 |
| `lovelace.dashboard_room` | 1 |
| `lovelace.google_log` | 1 |
| `lovelace.notifications_logs` | 1 |

---

## Files to Update

### Priority 1: Active Dashboards (in .storage/)
1. `lovelace.patio_ac`
2. `lovelace.dashboard_room`
3. `lovelace.google_log`
4. `lovelace.notifications_logs`

### Priority 2: Active YAML (if still loaded)
1. `configuration.yaml`

### Priority 3: Legacy/Archive (low priority)
- `automations.v2.9.yaml`
- `scripts.v2.5.yaml`
- `dashboards/*.yaml`

---

## Rollback Plan

```bash
# Restore from backup
ssh byrro@192.168.1.11 "cd /mnt/ByrroServer/docker-data/homeassistant && \
  tar -xzf /mnt/ByrroServer/backups/homeassistant/config-TIMESTAMP.tar.gz"

# Restart HA
ssh byrro@192.168.1.11 "docker restart homeassistant"
```

---

## Acceptance Criteria

- [ ] Zero references to `climate.150633095083490_climate` in active files
- [ ] Config check passes
- [ ] No new log errors
- [ ] Patio AC dashboard renders correctly
