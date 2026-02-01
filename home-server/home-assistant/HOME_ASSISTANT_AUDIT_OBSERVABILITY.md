# Home Assistant Audit: Observability & Dashboard Architecture

**Created:** 2026-01-31
**Status:** Audit Complete - Ready for Implementation
**Scope:** Dashboard inventory, automation ownership, observability gaps, canonical schemas

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Dashboard Inventory](#2-dashboard-inventory)
3. [Automation Inventory by Feature](#3-automation-inventory-by-feature)
4. [Redundancy Analysis](#4-redundancy-analysis)
5. [Observability Gap Analysis](#5-observability-gap-analysis)
6. [Existing Infrastructure](#6-existing-infrastructure)
7. [Canonical Schema Proposal](#7-canonical-schema-proposal)
8. [Automation Tab Information Architecture](#8-automation-tab-information-architecture)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Executive Summary

This audit documents the current state of Home Assistant dashboards and automations, identifying gaps in observability and proposing a canonical architecture for consistent automation visibility across all features.

### Key Findings

| Metric | Value |
|--------|-------|
| Total Dashboards | 13 |
| Dashboards with Automations Tab | 1 (partial) |
| Total Automation Features | 10 |
| Automations Without Dashboard Visibility | ~90% |
| Observability Mechanisms | Inconsistent |

### Critical Gaps

1. **No Automations Tabs** - 12 of 13 dashboards lack dedicated Automations tabs
2. **No Per-Automation Telemetry** - Last run, next run, run counts not exposed
3. **Inconsistent Logging** - Mixed formats across features
4. **No Documentation Panels** - Automation purpose/logic not visible in UI

---

## 2. Dashboard Inventory

| Dashboard | Path | Mode | Purpose | Has Automations Tab? |
|-----------|------|------|---------|---------------------|
| Byrro (Home) | `/dashboard-room` | Storage | Main home view | No |
| Jose Vacuum | `/jose` | Storage | Vacuum control | No |
| Daikin | `/daikin` | Storage | HVAC control | No |
| Patio AC | `/patio-ac` | YAML | AC automation | No |
| Kia EV9 | `/kia-ev9` | Storage | Vehicle control | No |
| Climate | `/climate` | Storage | Climate overview | No |
| Wyze Cameras | `/wyze-cameras` | YAML | Camera monitoring | No |
| Shield TV | `/shield-tv` | Storage | Media control | No |
| Homelab | `/homelab` | YAML | Server monitoring | No |
| Automations | `/dashboard-automations` | Storage | Automation meta-dashboard | Partial (Dawarich only) |
| Notifications | `/notifications-logs` | Storage | Logs & alerts | No |
| Activity | `/activity` | Storage | Activity feed | No |
| System Health | `/system-health` | YAML | Health monitoring | No |

### Dashboard Mode Distribution

| Mode | Count | Notes |
|------|-------|-------|
| Storage | 9 | Managed via UI, stored in `.storage/` |
| YAML | 4 | Version-controlled, declarative |

### Compliance Status

Per CLAUDE.md Section 5.7 and 6.2:

> **[HARD]** Every automation must appear in exactly ONE dashboard's Automations tab.

> **[HARD]** Required Tabs: Overview, Automations (required), Details (optional), Settings (if applicable)

**Current Compliance: 0%** - No dashboard fully implements required Automations tab.

---

## 3. Automation Inventory by Feature

| Feature | Count | Current Location | Target Dashboard |
|---------|-------|------------------|------------------|
| Kia EV9 | 36 | `ha-config/automations.v3.0.yaml` + `kia-ev9/automations.v2.8.yaml` | `/kia-ev9` |
| Patio AC | 30+ | `ha-config/packages/patio_ac.yaml` | `/patio-ac` |
| Dawarich | 8 | `automations/dawarich_automations.yaml` | `/dashboard-automations/dawarich` |
| System Health | 20+ | `packages/system_entity_health.v1.0.yaml`, `automation_health.v1.0.yaml`, `integration_health.yaml` | `/system-health` |
| Jose Vacuum | 8+ | `packages/jose_schedule_v2_0.yaml`, `ecovacs_recovery_package.yaml` | `/jose` |
| Daikin | 6 | `Daikin/daikin_automations.yaml` | `/daikin` |
| Wyze/Frigate | 4 | `ha-config/automations.v3.0.yaml` | `/wyze-cameras` |
| Network (NetAlertX) | 2 | `ha-config/automations.v3.0.yaml` | `/homelab` |
| Plex | 2 | `ha-config/automations.v3.0.yaml` | `/homelab` |
| Trackers (Reddit) | 1+ | TBD | `/notifications-logs/trackers` |

### Total Estimated Automations: ~120+

### File Location Analysis

| Location Pattern | Count | Recommendation |
|------------------|-------|----------------|
| Feature packages (`packages/*.yaml`) | ~60% | Keep - proper encapsulation |
| Root automations file (`automations.v3.0.yaml`) | ~30% | Migrate to feature packages |
| Feature subfolders (`kia-ev9/*.yaml`, etc.) | ~10% | Keep - proper encapsulation |

---

## 4. Redundancy Analysis

### Investigation: `/notifications-logs/trackers` vs `/dashboard-automations/dawarich`

**Page 1: `/notifications-logs/trackers`**
- **Purpose:** Reddit automation that monitors private tracker signups
- **Function:** Alerts when trackers open for registration
- **Domain:** Notification/monitoring

**Page 2: `/dashboard-automations/dawarich`**
- **Purpose:** Dawarich location trip automation management
- **Function:** Tracks physical trips and location data
- **Domain:** Location/GPS tracking

### Conclusion

**NOT REDUNDANT** - These are completely different features:

| Aspect | Trackers | Dawarich |
|--------|----------|----------|
| Data Source | Reddit API | GPS/Location |
| Trigger Type | External events | Zone transitions |
| Output | Notifications | Trip logs |
| User Action | Manual signup | Automatic logging |

Both pages should remain but be clearly documented in their respective dashboards.

---

## 5. Observability Gap Analysis

| Gap | Current State | Target State | Priority |
|-----|--------------|--------------|----------|
| Per-automation last_run | Only via `state_attr('automation.*', 'last_triggered')` | Dedicated telemetry sensor per automation | High |
| Per-automation next_run | Not tracked | Calculated for time-based triggers | High |
| Run count/frequency | Not tracked | Daily counter per automation | Medium |
| Trigger type visibility | Not exposed | Attribute on telemetry sensor | Medium |
| Consistent log format | Mixed (input_text, logbook, markdown) | Canonical pipe-delimited table format | High |
| Documentation panels | Non-existent | YAML metadata + dashboard display | Medium |
| Error tracking | Partial (`automation_health.v1.0.yaml`) | Unified error sensor per feature | Medium |
| Dashboard navigation | No cross-links | Consistent back-links to feature dashboard | Low |

### Current Observability by Feature

| Feature | Has Telemetry? | Has Log? | Has Error Tracking? | Has Documentation? |
|---------|---------------|----------|---------------------|-------------------|
| Kia EV9 | Partial | Yes (custom) | Yes | No |
| Patio AC | No | Yes (input_text) | No | No |
| Dawarich | Partial | Yes | No | No |
| System Health | Yes | Yes | Yes | No |
| Jose Vacuum | Partial | Yes | Yes | No |
| Daikin | No | No | Partial | No |
| Wyze/Frigate | No | No | No | No |
| Homelab | No | Partial | No | No |

---

## 6. Existing Infrastructure

### Health Packages

| Package | Path | Function |
|---------|------|----------|
| System Entity Health | `packages/system_entity_health.v1.0.yaml` | Entity availability monitoring |
| Automation Health | `packages/automation_health.v1.0.yaml` | Error tracking, stale detection |
| Integration Health | `packages/integration_health.yaml` | Integration status (EV9, Jose, Daikin, Patio AC) |

### Logging Mechanisms

| Mechanism | Usage | Pros | Cons |
|-----------|-------|------|------|
| `python_script.shift_event_log` | Rotating log entries | Flexible, self-managing | Requires python_script integration |
| `input_text.{feature}_event_{1-10}` | Log storage pattern | Simple, native | Fixed size, no timestamps |
| Logbook calls with `WATCHDOG_*` prefixes | System events | Searchable | Not visible in dashboards |
| Markdown cards | Display only | Rich formatting | Manual construction |

### Useful Patterns Found

**Rotating Event Log (Jose Vacuum):**
```yaml
python_script.shift_event_log:
  # Shifts entries down, adds new entry at top
  # Maintains fixed-size buffer
```

**Watchdog Logging (System Health):**
```yaml
service: logbook.log
data:
  name: "WATCHDOG_AUTOMATION_HEALTH"
  message: "{{ trigger.event.data.name }} failed"
```

**State Attribute Telemetry:**
```yaml
state: "{{ state_attr('automation.feature_name', 'last_triggered') }}"
```

---

## 7. Canonical Schema Proposal

### 7.1 Entity Naming Convention

Following CLAUDE.md Section 4.4 (`area_room_device_modifier`):

```
# Telemetry Sensors
sensor.{feature}_{automation_short_name}_telemetry

# Log Sensors
sensor.{feature}_automation_log

# Run Counters
counter.{feature}_{automation_short_name}_runs

# Error Tracking
sensor.{feature}_automation_errors
```

**Examples:**
```yaml
sensor.kia_ev9_departure_prep_telemetry
sensor.kia_ev9_automation_log
counter.kia_ev9_departure_prep_runs
sensor.kia_ev9_automation_errors
```

### 7.2 Telemetry Sensor Attributes

Every automation telemetry sensor MUST expose:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `alias` | string | Human-readable name | "Departure Prep" |
| `description` | string | What the automation does | "Preconditions car before departure" |
| `feature` | string | Feature grouping | "kia_ev9" |
| `dashboard` | string | Target dashboard path | "/kia-ev9" |
| `trigger_type` | enum | Primary trigger category | `state\|zone\|time_pattern\|time\|event\|webhook` |
| `last_triggered` | datetime | Last execution time | "2026-01-31T10:30:00" |
| `last_triggered_ago` | string | Human-readable elapsed | "2 hours ago" |
| `next_run` | datetime | Next scheduled run (if time-based) | "2026-01-31T18:00:00" |
| `run_count_today` | int | Executions since midnight | 3 |
| `last_result` | enum | Outcome of last run | `success\|error\|skipped\|timeout` |
| `mode` | enum | Automation mode | `single\|restart\|queued\|parallel` |

### 7.3 Trigger Type Enumeration

| Type | Description | Next Run Calculable? |
|------|-------------|---------------------|
| `state` | Entity state change | No |
| `zone` | Zone enter/leave | No |
| `time_pattern` | Cron-like pattern | Yes |
| `time` | Specific time | Yes |
| `event` | Event bus | No |
| `webhook` | HTTP webhook | No |
| `numeric_state` | Threshold crossing | No |
| `template` | Template condition | No |
| `sun` | Sunrise/sunset | Yes |

### 7.4 Standard Log Table Format

**Pipe-Delimited Schema:**
```
TIMESTAMP|AUTOMATION|ACTION|TRIGGER_TYPE|RESULT|DETAILS
```

**Column Definitions:**

| Column | Width | Description | Example |
|--------|-------|-------------|---------|
| `TIMESTAMP` | ISO 8601 | Execution time | `2026-01-31T10:30:00` |
| `AUTOMATION` | 30 chars max | Short automation name | `departure_prep` |
| `ACTION` | 20 chars max | Action taken | `climate_start` |
| `TRIGGER_TYPE` | 15 chars max | What triggered it | `time` |
| `RESULT` | 10 chars max | Outcome | `success` |
| `DETAILS` | Variable | Additional context | `Target: 72°F` |

**Example Log Entry:**
```
2026-01-31T10:30:00|departure_prep|climate_start|time|success|Target: 72°F, Duration: 15min
```

### 7.5 Template Sensor Definition

```yaml
template:
  - sensor:
      - name: "Kia EV9 Departure Prep Telemetry"
        unique_id: kia_ev9_departure_prep_telemetry
        state: >-
          {{ state_attr('automation.kia_ev9_departure_prep', 'last_triggered') | default('never') }}
        attributes:
          alias: "Departure Prep"
          description: "Preconditions EV9 climate before scheduled departure"
          feature: "kia_ev9"
          dashboard: "/kia-ev9"
          trigger_type: "time"
          last_triggered: >-
            {{ state_attr('automation.kia_ev9_departure_prep', 'last_triggered') }}
          last_triggered_ago: >-
            {{ relative_time(state_attr('automation.kia_ev9_departure_prep', 'last_triggered')) }}
          next_run: >-
            {{ states('input_datetime.kia_ev9_next_departure') }}
          run_count_today: >-
            {{ states('counter.kia_ev9_departure_prep_runs') | int(0) }}
          last_result: >-
            {{ states('input_select.kia_ev9_departure_prep_result') }}
          mode: "single"
        availability: >-
          {{ states('automation.kia_ev9_departure_prep') not in ['unavailable', 'unknown'] }}
```

---

## 8. Automation Tab Information Architecture

Per CLAUDE.md Section 6.1 (Observe → Understand → Act) and Section 6.2 (Required Tabs):

### 8.1 Three-Section Layout

Every Automations tab MUST contain these sections in order:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. DOCUMENTATION PANEL (Understand)                         │
│    - Goal: What this feature accomplishes                   │
│    - Method: How automations work together                  │
│    - Triggers: What initiates each automation               │
│    - Settings: Link to Settings tab (if applicable)         │
├─────────────────────────────────────────────────────────────┤
│ 2. OBSERVABILITY TABLE (Observe)                            │
│    flex-table-card with columns:                            │
│    Name | Description | Trigger | Last Run | Next Run | ●   │
├─────────────────────────────────────────────────────────────┤
│ 3. ACTIVITY LOG (Observe - Historical)                      │
│    markdown table with tap_action: none                     │
│    Time | Automation | Action | Result | Details            │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Documentation Panel Card

```yaml
type: markdown
title: "Feature Documentation"
content: |
  ## Goal
  {{ state_attr('sensor.{feature}_documentation', 'goal') }}

  ## How It Works
  {{ state_attr('sensor.{feature}_documentation', 'method') }}

  ## Triggers
  {{ state_attr('sensor.{feature}_documentation', 'triggers') }}

  ## Settings
  [Configure Settings](/lovelace/{feature}/settings)
```

### 8.3 Observability Table (flex-table-card)

```yaml
type: custom:flex-table-card
title: "Automations"
entities:
  include: sensor.*_telemetry
  exclude: sensor.other_*
columns:
  - name: Name
    data: alias
  - name: Description
    data: description
    modify: x.substring(0, 50) + (x.length > 50 ? '...' : '')
  - name: Trigger
    data: trigger_type
    icon: >-
      {% if x == 'time' %}mdi:clock{% elif x == 'state' %}mdi:toggle-switch{% else %}mdi:lightning-bolt{% endif %}
  - name: Last Run
    data: last_triggered_ago
  - name: Next Run
    data: next_run
    modify: x ? new Date(x).toLocaleTimeString() : '—'
  - name: Status
    data: last_result
    modify: >-
      x === 'success' ? '🟢' : x === 'error' ? '🔴' : x === 'skipped' ? '🟡' : '⚪'
css:
  tbody tr:nth-child(odd): 'background-color: var(--table-row-alternative-background-color)'
```

### 8.4 Activity Log Card

**[HARD] Must use `tap_action: none`** per CLAUDE.md Section 6.3:

```yaml
type: markdown
title: "Activity Log"
content: |
  | Time | Automation | Action | Result | Details |
  |------|------------|--------|--------|---------|
  {% for entry in state_attr('sensor.{feature}_automation_log', 'entries')[:10] %}
  | {{ entry.time }} | {{ entry.automation }} | {{ entry.action }} | {{ entry.result }} | {{ entry.details }} |
  {% endfor %}
card_mod:
  style: |
    ha-card {
      pointer-events: none;
    }
```

Alternative using `tap_action`:

```yaml
type: custom:auto-entities
card:
  type: entities
  title: "Activity Log"
filter:
  include:
    - entity_id: input_text.{feature}_event_*
entities:
  - entity: input_text.{feature}_event_1
    tap_action:
      action: none
  # ... repeat for all log entries
```

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Week 1)

| Task | Priority | Effort |
|------|----------|--------|
| Create telemetry sensor template | High | 2h |
| Create log sensor template | High | 2h |
| Create flex-table-card template | High | 1h |
| Create documentation sensor template | Medium | 1h |
| Update CLAUDE.md templates folder | Medium | 1h |

### Phase 2: High-Value Features (Week 2-3)

| Feature | Automation Count | Complexity | Priority |
|---------|-----------------|------------|----------|
| Kia EV9 | 36 | High | 1 |
| Patio AC | 30+ | Medium | 2 |
| System Health | 20+ | Medium | 3 |

### Phase 3: Remaining Features (Week 4-5)

| Feature | Automation Count | Complexity | Priority |
|---------|-----------------|------------|----------|
| Jose Vacuum | 8+ | Low | 4 |
| Dawarich | 8 | Low | 5 |
| Daikin | 6 | Low | 6 |
| Wyze/Frigate | 4 | Low | 7 |
| Homelab | 4 | Low | 8 |
| Trackers | 1+ | Low | 9 |

### Phase 4: Validation & Documentation (Week 6)

| Task | Priority | Effort |
|------|----------|--------|
| Verify all dashboards have Automations tab | High | 2h |
| Verify all automations visible in exactly one dashboard | High | 2h |
| Update REGISTRY.md with dashboard mappings | Medium | 1h |
| Update feature REQUIREMENTS.md files | Medium | 2h |
| Create runbook for adding new automations | Low | 1h |

---

## Appendix A: Migration Checklist per Feature

For each feature being migrated:

- [ ] Identify all automations belonging to feature
- [ ] Create telemetry sensors for each automation
- [ ] Create aggregate log sensor for feature
- [ ] Create documentation sensor with goal/method/triggers
- [ ] Create/update Automations tab on target dashboard
- [ ] Add Documentation Panel
- [ ] Add Observability Table (flex-table-card)
- [ ] Add Activity Log with `tap_action: none`
- [ ] Verify mobile/tablet/desktop rendering
- [ ] Update feature REQUIREMENTS.md
- [ ] Run full validation checklist

---

## Appendix B: Entity Examples by Feature

### Kia EV9

```yaml
# Telemetry Sensors
sensor.kia_ev9_departure_prep_telemetry
sensor.kia_ev9_charge_management_telemetry
sensor.kia_ev9_arrival_notification_telemetry
# ... (36 total)

# Log Sensor
sensor.kia_ev9_automation_log

# Counters
counter.kia_ev9_departure_prep_runs
counter.kia_ev9_charge_management_runs

# Error Tracking
sensor.kia_ev9_automation_errors
```

### Patio AC

```yaml
# Telemetry Sensors
sensor.patio_ac_schedule_telemetry
sensor.patio_ac_temperature_override_telemetry
sensor.patio_ac_presence_control_telemetry
# ... (30+ total)

# Log Sensor
sensor.patio_ac_automation_log

# Counters
counter.patio_ac_schedule_runs
```

---

## Appendix C: Related Documents

| Document | Path | Purpose |
|----------|------|---------|
| Constitution | `CLAUDE.md` | Engineering standards |
| Registry | `REGISTRY.md` | Feature inventory |
| Dependencies | `DEPENDENCIES.md` | HACS/custom components |
| Templates | `docs/templates/*.yaml` | Reusable patterns |

---

*End of Audit Document*
