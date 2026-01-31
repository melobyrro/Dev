# CLAUDE.md — Home Assistant Repository Constitution
**Last updated:** 2026-01-31
**Status:** Binding
**Authority:** This file is the law for this repository. If any instruction conflicts with this document, this document wins.

---

## 0) Scope and Intent
This document defines **how work is executed** in a complex Home Assistant repository:
- Engineering workflow and execution discipline
- Architecture and file standards
- Automation and dashboard engineering standards
- Regression control and rollback law

This document is **system-agnostic**:
- No hostnames, IPs, device brands, or environment-specific values appear here.
- Concrete values must live in feature-local requirements/config files, not in this constitution.

---

## 1) Operating Contract (Non‑Negotiables)

### 1.1 Definition of Done (DoD)
A change is **not done** until all applicable gates are satisfied.

#### A) Configuration DoD
| Gate | Requirement | Evidence |
|---|---|---|
| Config validity | Repository YAML is syntactically valid; Home Assistant configuration check passes | CLI/UI config check output captured in notes |
| No new log debt | No new warnings/errors caused by the change; no repeated stack traces | Log excerpt showing clean run after reload/restart |
| **HAL Compliance** | No physical device IDs used in automations (must use Templates/HAL) | Code review check |
| **Naming Compliance** | New entities follow `area_room_device_modifier` schema | Code review check |
| Reload safety | Prefer targeted reloads; restart only when required | Reload/restart performed and recorded |
| Drift prevention | Single source of truth maintained; no duplicate definitions introduced | Search confirms no duplicate entity/automation IDs or duplicated blocks |

#### B) UI / Dashboard DoD (Mobile/Tablet/Desktop)
| Gate | Requirement | Evidence |
|---|---|---|
| Responsiveness | Layout works on **mobile**, **tablet**, **desktop**; no overflow; no hidden controls | Screenshots per breakpoint |
| Hierarchy integrity | “Observe → Understand → Act” preserved; no mixing of advanced tuning into daily controls | Section-by-section review |
| **Read-Only Safety** | Log/Diagnostic entities have `tap_action: none` to prevent editing | YAML check |
| Readability | Aligned tables (via `card-mod` if needed), consistent units, consistent labels | UI check |

#### C) Rollback DoD
| Gate | Requirement | Evidence |
|---|---|---|
| Rollback plan exists | Every non-trivial change includes rollback steps | Rollback section in commit/notes |
| Rollback artifact exists | A **known-good backup** (repo + HA backup) exists **before** change | Backup IDs / filenames recorded |
| Rollback verified | Rollback procedure is executable with the artifacts created | Dry-run sanity check (paths/commands valid) |

---

### 1.2 Rollback Procedures (Mandatory)
Rollback is not a suggestion; it is a requirement.

**Rollback primitives (choose applicable):**
1. **Git rollback**: revert commit(s) or reset branch to a known-good commit.
2. **Config restore**: restore a file-level snapshot of the HA config directory.
3. **Platform backup restore**: restore a full Home Assistant backup (Supervisor or equivalent).

**Minimum rollback record (must be written before implementation):**
- What you will revert (commit hash / files)
- What artifact you will restore (backup filename / snapshot ID)
- How you will validate recovery (config check + log check + trace run)

---

## 2) Execution Discipline (Mandatory 11‑Step Sequence)
Every task follows the sequence below. No exceptions. Skipping steps is a defect.

### 2.1 The 11 Steps
1. **Nearest‑Requirements Discovery (NRR)**
   - Identify the file(s) you will touch.
   - Apply the **Nearest‑Requirements Rule** (below).
2. **Project Root Discovery**
   - Determine the feature boundary (project root) and confirm ownership.
3. **State Capture**
   - Capture baseline: `git status`, impacted files, relevant logs, and current behavior screenshots.
4. **Plan + Risk** (Sequential Thinking MCP required)
   - Write a small plan: inputs → transformation → outputs.
   - Identify regressions and define rollback.
5. **Branch**
   - Create a dedicated branch for the task (one task per branch).
6. **Backup**
   - Create the required backup artifacts (repo + HA config/backup).
7. **Implement** (use Run + Ref workflow)
   - Make the smallest possible change that satisfies requirements.
   - Keep the change localized to the owning feature boundary.
8. **Static Validation**
   - YAML checks, config checks, naming convention verification.
9. **Runtime Validation**
   - Reload/restart as needed.
   - Run at least one trace for affected automations/scripts.
   - Verify logs are clean.
10. **UI Validation** (Chrome DevTools evidence required)
    - Verify mobile/tablet/desktop responsiveness and “Observe → Understand → Act” hierarchy.
11. **Document + Commit + Post‑Check**
    - Update feature requirements/docs (if behavior changed).
    - Commit with a precise message.
    - Monitor logs after deployment/reload.

---

### 2.2 Nearest‑Requirements Rule (NRR)
**Definition:** For any file you modify, you must obey the nearest requirements document **closest to that file** in the directory tree.

**Procedure:**
- Starting from the directory of the file being edited, search upward for one of:
  - `REQUIREMENTS.md`
  - `requirements.md`
  - `README.md` (only if it explicitly contains requirements)
- The **first** one found is binding.
- If none exist before reaching repo root:
  - Create `REQUIREMENTS.md` in the **feature root** (see below) before making behavior changes.

**Why:** Requirements must be discoverable, local, and enforceable.

---

### 2.3 Project Root Discovery (Feature Boundary)
A “project root” (feature root) is the smallest folder that contains everything required to understand and safely modify a feature:
- Feature requirements (`REQUIREMENTS.md`)
- Feature package/config files
- Feature dashboard(s) (if any)
- Feature docs and test notes

**Boundary rule:** If a change requires crossing boundaries, the change must be split:
- Implement cross-feature behavior by **publishing stable outputs** (entities/events/services) from one feature and consuming them from another.
- Never directly edit internal implementation across multiple feature roots in a single change unless the requirements documents explicitly define shared ownership.

---

## 2.4 Tooling Constitution (MCP + DevTools + Ref)

This repository assumes work may be executed by an agentic coding environment. Tooling is not optional: it is part of verification and evidence.

### 2.4.1 MCP Tool Selection Matrix
| Phase | Primary tool | Purpose | Evidence artifact |
|---|---|---|---|
| Planning | **Sequential Thinking MCP** | Produce a structured plan, risks, invariants, and acceptance checks | Saved plan block in notes / PR description |
| Implementation | **Run + Ref workflow** | Make controlled edits; capture before/after references; ensure reversibility | `ref` snapshots (before/after), diff summary |
| UI Validation | **Chrome DevTools** | Responsive checks, state inspection, event/network verification, user simulation | Screenshots + DevTools notes |

### 2.4.2 Sequential Thinking MCP (Mandatory for Non‑Trivial Work)
**Use Sequential Thinking MCP whenever the task is not a one-line change.**

**Minimum outputs (must be written before editing):**
- Problem statement (one paragraph)
- Constraints and invariants (must-not-break rules)
- Plan in numbered steps (≤ 12 steps)
- Risk list (what can regress, how you will detect it)
- Rollback plan (exact commands/artifacts)
- Acceptance checks (what must be true at the end)

**Law:** If a plan is not written, the change is non-compliant.

### 2.4.3 Chrome DevTools Protocol (UI Testing is Evidence-Based)
Chrome DevTools is the default instrument for UI verification. “Looks fine” is not evidence.

#### A) Responsive Testing (Device Emulation)
Use **Device Toolbar** to test:
- narrow mobile widths
- tablet widths
- wide desktop widths

**Checklist:**
- No horizontal scroll unless intentional
- No hidden primary controls
- No overlapping cards
- Tables remain aligned and readable
- Critical actions remain reachable on mobile in first screen

#### B) Impersonating a User (Role/Permission Simulation)
UI validation must include a **non-admin** perspective when applicable.

**Approved methods (choose one):**
1. Create/use a dedicated **Test User** with restricted permissions.
2. Validate feature behavior using the exact navigation paths a normal user takes.

**What to verify:**
- Intended views are accessible
- Restricted actions are hidden/disabled as expected
- Explanatory “Understand” content remains visible even when actions are restricted
- No admin-only assumptions in dashboards (e.g., reliance on editing cards)

#### C) Network, Storage, and State Inspection
Use DevTools to verify:
- **Network**: service calls fire once, no repeated loops, no failing requests
- **Application/Storage**: ensure the UI is not relying on stale local storage
- **Console**: no persistent UI errors during interaction

**Law:** If an issue is visible in the console/network panel and ignored, the change is non-compliant.

### 2.4.4 “Ref” Protocol (Before/After Proof)
“Ref” is the canonical method to attach evidence to changes (before/after snapshots of relevant artifacts).

**Minimum ref artifacts for any non-trivial change:**
- **Before**: ref snapshot of each file touched and relevant requirements
- **After**: ref snapshot of each file touched
- **Runtime proof**: config check result and at least one trace evidence reference
- **UI proof** (if UI impacted): breakpoint screenshots and any DevTools findings

#### Ref Evidence Template
```text
REF (Before):
- <path>:<line-range or section>
- <path>:<line-range or section>

REF (After):
- <path>:<line-range or section>
- <path>:<line-range or section>

Validation:
- Config check: <result + timestamp>
- Logs: <clean excerpt / query>
- Trace: <automation/script + timestamp>
- UI: <mobile/tablet/desktop screenshots + DevTools notes>
Rollback:
- Git: <revert/reset commands>
- Restore: <backup artifact + restore command>
```

**Law:** If you cannot point to the before/after truth, you cannot claim the change is correct.

---

### 2.5 Session Start Protocol (Chrome MCP Validation)

Every Home Assistant work session MUST begin with browser validation before any implementation work.

#### Mandatory First Steps

1. **Verify Chrome MCP Connection:**
   ```
   - Call mcp__claude-in-chrome__tabs_context_mcp
   - Confirm extension is responding
   - If unavailable: STOP and alert user — cannot proceed
   ```

2. **Navigate to Authenticated HA Session:**
   ```
   - Open Home Assistant dashboard (or verify existing tab)
   - Confirm NOT on login page (authentication valid)
   - Take baseline screenshot for reference
   ```

3. **If Chrome MCP Unavailable:**
   - Stop immediately and inform user
   - Cannot proceed with UI validation work
   - No dashboard/automation changes allowed without validation capability

**Why:** Every change must be validated in the actual UI. No Chrome = no validation = no changes.

**Law:** A session without verified Chrome MCP access cannot make UI-affecting changes.

---

### 2.6 Context Window Management (Agent Delegation Law)

To maintain clean context and enable thorough validation, delegate implementation work to Task agents.

#### Delegation Pattern

| Role | Responsibilities |
|------|------------------|
| **Main context** | Planning, requirements gathering, user communication, orchestration |
| **Task agents** | File edits, searches, implementation, validation |

**Rule:** Keep main context clean. Spawn agents for implementation and validation.

#### Post-Change Validation Protocol (Mandatory)

After ANY dashboard or automation change, spawn a validation agent:

```
Task: Navigate to <dashboard URL>
      Go to <specific tab/section>
      Verify: <what should be visible>
      Check responsive views (mobile/tablet/desktop)
      Take screenshots as evidence
      Report: PASS with evidence, or FAIL with details
```

**Agent Responsibilities:**
- Navigate to affected dashboard in Chrome
- Verify change appears correctly
- Check at least mobile + desktop responsive views
- Screenshot evidence of success/failure
- Report back with clear PASS/FAIL and evidence

**Main Context Responsibilities:**
- Review agent validation result
- If PASS: proceed to next change or commit
- If FAIL: fix issue and re-validate

#### Validation Agent Prompt Template
```text
Navigate to Home Assistant at <HA_URL>.
Open dashboard: <dashboard_name>.
Go to tab/section: <specific_location>.

Verify the following:
1. <specific check 1>
2. <specific check 2>
3. ...

Test responsive views:
- Mobile (narrow)
- Desktop (wide)

Take screenshots as evidence.
Report: PASS if all checks succeed, FAIL with specific details if not.
```

**Law:** No change is complete until a validation agent confirms it in the live UI.

---

## 3) Architecture Standards

### 3.1 Packages as Feature Isolation (Law)
**Model:** Use **Home Assistant Packages** to isolate each feature as a cohesive unit.

**Rules:**
- A feature’s logic lives inside its feature package boundary.
- Root configuration is an **orchestrator**, not a logic dump:
  - It imports/includes packages and shared primitives only.
- No “split brain” configuration:
  - A thing is defined **once** in the entire repository (automation IDs, script IDs, helper names, template sensors, etc.).

**Approved boundaries (examples, not exhaustive):**
- Automations, scripts, helpers, templates, sensors, binary_sensors, input_* helpers, groups, scenes, alerts, dashboards.

---

### 3.2 Repository Layout (Recommended Pattern)
This constitution does not require a single layout, but it enforces boundaries and discoverability.
A common compliant layout:

```text
<REPO_ROOT>/
  home-assistant/
    configuration.yaml
    packages/
      <feature_name>/
        REQUIREMENTS.md
        package.v1.0.yaml
        automations.v1.0.yaml
        scripts.v1.0.yaml
        helpers.v1.0.yaml
        sensors.v1.0.yaml
        dashboards/
          <dashboard_name>.v1.0.yaml
        docs/
          notes.md
```

If your include strategy requires a different shape (single-file packages, `!include_dir_merge_named`, etc.), the same boundary rules apply.

---

### 3.3 File Naming Convention (Strict)
**Convention:** `{component}.v{major}.{minor}.{ext}`

Examples:
- `automations.v1.3.yaml`
- `scripts.v2.0.yaml`
- `dashboard_main.v1.1.yaml`
- `helpers.v1.0.yaml`

#### Versioning Semantics
| Version Part | Meaning | When to increment |
|---|---|---|
| `major` | Breaking change | Rename/remove entities, change service contract, change semantics in a way that breaks consumers |
| `minor` | Backward-compatible change | Add functionality, add entities, improve behavior without breaking existing consumers |
| `ext` | File type | Usually `yaml` or `md` |

**Law:** Version numbers are not decoration. They are a contract.

---

### 3.4 Component Versioning Rules (Recommended)
| Component | Typical file | Examples of breaking changes (major) | Examples of non-breaking changes (minor) |
|---|---|---|---|
| Automations | `automations.vX.Y.yaml` | Change `id`, rename exported helper/entity IDs used by consumers, semantic contract change | Add new automation, improve conditions, add guardrails |
| Scripts | `scripts.vX.Y.yaml` | Change script name/contract fields expected by callers | Add optional fields, strengthen idempotency |
| Helpers | `helpers.vX.Y.yaml` | Rename helper IDs referenced elsewhere | Add helpers, adjust default values (if safe) |
| Sensors/Templates | `sensors.vX.Y.yaml` | Rename entities, change units/meaning | Add new sensors, improve availability logic |
| Dashboards | `<dash>.vX.Y.yaml` | Remove/relocate critical controls, change interaction model | Add new views/sections, improve layout without removing behaviors |

---

### 3.5 Cross‑Feature Contracts
Cross-feature interaction must use explicit contracts:
- Entities (sensors, binary_sensors, helpers)
- Events
- Services (via scripts or service registrations, where applicable)
- MQTT topics (if used)

**Do not** consume internal implementation details (file paths, internal variable naming, undocumented helper/entity IDs).

---

### 3.6 Naming and Contextual Conventions (Strict)
**Schema:** `area_room_device_modifier`
**Example:** `binary_sensor.basement_laundry_washer_status`

| Type | Prefix | Example |
|---|---|---|
| **Helpers** | `logic_` or `helper_` | `input_boolean.logic_house_guest_mode` |
| **Automations** | `area_` or `function_` | `automation.area_bedroom_circadian_lighting` |

**Law:** Entities must be filterable by their ID alone.

---

### 3.7 Hardware Abstraction Layer (HAL)
**Law:** Automations must never target physical device IDs directly.
- **Pattern:** Create a Template Entity (e.g., `light.living_room_primary`) that proxies the physical device.
- **Benefit:** Swapping hardware only requires updating the template, not 50 automations.

---

### 3.8 Modern Template Syntax
**Law:** Legacy template formats are forbidden.
- **Bad:** `value_template: ...` inside a list without `state:` key.
- **Good:** Modern configuration format under `template:` integration.

---

### 3.9 File Organization Law (Active/Archive Discipline)

#### Active File Rule (Strict)
- **Only ONE active version** per component in any directory
- Active file naming: `<component>.v<major>.<minor>.yaml`
- **Forbidden in active directories:**
  - `_deployed`, `_backup`, `_old` suffixes
  - Timestamp-based names (e.g., `automations-20260115.yaml`)
  - Multiple version files (e.g., both `v1.10` and `v1.21` in same folder)

#### Archive Strategy (Mandatory)
Old versions MUST move to `.archive/` immediately upon new version deployment.

| Action | Requirement |
|--------|-------------|
| New version deployed | Move old version to `.archive/` same day |
| Archive naming | Keep original name, add `-archived-YYYYMMDD` suffix |
| Archive location | `.archive/` folder at feature root level |

#### Directory Structure Standard
```text
<feature>/
  REQUIREMENTS.md               # Required for every feature
  package.v<X>.<Y>.yaml         # Main package (if using packages)
  automations.v<X>.<Y>.yaml     # Single active automation file
  scripts.v<X>.<Y>.yaml         # Single active scripts file
  helpers.v<X>.<Y>.yaml         # Single active helpers file
  sensors.v<X>.<Y>.yaml         # Single active sensors file
  dashboards/
    <dashboard>.v<X>.<Y>.yaml   # Single active dashboard
  docs/
    notes.md
  .archive/                     # All old versions here
    automations.v1.0-archived-20260115.yaml
    dashboards/
      dashboard.v1.0-archived-20260110.yaml
```

**Law:** If `ls` in any active directory shows multiple versions of the same component, the repository is non-compliant.

---

### 3.10 Feature Registry (Central Index)

A **REGISTRY.md** file MUST exist at the repository root listing all features.

#### Registry Format
```markdown
# Home Assistant Feature Registry
**Last Updated:** YYYY-MM-DD

| Feature | Path | Dashboard | Automations | Scripts | Owner | Updated |
|---------|------|-----------|-------------|---------|-------|---------|
| Kia EV9 | kia-ev9/ | lovelace.kia_ev9.v2.10.yaml | automations.v2.8.yaml | scripts.v2.7.yaml | Andre | 2026-01-30 |
| Patio AC | patio-ac/ | patio_ac.v1.21.yaml | automations.v1.0.yaml | scripts.v1.0.yaml | Andre | 2026-01-28 |
| Daikin | Daikin/ | daikin.v2.0.yaml | daikin_automations.yaml | — | Andre | 2026-01-25 |
| Jose Vacuum | jose/ | jose_vacuum.v1.0.yaml | — | — | Andre | 2026-01-20 |
| Central Automations | ha-config/dashboards/ | automations_central.v1.0.yaml | (aggregates orphans) | — | Andre | 2026-01-31 |
```

#### Registry Rules

| Rule | Requirement |
|------|-------------|
| Update frequency | Must be updated on every feature structural change |
| Paths | Relative paths from repo root |
| "Updated" column | Date of last structural change (not every commit) |
| Completeness | Every feature with a dashboard MUST appear |
| Accuracy | Dead links = non-compliant registry |

**Verification command:**
```bash
# Check all registry paths resolve
grep -oP '\| [a-zA-Z0-9_/-]+\.yaml' REGISTRY.md | tr -d '| ' | while read f; do
  [ -f "$f" ] || echo "MISSING: $f"
done
```

**Law:** If a feature exists but is not in REGISTRY.md, the repository is non-compliant.

---

## 4) Automation Engineering Constitution

### 4.1 Mandatory Automation Fields
Every automation must define these fields:

| Field | Required | Rule |
|---|---:|---|
| `id` | Yes | Immutable once shipped; treat as primary key |
| `alias` | Yes | Human-readable, stable, unique |
| `description` | Yes | Plain English: what, why, and key safety assumptions |
| `mode` | Yes | Must be deliberate (`single`, `restart`, `queued`, `parallel`) |

**Strongly recommended (when applicable):**
- `max` / `max_exceeded` when `queued` or `parallel`
- Trace retention settings (where supported)
- `initial_state` only when a feature requires it (default is preferred)

---

### 4.2 Structure: Separate Decision from Actuation (Law)
**Decision** = compute intent, choose outcomes, set variables.
**Actuation** = perform side effects (service calls).

**Rules:**
- Put computation in `variables:` and `choose:` blocks.
- Put side effects in **scripts** whenever feasible.
- Service calls in automations must be minimal and must pass explicit parameters.
- Prefer **idempotent** scripts (safe to call repeatedly).

**Benefits:**
- Testable logic
- Reusable actions
- Reduced duplication and regression risk

---

### 4.3 Robust Waits (Deadline vs. Timeout)
**Never** use unbounded `wait_for_trigger`.

- **Short Waits (< 5 min):** Use `wait_for_trigger` with strict `timeout`, `continue_on_timeout: true`, and an explicit timeout handling branch.
- **Long Waits (> 5 min):** Use **Deadline Helpers** (`input_datetime`).
  - **Reason:** `wait_for_trigger` dies on restart/reload; `input_datetime` survives.

#### Safe Wait Template (Short)
```yaml
- wait_for_trigger:
    - platform: state
      entity_id: <ENTITY_ID>
      to: "<TARGET_STATE>"
  timeout: "00:05:00"
  continue_on_timeout: true

- choose:
    - conditions: "{{ wait.completed }}"
      sequence:
        - service: logbook.log
          data: ...
    - conditions: "{{ not wait.completed }}"
      sequence:
        - service: persistent_notification.create
          data: ...
        - stop: "Timeout safety stop"
```

---

### 4.4 Idempotency and Guardrails
Automations and scripts must be safe to re-run:
- Check current state before issuing commands.
- Avoid `toggle` when explicit services exist (`turn_on` / `turn_off`).
- Prefer `choose:` with explicit conditions over implicit state assumptions.
- If an action is destructive or costly, require confirmations or multi-condition guards.

---

### 4.5 Concurrency Rules (Mode Selection)
| Mode | Use when | Risks | Mitigations |
|---|---|---|---|
| `single` | The action must not overlap | Missed triggers | Use event aggregation or queued downstream script |
| `restart` | New trigger should replace old run | Partial side effects | Make actuation idempotent; script isolation |
| `queued` | Every trigger matters in order | Backlog | Set `max`; add throttling/guards |
| `parallel` | Truly independent runs are safe | Resource contention | Set `max`; isolate devices/resources |

**Law:** If you cannot justify the mode, the automation is non-compliant.

---

### 4.6 Time, Throttling, and “Safe Delays”
**Prohibited:** “naked” `delay` that assumes the world will be ready after a fixed duration.
**Allowed:** Bounded waits and delays inside a proven “safe wait” envelope.

**Approved patterns:**
- Wait for a state/event with timeout (preferred)
- Retry loops with maximum attempts and a backoff schedule
- Throttle noisy triggers using:
  - trigger `for:`
  - guard conditions (time windows, last-changed checks)
  - helper-based cooldown timers

---

### 4.7 Logging and Observability (Automation)
**Rules:**
- Every safety stop or timeout must log (logbook and/or persistent notification).
- Routine success logs must be low-noise; do not spam.
- Prefer:
  - `logbook.log` for human-readable event trails
  - `persistent_notification.create` for safety/failure signals
  - Dedicated sensors/entities for dashboards (stateful summaries)

**Anti-pattern:** Using editable helpers (e.g., text inputs) as “logs” in dashboards.

---

### 4.8 Self-Healing Triggers
**Law:** Prefer State Triggers over Event Triggers.

- **Bad:** Trigger on `event: sunset`. (Missed if HA is down at sunset).
- **Good:** Trigger on `sun.elevation < 0`. (Catches up when HA starts).

Automations should be triggered by any state change that *could* make conditions true, ensuring the system "heals" if a single event was missed.

---

### 4.9 Automation Visibility Law (Dashboard Observability)

Every automation must be visible and understandable from a dashboard. No automation should be "hidden" in YAML with no UI presence.

#### Automation Location Rules

| Automation Type | Dashboard Location |
|-----------------|-------------------|
| Feature-specific (e.g., EV9 lock, vacuum schedule) | **Automations tab** in that feature's dashboard |
| Cross-cutting (notifications, trackers, system) | **Central Automations dashboard** with categorized tabs |

**Law:** Every automation appears in exactly ONE dashboard's Automations tab.

#### Required Automations Tab Structure

Every feature dashboard MUST have an "Automations" tab containing a table with these columns:

| Column | Content | Notes |
|--------|---------|-------|
| **Name** | Automation alias | From `alias:` field |
| **Description** | What it does (1 line) | From `description:` field |
| **Trigger Type** | `scheduled` / `state` / `event` | Icon recommended |
| **Trigger Inputs** | Current values of ALL trigger entities + conditions | Live updating |
| **Last Run** | Timestamp of last execution | Only if ran |
| **Next Run** | Timestamp | Only for scheduled automations |
| **Status** | `idle` / `running` / `disabled` | Color-coded |
| **Last Action** | What happened | Only show if action taken or error |

#### Trigger Input Display (Critical for Debugging)

Show ALL monitored entities with their current values so users can verify automation logic:

**For Scheduled Automations:**
```
Next: 06:00 AM | Last: Yesterday 06:00 AM
```

**For State/Trigger-Based Automations:**
```
distance: 245m | car_locked: false | home_mode: away | battery: 78%
```

This allows users to see exactly what the automation is watching and confirm it will trigger as expected.

#### Logging Rules (Signal, Not Noise)

| Event | Log to "Last Action" column? |
|-------|------------------------------|
| Action was taken | **YES** — describe what action |
| Error occurred | **YES** — describe what error |
| Ran but conditions not met | **NO** — silent |
| "No action needed" | **NO** — silent |

**Why:** Users only care when something happened or broke, not when nothing happened.

#### Implementation Pattern (Automation Status Sensor)

Each automation needs a companion template sensor to expose its state to dashboards:

```yaml
template:
  - sensor:
      - name: "<feature>_automation_<name>_status"
        unique_id: "<feature>_automation_<name>_status"
        state: "{{ states('automation.<automation_id>') }}"
        attributes:
          alias: "<Human readable name>"
          description: "<What it does>"
          trigger_type: "state"  # or "scheduled" or "event"
          last_triggered: "{{ state_attr('automation.<automation_id>', 'last_triggered') }}"
          trigger_inputs:
            distance: "{{ states('sensor.ev9_distance_from_home') }}"
            car_locked: "{{ states('lock.ev9_door_lock') }}"
            home_mode: "{{ states('input_select.home_mode') }}"
          last_action: "{{ states('input_text.<feature>_<name>_last_action') }}"
          last_action_time: "{{ states('input_datetime.<feature>_<name>_last_action_time') }}"
```

#### Central Automations Dashboard

For automations not tied to a specific feature, create a central dashboard at:
`/ha-config/dashboards/automations_central.v1.0.yaml`

**Required tabs:**
- **Notifications** — all notification automations
- **Trackers** — presence, location, device tracking
- **System** — HA health, backups, maintenance
- **Misc** — anything not fitting above

Each tab follows the same table format.

**Law:** If an automation exists but is not visible in any dashboard's Automations tab, the repository is non-compliant.

---

## 5) Dashboard UX Standards Constitution

### 5.1 Primary Hierarchy: Observe → Understand → Act (Law)
Every dashboard and major section must follow this order:

1. **Observe** — “What is happening?”
   - Key state, trend graphs, summaries, health indicators
2. **Understand** — “Why is it happening?”
   - Logic explanations, thresholds, automation states, conditions, dependencies
3. **Act** — “What can I do?”
   - Controls, toggles, scripts, emergency actions

**Law:** Daily users should succeed using only Observe + Act. Understand is available but does not block.

---

### 5.2 Read‑Only Logs Rule (Hard Rule)
Dashboards must not contain any editable element that functions as a “log viewer.”

**Technical Implementation:**
- Use `type: simple-entity` where possible.
- Explicitly set `tap_action: none` and `hold_action: none`.
- Use Markdown cards for pure text logs.

#### Read‑Only Log Display Pattern (Template)
```yaml
type: markdown
title: "Recent Events (Read‑Only)"
content: |
  **Last update:** {{ states('sensor.<feature_last_update>') }}
  **Status:** {{ states('sensor.<feature_status>') }}
  **Last alert:** {{ states('sensor.<feature_last_alert>') }}
```

**Law:** If a user can click and edit it, it is not a log.

---

### 5.3 Aligned Tables (Single‑Surface Rule)
When presenting multiple rows/columns of related data:
- Use a **single-surface table card** that enforces column alignment.
- Avoid “stacked entities cards pretending to be a table.”

**Approved approach (example):** `flex-table-card` (or equivalent) configured with:
- fixed columns
- consistent units
- right/left alignment rules
- stable sorting

#### Table Specification Checklist
| Requirement | Rule |
|---|---|
| Alignment | Numeric columns right-aligned; labels left-aligned |
| Units | Units included in headers or cells, consistently |
| Density | Prefer fewer, higher-signal columns |
| Sorting | Stable sort (e.g., by severity, time, name) |
| Readability | No wrapped headers; predictable row height |

---

### 5.4 “Single Source of Control” for Settings
If a setting exists:
- It must be editable in **one** place in UI.
- Everywhere else is display-only.
- Advanced tuning settings must be visually separated from daily controls.

---

### 5.5 Controls: Guardrails and Safety
- Group controls by intent (daily vs advanced vs emergency).
- Destructive actions must be:
  - separated from routine toggles
  - guarded with confirmations and conditions
- Use consistent naming:
  - **Buttons**: verbs (“Run”, “Reset”, “Acknowledge”)
  - **Toggles**: adjectives/state (“Enabled”, “Auto”, “Armed”)

---

### 5.6 Responsiveness Standards
Dashboards must be verified at minimum:
- Mobile (narrow)
- Tablet (medium)
- Desktop (wide)

**Law:** A dashboard that looks good only on one breakpoint is non-compliant.

**Practical rules:**
- Avoid fixed pixel widths when possible.
- Prefer grid/layout constructs that adapt.
- Keep critical controls in the first screen on mobile.

---

### 5.7 Visual Engineering (card-mod)
**Law:** Use `card-mod` to resolve alignment issues.
- Do not accept "default" spacing if it breaks the grid or alignment.
- Ensure unified grid widths across stacks.
- Prevent visual regression by pinning complex layouts with explicit CSS.

---

### 5.8 Dashboard Layout Standards (Mandatory Structure)

Every feature dashboard MUST follow a consistent tab and section structure for visual consistency across the entire Home Assistant UI.

#### Mandatory Tab Structure

| Tab | Purpose | Required? |
|-----|---------|-----------|
| **Overview** | Primary Observe → Understand → Act interface | **Yes** |
| **Automations** | Table of all feature automations with live state (see 4.9) | **Yes** |
| **Details** | Deeper metrics, history graphs, trends | Optional |
| **Settings** | Configuration helpers, thresholds, modes | If applicable |

**Tab order is fixed.** Overview first, Automations second, then optional tabs.

#### Overview Tab Layout Template

```
┌─────────────────────────────────────────────────────────────┐
│ STATUS BAR                                                  │
│ Health indicator • Last update • Key metric summary         │
├─────────────────────────────────────────────────────────────┤
│ OBSERVE (2-3 cards max)                                     │
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐       │
│ │ Primary State │ │ Secondary     │ │ Tertiary      │       │
│ │ (biggest)     │ │ State         │ │ State         │       │
│ └───────────────┘ └───────────────┘ └───────────────┘       │
├─────────────────────────────────────────────────────────────┤
│ UNDERSTAND                                                  │
│ Current mode • Active logic explanation • Why this state    │
├─────────────────────────────────────────────────────────────┤
│ ACT (primary controls only)                                 │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐                         │
│ │ Toggle  │ │ Button  │ │ Button  │                         │
│ └─────────┘ └─────────┘ └─────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

#### Responsive Requirements (Strict)

| Breakpoint | Max Columns | Requirements |
|------------|-------------|--------------|
| **Mobile** (< 600px) | 1 column | Controls reachable without scroll; status bar visible |
| **Tablet** (600-1024px) | 2 columns | Cards stack naturally; no horizontal overflow |
| **Desktop** (> 1024px) | 3 columns max | No horizontal scroll; comfortable spacing |

**Checklist before any dashboard is considered complete:**
- [ ] Mobile: single column, no horizontal scroll
- [ ] Mobile: primary controls visible without scrolling
- [ ] Tablet: 2-column layout works
- [ ] Desktop: 3-column max, no wasted space
- [ ] All breakpoints: Status bar visible at top

#### Card Alignment Standards

| Element | Rule |
|---------|------|
| **Tables** | Must use `flex-table-card` — no stacked entity cards pretending to be tables |
| **Spacing** | Use `card-mod` for consistent margins/padding |
| **Grid widths** | Unified across all stacks in a view |
| **Units** | Always displayed, consistent format (e.g., always "78%" not sometimes "78" and sometimes "78%") |

#### Automations Tab Layout

The Automations tab uses `flex-table-card` with fixed columns:

```yaml
type: custom:flex-table-card
title: Feature Automations
entities:
  include: sensor.*_automation_*_status
columns:
  - name: Name
    data: alias
  - name: Description
    data: description
  - name: Trigger
    data: trigger_type
    icon: true
  - name: Inputs
    data: trigger_inputs
    modify: |-
      Object.entries(x).map(([k,v]) => `${k}: ${v}`).join(' | ')
  - name: Last Run
    data: last_triggered
    modify: |-
      if (x) new Date(x).toLocaleString()
      else '—'
  - name: Status
    data: state
  - name: Last Action
    data: last_action
    modify: x || '—'
```

#### Settings Tab Layout (If Applicable)

Group settings by category:
1. **Thresholds** — numeric inputs, sliders
2. **Modes** — dropdowns, radio buttons
3. **Toggles** — on/off switches for features
4. **Advanced** — hidden by default, expandable section

**Law:** A dashboard without Overview and Automations tabs is non-compliant.

---

## 6) Regression Control: Git + Backup Discipline (Mandatory)

### 6.1 Git Discipline (Law)
| Rule | Requirement |
|---|---|
| Clean baseline | Start from a clean working tree |
| One task per branch | No mixed objectives |
| Atomic commits | Each commit is a coherent change with a reason |
| Messages | Imperative, specific, scoped |
| Reverts | Must be possible without archaeology |

#### Branch Template
```bash
git checkout -b feature/<short-task-name>
```

#### Commit Message Template
```text
<scope>: <imperative summary>

Why:
- <reason>

What:
- <bullet list of changes>

Risk:
- <what could break>

Rollback:
- <exact revert/restore steps>
```

---

### 6.2 Backup Discipline (Law)
Backups must exist **before** modifications. Minimum artifacts:
- Repo state (commit hash + optional tag)
- Platform backup (Supervisor/full backup) **or** config directory snapshot/tar

#### Generic Backup Templates (Fill placeholders)
```bash
# Record baseline
pwd
git status
git rev-parse HEAD

# Create an annotated baseline tag (optional but recommended)
git tag -a "baseline-<YYYYMMDD>-<short>" -m "Baseline before <task>"

# File-level backup (example pattern; adjust paths)
tar -czf "<BACKUP_DIR>/ha-config-<YYYYMMDD>-<short>.tgz" "<HA_CONFIG_DIR>"
```

**Law:** If you cannot restore, you cannot change.

---

### 6.3 Post‑Change Monitoring
After reload/restart:
- Observe logs for a meaningful window (not zero seconds).
- Confirm no repeated errors.
- Confirm key entities used by dashboards/automations exist and update.

---

## 7) Validation Checklist (Use Every Time)

### 7.1 Static Validation
- YAML syntax check (tooling as configured in repo)
- Home Assistant configuration check (CLI or UI)
- Search for duplicate IDs (automation/script/entity IDs)
- **Entity Verification:** Run `watchman` (or equivalent grep) to catch dead entities or broken references.

### 7.2 Runtime Validation
- Reload/restart performed (only if needed)
- At least one successful trace for affected automations/scripts
- Logs reviewed: no new warnings/errors

### 7.3 UI Validation
- Mobile/tablet/desktop checked
- Observe → Understand → Act preserved
- Read‑Only Logs rule satisfied
- Tables aligned and readable

---

## 8) Appendices (Templates)

### 8.1 REQUIREMENTS.md Template (Feature‑Local Law)
```md
# <Feature Name> — Requirements
**Version:** v1.0
**Last Updated:** <YYYY-MM-DD>
**Owner:** <team/person>

## 1) Purpose
- What this feature does (user value)

## 2) Inputs
- Sensors/entities/events/services consumed

## 3) Outputs
- Sensors/entities/events/services produced

## 4) Controls
- What users can change (helpers/toggles/inputs)

## 5) Safety and Guardrails
- Timeouts, failsafes, error handling, safe states

## 6) UI Contract
- Where it appears in dashboards
- Observe → Understand → Act mapping

## 7) Acceptance Tests (Manual)
- Steps + expected results
- Required traces to run

## 8) Rollback
- Exact revert + restore steps and artifacts
```

---

### 8.2 Package Template (Feature Isolation)
```yaml
# package.v1.0.yaml
# Feature: <feature_name>
# Contract: See REQUIREMENTS.md

automation: !include automations.v1.0.yaml
script: !include scripts.v1.0.yaml
template: !include sensors.v1.0.yaml
# helpers.v1.0.yaml may define input_* helpers, groups, alerts, etc.
```

---

### 8.3 Automation Template (Compliant Skeleton)
```yaml
- id: "<immutable_id>"
  alias: "<Human readable name>"
  description: >
    What it does. Why it exists. Key safety assumptions.
  mode: single

  trigger:
    - platform: state
      entity_id: <ENTITY_ID>

  condition: []

  variables:
    feature_enabled: "{{ is_state('input_boolean.<feature_enabled>', 'on') }}"
    # decision variables...

  action:
    - choose:
        - conditions: "{{ not feature_enabled }}"
          sequence:
            - stop: "Feature disabled"
        - conditions: "{{ feature_enabled }}"
          sequence:
            # Decision → then Actuation via scripts
            - service: script.<feature_actuation_script>
              data:
                reason: "Automation <alias> triggered"
```

---

### 8.4 Script Template (Idempotent Actuation)
```yaml
<feature_actuation_script>:
  alias: "<Feature> — Actuation"
  description: "Performs side effects. Must be safe to re-run."
  mode: queued
  max: 5
  fields:
    reason:
      description: "Why this script was invoked"
      example: "Triggered by automation X"

  sequence:
    - choose:
        - conditions: "{{ <guard_condition> }}"
          sequence:
            - service: <domain.service>
              data:
                entity_id: <TARGET_ENTITY>
        - default:
            - service: logbook.log
              data:
                name: "<Feature>"
                message: "Actuation skipped: guard condition not met. Reason={{ reason }}"
```

---

### 8.5 Dashboard Section Template (Observe → Understand → Act)
```yaml
# Observe
# - high-signal status
# - trends
# - health indicators

# Understand
# - explanation markdown
# - automation state + key conditions
# - thresholds and reasoning

# Act
# - primary toggles
# - routine actions
# - guarded advanced controls
```

---

## 9) Final Enforcement
- If you are unsure which rule applies, you must:
  1) Locate the nearest requirements document, and
  2) Default to the safer option: bounded waits, idempotent actions, and reversible changes.
- Violations are defects. Fixes are mandatory.

---

## 10) Sync Protocol

This project syncs via the Dev monorepo. See `/CLAUDE.md` for system-wide context.
Check `/PLANS/` for pending tasks from ChatGPT before starting new work.