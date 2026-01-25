# Jose (Vacuum) Dashboard - Functional Requirements

## Dashboard Information
- **Dashboard ID**: ``jose_vacuum``
- **Title**: Jose (Vacuum)
- **URL Path**: ``/jose-vacuum/jose``
- **Source of Truth**: ``jose/lovelace.jose_vacuum.json``
- **Last Updated**: 2026-01-23

## 1. Dashboard Design (Actual)

The dashboard utilizes a responsive "Intent-Driven" layout (`custom:layout-card`) with a 2-column grid that stacks on mobile.

### 1.1 Left Column: Control & Status (The "Act" Loop)
- **Primary Control**: `tile` card for `vacuum.jose` with Start/Stop/Home/Locate commands.
- **Status Grid**:
  - **Battery**: Primary color.
  - **Station**: Cyan color.
  - **Mop**: Blue indicator (Binary Sensor).
  - **Error**: Red indicator (Sensor).
- **Session Metrics**: Area Cleaned, Duration, Last Job Result.
- **Quick Actions**:
  - **Empty Dustbin** (Orange button).
  - **Relocate** (Teal button).
- **Configuration (Selects)**:
  - Auto Empty Frequency.
  - Water Flow Level.
  - Active Map Selection.
- **Error History**: Rolling log of the last 10 errors (Markdown).

### 1.2 Right Column: Context & Maintenance (The "Observe" Loop)
- **Lifetime Statistics**: Total Cleanings, Total Area, Total Duration.
- **Consumables (Gauges)**:
  - **Brush/Filter**: Filter, Main Brush, Side Brush.
  - **Maintenance**: Hand Filter, Unit Care.
- **Map**: Live `picture-entity` showing the cleaning map.

## 2. Automation & Logic Requirements

### 2.1 Error Logging System
- **Mechanism**: An automation triggers on `sensor.jose_error` state changes.
- **Storage**: Pushes the error text into a FIFO queue of 10 `input_text` helpers (`jose_error_log_1` to `_10`).
- **Display**: The dashboard Markdown card iterates through these helpers to display the log.

### 2.2 Entity Inventory
- **Vacuum**: `vacuum.jose` (Dreame Integration).
- **Sensors**: Battery, Area, Duration, Error, Lifespan sensors.
- **Helpers**: 10 `input_text` helpers for error logging.

## 3. Configuration Management

| File | Purpose | Location |
|------|---------|----------|
| `lovelace.jose_vacuum.json` | Dashboard Layout | `jose/` |
| `jose_vacuum_package.yaml` | Error Logging Automation | `ha-config/packages/` |

## 4. Future Enhancements (Gap Analysis)

- **Zone Presets**: Add "Quick Clean" buttons for high-traffic zones (Kitchen, Hallway) directly to the main view, bypassing the map selection requirement.
- **Bin Full Prediction**: Implement a predictive model based on `sqft_cleaned` since last empty, rather than relying solely on the sensor.