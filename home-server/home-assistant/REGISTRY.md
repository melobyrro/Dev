# Home Assistant Feature Registry

**Last Updated:** 2026-01-31
**Purpose:** Central index of all features, their locations, and active files.

---

## Feature Index

| Feature | Path | Dashboard | Automations | Scripts | Owner | Updated |
|---------|------|-----------|-------------|---------|-------|---------|
| Kia EV9 | `kia-ev9/` | `lovelace.kia_ev9.v2.10.yaml` | `automations.v2.8.yaml` | `scripts.v2.7.yaml` | Andre | 2026-01-30 |
| Patio AC | `patio-ac/` | `dashboards/patio_ac_control.v1.21.yaml` | `automations.v1.0.yaml` | — | Andre | 2026-01-28 |
| Daikin | `Daikin/` | `daikin_dashboard_deployed_v2.yaml` | `daikin_automations.yaml` | — | Andre | 2026-01-25 |
| Jose Vacuum | `jose/` | `lovelace.jose_vacuum.json` | — | — | Andre | 2026-01-20 |
| Homelab | `homelab/` | `lovelace.homelab.yaml` | — | — | Andre | 2026-01-15 |
| System Health | `ha-config/dashboards/` | `system_health.v1.0.yaml` | — | — | Andre | 2026-01-10 |
| Claude Config | `ha-config/dashboards/` | `claude_config.yaml` | — | — | Andre | 2026-01-23 |
| Wyze Cameras | `ha-config/dashboards/` | `wyze_cameras.yaml` | — | — | Andre | 2026-01-05 |
| Central Automations | `ha-config/dashboards/` | `automations_central.v1.0.yaml` | (aggregates orphans) | — | Andre | 2026-01-31 |

---

## Orchestrator Files (Root Config)

These files live at `ha-config/` and aggregate/include feature components:

| File | Version | Purpose |
|------|---------|---------|
| `configuration.yaml` | — | Main HA config, imports packages |
| `automations.v3.0.yaml` | v3.0 | Aggregated automations (cross-feature) |
| `scripts.v3.0.yaml` | v3.0 | Aggregated scripts (cross-feature) |
| `helpers.v1.0.yaml` | v1.0 | Global helpers |

---

## Packages

| Package | Path | Status |
|---------|------|--------|
| Patio AC | `ha-config/packages/patio_ac/` | Active |
| Claude Config Auditor | `ha-config/packages/claude_config_auditor/` | Active |

---

## Maintenance Notes

### Updating This Registry

1. **When to update:**
   - Adding a new feature
   - Changing a feature's active file versions
   - Archiving old versions
   - Moving files

2. **Verification command:**
   ```bash
   # Check all paths exist
   cd /path/to/home-assistant
   # Manual check: verify each path in table resolves
   ```

3. **Non-compliance indicators:**
   - Feature exists but not listed here
   - Path in table doesn't resolve to a file
   - Multiple versions shown (should be single active version)

---

## Known Issues (To Be Resolved)

> **Note:** The following items need cleanup to comply with CLAUDE.md File Organization Law (3.9):

- [ ] Patio AC: Multiple dashboard versions in `ha-config/dashboards/` (v1.10, v1.11, v1.21)
- [ ] Kia EV9: Multiple automation versions not archived (v2.0-v2.8 in main folder)
- [ ] Daikin: Dashboard has `_deployed_v2` naming instead of standard versioning
- [ ] Jose Vacuum: Dashboard is JSON format instead of YAML
- [ ] Central Automations dashboard: Not yet created

These will be addressed incrementally as features are touched.
