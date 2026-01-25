# Home Assistant State Audit
**Date:** 2026-01-24
**Purpose:** Document current state before Phase 0 remediation
**Authority:** HA-FIX-PLAN.md, CLAUDE.md

---

## 1. Executive Summary

| Category | Status | Severity |
|----------|--------|----------|
| Split-brain configuration | CONFIRMED | HIGH |
| Multiple EV9 packages | INTENTIONAL (additive) | LOW |
| Patio AC package not loaded | CONFIRMED | HIGH |
| Package boundary violations | CONFIRMED | MEDIUM |
| HAL violations | CONFIRMED | MEDIUM |
| Dashboard split-brain | CONFIRMED | MEDIUM |
| Missing critical automations | CONFIRMED | HIGH |

---

## 2. Configuration Structure

### 2.1 Root Configuration (`ha-config/configuration.yaml`)
- **Packages**: `!include_dir_named packages` (loads all YAML in packages/)
- **Automations**: `!include automations.yaml` (UNVERSIONED)
- **Scripts**: `!include scripts.yaml` (UNVERSIONED)
- **Lovelace**: `mode: storage` (UI-managed, not YAML)
- **Only YAML dashboard**: `wyze_cameras.yaml`

### 2.2 File Line Counts
| File | Lines | Status |
|------|-------|--------|
| `automations.yaml` (unversioned) | 1,452 | ACTIVE (includes EV9) |
| `scripts.yaml` (unversioned) | 180 | ACTIVE |
| `automations.v2.9.yaml` (versioned) | 895 | NOT LOADED |
| `automations.v1.3.yaml` (versioned) | 490 | NOT LOADED |
| `scripts.v2.5.yaml` (versioned) | 276 | NOT LOADED |

**FINDING:** Versioned files exist but are NOT referenced by configuration.yaml

---

## 3. Packages Inventory

### 3.1 Loaded Packages (`ha-config/packages/`)
| Package | Size | Purpose | Notes |
|---------|------|---------|-------|
| `daikin.yaml` | 13,614 | Daikin integration | Contains automations + helpers |
| `ev9_v1_4.yaml` | 4,598 | EV9 helpers v1.4 | Helpers only (additive) |
| `ev9_v2_0.yaml` | 2,639 | EV9 helpers v2.0 | Helpers only (additive) |
| `ev9_v2_2.yaml` | 2,714 | EV9 helpers v2.2 | Helpers only (additive) |
| `ev9_v2_4.yaml` | 1,832 | EV9 helpers v2.4 | Helpers only (additive) |
| `jose_vacuum_package.yaml` | 2,505 | Jose vacuum | Complete package |
| `ecovacs_recovery_package.yaml` | 7,610 | Ecovacs recovery | Complete package |

**FINDING:** EV9 packages are ADDITIVE (helpers only) - NOT a conflict issue!

### 3.2 Unloaded Packages (Not in `ha-config/packages/`)
| Location | Files | Status |
|----------|-------|--------|
| `packages/patio_ac/patio_ac.yaml` | 1 | NOT LOADED - should be in ha-config/packages/ |

---

## 4. Automation Coverage

### 4.1 Main automations.yaml Content
- **Total automation IDs:** 37
- **EV9/Kia references:** 267 occurrences
- **Patio AC automations:** 0 (MISSING)
- **Daikin automations:** 0 (may be in package)
- **Uptime/health automations:** 0 (MISSING)

### 4.2 Critical Missing Systems
| System | Expected Location | Status |
|--------|-------------------|--------|
| Patio AC automations | automations.yaml or package | MISSING |
| Daikin maintenance alerts | automations.yaml or package | Needs verification |
| Uptime Kuma integration | automations.yaml | MISSING |

---

## 5. Dashboard Inventory

### 5.1 UI Storage Dashboards (`.storage/lovelace.*`)
| Dashboard | Type | Notes |
|-----------|------|-------|
| `lovelace` (default) | storage | Main dashboard |
| `lovelace.homelab` | storage | Homelab monitoring |
| `lovelace.kia_ev9` | storage | EV9 dashboard |
| `lovelace.patio_ac` | storage | Patio AC dashboard |
| `lovelace.notifications_logs` | storage | Logs/notifications |

### 5.2 YAML Dashboard Files
| File | Referenced | Status |
|------|------------|--------|
| `dashboards/wyze_cameras.yaml` | YES | Active |
| `dashboards/patio_ac_control.v1.8.yaml` | NO | ORPHANED |
| `dashboards/patio_ac_control.v1.10.yaml` | NO | ORPHANED |
| `dashboards/patio_ac_control.v1.11.yaml` | NO | ORPHANED |

**FINDING:** Only `wyze_cameras.yaml` is referenced. Patio AC dashboard YAMLs are dead files.

---

## 6. Package Boundary Violations

### 6.1 Root configuration.yaml Helper Definitions
The following should be moved to feature packages:

**Patio AC Helpers (lines 130-200+):**
- `input_select.patio_ac_reason`
- `input_boolean.patio_ac_manual_override`
- `input_boolean.patio_ac_compressor_cooldown`
- (and more...)

**Falco/Monitoring Helpers:**
- `input_select.falco_event_filter`

**Plex Priority Helpers:**
- `input_select.plex_io_class`
- `input_select.qbit_io_class`

**EV9 Helpers:**
- `input_select.ev9_charging_current`

### 6.2 Conflict Potential
The `packages/patio_ac/patio_ac.yaml` file defines:
- `input_boolean.patio_ac_manual_override`
- `input_boolean.patio_ac_compressor_cooldown`

These SAME helpers are defined in root configuration.yaml, creating potential conflict if package is loaded.

---

## 7. HAL Violations

### 7.1 Direct Hardware Entity References
| Entity ID | Location | Issue |
|-----------|----------|-------|
| `climate.150633095083490_climate` | configuration.yaml (google_assistant) | Hardware-derived ID |
| `lock.ev9_door_lock` | (need to verify) | May be hardware-derived |

---

## 8. Development vs Deployed Files

### 8.1 Kia EV9
| Type | Development Location | Deployed Location |
|------|---------------------|-------------------|
| Automations | `kia-ev9/automations.v2.6.yaml` | `ha-config/automations.yaml` |
| Helpers | `kia-ev9/helpers.v2.6.yaml` | `ha-config/packages/ev9_v*.yaml` |
| Scripts | `kia-ev9/scripts.v2.5.yaml` | `ha-config/scripts.yaml` |
| Dashboard | `kia-ev9/lovelace.*.json` | `.storage/lovelace.kia_ev9` |

### 8.2 Patio AC
| Type | Development Location | Deployed Location |
|------|---------------------|-------------------|
| Package | `packages/patio_ac/patio_ac.yaml` | NOT DEPLOYED |
| Control | `patio-ac/patio_ac_control.v1.20.yaml` | NOT DEPLOYED |
| Dashboard | `patio-ac/lovelace.patio_ac.v1.17.json` | `.storage/lovelace.patio_ac` |

---

## 9. Remediation Priority

### HIGH Priority (Phase 0)
1. **Fix Patio AC package loading** - Critical system not functioning
2. **Resolve helper conflicts** - Remove duplicates from root config
3. **Point to versioned files** - Establish clear version history

### MEDIUM Priority (Phase 1)
4. **Verify Daikin automations** - Confirm maintenance alerts are active
5. **Document dashboard source of truth** - Choose UI or YAML per dashboard

### LOW Priority (Phase 2+)
6. **HAL migration** - Create proxy entities for hardware IDs
7. **Naming normalization** - Follow `area_room_device_modifier` schema

---

## 10. Rollback Artifacts

### Required Before Any Changes
- [ ] Git baseline tag: `git tag -a "baseline-2026-01-24" -m "Before Phase 0 remediation"`
- [ ] File backup: `tar -czf ha-config-backup-2026-01-24.tgz ha-config/`
- [ ] HA backup (if accessible via SSH)

### Rollback Commands
```bash
# Revert to baseline
git checkout baseline-2026-01-24 -- ha-config/

# Or restore from tar
tar -xzf ha-config-backup-2026-01-24.tgz
```

---

## 11. Next Steps

1. Create git baseline tag
2. Execute Phase 0.2: Consolidate EV9 packages (or mark as intentional additive)
3. Execute Phase 0.3: Deploy patio_ac package to ha-config/packages/
4. Execute Phase 0.4: Update configuration.yaml to use versioned files
5. Execute Phase 0.5: Document dashboard source of truth decision

---

*Audit generated by Claude Code following CLAUDE.md execution discipline*
