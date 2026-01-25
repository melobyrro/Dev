# Phase 4: Patio AC Split-Brain Configuration - FIXED
**Date:** 2026-01-23
**Status:** RESOLVED

---

## Problem

Patio AC helpers and template sensors were defined in BOTH:
1. `configuration.yaml` (legacy location)
2. `packages/patio_ac/patio_ac.yaml` (canonical package)

This caused:
- "duplicate key 'name'" errors for helpers (input_boolean, input_number, etc.)
- "unique_id already exists" errors for template sensors

---

## Solution Summary

### 1. Pre-existing YAML Corruption Fixed

**Stray Trivy Lines Removed:**
- Lines `- sensor.trivy_api_summary` and `- sensor.trivy_api_vulnerabilities` were incorrectly placed inside a template sensor definition
- Removed from line 3080-3081

**Missing Trigger Block Added:**
- The `patio_ac_activity` trigger-based template sensor was missing its trigger definition
- Added `- trigger:` and `- platform: homeassistant` before `event: start`

### 2. Duplicate Helper Definitions Removed (75 entries)

| Helper Type | Entries Removed |
|-------------|----------------:|
| input_select | 1 (patio_ac_reason) |
| input_boolean | 20 |
| input_text | 11 |
| input_datetime | 12 |
| timer | 6 |
| input_number | 23 |
| input_button | 2 |
| **Total** | **75** |

### 3. Duplicate Template Sensors Removed (28 entries)

**Binary Sensors Removed (7):**
- patio_ac_automation_cool_running
- patio_ac_automation_dry_running
- patio_ac_manual_cool_running
- patio_ac_manual_dry_running
- patio_ac_running
- patio_ac_mode_cool
- patio_ac_mode_dry

**Sensors Removed (21):**
- patio_ac_last_evaluated
- patio_ac_reason_friendly
- patio_ac_runtime_* (multiple)
- patio_ac_daily_limit_display
- patio_ac_heat_duration_display
- patio_ac_override_state
- patio_ac_mode_numeric
- And more...

**Sensors Kept (unique to configuration.yaml):**
- patio_ac_event_log
- patio_ac_total_all_runtime
- patio_ac_activity

---

## Verification

```bash
# Count of patio_ac helper definitions (should be 0)
grep -n '^  patio_ac' /config/configuration.yaml | wc -l
# Result: 0

# Count of duplicate unique_id errors (should be 0)
docker logs --since 60s homeassistant 2>&1 | grep 'already exists' | wc -l
# Result: 0

# HA container health
docker ps | grep homeassistant
# Result: healthy
```

---

## Before/After

| Metric | Before | After |
|--------|--------|-------|
| patio_ac references in configuration.yaml | 170 | 67 |
| patio_ac helper definitions in configuration.yaml | 75 | 0 |
| patio_ac template sensors in configuration.yaml | 30 | 3 |
| Duplicate unique_id errors | 28 | 0 |
| "duplicate key 'name'" errors | Multiple | 0 |

---

## Rollback

```bash
# Backup location
/mnt/ByrroServer/backups/homeassistant/configuration.yaml.phase4-splitbrain-20260123-195949

# Restore command
sudo cp /mnt/ByrroServer/backups/homeassistant/configuration.yaml.phase4-splitbrain-20260123-195949 \
  /mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml
docker restart homeassistant
```

---

## Architecture Status

**Single Source of Truth: ACHIEVED**

The patio_ac package (`packages/patio_ac/patio_ac.yaml`) is now the canonical source for:
- All patio_ac helpers (input_boolean, input_number, input_select, input_text, input_datetime, timer, input_button)
- All patio_ac template sensors (except 3 unique ones in configuration.yaml)
- All patio_ac automations and scripts

---

## Phase 4: RESOLVED
