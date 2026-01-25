# Phase 0 Baseline Capture
**Date:** 2026-01-23
**Purpose:** Establish ground truth before HA-FIX-PLAN implementation

---

## 1) Local Repository State

**Working Directory:** `/Users/andrebyrro/Dev/home-server/home-assistant`
**Branch:** `main`
**Commit Hash:** `140c68e7d628331110511a011281033a5557b21e`
**Git Status:** Clean (many untracked files, no staged changes)

---

## 2) Production HA State

**Container:** `homeassistant`
**Image:** `ghcr.io/home-assistant/home-assistant:stable`
**Status:** Up 10+ hours (healthy)
**Config Check:** PASSED (Successful config)

### Known Active Issues

| Issue | Status | Evidence |
|---|---|---|
| BUG-1: NotImplementedError | NOT OBSERVED in last 1h | No log entries |
| BUG-3: Duplicate unique_id | NOT OBSERVED in last 1h | No log entries |
| BUG-6: Oversized attributes | ACTIVE | Recurring warnings for `sensor.falco_api_events`, `sensor.hardlink_other_status`, `sensor.filebot_other_status` |

### Entity ID Status (BUG-5)

| Entity | Reference Count |
|---|---:|
| `climate.150633095083490_climate` (OLD) | 1677 |
| `climate.patio_ac` (NEW) | 44 |

**Status:** Mixed - partial migration, most references still use old ID.

---

## 3) Packages Structure

**Location:** `/mnt/ByrroServer/docker-data/homeassistant/config/packages/`
**Include:** `!include_dir_named packages` (line 2 of configuration.yaml)

### Current Packages Tree

```
packages/
├── _archive/
├── daikin.yaml
├── ecovacs_recovery_package.yaml
├── ev9_v1_4.yaml          # EV9 v1.4
├── ev9_v2_0.yaml          # EV9 v2.0
├── ev9_v2_2.yaml          # EV9 v2.2
├── ev9_v2_4.yaml          # EV9 v2.4  <-- MULTIPLE VERSIONS LOADED!
├── jose_vacuum_package.yaml
└── patio_ac/
    └── patio_ac.yaml      # 74KB consolidated package
```

**Issue:** 4 EV9 package versions are loaded simultaneously (v1.4, v2.0, v2.2, v2.4)

---

## 4) Dashboard Sources

**Default Mode:** `storage` (UI-stored)

### UI-Stored Dashboards (in .storage/)

| Dashboard | Canonical File | Notes |
|---|---|---|
| Default | `lovelace` | Main dashboard |
| Automations | `lovelace.dashboard_automations` | |
| Daikin | `lovelace.dashboard_daikn` | Note: typo in filename |
| Room | `lovelace.dashboard_room` | |
| Google Log | `lovelace.google_log` | |
| Homelab | `lovelace.homelab` | |
| Jose Vacuum | `lovelace.jose_vacuum` | |
| Kia EV9 | `lovelace.kia_ev9` | Many backup versions |
| Map | `lovelace.map` | |
| Notifications | `lovelace.notifications_logs` | |
| Patio AC | `lovelace.patio_ac` | Many backup versions |
| Shield TV | `lovelace.shield_tv` | |
| Temperature | `lovelace.temperature_snesors` | Note: typo in filename |

### YAML-Mode Dashboards

| Dashboard | File Path |
|---|---|
| Wyze Cameras | `dashboards/wyze_cameras.yaml` |

---

## 5) Rollback Artifacts

### Git Baseline

```bash
# Current commit (baseline)
git rev-parse HEAD
# Output: 140c68e7d628331110511a011281033a5557b21e

# Revert to baseline
git reset --hard 140c68e7d628331110511a011281033a5557b21e
```

### HA Backup

**Required before Phase 1:** Create full HA backup via Supervisor or manual tarball.

```bash
# Manual backup command
ssh byrro@192.168.1.11 "tar -czf /mnt/ByrroServer/backups/ha-config-$(date +%Y%m%d-%H%M%S).tgz /mnt/ByrroServer/docker-data/homeassistant/config/"
```

---

## 6) Phase 0 Gate Status

| Gate | Status | Evidence |
|---|---|---|
| Baseline config check captured | PASS | Config check output shows "Successful config" |
| Baseline log tail captured | PASS | Logs captured, oversized attribute warnings documented |
| Dashboard source-of-truth known | PASS | UI-storage mode documented, 13 UI dashboards, 1 YAML dashboard |
| Packages structure documented | PASS | Tree documented, EV9 version overlap identified |
| Git repo clean | PASS | No staged changes |
| Rollback capability verified | PENDING | Need to create HA backup before Phase 1 |

---

## 7) Key Findings Summary

### Confirmed Issues

1. **BUG-5 (Entity ID):** 1677 references to old opaque ID vs 44 to semantic ID
2. **BUG-6 (Oversized attributes):** 3 sensors generating recurring warnings every 5 minutes
3. **EV9 Version Overlap:** 4 versions loaded simultaneously

### Already Addressed (Not Observed)

1. **BUG-1 (NotImplementedError):** No occurrences in recent logs
2. **BUG-3 (Duplicate unique_id):** No warnings in recent logs

### Architecture Status

- Packages architecture is **enabled and in use**
- Patio AC is consolidated into single package
- EV9 needs version consolidation
- Most dashboards are UI-stored (split-brain risk)

---

## 8) Next Steps (Phase 1)

1. Create HA backup before any changes
2. Validate EV9 version overlap impact
3. Begin entity ID standardization (BUG-5)

---

**Phase 0 Complete:** Ready for Phase 1 pending backup creation.
