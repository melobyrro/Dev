# Jose (Vacuum) Dashboard - Functional Requirements

## Dashboard Information
- **Dashboard ID**: ``jose_vacuum``
- **Title**: Jose (Vacuum)
- **URL Path**: ``/jose-vacuum/jose``
- **Source of Truth**: ``jose/lovelace.jose_vacuum.json``
- **Last Updated**: 2026-01-28

## 1. Dashboard Design (Actual)

The dashboard uses a responsive layout (`custom:layout-card`) with a 2-column grid that stacks on mobile.

### 1.1 Main View: Jose
**Left Column (Act)**
- **Auto Clean** hero control with Start/Stop/Home/Locate
- Status chips (Battery, Station, Mop, Error)
- **AI Clean** toggle
- **Cleaning Mode** chips (Vacuum, Vacuum + Mop, Mop, Mop after Vacuum)
- **Suction Power** chips (quiet/normal/max/max_plus)
- Last cleaning session metrics
- Quick actions (Empty Dustbin, Relocate)
- Settings (Auto Empty, Water Flow when mop is attached, Active Map)
- Error History (read-only Markdown log table)

**Right Column (Observe)**
- Lifetime statistics
- Consumables gauges
- Live map

### 1.2 Schedules View (Tab)
**Observe → Act**
- **Observe**: Vacuum status chips + last run/result per schedule (read-only Markdown)
- **Act**: Enable toggle, time, weekday toggles, power selection, AI Clean, minimum battery, and “Run Now”

## 2. Automation & Logic Requirements

### 2.1 Error Logging System
- Automation triggers on `sensor.jose_error`
- FIFO log stored in `input_text.jose_error_log_1..10`
- Displayed in dashboard Markdown table

### 2.2 Schedule System (v2.0)
- **Option Sync**: `script.function_jose_schedule_sync_options` copies vacuum fan speeds into schedule power selectors
- **Execution**: `script.function_jose_schedule_run` applies schedule settings, enforces guardrails, and starts cleaning
- **Automations**: `automation.function_jose_schedule_1_run` and `_2_run` fire at configured times when enabled
- **Behavior**:
  - **Vacuum-only**: schedules force `select.jose_work_mode = vacuum` when available
  - **Power-only**: schedules set `vacuum.set_fan_speed` from helper selection
  - Optional **AI Clean** toggle per schedule
- **Guardrails**:
  - Skip if vacuum unavailable or busy
  - Skip if battery below minimum threshold
  - Bounded wait for `vacuum.jose` to reach `cleaning` state; notify on failure
- **Notifications**: Mobile notifications on failures; logbook entries for skips/success

## 3. Entity Inventory (Selected)

### 3.1 Primary Entities
- `vacuum.jose`
- `sensor.jose_battery`, `sensor.jose_error`, `sensor.jose_area_cleaned`, `sensor.jose_cleaning_duration`
- `binary_sensor.jose_mop_attached`, `event.jose_last_job`

### 3.2 Configuration / Controls
- `select.jose_work_mode`, `select.jose_water_flow_level`, `select.jose_auto_empty_frequency`, `select.jose_active_map`
- `switch.jose_clean_preference`
- `button.jose_empty_dustbin`, `button.jose_relocate`

### 3.3 Schedule Helpers (per schedule 1 & 2)
- **Timing**: `input_boolean.helper_jose_schedule_<n>_enabled`, `input_datetime.helper_jose_schedule_<n>_time`, `input_boolean.helper_jose_schedule_<n>_<day>`
- **Cleaning Settings**: `input_select.helper_jose_schedule_<n>_power`, `input_number.helper_jose_schedule_<n>_min_battery`
- **Behavior**: `input_boolean.helper_jose_schedule_<n>_clean_preference`
- **Status**: `input_text.helper_jose_schedule_<n>_last_run`, `_last_result`

## 4. Configuration Management

| File | Purpose | Location |
|------|---------|----------|
| `lovelace.jose_vacuum.json` | Dashboard Layout | `jose/` |
| `jose_vacuum_package.yaml` | Error Logging Automation | `ha-config/packages/` |
| `jose_schedule_v2_0.yaml` | Schedule Helpers/Scripts/Automations | `ha-config/packages/` |
| `REQUIREMENTS.md` | Package Requirements | `ha-config/packages/` |

## 5. Future Enhancements (Gap Analysis)
- **Zone/Room Schedules**: Add support for segment/room targets if exposed by the integration
- **Quick Clean Presets**: High-traffic zone buttons
- **Bin Full Prediction**: Estimate based on area cleaned since last empty
