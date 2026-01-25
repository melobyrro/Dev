# HOME_ASSISTANT_MEGA_MASTER_PLAN.md
Last Updated: 2026-01-23

> This file is a consolidated union of unique content from:
> - HOME_ASSISTANT_MASTER_PLAN.md
> - fix_plan open.md
>
> Consult **CLAUDE.md** for the reusable Home Assistant engineering playbook and standards (dashboards, automations, logging, testing).

---

## Part A — Audit, Target State, and Roadmap (source: HOME_ASSISTANT_MASTER_PLAN.md)

### HOME_ASSISTANT_MASTER_PLAN.md
Last Updated: 2026-01-23

> **Authority**: All execution under this plan is governed by `CLAUDE.md`.
> Before any task: read `CLAUDE.md`, locate the nearest `REQUIREMENTS.md`, capture system state, and proceed one step at a time with validation gates.

#### 1. Purpose

This document is the single operational master plan for repairing, stabilizing, and evolving the Home Assistant ecosystem in production. It consolidates all findings from prior audits and plans into one authoritative reality and a phased remediation roadmap.

It answers four questions:
1. What is broken or drifting today?
2. Why it is risky or misleading?
3. What the intended end-state is (while keeping the versioned-file model canonical).
4. How to get there safely in production.

This plan removes split narratives and replaces them with a single source of truth.

#### 2. System Reality Snapshot (Consolidated)

##### Structural Drift
- Split-brain configuration exists between:
  - UI-stored dashboards and YAML files
  - Versioned patch files vs. active configuration
- It is unclear which logic is live for several features.
- Active canonical files are unversioned (`ha-config/automations.yaml`, `ha-config/scripts.yaml`), violating the versioned-file law.
- Feature logic and helpers live in root config instead of feature packages, violating package isolation.
- Dashboard YAMLs exist in `/config/dashboards/` (e.g., patio AC), but are not referenced by `configuration.yaml`.
- Package subdirectories (e.g., `packages/patio_ac/`) are ignored by `!include_dir_named`, leaving intended packages unloaded.
- Some automations exist in YAML but are not loaded; others are active but not represented in repo.
- Multiple versions of the same feature packages are loaded (EV9), increasing drift.

##### Behavioral Drift
- Critical automations appear documented but are not loaded (Patio AC, Daikin maintenance alerts).
- Fixed delays are used in automations (e.g., EV9 charge restart), bypassing safe wait patterns.

##### UX Drift
- Dashboards present editable surfaces that behave like logs.
- “Tables” are constructed from multiple cards and drift at breakpoints.
- Users cannot tell whether state reflects reality or a stale helper.
- Most dashboards are stored in `.storage`, so UI can diverge from repo truth.

##### Entity Fragility
- Hardware-derived entity IDs are referenced directly in automations and dashboards (HAL violation).
- Naming does not follow the `area_room_device_modifier` or `logic_`/`helper_` conventions.
- Renames or integration reloads risk silent breakage.

##### Observability Gaps
- No canonical “last decision”, “next run”, or “why” surfaces for critical systems.
- Errors are visible only in logs, not in UI.
- Automation health visibility is missing in EV9/Daikin/Patio dashboards.

#### 3. Risk Map

| Risk | Impact |
|------|--------|
| Silent automation failure | Systems appear protected but are inert |
| Split-brain dashboards | UI lies about system state |
| Editable logs | User can corrupt state |
| Unversioned canonical files | Rollback/audit ambiguity and accidental drift |
| Package boundary violations | Duplicate or conflicting definitions |
| Hard-coded entity IDs | Breakage on rename or hardware swap |
| Naked delays in automations | Race conditions and inconsistent outcomes |

#### 4. Target State (While Keeping Versioned Files Canonical)

- Versioned YAML files remain the primary source of truth:
  - `automations.vX.yaml`
  - `configuration.vX.yaml`
  - `scripts.vX.yaml`
  - `dashboard.vX.yaml`
- All active canonical files are versioned and named consistently.
- Feature logic lives inside feature packages; root config is orchestrator-only.
- HAL proxy entities exist for all hardware control surfaces.
- No hidden logic in UI-only storage.
- Every system exposes:
  - Last decision
  - Current intent
  - Next evaluation
  - Failure surface
- Dashboards:
  - Observe → Understand → Act
  - Logs are read-only
  - Tables are single-surface and breakpoint-stable
  - YAML exports exist in repo for every dashboard
- Automations:
  - Idempotent
  - Explicit concurrency
  - Deadbands and debouncing
  - Failure-aware scripts

#### 5. Phased Remediation Roadmap (Production Only)

##### Phase 0 — Stop Split-Brain
- Inventory all dashboards (UI vs YAML).
- Choose one canonical form per dashboard.
- Export UI dashboards into repo or delete dead YAML.
- Inventory unversioned canonical files in `ha-config/` and map to versioned targets.
- Result: one source of truth per surface.

##### Phase 1 — Restore Broken Systems
- Patio AC: ensure all automations are loaded and executing.
- Uptime/Watchdog systems: verify heartbeat paths.
- Daikin: load maintenance/fault alert automations.
- Add visible “last decision” and “error” sensors.
- Replace fixed-delay automation steps with bounded waits where safety-critical.

##### Phase 2 — Entity Sanitation
- Replace hardware-derived entity IDs with semantic names.
- Update all references.
- Document in an ENTITY_MAP.md per project.
- Introduce HAL proxy entities and migrate automations/scripts to target proxies.
- Normalize helper/entity naming to the schema in `CLAUDE.md`.

##### Phase 3 — Structural Cleanup
- Collapse dead or duplicated automations.
- Remove orphaned helpers.
- Normalize naming and IDs across versioned files.
- Move feature logic out of root config and into package boundaries.
- Retire unversioned `automations.yaml`/`scripts.yaml` in favor of versioned files.

##### Phase 4 — Dashboard Normalization
- Replace fake tables with single-surface tables.
- Remove all editable log surfaces and replace with read-only logbook/persistent sensors.
- Add “Why” and “Next” context cards.

##### Phase 5 — Reliability Layer
- Add failure notifications for all critical scripts.
- Add guard rails (cooldowns, locks, deadbands).
- Add visible state machines for complex systems.

Each phase:
- Follows `CLAUDE.md` execution rules.
- Has explicit validation gates.
- Requires proof before advancing.

#### 6. Execution Protocol

Every task under this plan MUST:
1. Load and obey `CLAUDE.md`.
2. Capture current state (git + HA health).
3. Execute ONE step.
4. Validate:
   - Config check
   - Logs
   - Traces
   - UI in Chrome MCP
5. Present evidence.
6. Await confirmation.

#### 7. Appendices (Source Material)

##### Appendix A — Current Live Config Issues (2026-01-23)
- `lovelace: mode: storage` is active; only `wyze_cameras.yaml` is configured in YAML mode.
- Multiple Lovelace dashboards are stored in `.storage` (`lovelace.homelab`, `lovelace.kia_ev9`, `lovelace.patio_ac`, `lovelace.notifications_logs`, etc.).
- `packages/patio_ac/` exists but is not loaded by `!include_dir_named packages`.
- `packages/_archive/` exists (ignored by `!include_dir_named`, but still adds confusion about active state).
- `automations.yaml` contains no `patio_ac`, `daikin`, or `uptime_kuma` entries (missing core systems/alerts).
- `/config/dashboards/` contains patio AC YAMLs not referenced by `configuration.yaml`.
- Multiple EV9 packages are loaded concurrently (`ev9_v1_4.yaml`, `ev9_v2_0.yaml`, `ev9_v2_2.yaml`, `ev9_v2_4.yaml`).
- Automations target hardware entities directly (`lock.ev9_door_lock`, `climate.150633095083490_climate`).
- Editable `input_text` log helpers are used for dashboards logs (EV9/Jose/Patio).
- Fixed delays exist in automations (EV9 charge restart) instead of bounded waits.
- No FPL integration present in `custom_components` (no `fpl`).

---

## Part B — Dashboard & Automation Enhancement Plan (Source: Dashboard_Automation_Enhancement_Plan.md)

### Home Assistant Enhancement Plan: Dashboards & Logic
**Date:** January 23, 2026
**Focus:** Conciseness, Robustness, and Missing Functionality

#### 1. Executive Summary
Your system has evolved into distinct "design generations."
- **Gen 1 (Homelab):** Dense, data-heavy, scrolling lists. Functional but high cognitive load.
- **Gen 2 (Daikin):** Educational, utilizing "Explainers" and high-density graphs. Excellent for deep dives.
- **Gen 3 (Kia EV9 / Jose):** **The Gold Standard.** Tabbed interfaces (Main/Config/Logs), Intent-Driven hierarchy ("Observe -> Act"), and responsive layouts.

**Goal:** Elevate all dashboards to "Gen 3" standards and implement "Exception-Based" monitoring to reduce noise.

#### 2. Dashboard Design Strategy (The "Gen 3" Standard)

**Core Principle:** "Don't show me everything. Show me what matters."

**Standard Template for All Dashboards**
1.  **Status Header (The "Glance"):**
    *   Top 10% of screen.
    *   Key KPIs only (Temp, Status, Battery, Error Count).
    *   *Design:* `tile` cards or `custom:button-card` with color-coded state.
2.  **Primary Actions (The "Controls"):**
    *   Big, tap-friendly targets.
    *   Immediate feedback (visual change).
    *   *Design:* `grid` card (2 columns mobile, 4 columns desktop).
3.  **Context (The "Graphs"):**
    *   Historical trend (last 24h).
    *   *Design:* `custom:mini-graph-card` or `apexcharts` (clean, minimal chrome).
4.  **Configuration Toggles (The "Fold"):**
    *   Hidden by default or moved to a "Config" tab.
    *   *Design:* `conditional` cards or separate Lovelace Views.

#### 3. High-Value Functional Gaps & Additions

**3.1 Homelab: From "Data Dump" to "Health Center"**
- **Current:** Shows CPU/RAM for every single container.
- **Problem:** To find a problem, you have to read every number.
- **Proposed Enhancement:** **"Exception-Based" Monitoring.**
    - **Feature:** "System Health" Traffic Light (Green/Yellow/Red).
    - **Feature:** "Problem Child" Card (using `auto-entities`). Only shows broken containers.
    - **Feature:** Backup Age Monitor.

**3.2 Patio AC: "Comfort" vs "Temperature"**
- **Current:** Controls based on raw Temp/Humidity.
- **Proposed Enhancement:** **Dew Point / Thermal Comfort.**
    - **Feature:** "Thermal Comfort" Sensor (Template).
    - **Feature:** "Window Open" Opportunity (Indoor vs Outdoor Dew Point).

**3.3 Vacuum (Jose): Maintenance Prediction**
- **Current:** Shows sensor lifespan %.
- **Proposed Enhancement:** **Proactive Maintenance.**
    - **Feature:** "Bin Full" Probability (based on `sqft_cleaned`).
    - **Feature:** Zone Presets ("Quick Clean" buttons) directly on main view.

**3.4 System-Wide: The "Meta-Dashboard" (Admin Only)**
- **Missing:** A single view that answers "Is my Smart Home healthy?"
- **Proposed Enhancement:** **Admin / Health View.**
    - **Dead Node Hunter:** List unavailable entities > 24h.
    - **Battery Triage:** List batteries < 15%.
    - **Error Trap:** Count of error logs.
    - **Update Manager:** Pending updates.

#### 4. Automation Logic Refactor Plan

**Current Issue:** `automations/configuration.yaml` is a 2,900-line monolith containing legacy logic that likely conflicts with your new Packages.

**4.1 The "Migration & Murder" Strategy**
1.  **Inventory:** Identify every active automation in the monolith.
2.  **Migrate:** Move valid logic to domain-specific packages.
3.  **Modernize:** Refactor legacy "State Machine" input_selects into modern `trigger_id` + `choose` blocks.
4.  **Murder:** Delete `automations/configuration.yaml`.

**4.2 Robustness Upgrades (The "Dead Man" Pattern)**
- **Time-Limited Actions:** High-stakes devices use `wait_for_trigger` with `timeout` -> Safety Off.
- **Self-Healing:** Run "State Check" automation on `homeassistant.start`.

#### 5. Implementation Roadmap (Part B)

**Phase 1: Clean Up & Consolidate (High Impact, Low Risk)**
1.  **Refactor Homelab Dashboard:** Implement `auto-entities` to hide healthy containers.
2.  **Create "Health" View:** Build the Battery/Unavailable entity tracker.
3.  **Kill the Monolith:** Begin migrating `automations/configuration.yaml` logic to packages.

**Phase 2: Intelligence Upgrades**
4.  **Patio AC Comfort Logic:** Implement Dew Point sensors and automation logic.
5.  **Vacuum Zone Presets:** Script specific zone coordinates for "Kitchen Clean" button.

**Phase 3: Visual Polish**
6.  **Apply "Gen 3" Style:** Update `dashboard_room` and `notifications` to match the Kia/Jose aesthetic.