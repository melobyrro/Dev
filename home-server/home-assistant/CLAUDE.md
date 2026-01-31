# CLAUDE.md — Home Assistant Repository Constitution

> **Inherits from:** [/Dev/CLAUDE.md](../../CLAUDE.md) — Read root file for universal workflow (git sync, Chrome MCP, Tasks, /done)

**Last updated:** 2026-01-31 | **Status:** Binding

This document defines engineering standards for this Home Assistant repository. All rules marked with **[HARD]** are non-negotiable.

---

## 1) Definition of Done

A change is **not done** until all applicable gates pass.

### Configuration DoD
| Gate | Requirement |
|------|-------------|
| Config validity | YAML valid; HA config check passes |
| No new log debt | No new warnings/errors from this change |
| **[HARD] HAL Compliance** | No physical device IDs in automations (use Templates) |
| **[HARD] Naming Compliance** | Entities follow `area_room_device_modifier` schema |
| Reload safety | Prefer targeted reloads; restart only when required |
| No duplicates | No duplicate entity/automation IDs |

### UI DoD
| Gate | Requirement |
|------|-------------|
| Responsiveness | Works on mobile, tablet, desktop |
| Hierarchy | "Observe → Understand → Act" preserved |
| **[HARD] Read-Only Logs** | Log entities have `tap_action: none` |
| Alignment | Tables aligned, consistent units |

### Rollback DoD
| Gate | Requirement |
|------|-------------|
| Plan exists | Rollback steps documented before change |
| Artifact exists | Known-good backup exists before change |
| Verified | Rollback procedure tested |

---

## 2) Secrets **[HARD]**

No credentials, tokens, or personal data in git history, screenshots, or notes.

- **Allowed:** `secrets.yaml`, `.env` (gitignored)
- **Forbidden:** Committed YAML with secrets, screenshots with tokens/coordinates/SSIDs
- **Violation:** SEV-0 — rotate immediately

---

## 3) Execution Workflow (11 Steps)

1. **Find nearest REQUIREMENTS.md** — search upward from file being edited
2. **Identify feature boundary** — the folder containing all related files
3. **Capture baseline** — git status, logs, screenshots
4. **Plan + Risk** — write plan, identify regressions, define rollback
5. **Branch** — one task per branch
6. **Backup** — create backup artifacts
7. **Implement** — smallest possible change
8. **Static validation** — YAML check, config check, naming check
9. **Runtime validation** — reload, trace, check logs
10. **UI validation** — mobile/tablet/desktop via Chrome
11. **Document + Commit** — update REQUIREMENTS.md if behavior changed

**Rule:** If no REQUIREMENTS.md exists, create one before making behavior changes.

---

## 4) Architecture Standards

### 4.1 Packages
- Each feature is a self-contained package
- Root config is an orchestrator only — no logic
- **[HARD]** Every entity/automation defined exactly once

### 4.2 File Naming **[HARD]**
Convention: `{component}.v{major}.{minor}.yaml`

| Version | Meaning |
|---------|---------|
| Major | Breaking change (rename/remove entities, change contract) |
| Minor | Backward-compatible (add functionality) |

### 4.3 Active File Rule **[HARD]**
- Only ONE active version per component in any directory
- Old versions → `.archive/` immediately
- Forbidden: `_deployed`, `_backup`, `_old` suffixes, multiple versions

### 4.4 Naming Convention **[HARD]**
Schema: `area_room_device_modifier`
Example: `binary_sensor.basement_laundry_washer_status`

| Type | Prefix | Example |
|------|--------|---------|
| Helpers | `logic_` or `helper_` | `input_boolean.logic_house_guest_mode` |
| Automations | `area_` or `function_` | `automation.area_bedroom_circadian_lighting` |

### 4.5 Hardware Abstraction Layer (HAL) **[HARD]**
Automations must never target physical device IDs directly.
- Create Template Entities that proxy physical devices
- Swapping hardware = update template, not 50 automations

### 4.6 Modern Template Syntax **[HARD]**
Use modern `template:` integration format. Legacy `value_template:` in lists is forbidden.

### 4.7 Feature Registry
`REGISTRY.md` at repo root must list all features with paths, dashboards, and last-updated dates.

### 4.8 Dependencies
`DEPENDENCIES.md` at repo root must list custom cards and HACS integrations with pinned versions.

---

## 5) Automation Standards

### 5.1 Required Fields **[HARD]**
Every automation must have: `id`, `alias`, `description`, `mode`

### 5.2 Decision vs Actuation **[HARD]**
- **Decision** (compute intent) → `variables:`, `choose:`
- **Actuation** (side effects) → Scripts
- Scripts must be idempotent (safe to re-run)

### 5.3 Waits **[HARD]**
- **Never** use unbounded `wait_for_trigger`
- Short waits (< 5 min): use `timeout` + `continue_on_timeout: true`
- Long waits (> 5 min): use `input_datetime` deadline helpers

### 5.4 Idempotency
- Check current state before issuing commands
- Avoid `toggle`; use explicit `turn_on`/`turn_off`
- Guard destructive actions with confirmations

### 5.5 Mode Selection **[HARD]**
| Mode | Use when |
|------|----------|
| `single` | Action must not overlap |
| `restart` | New trigger replaces old run |
| `queued` | Every trigger matters in order (set `max`) |
| `parallel` | Independent runs are safe (set `max`) |

### 5.6 Self-Healing Triggers
Prefer state triggers over event triggers. State triggers catch up after HA restart.

### 5.7 Visibility **[HARD]**
Every automation must appear in exactly ONE dashboard's Automations tab.
- Feature automations → feature dashboard
- Cross-cutting automations → Central Automations dashboard

---

## 6) Dashboard Standards

### 6.1 Hierarchy **[HARD]**
Every dashboard follows: **Observe → Understand → Act**

1. **Observe** — What is happening? (status, graphs, indicators)
2. **Understand** — Why? (logic explanations, thresholds, conditions)
3. **Act** — What can I do? (controls, toggles, scripts)

### 6.2 Required Tabs **[HARD]**
| Tab | Purpose | Required |
|-----|---------|----------|
| Overview | Observe → Understand → Act | Yes |
| Automations | Table of all feature automations | Yes |
| Details | Metrics, history, trends | Optional |
| Settings | Configuration helpers | If applicable |

### 6.3 Read-Only Logs **[HARD]**
Log displays must use `tap_action: none`. If users can edit it, it's not a log.

### 6.4 Tables
Use `flex-table-card` for aligned data. No stacked entity cards pretending to be tables.

### 6.5 Responsiveness **[HARD]**
Must work on mobile, tablet, desktop. Critical controls visible without scrolling on mobile.

### 6.6 Single Source of Control
Settings editable in ONE place only. Everywhere else is display-only.

---

## 7) Validation Checklist

### Static
- [ ] YAML syntax valid
- [ ] HA config check passes
- [ ] No duplicate IDs
- [ ] Naming convention followed

### Runtime
- [ ] Reload/restart performed
- [ ] Trace run for affected automations
- [ ] Logs clean (no new errors)

### UI
- [ ] Mobile/tablet/desktop checked
- [ ] Observe → Understand → Act preserved
- [ ] Tables aligned

### Entity Quality **[HARD]**
New template sensors must have: `unique_id`, `availability`, correct `device_class`/`state_class`/`unit_of_measurement`

---

## 8) Git Discipline

- Clean baseline before starting
- One task per branch
- Atomic commits with imperative messages
- Backup artifacts before changes

---

## 9) Templates

See `docs/templates/` for:
- `REQUIREMENTS.md.template` — Feature requirements document
- `package.yaml.template` — Package structure
- `automation.yaml.template` — Compliant automation skeleton
- `script.yaml.template` — Idempotent script pattern
- `safe-wait.yaml.template` — Bounded wait pattern
- `automation-status-sensor.yaml.template` — Dashboard observability
- `flex-table-card.yaml.template` — Automations tab table
- `dashboard-section.yaml.template` — Observe → Understand → Act layout
- `read-only-log.yaml.template` — Non-editable log display

---

## 10) When Unsure

1. Find the nearest REQUIREMENTS.md
2. Default to the safer option: bounded waits, idempotent actions, reversible changes
