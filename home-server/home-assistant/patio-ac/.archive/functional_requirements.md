# Patio AC Control System — Functional Requirements Document (FRD)

| Field | Value |
|---|---|
| Version | **1.6** |
| Date | **2026-01-13** |
| System | Patio mini-split / AC + Home Assistant automations + dashboard |
| Decision model | **Manual is authoritative and ungoverned** (automation governance does not throttle/stop manual runs; safety may still force OFF) |

---

## 1. Purpose

Operate a patio mini-split / AC through a small set of domains and a unified dashboard UX so the system is:

- **Predictable** (no “mystery runs”)
- **Tunable** (helpers expose triggers/targets)
- **Safe** (protections; emergency stop)
- **Respectful of manual control** (manual is authoritative and ungoverned)
- **Explainable** (reasons, timestamps, activity log, graphs)

---

## 2. Scope

### 2.1 In scope (FR-SCOPE)

- Dashboard functional behavior (labels, explanations, graphs, status semantics)
- Entities consumed/produced by the dashboard (helpers, sensors, timers, derived sensors)
- Automation/state-machine behavior required to satisfy the dashboard contract
- Attribution logic (manual vs automation) and how it surfaces in UI/logs and runtime buckets
- Day/night schedule eligibility behavior

### 2.2 Out of scope (FR-OOS)

- Aesthetic redesign beyond what is required to satisfy this FRD (layout/theme changes)
- New features unrelated to Patio AC governance, observability, and UX contract

---

## 3. Desired outcomes

### FR-OUT-01 Correct attribution
If an automation started/changed the AC, it must be labeled and accounted as **automation**, not manual.

### FR-OUT-02 Single, clear authority indicator
The dashboard must show **who/what is currently driving** the AC using **one** user-facing field:
- Manual / Day Humidity / Night Humidity / Heat Guard / Safety / Idle

### FR-OUT-03 Day/night cutoff correctness
After night start (default **22:00**), **Day Humidity must not remain** the active logic.

### FR-OUT-04 Global Config clarity and observability
Global Configuration must show:
- last evaluation time (timestamp)
- countdown to next evaluation
- descriptive labels
- working explanation panel

### FR-OUT-05 Graph correctness
Exactly **two** graphs exist and display the required series (no extra graphs).

### FR-OUT-06 Runtime accounting correctness
- Total-by-mode runtime (DRY/COOL) includes **manual + automation**
- Bucketed runtimes exist and are accurate (manual vs automation, by mode and totals)

---

## 4. Canonical entities

### 4.1 Primary device (FR-ENT-DEV)

| Concept | Entity ID | Notes |
|---|---|---|
| AC Unit | `climate.150633095083490_climate` | Primary control surface (hvac modes + target temp). |

### 4.2 Environment sensors (FR-ENT-ENV)

| Metric | Entity ID | Notes |
|---|---|---|
| Temperature | `sensor.patio_temp_sensor_temperature` | Used by Heat Guard and Graph 2. |
| Humidity (RH) | `sensor.patio_temp_sensor_humidity` | Used by Graph 1; not used for humidity domain decisions in v1.5+. |
| Dew Point | `sensor.patio_dew_point` | Primary decision metric for Day/Night humidity. |

### 4.3 Authority + reason (single-field rule) (FR-ENT-STATE)

| Concept | Entity ID | Notes |
|---|---|---|
| Active Logic (user-facing) | `sensor.patio_ac_reason_friendly` | **Single** user-facing indicator of current authority/logic. Must include: `Idle`, `Manual`, `Day Humidity`, `Night Humidity`, `Heat Guard`, `Safety/Emergency`. |
| Internal reason (state machine) | `input_select.patio_ac_reason` | Internal; not directly editable from dashboard. |

#### FR-STATE-01 Single field rule
The dashboard must not show redundant fields that represent the same concept (e.g., “override=manual” plus “active logic”). Manual authority must be represented by the Active Logic field value (and underlying state).

---

## 5. Configuration ranges

### FR-RANGE-01 Temperature and dew point helper ranges
All temperature and dew point configuration helpers (trigger/target) must have:

- **min:** 45  
- **max:** 100

Applies to:
- Heat Guard trigger/target temperature
- Day/Night trigger/target dew point

Does not apply to:
- RH percent thresholds (0–100%)
- Climate setpoint control on the climate tile

---

## 6. Control authority model (Manual vs Automation)

### 6.1 Strict definitions

#### FR-AUTH-01 Manual classification (reserved)
Manual must be used **only** when a human initiated the change via:
- physical AC unit controls
- AC remote
- voice assistant (e.g., Google)
- clicking controls in Home Assistant UI (including the climate tile)

#### FR-AUTH-02 Automation classification (never manual)
Changes initiated by these must **never** be classified as manual:
- Day Humidity domain (and supporting scripts/state machine)
- Night Humidity domain (and supporting scripts/state machine)
- Heat Guard domain (and supporting scripts/state machine)
- Safety/Emergency actions

### 6.2 Manual authority effects

#### FR-AUTH-03 Manual is authoritative
Automations must not revert a manual hvac_mode/setpoint (no “fighting the user”).

#### FR-AUTH-04 Manual is ungoverned
Automation governance (caps/limits/cool-offs) must not stop or throttle a manual run.

#### FR-AUTH-05 Manual blocks automation starts (except safety)
While Active Logic is `Manual`:
- Day/Night/Heat Guard must not initiate new runs
- Safety/Emergency may still force OFF if required

#### FR-AUTH-06 Resume Automation is explicit
The system provides a way to return to `Idle` so automation control can resume at the next evaluation cycle.

---

## 7. Domains

### 7.1 Heat Guard (COOL)

#### FR-HG-01 Enable/disable
Heat Guard must be enable/disable-able from its card. If disabled, it cannot initiate runs.

#### FR-HG-02 Trigger + target (no dwell)
- Start COOL when `Temp >= Trigger`
- Stop COOL when `Temp <= Target`

#### FR-HG-03 Mode restriction
Heat Guard uses **COOL only**.

#### FR-HG-04 Misconfiguration guard
If `Target >= Trigger`, Heat Guard must not start and must surface a clear “invalid configuration” reason.

#### FR-HG-05 Max duration configuration (if present)
If Heat Guard exposes max duration:
- configurable **0–24h**
- **30-minute increments**

#### FR-HG-06 Explanation support
Heat Guard must have a working explanation affordance consistent with the dashboard explanation pattern.

---

### 7.2 Day Humidity (DRY, dew-point-only)

#### FR-DH-01 Enable/disable
Day Humidity must be enable/disable-able. If disabled, it cannot initiate runs.

#### FR-DH-02 Dew point trigger + target (no dwell)
- Start DRY when `Dew Point >= Trigger`
- Stop DRY when `Dew Point <= Target`

#### FR-DH-03 Mode restriction
Day Humidity uses **DRY only**.

#### FR-DH-04 Misconfiguration guard
If `Target >= Trigger`, Day Humidity must not start and must surface a clear reason.

---

### 7.3 Night Humidity (DRY, dew-point-only)

#### FR-NH-01 Enable/disable
Night Humidity must be enable/disable-able. If disabled, it cannot initiate runs.

#### FR-NH-02 Dew point trigger + target (no dwell)
- Start DRY when `Dew Point >= Trigger`
- Stop DRY when `Dew Point <= Target`

#### FR-NH-03 Mode restriction
Night Humidity uses **DRY only**.

#### FR-NH-04 Misconfiguration guard
If `Target >= Trigger`, Night Humidity must not start and must surface a clear reason.

---

### 7.4 Safety & Emergency

#### FR-SE-01 Emergency RH stop
If RH exceeds the configured emergency threshold:
- AC must be forced **OFF immediately**
- Active Logic must reflect **Safety/Emergency**

#### FR-SE-02 Safety overrides
Safety/Emergency overrides other domains (including currently running automation-driven runs).

#### FR-SE-03 Clear naming
UI naming and explanations must clearly describe what the emergency RH threshold does (avoid ambiguous labels like “Emergency stop RH” without context).

---

## 8. Schedule semantics (day/night eligibility)

### 8.1 Schedule controls (FR-SCHED-ENT)

- `input_datetime.patio_ac_day_start`  
- `input_datetime.patio_ac_night_start`

Defaults:
- Day: **07:00–22:00**
- Night: **22:00–07:00**

### 8.2 Eligibility and cutoff (FR-SCHED)

#### FR-SCHED-01 Schedule selects eligible ruleset
Schedule determines which humidity domain is eligible to run; schedule does not force the AC on/off by itself.

#### FR-SCHED-02 Hard cutoff
After night start (default 22:00):
- Day Humidity must be ineligible
- Active Logic must not display Day Humidity past the cutoff

---

## 9. Global Configuration UX and observability contract

### 9.1 Automation status timing (FR-GC-TIME)

#### FR-GC-01 Last checked is a timestamp
The system provides a value representing the last evaluation time as a timestamp.

Required entity:
- `sensor.patio_ac_last_evaluated`

#### FR-GC-02 Next check is a countdown
The system provides a value representing time remaining until the next evaluation cycle as a countdown (duration).

Required entity:
- `sensor.patio_ac_next_evaluation`

### 9.2 Organization, labels, explanations (FR-GC-UX)

#### FR-GC-03 Logical grouping
Controls in Global Configuration are logically grouped (status/timing, authority/eligibility, protections/cooldowns, caps/limits, diagnostics/actions) while preserving overall dashboard layout style.

#### FR-GC-04 Descriptive labels
Ambiguous labels (e.g., “available in ready”) are replaced with descriptive labels that convey meaning (e.g., “Eligible to start”, “Cooldown complete”, “Automation allowed”).

#### FR-GC-05 Single explanation toggle for the card
Global Configuration uses one explanation toggle that reveals a single explanation panel documenting:
- each field/button
- what it controls (entity/service)
- purpose
- behavioral effect on automations

#### FR-GC-06 No redundant authority controls
There are not separate “override/manual” vs “active logic” mechanisms representing the same idea. Manual authority is represented via Active Logic.

---

## 10. Attribution signals (automation vs manual)

### FR-ATTR-01 Expected signature
When automation issues climate commands, it publishes an expected signature (mode/setpoint/etc.) for attribution.

### FR-ATTR-02 TTL verification
If state changes within TTL:
- matches expected signature → automation
- does not match → manual

### FR-ATTR-03 Polling settle window
Transient polling mismatches do not get misclassified as manual unless persistent beyond the settle window.

### FR-ATTR-04 No “manual by default”
Unknown/uncertain attribution must not be labeled manual without evidence.

---

## 11. Runtime accounting

### 11.1 Total-by-mode runtime for graphs (FR-RT-GRAPH)

#### FR-RT-01 Total-by-mode runtime includes manual + automation
Total runtime in DRY and COOL includes all runtime regardless of origin.

Required entities (IDs may be adjusted if already present, but must exist):
- `sensor.patio_ac_runtime_dry_total`
- `sensor.patio_ac_runtime_cool_total`

### 11.2 Bucketed runtimes (manual vs automation) (FR-RT-BUCKET)

#### FR-RT-02 Bucketed runtimes exist
The system provides these runtime buckets:

Automation-driven:
- `sensor.patio_ac_runtime_dry_automation`
- `sensor.patio_ac_runtime_cool_automation`
- `sensor.patio_ac_runtime_total_automation`

Manual:
- `sensor.patio_ac_runtime_dry_manual`
- `sensor.patio_ac_runtime_cool_manual`
- `sensor.patio_ac_runtime_total_manual`

Overall:
- `sensor.patio_ac_runtime_total_all` = automation_total + manual_total

#### FR-RT-03 Bucket semantics
- Manual buckets increment only when the run was initiated under manual authority per FR-AUTH-01.
- Automation buckets increment only when the run was initiated by automation domains per FR-AUTH-02.

---

## 12. Graphs (exactly two)

### FR-GRAPH-01 Exactly two graphs exist
The dashboard shows exactly two graphs.

### 12.1 Graph 1 (4 lines)
Title: `24h Humidity + Dew Point + AC Dry Runtime + AC Cool Runtime`

Series:
1. Humidity (RH) — `sensor.patio_temp_sensor_humidity`
2. Dew Point — `sensor.patio_dew_point`
3. Total DRY runtime (manual + automation) — `sensor.patio_ac_runtime_dry_total`
4. Total COOL runtime (manual + automation) — `sensor.patio_ac_runtime_cool_total`

### 12.2 Graph 2 (3 lines)
Title: `24h Temperature + AC Dry Runtime + AC Cool Runtime`

Series:
1. Temperature — `sensor.patio_temp_sensor_temperature`
2. Total DRY runtime (manual + automation) — `sensor.patio_ac_runtime_dry_total`
3. Total COOL runtime (manual + automation) — `sensor.patio_ac_runtime_cool_total`

---

## 13. Dew Point explanation requirements

### FR-DP-01 Dew point sensor health
`sensor.patio_dew_point` is numeric, unit-valid, and actively produced without orphaned template artifacts.

### FR-DP-02 Dew point help text content
Dew point help explains:
- dew point meaning and comfort/mold context
- Day/Night humidity are dew-point-only
- trigger/target behavior
- DRY stops when dew point reaches target

---

## 14. System-level acceptance criteria

- Automation-triggered DRY runs are not labeled manual in UI/logs or runtime buckets.
- Past night start, Active Logic does not show Day Humidity.
- Global Config shows Last checked (timestamp) and Next check (countdown).
- Global Config has one working explanation toggle/panel documenting all fields/buttons.
- Exactly two graphs exist and match required series.
- Total-by-mode runtime sensors include manual + automation and are accurate.
- Bucketed runtime sensors exist and correctly reflect manual vs automation runs.
