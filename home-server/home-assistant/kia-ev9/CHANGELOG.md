# Kia EV9 Integration - Changelog

All notable changes documented here. See [CLAUDE.md](./CLAUDE.md) for project instructions.

---

## v2.8 (2026-01-24) - Car Status Visibility Enhancement

**New Features**
- Added `sensor.ev9_car_mode` template sensor - Combined status showing:
  - "Parked" - Engine off, climate off
  - "Climate Running" - Engine off, climate on (remote start)
  - "Driving" - Engine on, climate off
  - "Driving (Climate On)" - Engine on, climate on
  - Dynamic icon: mdi:car-off, mdi:air-conditioner, or mdi:car

**Dashboard Changes**
- Added "Car Status" card to **Main tab** (after Vehicle Security, before Vehicle Info)
- Added "Car Status" card to **Climate tab** (at top, before Pre-conditioning Settings)
- Car Status card shows: Mode, Climate System, Set Temp, Engine, Defrost, Heaters
- Added **Calculation Debug** section under Schedule 1 showing:
  - Outside Temp, Target Temp, Temp Diff
  - Rate, Runtime calculation, Departure time, Eval Window

**Files Changed**
- `helpers.v2.8.yaml` - Added `sensor.ev9_car_mode` template sensor
- `lovelace.kia_ev9.v2.8.json` - Added Car Status cards to Main + Climate tabs, added debug display

---

## v2.7 (2026-01-24) - Per-Schedule Smart Rate & Climate Tab

**Per-Schedule Smart Rate**
- Each of the 5 schedules now has its own smart rate slider (`input_number.ev9_schedule_X_rate`)
- Rate range expanded to 0.5-10.0 min/F (was 0.5-2.0 globally)
- Automation reads the matched schedule's rate instead of a global rate
- Unit label fixed: now displays "min/F" (minutes per degree) instead of the inverted "F/min"

**Countdown Display Sensors**
- Added 10 new template sensors for real-time schedule countdown displays
- `sensor.ev9_schedule_X_next_eval` - Time until evaluation begins for each schedule
- `sensor.ev9_schedule_X_climate_start` - Time until climate actually starts (computed from rate)
- States: "Disabled", "Not today", "X min", "Evaluating", "Running", "Done", "--"

**Dashboard Restructure - New Climate Tab**
- Tab order changed: Main -> **Climate** -> Config -> Logs -> Info
- Pre-conditioning settings moved from Config tab to dedicated Climate tab
- Each schedule card now shows:
  - Enable toggle, time, target temp
  - Per-schedule rate slider
  - Day buttons (M T W T F S S)
  - Countdown displays: "Next Eval: X min | Climate Start: Y min"
- Config tab now only contains: Proximity Security, Alerts, System Health

**Files Changed**
- `helpers.v2.7.yaml` - Added 5 per-schedule rate helpers, added 10 countdown template sensors
- `automations.v2.7.yaml` - Changed smart_rate lookup from global to per-schedule
- `lovelace.kia_ev9.v2.7.json` - New Climate tab, restructured tabs, added countdown displays

---

## v2.6.2 (2026-01-24) - Walk-Away Lock Desync Fix

**Critical Bug Fix**
- Walk-Away Lock now requires **BOTH** lock entities to agree before skipping
- If `lock.ev9_door_lock` and `binary_sensor.ev9_locked` disagree, the automation attempts to lock anyway
- This prevents false "SKIPPED: Already locked" when the Kia API reports stale/incorrect lock state

**Root Cause**
The Kia API can report conflicting states where `lock.ev9_door_lock` = "locked" but `binary_sensor.ev9_locked` = "off". Previously, the automation only checked `lock.ev9_door_lock`, leading to skipped locks when the car was actually unlocked.

**New Logic**
| lock.ev9_door_lock | binary_sensor.ev9_locked | Action |
|--------------------|-------------------------|--------|
| locked | on | SKIP (both agree) |
| locked | off | LOCK ANYWAY (desync!) |
| unlocked | on | LOCK ANYWAY (desync!) |
| unlocked | off | LOCK (normal) |

**Files Changed**
- `automations.v3.0.yaml` (deployed) - Added dual-check logic with `entities_disagree` branch
- Notification: "Walk-Away Locked (Desync)" when desync is detected and corrected

---

## v2.6.1 (2026-01-24) - Cleanup & Simplification

**Removed Features**
1. **Removed Theft Detection entirely** - Automations, helpers, and dashboard controls all removed per user request
2. **Removed `sensor.ev9_next_schedule_check`** from dashboard (entity never existed, caused "Entity not found")
3. **Removed `overnight_charge_monitor` toggle** - Charging interruption now works 24/7 with single toggle

**Bug Fixes**
4. **Fixed lock entity in `ev9_unlocked_at_home`** - Changed from `binary_sensor.ev9_locked` to `lock.ev9_door_lock` (binary sensor can desync)
5. **Added self-healing to Walk-Away Lock** - Added `homeassistant.start` trigger for HA restart recovery

**Clarifications**
- **Charging Interrupted** notification: Single toggle (`ev9_notify_charging_interrupted`), works anytime 24/7, no day/night distinction

**Files Changed**
- `automations.v2.6.yaml` - Removed 3 theft automations, fixed lock entity, added startup trigger
- `lovelace.kia_ev9.v2.6.json` - Removed broken entities, theft card, and overnight toggle
- `requirements.md` - Updated to reflect removed features

---

## v2.6 (2026-01-22) - Smart Mode Preconditioning Redesign

**Major Architecture Change**

The preconditioning automation was completely redesigned to evaluate conditions at a configurable evaluation window BEFORE the schedule, then compute the optimal climate start time.

**Old (Wrong) Behavior:**
- Lead time was fixed minutes before schedule
- Climate started at `schedule_time - lead_time`
- No consideration of actual temperature difference

**New (Correct) Behavior:**
1. At `schedule_time - evaluation_window`, automation wakes up
2. Reads outside temperature from weather entity
3. Computes runtime: `runtime = |target - outside| * smart_rate`
4. Calculates start time: `start_time = schedule_time - runtime`
5. Delays until start_time (if in future)
6. Starts climate at computed time
7. Vehicle reaches target temp exactly at schedule time

**Example:**
- Schedule: 9:30 AM, target 70F
- Evaluation Window: 30 min (configurable, 15-60 min)
- Smart Rate: 1.0 min/F (configurable, 0.5-2.0)
- Outside temp at 9:00 AM: 90F

At 9:00 AM (evaluation):
- Runtime = |70 - 90| * 1.0 = 20 min
- Start time = 9:30 - 20 = 9:10 AM
- Delay = 10 min
At 9:10 AM: Start climate
At 9:30 AM: Cabin at target temp

**New Helpers:**
- `input_number.ev9_evaluation_window` - How far in advance to evaluate (min 15, max 60, default 30)
- Replaced `input_number.ev9_precondition_lead_time` (deprecated)

**Removed:**
- Master Enable toggle (`input_boolean.ev9_precondition_enabled`) - per-schedule enables are sufficient

**Dashboard Changes:**
- Removed "Master Enable" toggle from Pre-conditioning section
- Added "Evaluation Window" slider (replaces "Lead Time")
- Added explanation text showing how Smart Mode works

**Technical Fixes:**
- Fixed datetime arithmetic by keeping calculations within single template blocks
- Fixed YAML block scalar whitespace issues that broke `from_json`
- All datetime calculations now done inline without intermediate variables

---

## v2.5.1 (2026-01-22) - Time-Based Timeout Lock with Countdown

**Problem Solved**
- Old timeout lock used `state` trigger with `for:` duration - only triggered on state *change*
- If car was already unlocked when automation loaded, no timer would start
- Changing timeout slider didn't affect already-running timers

**New Time-Based Approach**
- **`ev9_track_unlock_time`** automation: Records timestamp when car unlocks
- **`ev9_timeout_lock_check`** automation: Runs every minute, checks if unlocked > timeout duration
- **`input_datetime.ev9_unlocked_since`** helper: Stores unlock timestamp
- **`sensor.ev9_timeout_countdown`** template sensor: Real-time countdown display

**Countdown Display States**
| State | Meaning |
|-------|---------|
| Locked | Car is currently locked |
| Disabled | Timeout lock feature is off |
| Driving | Engine is running |
| X min | Countdown to auto-lock |
| Locking... | About to lock (0 min remaining) |

**Dashboard Update**
- Added "Auto-Lock In" row to Security card showing countdown
- Timeout Duration slider changes take effect immediately

**How It Works**
1. Car unlocks -> timestamp saved to `input_datetime.ev9_unlocked_since`
2. Every minute, `ev9_timeout_lock_check` runs
3. Calculates: `elapsed = now() - unlocked_since`
4. If `elapsed >= timeout_duration` -> lock the car
5. Dashboard shows remaining minutes until auto-lock

---

## v2.5 (2026-01-22) - Smart Mode Always-On & Dashboard Button Fix

**Dashboard Button Fixes**
- All dashboard buttons now use scripts instead of hardcoded device_ids
- New wrapper scripts: `ev9_start_charge`, `ev9_stop_charge`, `ev9_force_update`
- Buttons will continue working even after integration recreation

**Smart Mode Always-On**
- Smart mode is now always enabled for climate schedules (no toggle)
- Configurable rate via `input_number.ev9_smart_mode_rate` (0.1-1.0 min/F, default 0.5)
- Formula: `extra_time = temp_diff * rate` (capped at 20 min)
- Example: 20F diff * 0.5 rate = 10 min extra lead time

**OTP Script Auto-Updates Device ID**
- `ev9_submit_otp.sh` now auto-updates `input_text.ev9_device_id` after recovery
- Queries device registry via template API as fallback
- Prevents device_id mismatch issues after integration recreation

**New/Updated Files**
- `scripts.v2.5.yaml` - Added 3 charging wrapper scripts
- `helpers.v2.5.yaml` - Added `ev9_smart_mode_rate`, deprecated toggle
- `automations.v2.5.yaml` - Always-on smart mode with configurable rate
- `lovelace.kia_ev9.v2.3.json` - All buttons use scripts, rate slider replaces toggle
- `scripts/ev9_submit_otp.sh` - Auto-updates device_id helper

---

## v2.4.3 (2026-01-22) - Verified End-to-End Self-Healing

**Bug Fixes Applied**

1. **IMAP `imap.fetch` Parameter Fix**
   - **Issue**: `imap.fetch` service was using `entry_id` parameter
   - **Fix**: Changed to `entry` (correct HA IMAP service parameter)
   - **Error before fix**: `extra keys not allowed @ data['entry_id']`

2. **OTP Extraction Filter**
   - **Issue**: Every Kia email contains static `797979` in HTML template CSS
   - **Fix**: Added `reject('eq', '797979')` filter to skip static number
   - **Pattern**: Now extracts the real OTP (e.g., `394721`) not the template ID

3. **Shell Script Reads from Helpers**
   - `ev9_submit_otp.sh` (v2.4.2) reads flow_id and OTP from input_text helpers
   - No template variables passed via shell_command
   - More reliable than passing arguments through HA templates

**New Helper (v2.4.3)**
- `input_text.ev9_otp_code` - Stores extracted OTP code for shell script to read

**Verified Working (2026-01-22)**
- Full end-to-end test successful
- Watchdog triggered -> Config flow started -> OTP requested -> Email received -> OTP extracted -> Integration created
- Battery sensor confirmed reporting: 46%
- Final result: `SUCCESS: Auto-recovered with OTP`

---

## v2.4 (2026-01-22) - Email OTP Automation (Full Self-Healing)

**Fully Automated Recovery with Email OTP**
- Enhanced `ev9_connection_watchdog` to trigger full config flow with OTP request
- Added `ev9_otp_received` automation - Extracts OTP from Kia email and completes config flow
- Added `ev9_otp_timeout` automation - Handles timeout if OTP email doesn't arrive in 5 minutes
- Integration now self-heals completely without manual intervention

**How It Works**
1. Watchdog detects integration unavailable for 2+ hours
2. Deletes old integration, starts new config flow
3. Submits region (USA) and brand (Kia)
4. Submits credentials from secrets.yaml
5. Requests OTP via EMAIL method
6. IMAP integration monitors Gmail for Kia email
7. When email arrives, extracts 6-digit OTP using regex
8. Submits OTP to complete config flow
9. Notifies success/failure

**New Helpers (v2.4/v2.4.3)**
- `input_text.ev9_recovery_flow_id` - Stores config flow ID during OTP wait
- `input_text.ev9_recovery_state` - State machine (idle/starting/awaiting_otp/completing/failed)
- `input_datetime.ev9_otp_requested_at` - Timestamp for timeout tracking
- `input_text.ev9_otp_code` - Stores extracted OTP code (added v2.4.3)

**New Shell Scripts**
- `scripts/ev9_recovery_with_otp.sh` - Handles multi-step config flow up to OTP request
- `scripts/ev9_submit_otp.sh` - Submits OTP code to complete config flow

**Required Configuration**
1. Gmail App Password in secrets.yaml:
   ```yaml
   gmail_app_password: "xxxx xxxx xxxx xxxx"
   kia_username: "your_email@gmail.com"
   kia_password: "your_kia_password"
   kia_pin: "1234"
   ```
2. IMAP integration configured (Settings > Integrations > IMAP):
   - Server: imap.gmail.com
   - Username: your_email@gmail.com
   - Password: Gmail App Password
   - Folder: INBOX
   - Search: `FROM notification.kiausa.com UNSEEN`
3. Shell commands in configuration.yaml:
   ```yaml
   shell_command:
     ev9_recovery_start: "bash /config/scripts/ev9_recovery_with_otp.sh '{{ token }}' /config/secrets.yaml"
     ev9_submit_otp: "bash /config/scripts/ev9_submit_otp.sh /config/secrets.yaml"
   ```
   **Note**: `ev9_submit_otp.sh` reads flow_id and OTP from `input_text.ev9_recovery_flow_id` and `input_text.ev9_otp_code` helpers (not from arguments)

**Event Log Types (v2.4)**
- `WATCHDOG_START` - Recovery initiated
- `WATCHDOG_OTP_REQUESTED` - OTP email requested from Kia
- `WATCHDOG_OTP_RECEIVED` - OTP extracted from email
- `WATCHDOG_SUCCESS` - Full recovery completed
- `WATCHDOG_TIMEOUT` - OTP email not received in time
- `WATCHDOG_FAILED` - Recovery failed

**Timing**
| Step | Duration |
|------|----------|
| Delete old integration | ~10s |
| Start config flow | ~3s |
| Submit credentials | ~3s |
| Request OTP | ~3s |
| Email delivery | 1-2 min |
| IMAP poll | 60s max |
| OTP submission | ~3s |
| Integration init | ~2 min |
| **Total** | **~5-7 min** |

---

## v2.3 (2026-01-21) - Connection Watchdog (Notification Only)

**Connection Watchdog Automation**
- Added `ev9_connection_watchdog` automation - Auto-recovers kia_uvo integration when unavailable for 2+ hours
- Attempts reload first, if that fails, deletes and recreates the integration using stored credentials
- 4-hour cooldown between recovery attempts to prevent spam during extended Kia outages

**New Helpers**
- `input_boolean.ev9_connection_watchdog_enabled` - Master toggle for watchdog (default: on)
- `input_text.ev9_last_recovery_attempt` - Timestamp of last recovery attempt (cooldown tracking)
- `input_text.ev9_last_recovery_result` - Last recovery result (SUCCESS/FAILED + details)

**New Files**
- `scripts/ev9_connection_recovery.sh` - Shell script for full integration recreation
- `secrets_template.yaml` - Template showing required Kia credentials in secrets.yaml
- `docs/plans/2026-01-21-connection-watchdog-design.md` - Design document

**How Connection Watchdog Works**
1. Detects when `sensor.ev9_ev_battery_level` is `unavailable` for 2+ hours
2. Sends "Recovery Starting" notification
3. Attempts to reload the integration via `homeassistant.reload_config_entry`
4. Waits 5 minutes, checks if sensor is available
5. If reload worked: SUCCESS notification, done
6. If reload failed: Calls shell script to delete and recreate integration
7. Shell script reads credentials from secrets.yaml and uses HA API to recreate
8. Final notification: SUCCESS or FAILED (manual intervention needed)

**Deployment Requirements**
1. Add credentials to `/config/secrets.yaml`:
   ```yaml
   kia_username: "your_email@example.com"
   kia_password: "your_password"
   kia_pin: "1234"
   ```
2. Deploy `scripts/ev9_connection_recovery.sh` to `/config/scripts/`
3. Add to `configuration.yaml`:
   ```yaml
   shell_command:
     ev9_connection_recovery: "bash /config/scripts/ev9_connection_recovery.sh {{ ha_token }} /config/secrets.yaml"
   ```
4. Deploy helpers and automations
5. Restart Home Assistant

**Event Log Types Added**
- `WATCHDOG_START` - Recovery process initiated
- `WATCHDOG_RELOAD` - Reload attempt
- `WATCHDOG_RECREATE` - Full recreation attempted
- `WATCHDOG_SUCCESS` - Recovery completed successfully
- `WATCHDOG_FAILED` - Recovery failed, manual intervention needed

---

## v2.2 (2026-01-20) - Theft Detection + Lock Improvements

**Theft Detection System**
- Added `ev9_theft_alert` automation - Detects suspicious vehicle movement when phone is away
- Added `ev9_update_last_location` automation - Stores parked location when engine turns off
- Added `ev9_lock_from_theft_notification` automation - Handles emergency lock from notification

**New Helpers**
- `input_boolean.ev9_theft_alert_enabled` - Master toggle for theft detection
- `input_number.ev9_theft_distance_threshold` (50-500m) - Vehicle movement threshold
- `input_number.ev9_theft_phone_distance_threshold` (100-1000m) - Phone distance threshold
- `input_text.ev9_last_known_location` - Stores lat,lon of parked position
- `input_text.ev9_last_theft_alert` - Cooldown timestamp
- `input_text.ev9_last_theft_result` - Last alert result
- `sensor.ev9_movement_distance` - Calculated distance from parked location

**Dashboard Updates**
- Added "Theft Detection" card on Config tab with enable/distance settings
- Added theft alert result to Automation Health section
- Added Theft/Movement Alert documentation to Logic & Info tab
- Added new event types to Event Log Reference: PARKED, THEFT_ALERT, EMERGENCY_LOCK

**How Theft Detection Works**
1. When engine turns off, parked location is saved
2. If vehicle moves >threshold while phone is >phone_threshold away, CRITICAL alert is sent
3. 15-minute cooldown prevents notification spam
4. Notification includes map link and "Lock Vehicle" action button

**Walk-Away & Timeout Lock Improvements (2026-01-20)**
- **Check before locking**: Automations now check `lock.ev9_door_lock` state BEFORE sending lock command
- **Skip if already locked**: If vehicle is already locked, logs "SKIPPED: Already locked" instead of redundant API call
- **Use reliable entity**: Changed from `binary_sensor.ev9_locked` to `lock.ev9_door_lock` for state verification (see Known Issues below)
- **Increased timeout**: Wait 10 seconds (was 5) for Kia API to respond
- **Error handling**: `continue_on_error: true` on lock service call prevents automation failure
- **Three possible outcomes**: SUCCESS (locked), FAILED (API error), SKIPPED (already locked)

---

## v2.1 (2026-01-19) - Complete Refactor (6 Tasks)

**Task 1: Logic & Info Tab**
- Added 4th tab "Logic & Info" with comprehensive Markdown documentation
- Removed all inline `<details>` sections from Main, Config, Logs tabs
- Documentation includes: Walk-Away logic, Timeout Failsafe, Smart Mode formula, Event Log reference

**Task 2: Integration Debugging**
- Verified entity states and service calls via HA API
- Identified walkaway automation issue: `numeric_state` only fires on threshold crossing
- All kia_uvo services confirmed functional

**Task 3: Vehicle Security Consolidation**
- Merged Security + Vehicle Status into unified "Vehicle Security" card on Main tab
- Includes: Lock/Unlock buttons, Door status (FL/FR/BL/BR/Trunk/Hood), Walk-Away status, Timeout status
- Shows "Last Ran" timestamps for both auto-lock methods

**Task 4: Pre-conditioning Refactor**
- **Fixed Smart Mode Formula**: Changed from `/3` to `*0.5`
  - OLD: 20F difference = 6.7 min extra (too short)
  - NEW: 20F difference = 10 min extra (correct)
- **Removed Global Enable Toggle**: Per-schedule enables are now sufficient

**Task 5: Config Tab Cleanup**
- Removed ALL Start/Stop/Refresh charging buttons (per user request)
- Consolidated alerts: Single "Alerts & Notifications" card with all 8 toggles
- Converted Automation Health to Markdown template

**Task 6: Centralized Device ID & Debug Sensors**
- Created `input_text.ev9_device_id` helper for centralized device ID management
- Created `sensor.ev9_walkaway_conditions_met` template sensor for debugging
- Updated all 7 automations + 2 scripts to use `{{ states('input_text.ev9_device_id') }}`

---

## v2.0 (2026-01-18) - Major Redesign

- **3-Tab Dashboard**: Main (operational), Config (all settings), Logs (automation history)
- **Main Tab Cards**: Battery, Charging (read-only), Climate with timer, Security, Vehicle Status, Map
- **Charging Card Redesign**:
  - Removed Start/Stop/Refresh buttons (moved to Config)
  - Time remaining formatted as hh:mm
  - ApexCharts graph at 350px height with fixed 0-1.5kW L1 scale
- **Proximity Security Card**: Merged Walk-Away + Timeout into one teaching card
- **Preconditioning Redesign**:
  - Per-schedule temperatures
  - Computed lead time display (no manual input on UI)
  - Circular day monograms (28-32px, grey inactive / primary-color active)
- **Alerts & Safety**: Consolidated card merging charging, battery, security, window alerts
- **Logs Tab**: Hybrid format with Last Run Summary + rolling 10 events
- **Inline Logic & Info**: Every card has collapsible documentation
- **Read-Only Logs**: Event log entries are read-only markdown, not editable inputs

---

## v2.4 Dashboard (2026-01-22) - Read-Only Logs

**Changed:**
- Event log on Logs tab now uses markdown card (was editable entities card)
- Last Run Summary on Logs tab now uses markdown table (was editable entities card)
- All log entries are now read-only text, not editable input fields

**Why:**
- `input_text` entities displayed in `entities` cards create editable text inputs
- Users could accidentally modify log history
- Markdown cards with Jinja2 templates display the same data as read-only text

---

## v1.5 (2026-01-17) - Dashboard

- Compact schedule UI redesign: All 5 schedules in a single grouped card
- Each schedule is a single horizontal row: enable toggle, number, time, temp, 7 day buttons inline
- Uses `custom:stack-in-card` + `custom:button-card` for compact layout
- Day buttons with visual toggle state (primary color when on)
- Tap time/temp to edit via more-info dialog

---

## v1.4 (2026-01-16)

- Per-schedule temperatures (each schedule has its own target temp)
- Dedicated climate card with timer auto-shutoff
- Compact day selector UI
- Proximity-based auto-lock (GPS distance from vehicle)
- Trunk left open alert
- Graph scale selector (Auto / Level 2 / DC Fast)
- DC charging filter for graph
- Overnight charge monitor toggle wired to automation
