# Phase 0 Validation Test Plan
**Date:** 2026-01-24
**Purpose:** Validate all changes from Phase 0 remediation are working correctly

---

## Test Environment
- **HA URL:** http://192.168.1.11:8123
- **Tool:** Chrome DevTools MCP
- **Breakpoints:** Mobile (375px), Tablet (768px), Desktop (1920px)

---

## 1. Dashboard Validation

### 1.1 Default Dashboard
- [ ] Loads without errors
- [ ] No console errors
- [ ] Responsive at all breakpoints
- [ ] Key entities display correctly

### 1.2 Patio AC Dashboard
- [ ] Loads without errors
- [ ] Shows current AC state (on/off/mode)
- [ ] Shows temperature/humidity readings
- [ ] Manual override controls work
- [ ] Activity log displays
- [ ] Automation status indicators visible
- [ ] Responsive at all breakpoints

### 1.3 Kia EV9 Dashboard
- [ ] Loads without errors
- [ ] Shows vehicle status
- [ ] Battery/charging state visible
- [ ] Controls accessible
- [ ] Responsive at all breakpoints

### 1.4 Homelab Dashboard
- [ ] Loads without errors
- [ ] Container metrics display
- [ ] Proxmox metrics display
- [ ] No missing entities
- [ ] Responsive at all breakpoints

### 1.5 Notifications/Logs Dashboard
- [ ] Loads without errors
- [ ] Event logs display
- [ ] Responsive at all breakpoints

---

## 2. Patio AC Automation Validation

### 2.1 Core Automations (verify enabled & last_triggered exists)
| Automation | Enabled | Has Triggered | Notes |
|------------|---------|---------------|-------|
| patio_ac_evaluation_logic | | | Main 5-min evaluation |
| patio_ac_heat_guard_on | | | Heat protection |
| patio_ac_heat_guard_off_early_stop | | | |
| patio_ac_humidity_day_on | | | Day dehumidification |
| patio_ac_humidity_night_on | | | Night dehumidification |
| patio_ac_humidity_guard | | | Humidity protection |
| patio_ac_emergency_humidity_on | | | Emergency RH stop |
| patio_ac_daily_limit_enforcer | | | Runtime cap |
| patio_ac_day_night_boundary_handler | | | Day/night transition |
| patio_ac_manual_override_handler | | | Manual mode handling |

### 2.2 Helper Entities (verify exist & have valid state)
| Entity | Exists | State Valid | Notes |
|--------|--------|-------------|-------|
| input_select.patio_ac_reason | | | Should be idle/manual/heat_guard/etc |
| input_boolean.patio_ac_manual_override | | | on/off |
| input_boolean.patio_ac_heat_guard_enabled | | | on/off |
| input_boolean.patio_ac_humidity_day_enabled | | | on/off |
| input_boolean.patio_ac_humidity_night_enabled | | | on/off |
| input_number.patio_ac_daily_limit | | | Minutes |
| input_number.patio_ac_heat_threshold | | | Temperature °F |
| input_number.patio_ac_humidity_day_threshold | | | % RH |
| input_number.patio_ac_humidity_night_threshold | | | % RH |

### 2.3 Sensor Entities (verify exist & updating)
| Entity | Exists | State | Notes |
|--------|--------|-------|-------|
| sensor.patio_ac_reason_friendly | | | Human-readable reason |
| sensor.patio_ac_next_evaluation | | | Countdown timer |
| sensor.patio_ac_compressor_wait | | | Protection countdown |
| sensor.patio_ac_activity | | | Activity log |
| binary_sensor.patio_ac_running | | | AC on/off |
| binary_sensor.patio_ac_mode_cool | | | Cool mode |
| binary_sensor.patio_ac_mode_dry | | | Dry mode |

---

## 3. Entity Validation

### 3.1 Check for Unavailable Entities
- [ ] No patio_ac entities showing "unavailable"
- [ ] No patio_ac entities showing "unknown"
- [ ] Climate entity (150633095083490_climate) responsive

### 3.2 Check for Duplicate Entities
- [ ] No duplicate automation IDs
- [ ] No duplicate helper IDs
- [ ] No duplicate sensor IDs

---

## 4. Console/Network Validation

### 4.1 Browser Console
- [ ] No JavaScript errors on dashboard load
- [ ] No WebSocket connection errors
- [ ] No 404/500 API errors

### 4.2 Network Tab
- [ ] API calls completing successfully
- [ ] No failed state fetches
- [ ] WebSocket connection stable

---

## 5. Functional Tests

### 5.1 Patio AC Manual Control
- [ ] Can toggle manual override on
- [ ] Can toggle manual override off
- [ ] Reason changes to "manual" when override enabled
- [ ] Reason changes to "idle" when override disabled

### 5.2 Automation Trace
- [ ] Run trace on patio_ac_evaluation_logic
- [ ] Verify conditions evaluate correctly
- [ ] Verify no errors in trace

---

## Test Execution Log

| Test | Time | Result | Notes |
|------|------|--------|-------|
| | | | |

---

## Rollback Trigger Conditions
If any of these occur, execute rollback:
1. Dashboard completely fails to load
2. More than 10 patio_ac entities unavailable
3. Climate entity unresponsive
4. Automations causing unexpected AC behavior

**Rollback command:**
```bash
cd /Users/andrebyrro/Dev/home-server/home-assistant
rsync -avz ha-config.backup-2026-01-24/ byrro@192.168.1.11:/mnt/ByrroServer/docker-data/homeassistant/config/
ssh byrro@192.168.1.11 "docker restart homeassistant"
```
