# Daikin Fit (Skyport) Enhanced Monitoring - Requirements Document

## Current Integration Status

**Integration**: `daikinskyport` (HACS custom component)
**Device**: Daikin Fit with Skyport thermostat
**Entity Prefix**: `main_room`
**Dashboard**: `dashboard-daikn` (Deployed v2.0)

---

## 1. Dashboard Design & Functionality (Actual)

The dashboard uses a vertical stack of specialized cards to provide a "Generational" improvement over standard views.

### 1.1 Header & Status
- **Thermostat Card**: Primary control surface (`climate.daikin`).
- **Gauges (Horizontal Stack)**:
  - **Indoor Temp**: 60-85°F range, color-coded severity.
  - **Power**: 0-3500W range, yellow at 2000W, red at 2500W.
  - **Compressor**: 0-100% load, visualizes inverter modulation.

### 1.2 "Glance" Metrics
- **Current Status**:
  - System Status (Idle/Cooling/Heating)
  - Setpoint
  - Humidity
  - **Cost/hr** (Real-time cost calculation based on FPL rates)
- **Runtime Statistics**:
  - Today's Runtime (hr)
  - Cooling Hours
  - Energy Today (kWh)
  - Monthly Runtime

### 1.3 Historical Context (Graphs)
- **Temperature History (ApexCharts)**: 24h span showing Indoor vs Outdoor vs Setpoint.
- **Power & Compressor**: 24h history graph correlating Wattage with Compressor Load %.
- **Demand Metrics**: 24h history of Cooling Demand, Fan Demand, and Frequency.

### 1.4 "Understand" Section (Expandable Explainers)
The dashboard implements an "Observe -> Understand" pattern using `conditional` cards toggled by `input_boolean` helpers.
- **Performance**: Explains Compressor Load, Cooling Demand, Fan Demand, CFM.
- **Runtime**: Explains efficiency of long runtimes with inverter systems.
- **Energy**: Details the FPL 2026 rate calculation ($0.137/kWh).
- **Air Quality**: Explains AQI, PM1, and Ozone levels from the outdoor sensor.
- **Filter**: Explains the maintenance countdown logic.

### 1.5 Detailed Metrics (Entities Cards)
- **System Details**: Indoor/Outdoor Temp & Humidity, Power breakdown (Indoor/Outdoor units).
- **Air Quality**: AQI, PM1, Ozone.
- **Maintenance**: Filter Days Remaining, Fault Codes (Air Handler, Outdoor, Thermostat).

---

## 2. Automation & Logic Requirements

### 2.1 Sensors & Helpers
- **Template Sensors**:
  - `sensor.daikin_cost_per_hour`: Real-time cost calculation.
  - `sensor.daikin_cost_today/weekly/monthly`: Riemann sum integrations.
  - `sensor.daikin_runtime_*`: History stats for cooling/heating duration.
- **Input Booleans**:
  - `daikin_show_explain_*`: Toggles for the educational sections.

### 2.2 Alerts
- **Filter Alert**: Binary sensor triggering when `media_filter_days` < 7.
- **Fault Monitoring**: Sensors for critical fault codes on all 3 components.

---

## 3. Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `daikin_dashboard_deployed_v2.yaml` | The active dashboard configuration | `Daikin/` |
| `daikin.yaml` | The package containing all sensors/automations | `ha-config/packages/` |

---

## 4. Future Enhancements (Gap Analysis)

- **Comfort Score**: Add a "Thermal Comfort" or "Dew Point" gauge to better represent "Feels Like" conditions.
- **Predictive Maintenance**: Estimate filter end-of-life based on actual *runtime hours* rather than just calendar days.
- **Energy Attribution**: Link directly to `fpl-energy` integration for exact rate synchronization.