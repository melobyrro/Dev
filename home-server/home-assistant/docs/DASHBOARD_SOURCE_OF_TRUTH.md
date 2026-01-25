# Dashboard Source of Truth
**Last Updated:** 2026-01-24
**Authority:** HA-FIX-PLAN.md Phase 0.5

---

## Decision

All dashboards are **UI-managed** (storage mode) except where YAML mode is explicitly required.

**Rationale:**
- UI mode allows visual editing through the HA interface
- Changes are immediately visible without reload
- Most users prefer the drag-and-drop experience
- YAML mode reserved only for dashboards requiring version control or programmatic generation

---

## Active Dashboards

### UI-Managed (Storage Mode)
These dashboards are stored in `.storage/lovelace.*` on the live HA instance (not in repo).

| Dashboard | Storage Key | Purpose |
|-----------|-------------|---------|
| Default | `lovelace` | Main home dashboard |
| Homelab | `lovelace.homelab` | Server/container monitoring |
| Kia EV9 | `lovelace.kia_ev9` | Vehicle status and controls |
| Patio AC | `lovelace.patio_ac` | AC automation controls |
| Notifications/Logs | `lovelace.notifications_logs` | Event logs and alerts |

**Export Pattern:** When major changes are made to UI dashboards, export a snapshot to:
- `<feature-dir>/lovelace.<name>.v<X.Y>.json`

Example: `kia-ev9/lovelace.kia_ev9.v2.5.json`

### YAML-Managed
These dashboards are defined in version-controlled YAML files.

| Dashboard | Config Key | File | Purpose |
|-----------|------------|------|---------|
| Wyze Cameras | `wyze-cameras` | `dashboards/wyze_cameras.yaml` | Camera feeds (RTSP) |

---

## Archived/Orphaned Files

The following YAML files in `dashboards/` are **not referenced** by `configuration.yaml` and have been superseded by the UI-managed Patio AC dashboard:

| File | Status | Action |
|------|--------|--------|
| `patio_ac_control.v1.8.yaml` | Orphaned | Moved to `.archive/` |
| `patio_ac_control.v1.10.yaml` | Orphaned | Moved to `.archive/` |
| `patio_ac_control.v1.11.yaml` | Orphaned | Moved to `.archive/` |

---

## Development Workflow

### For UI Dashboards
1. Make changes via HA UI
2. When stable, export JSON snapshot to feature directory
3. Version the export: `lovelace.<name>.v<X.Y>.json`

### For YAML Dashboards
1. Edit the YAML file directly
2. Reload dashboards in HA (Developer Tools > YAML > Reload)
3. Version bump if breaking changes

---

## Future Consideration

If a dashboard needs to be converted from UI to YAML mode:
1. Export current state from HA UI
2. Convert to YAML format
3. Add to `lovelace.dashboards` in `configuration.yaml`
4. Remove from `.storage/` on live instance

---

*Document created as part of HA-FIX-PLAN Phase 0 remediation*
