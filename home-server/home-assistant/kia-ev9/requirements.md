# Kia EV9 Integration – Functional Requirements Document

**Version**: 2.2 (Matched to Actual)
**Last Updated**: 2026-01-23
**Dashboard Source**: `kia-ev9/lovelace.kia-ev9.v2.2.yaml`

---

## 1. Dashboard Design (Actual)

The dashboard is the system's "Gold Standard" for Intent-Driven Design, utilizing a Tabbed interface to separate concerns.

### Tab 1: Main (Operations Only)
**Goal:** Daily driving needs. Read-only status + Safe Actions.
- **Battery & Range**: Gauge and entity stack.
- **Charging Status**:
  - Shows Power (kW) and "Time Left" (hh:mm format).
  - **Graph**: 7-day charging history graph (ApexCharts) with Battery % vs Power kW.
  - *Constraint:* No start/stop controls here (auto-charge assumed).
- **Climate Control**: Start/Stop buttons with Auto-Stop Timer visibility.
- **Vehicle Security (Unified)**:
  - Lock/Unlock buttons (color-coded state).
  - **Door Status**: Compact inline text (FL/FR/BL/BR/Trunk/Hood) using color font.
  - **Automation Status**: Shows "Walk-Away" and "Timeout" enabled state and last run result.
- **Map**: Live location.

### Tab 2: Config (Settings & Tuning)
**Goal:** Adjusting behavior and thresholds.
- **Proximity Security**:
  - Walk-Away Lock: Enable toggle, Distance Threshold slider.
  - Timeout Failsafe: Enable toggle, Duration slider.
- **Pre-conditioning**:
  - "Smart Mode" toggle (Weather-based).
  - **Schedules**: 5 distinct schedules with Day-of-Week chips (M T W T F S S), Time, and Temp setpoints.
- **Alerts**: Consolidated card for all notifications (Charging, Low Battery, Unlocked, etc.).

### Tab 3: Logs (History)
**Goal:** Observability.
- **Summary**: Last run result for Walk-Away, Timeout, and Precondition.
- **Event Log**: Markdown list of the last 10 system events (e.g., `WALKAWAY_LOCK`, `CHARGING_INTERRUPTED`).
- **Control**: "Clear Log" button.

### Tab 4: Logic & Info (Documentation)
**Goal:** In-dashboard documentation.
- Markdown cards explaining how Walk-Away, Timeout Failsafe, and Smart Pre-conditioning algorithms work.

---

## 2. Automation & Logic Requirements

### 2.1 Core Automations
- **Walk-Away Lock**: Triggers when phone GPS distance > Threshold (default 5m). Safe-guarded by engine state. Self-heals on HA restart.
- **Timeout Failsafe**: Triggers if unlocked > N minutes.
- **Charging Interrupted**: Notifies anytime (24/7) if charging stops unexpectedly while still plugged in and battery < 95%. Single toggle, no day/night distinction.
- **Pre-conditioning**:
  - **Smart Mode**: `Lead Time = |Outside - Target| * 0.5 min`.
  - Schedules trigger based on Time + Day + Enable check.

### 2.2 Self-Healing & Reliability
- **OTP Recovery**: Logic exists to parse email OTPs for re-authentication (documented in v2.2 requirements).
- **Logging**: All major actions write to the `input_text` event log.

---

## 3. Configuration Management

| File | Purpose | Location |
|------|---------|----------|
| `lovelace.kia-ev9.v2.2.yaml` | Dashboard Layout | `kia-ev9/` |
| `ev9_v2_4.yaml` | Package (Logic/Helpers) | `ha-config/packages/` |

---

## 4. Future Enhancements

- **Charging Control**: Move Start/Stop charging controls to a dedicated "Advanced" or "Config" section (currently removed from Main).
- **Consolidation**: Verify that `ev9_v2_4.yaml` is the *only* loaded EV9 package (audit found multiple versions potentially loading).