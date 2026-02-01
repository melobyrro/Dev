# Home Assistant Implementation Plan: Observability & Dashboard Standardization

**Created:** 2026-01-31
**Status:** Ready for Execution
**Approach:** Backend-First (Infrastructure before UI)
**Predecessor:** `HOME_ASSISTANT_AUDIT_OBSERVABILITY.md`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Phase 1: Shared Observability Primitives](#2-phase-1-shared-observability-primitives)
3. [Phase 2: Automation Ownership Refactor](#3-phase-2-automation-ownership-refactor)
4. [Phase 3: Dashboard Tab Rollout](#4-phase-3-dashboard-tab-rollout)
5. [Validation & Regression Safety](#5-validation--regression-safety)
6. [Templates](#6-templates)
7. [Execution Strategy](#7-execution-strategy)

---

## 1. Overview

### 1.1 Goal

Transform Home Assistant dashboards from ad-hoc control panels to standardized observability surfaces where every automation is visible, documented, and traceable.

### 1.2 Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Dashboards with Automations tab | 1 (partial) | 9 (all with owned automations) |
| Dashboards skipped (no owned automations) | N/A | 4 (Byrro, Climate, Shield TV, Activity) |
| Automations with telemetry sensors | 0 | 120+ |
| Log format consistency | Mixed | Canonical (pipe-delimited) |
| Documentation panels | 0 | 9 features |

### 1.3 Principles

1. **Backend-First**: Create sensors and helpers before UI changes
2. **One-at-a-Time**: Migrate one dashboard completely before starting another
3. **Rollback-Ready**: Every change has a documented rollback procedure
4. **Validation-Gated**: No proceeding until current step validates

---

## 2. Phase 1: Shared Observability Primitives

### 2.1 Create `automation_observability.v1.0.yaml` Package

**Location:** `ha-config/packages/automation_observability.v1.0.yaml`

**Purpose:** Shared infrastructure for per-automation telemetry across all features.

**Contents:**

```yaml
# automation_observability.v1.0.yaml
# Shared observability infrastructure for automation telemetry
# Version: 1.0
# Created: 2026-01-31
# Location: ha-config/packages/automation_observability.v1.0.yaml

# ============================================================
# DOCUMENTATION
# ============================================================
# This package provides:
# 1. Daily counter reset automation for all feature counters
# 2. Template sensor patterns (document-only - actual sensors in feature packages)
# 3. Log aggregation sensor template
#
# Each feature package should:
# - Create counter.{feature}_{automation}_runs for each automation
# - Create sensor.{feature}_{automation}_telemetry for each automation
# - Create sensor.{feature}_automation_log for activity logging
# ============================================================

# ============================================================
# SHARED AUTOMATIONS
# ============================================================

automation:
  # Reset all automation run counters at midnight
  # Features must name their counters: counter.{feature}_{automation}_runs
  - alias: "Observability: Reset Daily Run Counters"
    id: observability_reset_daily_run_counters
    description: >
      Resets all automation run counters at midnight.
      Counter naming convention: counter.{feature}_{automation}_runs
    mode: single
    trigger:
      - platform: time
        at: "00:00:00"
    action:
      - service: counter.reset
        target:
          entity_id: >
            {{ states.counter
               | selectattr('entity_id', 'search', '_runs$')
               | map(attribute='entity_id')
               | list }}
      - service: logbook.log
        data:
          name: "OBSERVABILITY"
          message: "Daily run counters reset for {{ states.counter | selectattr('entity_id', 'search', '_runs$') | list | count }} counters"

# ============================================================
# SHARED SCRIPT: Log Automation Run
# ============================================================
# Call this script from automations to log execution with a single call
# Handles: counter increment, result tracking, and activity log entry

script:
  observability_log_run:
    alias: "Observability: Log Automation Run"
    description: >
      Universal script for logging automation execution.
      Increments run counter, sets result status, and adds log entry.
      Call at the end of any automation to log its execution.
    mode: parallel
    max: 50
    fields:
      feature:
        description: "Feature name (e.g., kia_ev9)"
        required: true
        example: "kia_ev9"
      automation:
        description: "Automation short name (e.g., departure_prep)"
        required: true
        example: "departure_prep"
      action:
        description: "Action performed (e.g., climate_start)"
        required: true
        example: "climate_start"
      trigger_type:
        description: "What triggered this (e.g., time, state, manual)"
        required: false
        default: "unknown"
        example: "time"
      result:
        description: "Outcome: success, error, skipped, timeout"
        required: false
        default: "success"
        selector:
          select:
            options:
              - success
              - error
              - skipped
              - timeout
      details:
        description: "Additional context"
        required: false
        default: ""
        example: "Target: 72F"
    sequence:
      # 1. Increment run counter
      - service: counter.increment
        target:
          entity_id: "counter.{{ feature }}_{{ automation }}_runs"
      # 2. Update result status
      - service: input_select.select_option
        target:
          entity_id: "input_select.{{ feature }}_{{ automation }}_result"
        data:
          option: "{{ result }}"
      # 3. Add log entry using canonical format
      - service: python_script.shift_event_log
        data:
          entity_prefix: "input_text.{{ feature }}_event"
          new_event: >-
            {{ now().isoformat()[:19] }}|{{ automation }}|{{ action }}|{{ trigger_type }}|{{ result }}|{{ details }}
          max_events: 10

# Usage example in an automation:
# action:
#   - service: script.observability_log_run
#     data:
#       feature: kia_ev9
#       automation: departure_prep
#       action: climate_start
#       trigger_type: time
#       result: success
#       details: "Target: 72F"

# ============================================================
# REFERENCE TEMPLATES (Copy to feature packages)
# ============================================================
# These are DOCUMENTATION ONLY - do not uncomment
# Copy and customize for each feature package

# --- Per-Automation Telemetry Sensor ---
# template:
#   - sensor:
#       - name: "{Feature} {Automation Name} Telemetry"
#         unique_id: {feature}_{automation}_telemetry
#         state: >-
#           {{ 'on' if is_state('automation.{feature}_{automation}', 'on') else 'off' }}
#         attributes:
#           alias: "{Human Readable Name}"
#           description: "{What it does}"
#           feature: "{feature}"
#           dashboard: "/{feature}"
#           trigger_type: "state|time|zone|event"  # Pick one
#           last_triggered: >-
#             {{ state_attr('automation.{feature}_{automation}', 'last_triggered') }}
#           last_triggered_ago: >-
#             {% set lt = state_attr('automation.{feature}_{automation}', 'last_triggered') %}
#             {% if lt %}{{ relative_time(lt) }}{% else %}never{% endif %}
#           next_run: >-
#             {{ states('input_datetime.{feature}_next_run') | default('N/A') }}
#           run_count_today: >-
#             {{ states('counter.{feature}_{automation}_runs') | int(0) }}
#           last_result: >-
#             {{ states('input_select.{feature}_{automation}_result') | default('unknown') }}
#           mode: "single|restart|queued|parallel"  # Match automation mode
#         availability: >-
#           {{ states('automation.{feature}_{automation}') not in ['unavailable', 'unknown'] }}

# --- Feature Log Sensor ---
# template:
#   - sensor:
#       - name: "{Feature} Automation Log"
#         unique_id: {feature}_automation_log
#         state: "{{ states('input_text.{feature}_event_1') | truncate(40) }}"
#         attributes:
#           entries: >-
#             {% set ns = namespace(entries=[]) %}
#             {% for i in range(1, 11) %}
#               {% set entry = states('input_text.{feature}_event_' ~ i) %}
#               {% if entry and entry not in ['unknown', 'unavailable', ''] %}
#                 {% set parts = entry.split('|') %}
#                 {% if parts | length >= 5 %}
#                   {% set ns.entries = ns.entries + [{
#                     'time': parts[0],
#                     'automation': parts[1],
#                     'action': parts[2],
#                     'trigger_type': parts[3],
#                     'result': parts[4],
#                     'details': parts[5] if parts | length > 5 else ''
#                   }] %}
#                 {% endif %}
#               {% endif %}
#             {% endfor %}
#             {{ ns.entries }}
#           last_update: "{{ now().isoformat() }}"
```

**Validation Command:**
```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('ha-config/packages/automation_observability.v1.0.yaml'))"

# After deployment, verify automation exists
curl -s -H "Authorization: Bearer $HA_TOKEN" http://homeassistant.local:8123/api/states/automation.observability_reset_daily_run_counters | jq .
```

### 2.2 Create Documentation Templates

**Location:** `docs/templates/`

#### 2.2.1 `automation-telemetry.yaml.template`

```yaml
# Automation Telemetry Sensor Template
# Copy this for each automation that needs dashboard visibility
#
# Required substitutions:
#   {FEATURE}         - Feature name (e.g., kia_ev9)
#   {AUTOMATION}      - Automation short name (e.g., departure_prep)
#   {ALIAS}           - Human readable name (e.g., "Departure Prep")
#   {DESCRIPTION}     - What it does
#   {DASHBOARD}       - Dashboard path (e.g., /kia-ev9)
#   {TRIGGER_TYPE}    - state|time|zone|event|webhook|numeric_state|template|sun
#   {MODE}            - single|restart|queued|parallel

template:
  - sensor:
      - name: "{FEATURE} {AUTOMATION} Telemetry"
        unique_id: {FEATURE}_{AUTOMATION}_telemetry
        icon: mdi:robot
        state: >-
          {{ 'on' if is_state('automation.{FEATURE}_{AUTOMATION}', 'on') else 'off' }}
        attributes:
          alias: "{ALIAS}"
          description: "{DESCRIPTION}"
          feature: "{FEATURE}"
          dashboard: "{DASHBOARD}"
          trigger_type: "{TRIGGER_TYPE}"
          last_triggered: >-
            {{ state_attr('automation.{FEATURE}_{AUTOMATION}', 'last_triggered') }}
          last_triggered_ago: >-
            {% set lt = state_attr('automation.{FEATURE}_{AUTOMATION}', 'last_triggered') %}
            {% if lt %}{{ relative_time(lt) }}{% else %}never{% endif %}
          next_run: >-
            {{ states('input_datetime.{FEATURE}_next_run') | default('N/A') }}
          run_count_today: >-
            {{ states('counter.{FEATURE}_{AUTOMATION}_runs') | int(0) }}
          last_result: >-
            {{ states('input_select.{FEATURE}_{AUTOMATION}_result') | default('unknown') }}
          mode: "{MODE}"
        availability: >-
          {{ states('automation.{FEATURE}_{AUTOMATION}') not in ['unavailable', 'unknown'] }}

# Supporting helpers (add to feature package)
counter:
  {FEATURE}_{AUTOMATION}_runs:
    name: "{ALIAS} Run Count"
    initial: 0
    step: 1
    icon: mdi:counter

input_select:
  {FEATURE}_{AUTOMATION}_result:
    name: "{ALIAS} Last Result"
    options:
      - success
      - error
      - skipped
      - timeout
      - unknown
    initial: unknown
    icon: mdi:check-circle
```

#### 2.2.2 `automations-tab.yaml.template`

```yaml
# Automations Tab Template
# Add this tab to every feature dashboard
#
# Required substitutions:
#   {FEATURE}         - Feature name for entity filtering
#   {FEATURE_TITLE}   - Human readable feature name
#
# Tab Structure (per CLAUDE.md Section 6.1):
# 1. Documentation Panel (Understand)
# 2. Observability Table (Observe)
# 3. Activity Log (Observe - Historical)

# For YAML dashboards: Add as a view in your dashboard YAML
# For Storage dashboards: Create these cards manually via UI

# ============================================================
# 1. DOCUMENTATION PANEL (Understand)
# ============================================================
# What this feature does, how automations work together

- type: markdown
  title: "{FEATURE_TITLE} Automation Overview"
  content: |
    ## Purpose
    [Describe what this feature accomplishes]

    ## How It Works
    [Explain how the automations coordinate]

    ## Triggers
    | Automation | Trigger | Condition |
    |------------|---------|-----------|
    | Automation 1 | State change | When X happens |
    | Automation 2 | Time-based | At 6:00 AM |

    ## Settings
    Configure in [Settings tab](/lovelace/{FEATURE}/settings) if applicable.

# ============================================================
# 2. OBSERVABILITY TABLE (Observe)
# ============================================================
# Shows all automations with their current status

- type: custom:flex-table-card
  title: "{FEATURE_TITLE} Automations"
  entities:
    include: sensor.{FEATURE}_*_telemetry
  columns:
    - name: Name
      data: alias
    - name: Description
      data: description
      modify: x ? (x.substring(0, 40) + (x.length > 40 ? '...' : '')) : '—'
    - name: Trigger
      data: trigger_type
      icon: true
    - name: Last Run
      data: last_triggered_ago
    - name: Today
      data: run_count_today
    - name: Status
      data: last_result
      modify: |-
        x === 'success' ? '✓' :
        x === 'error' ? '✗' :
        x === 'skipped' ? '○' :
        x === 'timeout' ? '⏱' : '—'
  css:
    tbody tr:nth-child(odd): 'background-color: var(--table-row-alternative-background-color)'
    th+th+th+th+th+th: 'text-align: center'
    td+td+td+td+td+td: 'text-align: center'

# ============================================================
# 3. ACTIVITY LOG (Observe - Historical)
# ============================================================
# [HARD] Must use tap_action: none per CLAUDE.md Section 6.3

- type: markdown
  title: "Recent Activity"
  content: |
    | Time | Automation | Action | Result | Details |
    |------|------------|--------|--------|---------|
    {% for entry in state_attr('sensor.{FEATURE}_automation_log', 'entries')[:10] -%}
    | {{ entry.time }} | {{ entry.automation }} | {{ entry.action }} | {{ entry.result }} | {{ entry.details }} |
    {% endfor %}
  card_mod:
    style: |
      ha-card {
        pointer-events: none;
      }

# Alternative for Storage dashboards (simpler, no card_mod needed):
# Use entities card with tap_action: none
- type: entities
  title: "Recent Activity"
  show_header_toggle: false
  entities:
    - entity: input_text.{FEATURE}_event_1
      tap_action:
        action: none
      hold_action:
        action: none
    - entity: input_text.{FEATURE}_event_2
      tap_action:
        action: none
      hold_action:
        action: none
    # ... repeat for event_3 through event_10
```

#### 2.2.3 `activity-log-card.yaml.template`

```yaml
# Activity Log Card Template
# [HARD] Must be read-only per CLAUDE.md Section 6.3
#
# Required substitutions:
#   {FEATURE}         - Feature name for entity filtering
#
# This template provides two options:
# 1. Markdown table (recommended for YAML dashboards)
# 2. Entities card (recommended for Storage dashboards)

# ============================================================
# OPTION 1: Markdown Table (Rich formatting)
# ============================================================
# Best for YAML dashboards where card_mod is available

type: markdown
title: "Activity Log"
content: |
  | Time | Automation | Action | Result | Details |
  |------|------------|--------|--------|---------|
  {% for entry in state_attr('sensor.{FEATURE}_automation_log', 'entries')[:10] -%}
  | {{ entry.time[-8:] }} | {{ entry.automation[:15] }} | {{ entry.action[:15] }} | {{ entry.result }} | {{ entry.details[:20] }} |
  {% endfor %}
card_mod:
  style: |
    ha-card {
      pointer-events: none;
    }

# ============================================================
# OPTION 2: Entities Card (No card_mod dependency)
# ============================================================
# Best for Storage dashboards managed via UI

# type: entities
# title: "Activity Log"
# show_header_toggle: false
# entities:
#   - entity: input_text.{FEATURE}_event_1
#     name: "Event 1"
#     tap_action:
#       action: none
#     hold_action:
#       action: none
#   - entity: input_text.{FEATURE}_event_2
#     name: "Event 2"
#     tap_action:
#       action: none
#     hold_action:
#       action: none
#   # ... continue for event_3 through event_10
```

#### 2.2.4 `documentation-panel.yaml.template`

```yaml
# Documentation Panel Template
# First section in every Automations tab (Understand)
#
# Required substitutions:
#   {FEATURE}         - Feature name
#   {FEATURE_TITLE}   - Human readable feature name
#   {PURPOSE}         - What this feature accomplishes
#   {HOW_IT_WORKS}    - How automations coordinate
#   {TRIGGER_TABLE}   - Markdown table of triggers

type: markdown
title: "{FEATURE_TITLE} Overview"
content: |
  ## Purpose
  {PURPOSE}

  ## How It Works
  {HOW_IT_WORKS}

  ## Automation Triggers
  {TRIGGER_TABLE}

  ## Related
  - [Settings](/lovelace/{FEATURE}/settings) — Configure thresholds and modes
  - [Requirements](/docs/{FEATURE}/REQUIREMENTS.md) — Feature specification

# ============================================================
# EXAMPLE (Patio AC)
# ============================================================
# type: markdown
# title: "Patio AC Overview"
# content: |
#   ## Purpose
#   Automatically manages patio AC based on time, temperature, and presence.
#
#   ## How It Works
#   1. **Day/Night Boundary** automations adjust schedules at sunrise/sunset
#   2. **Temperature Override** kicks in when outdoor temp exceeds threshold
#   3. **Presence Control** pauses AC when nobody is home
#
#   ## Automation Triggers
#   | Automation | Trigger | When |
#   |------------|---------|------|
#   | Day Start | Sun (sunrise) | Every sunrise |
#   | Night Start | Sun (sunset) | Every sunset |
#   | Temp Override | Numeric state | Outdoor > 85°F |
#   | Presence Off | State | Nobody home for 30min |
#
#   ## Related
#   - [Settings](/lovelace/patio-ac/settings) — Configure thresholds
```

### 2.3 Standardize Logging Format

**Canonical Log Entry Format:**
```
TIMESTAMP|AUTOMATION|ACTION|TRIGGER_TYPE|RESULT|DETAILS
```

**Example:**
```
2026-01-31T10:30:00|departure_prep|climate_start|time|success|Target: 72°F
```

**Update Pattern for Feature Automations:**

When an automation runs, it should call `python_script.shift_event_log` with the canonical format:

```yaml
action:
  - service: python_script.shift_event_log
    data:
      entity_prefix: input_text.{feature}_event
      new_event: >-
        {{ now().isoformat()[:19] }}|{automation}|{action}|{trigger_type}|success|{details}
      max_events: 10
```

**Validation:**
- Verify `shift_event_log.py` exists at `ha-config/python_scripts/shift_event_log.py`
- No changes needed to the script - format enforcement is in automation calls

---

## 3. Phase 2: Automation Ownership Refactor

> **NOTE: Phase 2 Merged into Phase 3**
>
> Sequential thinking validation identified a dependency mismatch: Phase 2 prioritized "high-value" features (System Health first) while Phase 3 prioritized "low-risk" dashboards (Dawarich first). This created a conflict.
>
> **Resolution:** Telemetry sensors are now created per-dashboard during the Phase 3 rollout, not all upfront. This ensures each dashboard has its telemetry ready immediately before its UI rollout.
>
> The sections below remain as reference for the work to be done, but the execution happens in Phase 3 on a per-dashboard basis.

### 3.1 Update REGISTRY.md with Automation Ownership

Add a new section to `REGISTRY.md`:

```markdown
## Automation Ownership

Every automation must appear in exactly ONE dashboard's Automations tab.

| Automation ID | Feature | Dashboard | File Location |
|---------------|---------|-----------|---------------|
| kia_ev9_departure_prep | Kia EV9 | /kia-ev9 | kia-ev9/automations.v2.8.yaml |
| kia_ev9_charge_management | Kia EV9 | /kia-ev9 | kia-ev9/automations.v2.8.yaml |
| patio_ac_day_boundary | Patio AC | /patio-ac | ha-config/packages/patio_ac.yaml |
| ... | ... | ... | ... |
```

### 3.2 Add Telemetry Sensors

**Priority Order (high-value first):**

1. **System Health** (safety/monitoring) - 20+ automations
2. **Kia EV9** (high complexity) - 36 automations
3. **Patio AC** (medium complexity) - 30+ automations
4. **Jose Vacuum** (low complexity) - 8+ automations
5. **Daikin** (low complexity) - 6 automations
6. Remaining features...

**Per-Feature Implementation:**

For each feature:
1. List all automations belonging to feature
2. Create telemetry sensors in feature package
3. Create run counters in feature package
4. Create result trackers in feature package
5. Create log sensor aggregating `input_text.{feature}_event_*`

### 3.3 Migrate Logging to Canonical Format

**Current State Analysis:**

| Feature | Current Log Pattern | Migration Needed |
|---------|---------------------|------------------|
| Kia EV9 | Custom `shift_event_log` | Update format |
| Patio AC | `input_text.patio_ac_event_*` | Update format |
| Jose Vacuum | `input_text.jose_event_*` | Update format |
| Dawarich | Mixed | Standardize |
| Others | None | Add |

**Migration Pattern:**

Replace existing log calls like:
```yaml
# OLD
- service: python_script.shift_event_log
  data:
    new_event: "Automation triggered at {{ now() }}"
```

With canonical format:
```yaml
# NEW
- service: python_script.shift_event_log
  data:
    entity_prefix: input_text.{feature}_event
    new_event: >-
      {{ now().isoformat()[:19] }}|{automation}|{action}|{{ trigger.platform }}|success|{{ details }}
    max_events: 10
```

---

## 4. Phase 3: Dashboard Tab Rollout

### 4.1 Rollout Order (Low-Risk First)

**Dashboards Receiving Automations Tab (9 total):**

| Order | Dashboard | Mode | Automations | Complexity | Rollback Method |
|-------|-----------|------|-------------|------------|-----------------|
| 1 | Dawarich | Storage | 8 | Low | HA UI: remove Automations view |
| 2 | Daikin | Storage | 6 | Low | HA UI: remove Automations view |
| 3 | Trackers | Storage | 1 | Low | HA UI: remove Automations view |
| 4 | Wyze Cameras | YAML | 4 | Low | `git checkout HEAD~1 -- ha-config/dashboards/wyze_cameras.yaml` |
| 5 | Homelab | YAML | 4 | Low | `git checkout HEAD~1 -- homelab/lovelace.homelab.yaml` |
| 6 | Jose Vacuum | Storage | 8+ | Medium | HA UI: remove Automations view |
| 7 | System Health | YAML | 20+ | Medium | `git checkout HEAD~1 -- ha-config/dashboards/system_health.yaml` |
| 8 | Patio AC | YAML | 30+ | High | `git checkout HEAD~1 -- patio-ac/dashboards/patio_ac.*.yaml` |
| 9 | Kia EV9 | Storage | 36 | High | HA UI: remove Automations view + restore backup |

**Dashboards Skipped (4 total - No Owned Automations):**

Per CLAUDE.md Section 5.7: "Every automation must appear in exactly ONE dashboard's Automations tab."

| Dashboard | Path | Rationale |
|-----------|------|-----------|
| Byrro (Home) | `/dashboard-room` | Overview dashboard - automations belong to feature dashboards |
| Climate | `/climate` | Aggregate view - automations owned by Patio AC and Daikin |
| Shield TV | `/shield-tv` | Control dashboard only - no automations |
| Activity | `/activity` | Aggregation view - displays activity from all features, no owned automations |

These dashboards display data from features but don't own any automations. Adding empty Automations tabs would violate the "exactly one dashboard" rule and add visual clutter.

**Revised Per-Dashboard Workflow:**

For each dashboard in rollout order:
1. **Prep**: Identify automations belonging to this dashboard
2. **Telemetry**: Create sensors, counters, result trackers for those automations
3. **Logging**: Create log infrastructure, update automations to call `script.observability_log_run`
4. **Dashboard**: Add Automations tab with 3-section layout
5. **Validate**: YAML check, HA config, Chrome MCP visual inspection
6. **Commit**: Atomic commit for this dashboard complete

### 4.2 Per-Dashboard Procedure

For each dashboard in order:

#### Step 1: Backup
```bash
# For YAML dashboards
git add -A && git commit -m "backup: pre-{dashboard} automations tab"
cp {dashboard_file} {dashboard_file}.backup-$(date +%Y%m%d-%H%M%S)

# For Storage dashboards
# Export via HA UI: Settings → Dashboards → {dashboard} → Raw Configuration Editor → Copy
# Save to: {feature}/.backup/dashboard-{date}.yaml
```

#### Step 2: Create Telemetry Sensors
```yaml
# Add to feature package
template:
  - sensor:
      - name: "{Feature} {Automation} Telemetry"
        # ... (use automation-telemetry.yaml.template)
```

#### Step 3: Create Log Infrastructure
```yaml
# Add to feature package
input_text:
  {feature}_event_1:
    name: "{Feature} Event 1"
    max: 255
  {feature}_event_2:
    name: "{Feature} Event 2"
    max: 255
  # ... through event_10

template:
  - sensor:
      - name: "{Feature} Automation Log"
        unique_id: {feature}_automation_log
        # ... (use template from Phase 1)
```

#### Step 4: Add Automations Tab

**For YAML dashboards:**
```yaml
views:
  # ... existing views ...
  - title: Automations
    path: automations
    icon: mdi:robot
    cards:
      # 1. Documentation Panel
      - type: markdown
        # ... (use documentation-panel.yaml.template)

      # 2. Observability Table
      - type: custom:flex-table-card
        # ... (use automations-tab.yaml.template)

      # 3. Activity Log
      - type: markdown
        # ... (use activity-log-card.yaml.template)
```

**For Storage dashboards:**
1. Open dashboard in HA UI
2. Click "Edit Dashboard"
3. Add new view "Automations"
4. Add cards manually following template structure

#### Step 5: Validate

```bash
# 1. YAML syntax check
python3 -c "import yaml; yaml.safe_load(open('{dashboard_file}'))"

# 2. HA config check
ha core check

# 3. Reload dashboard
ha service call lovelace.reload_resources

# 4. Visual validation via Chrome MCP
# - Navigate to dashboard
# - Verify Automations tab exists
# - Verify 3-section layout (Documentation, Table, Log)
# - Check mobile view
# - Check tablet view
# - Check desktop view

# 5. Console error check
# - Open browser dev tools
# - Verify no JS errors
```

#### Step 6: Commit (if successful)
```bash
git add -A
git commit -m "feat({feature}): Add Automations tab to dashboard

- Add telemetry sensors for {N} automations
- Add activity log infrastructure
- Add Automations tab with Documentation/Table/Log sections
- Follows CLAUDE.md Section 6.1 (Observe → Understand → Act)

Completes dashboard compliance per CLAUDE.md Section 5.7"
```

#### Step 7: Rollback (if failed)

**For YAML dashboards:**
```bash
git checkout HEAD~1 -- {dashboard_file}
ha service call lovelace.reload_resources
```

**For Storage dashboards:**
1. HA UI → Settings → Dashboards
2. Edit dashboard
3. Delete Automations view
4. Or: Restore from backup file via Raw Configuration Editor

### 4.3 Dashboard-Specific Notes

#### Dawarich (Order 1)
- Simplest - already has partial automation visibility
- 8 automations to add telemetry
- Path: `/dashboard-automations` (Dawarich subview)

#### Daikin (Order 2)
- 6 automations in `Daikin/daikin_automations.yaml`
- Dashboard: `daikin_dashboard_deployed_v2.yaml` (non-standard naming - consider rename)
- Mode: Storage

#### Trackers (Order 3)
- Minimal automations (Reddit tracker only)
- Part of notifications dashboard
- Mode: Storage

#### Wyze Cameras (Order 4)
- First YAML dashboard in sequence
- 4 automations (Frigate-related)
- Path: `ha-config/dashboards/wyze_cameras.yaml`

#### Homelab (Order 5)
- Mixed automations (NetAlertX, Plex)
- May need to split automations by source
- Path: `homelab/lovelace.homelab.yaml`

#### Jose Vacuum (Order 6)
- 8+ automations across multiple packages
- `packages/jose_schedule_v2_0.yaml`
- `packages/ecovacs_recovery_package.yaml`
- Already has some telemetry - enhance

#### System Health (Order 7)
- 20+ automations across health packages
- Critical observability target
- Path: TBD (create if missing)

#### Patio AC (Order 8)
- 30+ automations
- Complex package: `packages/patio_ac.yaml`
- YAML dashboard: `patio-ac/dashboards/patio_ac.*.yaml`

#### Kia EV9 (Order 9)
- Most complex - 36 automations
- Multiple files: `kia-ev9/automations.v2.8.yaml`, `ha-config/automations.v3.0.yaml`
- Storage dashboard - backup carefully
- Has existing telemetry to enhance

---

## 5. Validation & Regression Safety

### 5.1 Per-Change Definition of Done

| Gate | Requirement | Check Command |
|------|-------------|---------------|
| YAML Valid | No syntax errors | `python3 -c "import yaml; yaml.safe_load(open('file'))"` |
| HA Config | Config check passes | `ha core check` |
| No Log Errors | No new errors after reload | Check HA logs |
| Mobile OK | Renders correctly | Chrome MCP screenshot |
| Tablet OK | Renders correctly | Chrome MCP screenshot |
| Desktop OK | Renders correctly | Chrome MCP screenshot |
| Hierarchy | Observe → Understand → Act preserved | Visual inspection |

### 5.2 Rollback Procedures

#### YAML Dashboard Rollback
```bash
# Revert single file
git checkout HEAD~1 -- {file_path}

# Reload in HA
ha service call lovelace.reload_resources

# Verify
# - Navigate to dashboard
# - Confirm Automations tab removed
# - Confirm no errors
```

#### Storage Dashboard Rollback
```
1. HA UI → Settings → Dashboards
2. Find affected dashboard
3. Edit → delete Automations view
4. Save
5. Refresh browser
6. Verify functionality restored
```

#### Package Rollback
```bash
# Revert package file
git checkout HEAD~1 -- ha-config/packages/{package}.yaml

# Reload HA
ha core restart  # Required for package changes

# Verify
# - Check entities exist
# - Check automations functional
```

### 5.3 If a Dashboard Breaks

**STOP immediately** - do not continue to next dashboard.

1. Execute rollback for that specific dashboard
2. Reload dashboard in HA
3. Verify functionality restored via Chrome MCP
4. Document what went wrong:
   ```
   ## Failure Log: {Dashboard}
   - Date: {date}
   - Step failed: {step}
   - Error: {error message}
   - Root cause: {analysis}
   - Fix: {what to do differently}
   ```
5. Create issue if systemic problem
6. Retry with fixes before proceeding

---

## 6. Templates

### 6.1 automation-telemetry.yaml.template

Full template available in `docs/templates/automation-telemetry.yaml.template` (created in Phase 1.2.1)

### 6.2 automations-tab.yaml.template

Full template available in `docs/templates/automations-tab.yaml.template` (created in Phase 1.2.2)

### 6.3 activity-log-card.yaml.template

Full template available in `docs/templates/activity-log-card.yaml.template` (created in Phase 1.2.3)

### 6.4 documentation-panel.yaml.template

Full template available in `docs/templates/documentation-panel.yaml.template` (created in Phase 1.2.4)

---

## 7. Execution Strategy

### 7.1 Task Isolation

Each phase/step runs in its own Task subagent:

```
Phase 1: Primitives
├── Task 1.1: Create automation_observability.v1.0.yaml
├── Task 1.2: Create documentation templates
└── Task 1.3: Validate primitives deploy correctly

Phase 2: Refactor
├── Task 2.1: Update REGISTRY.md with ownership
├── Task 2.2: Add telemetry to first feature (System Health)
└── Task 2.3: Migrate logging format

Phase 3: Dashboard Rollout (sequential)
├── Task 3.1: Dawarich dashboard
├── Task 3.2: Daikin dashboard
├── Task 3.3: Trackers dashboard
├── Task 3.4: Wyze Cameras dashboard
├── Task 3.5: Homelab dashboard
├── Task 3.6: Jose Vacuum dashboard
├── Task 3.7: System Health dashboard
├── Task 3.8: Patio AC dashboard
└── Task 3.9: Kia EV9 dashboard
```

### 7.2 Dependencies

```
Phase 1.1 → Phase 1.2 → Phase 1.3
                           ↓
Phase 2.1 → Phase 2.2 → Phase 2.3
                           ↓
Phase 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7 → 3.8 → 3.9
```

### 7.3 Estimated Timeline

| Phase | Estimated Duration | Blocking? |
|-------|-------------------|-----------|
| Phase 1 | 2-3 hours | Yes |
| Phase 2 | 3-4 hours | Yes |
| Phase 3.1-3.3 | 1 hour each | Sequential |
| Phase 3.4-3.6 | 1.5 hours each | Sequential |
| Phase 3.7-3.9 | 2-3 hours each | Sequential |

**Total: ~20-25 hours**

### 7.4 Success Metrics

After completion:

| Metric | Target |
|--------|--------|
| Dashboards with Automations tab | 13/13 (100%) |
| Automations with telemetry | 120+/120+ (100%) |
| Automations visible in exactly one dashboard | 120+/120+ (100%) |
| Documentation panels | 10/10 features |
| Log format compliance | 100% canonical |

---

## Appendix A: File Paths Reference

| File | Purpose |
|------|---------|
| `ha-config/packages/automation_observability.v1.0.yaml` | Shared observability primitives |
| `docs/templates/automation-telemetry.yaml.template` | Per-automation sensor template |
| `docs/templates/automations-tab.yaml.template` | Dashboard tab structure template |
| `docs/templates/activity-log-card.yaml.template` | Read-only log card template |
| `docs/templates/documentation-panel.yaml.template` | Feature docs panel template |
| `REGISTRY.md` | Feature registry with automation ownership |
| `ha-config/python_scripts/shift_event_log.py` | Rotating log utility |

---

## Appendix B: Command Reference

```bash
# YAML validation
python3 -c "import yaml; yaml.safe_load(open('file.yaml'))"

# HA config check
ha core check

# Reload dashboards
ha service call lovelace.reload_resources

# Restart HA (for package changes)
ha core restart

# Git backup
git add -A && git commit -m "backup: pre-change"

# Git rollback single file
git checkout HEAD~1 -- path/to/file

# Check entity exists
curl -s -H "Authorization: Bearer $HA_TOKEN" \
  http://homeassistant.local:8123/api/states/sensor.{entity_id} | jq .
```

---

*End of Implementation Plan*
