# Home Assistant Feature Registry

**Last Updated:** 2026-01-31
**Purpose:** Central index of all features, their locations, and active files.

---

## Feature Index

| Feature | Path | Requirements | Dashboard | Automations | Scripts | Owner | Updated |
|---------|------|--------------|-----------|-------------|---------|-------|---------|
| Kia EV9 | `kia-ev9/` | `requirements.md` | `lovelace.kia_ev9.v2.10.yaml` | `automations.v2.8.yaml` | `scripts.v2.7.yaml` | Andre | 2026-01-30 |
| Patio AC | `patio-ac/` | `REQUIREMENTS.md` | `dashboards/patio_ac.v1.21.yaml` | (in package) | (in package) | Andre | 2026-01-31 |
| Daikin | `Daikin/` | `REQUIREMENTS.md` | `daikin_dashboard_deployed_v2.yaml` | `daikin_automations.yaml` | — | Andre | 2026-01-25 |
| Jose Vacuum | `jose/` | `requirements.md` | `lovelace.jose_vacuum.json` | — | — | Andre | 2026-01-28 |
| Homelab | `homelab/` | `REQUIREMENTS.md` | `lovelace.homelab.yaml` | — | — | Andre | 2026-01-15 |
| Wyze Cameras | `wyze/` | `requirements.md` | `ha-config/dashboards/wyze_cameras.yaml` | — | — | Andre | 2026-01-23 |
| FPL Energy | `fpl-energy/` | `requirements.md` | — | — | — | Andre | 2025-01-19 |
| Dashboard Room | `dashboard_room/` | `REQUIREMENTS.md` | — | — | — | Andre | 2026-01-12 |
| Climate Sensors | `Climate Sensors/` | `REQUIREMENTS.md` | — | — | — | Andre | 2026-01-12 |
| Shield TV | `shield-tv/` | `REQUIREMENTS.md` | — | — | — | Andre | 2026-01-12 |
| Map | `map/` | `REQUIREMENTS.md` | — | — | — | Andre | 2026-01-12 |
| Notifications | `notifications/` | `REQUIREMENTS.md` | — | — | — | Andre | 2026-01-12 |
| Google Logs | `google-logs/` | `REQUIREMENTS.md` | — | — | — | Andre | 2026-01-12 |
| Central Automations | `automations/` | `REQUIREMENTS.md` | (TBD) | (aggregates) | — | Andre | 2026-01-31 |

---

## Orchestrator Files (Root Config)

These files live at `ha-config/` and aggregate/include feature components:

| File | Version | Purpose |
|------|---------|---------|
| `configuration.yaml` | — | Main HA config, imports packages |
| `automations.v3.0.yaml` | v3.0 | Aggregated automations (cross-feature) |
| `scripts.v3.0.yaml` | v3.0 | Aggregated scripts (cross-feature) |

---

## Packages (in ha-config/packages/)

| Package | File | Related Feature |
|---------|------|-----------------|
| Patio AC | `patio_ac.yaml` | `patio-ac/` |
| Daikin | `daikin.yaml` | `Daikin/` |
| Claude Config Auditor | `claude_config_auditor.yaml` | — |
| Jose Vacuum | `jose_vacuum_package.yaml` | `jose/` |
| Jose Schedule | `jose_schedule_v2_0.yaml` | `jose/` |
| EV9 | `ev9_v2_8.yaml` | `kia-ev9/` |
| System Entity Health | `system_entity_health.v1.0.yaml` | — |
| Automation Health | `automation_health.v1.0.yaml` | — |
| Integration Health | `integration_health.yaml` | — |
| Watchman | `watchman_config.v1.0.yaml` | — |
| Ecovacs Recovery | `ecovacs_recovery_package.yaml` | — |

---

## Automation Ownership Matrix

> **Rule:** Each automation MUST appear in exactly ONE dashboard's Automations tab. This prevents confusion about where to monitor/control each automation.

### Ownership Mapping

| Feature | Dashboard Path | Automation Prefixes | Automation Count | File Locations |
|---------|---------------|---------------------|------------------|----------------|
| Kia EV9 | `/kia-ev9` | `ev9_*` | 36 | `ha-config/automations.v3.0.yaml`, `kia-ev9/automations.v2.8.yaml` |
| Patio AC | `/patio-ac` | `patio_ac_*` | 30+ | `ha-config/packages/patio_ac.yaml` |
| Dawarich | `/dashboard-automations/dawarich` | `dawarich_*` | 8 | `automations/dawarich_automations.yaml` |
| System Health | `/system-health` | `system_health_*`, `integration_health_*`, `watchdog_*` | 20+ | `packages/system_entity_health.v1.0.yaml`, `packages/automation_health.v1.0.yaml`, `packages/integration_health.yaml` |
| Jose Vacuum | `/jose` | `jose_*`, `ecovacs_*` | 8+ | `packages/jose_schedule_v2_0.yaml`, `packages/ecovacs_recovery_package.yaml` |
| Daikin | `/daikin` | `daikin_*` | 6 | `Daikin/daikin_automations.yaml` |
| Wyze/Frigate | `/wyze-cameras` | `wyze_*`, `frigate_*` | 4 | `ha-config/automations.v3.0.yaml` |
| Homelab | `/homelab` | `netalertx_*`, `plex_*` | 4 | `ha-config/automations.v3.0.yaml` |
| Trackers (Reddit) | `/notifications-logs/trackers` | `tracker_*` | TBD | TBD |

### Automations Tab Implementation Status

| Dashboard | Has Automations Tab | Status |
|-----------|---------------------|--------|
| Kia EV9 | Yes | Complete |
| Patio AC | Yes | Complete |
| System Health | Yes | Complete |
| Jose Vacuum | Partial | Needs update |
| Daikin | No | TODO |
| Wyze Cameras | No | TODO |
| Homelab | No | TODO |
| Dawarich | Yes | Complete |
| Trackers | No | TODO |

### Notes

- **Central Automations Dashboard:** For cross-cutting automations that don't belong to a specific feature, a Central Automations dashboard is planned but not yet implemented.
- **Full Audit Details:** See `docs/HOME_ASSISTANT_AUDIT_OBSERVABILITY.md` for the complete observability audit findings and recommendations.
- **Automation Visibility Rule:** Per `CLAUDE.md` section 5.7, every automation must be visible in exactly ONE dashboard's Automations tab.

---

## Maintenance

### When to Update This Registry

- Adding a new feature
- Renaming or moving files
- Changing active versions
- Archiving old versions

### Verification

```bash
# Check requirements files exist
for f in kia-ev9/requirements.md patio-ac/REQUIREMENTS.md Daikin/REQUIREMENTS.md; do
  [ -f "$f" ] && echo "✓ $f" || echo "✗ MISSING: $f"
done
```

---

## Known Issues

- [ ] Multiple EV9 package versions in packages/ (should archive old ones)
- [ ] Daikin dashboard uses non-standard naming (`_deployed_v2`)
- [ ] Jose dashboard is JSON format, should convert to YAML
- [ ] Central Automations dashboard not yet created
