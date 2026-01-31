# Central Automations — Requirements

**Version:** 1.0
**Last Updated:** 2026-01-31
**Owner:** Andre

---

## 1) Purpose

This folder contains **cross-feature automations** that don't belong to a specific feature:
- Dashboard-related automations
- Location tracking (Dawarich)
- Plex media automations
- System-level automations

---

## 2) Scope

| File | Purpose | Feature |
|------|---------|---------|
| `configuration.yaml` | Legacy aggregated config (reference) | Multiple |
| `dashboard_automations.v3.yaml` | Dashboard UI automations | Dashboard |
| `dawarich_automations.yaml` | Location tracking | Dawarich |
| `plex/` | Plex media automations | Plex |

---

## 3) Guidelines

### Creating New Automations

1. **Feature-specific automations** → Go in the feature folder, NOT here
2. **Cross-feature automations** → Create in this folder with clear naming
3. **Follow naming convention:** `<category>_automations.v<X>.<Y>.yaml`

### Automation Visibility

Per Section 4.9 of the constitution, all automations here must be visible in the **Central Automations Dashboard** at `ha-config/dashboards/automations_central.v1.0.yaml`.

---

## 4) Migration Notes

- Legacy `configuration.yaml` contains old aggregated automations
- Active automations are being migrated to feature packages
- This folder is transitioning to **cross-feature only** automations

---

## 5) Safety

| Guardrail | Description |
|-----------|-------------|
| No duplication | Automations must exist in ONE location only |
| Feature isolation | Feature-specific logic must NOT be here |
| Documentation | Each automation must have `description:` field |

---

## 6) Rollback

**Git revert:** `git revert <commit>`
**Archive:** Old versions should go to `.archive/` when superseded
