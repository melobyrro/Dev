# Patio AC Control System - Functional Requirements

**Version**: 1.9 (Updated to Actual)
**Last Updated**: 2026-01-23
**Dashboard Source**: `patio-ac/patio_ac_control.v1.20.yaml`

---

## 1. Dashboard Design (Actual)

The dashboard provides deep control over the State Machine logic governing the Patio AC.

### 1.1 Status & Control
- **Entity**: `climate.patio_ac` (formerly `150633...`).
- **State Machine**:
  - `input_select.patio_ac_reason`: Shows the *why* (Idle, Heat Guard, Humidity Day/Night, etc.).
  - **Manual Override**: Toggle to force control.
- **Environmental**:
  - **Graphs**: Temperature and Humidity history (24h).
  - **Dew Point**: Calculated dew point values.

### 1.2 Configuration Sections (Folded)
- **Heat Guard**: Thresholds for high-temp protection.
- **Humidity Rules**:
  - **Day**: Start/Stop RH%.
  - **Night**: Start/Stop RH% (distinct logic).
- **Protections**:
  - Compressor Cooldown (timer).
  - Min Run/Off times.

---

## 2. Automation & Logic Requirements

### 2.1 State Machine Logic (The "Split-Brain" Risk)
- **Intended**: All logic resides in `packages/patio_ac/patio_ac.yaml`.
- **Actual Risk**: The system currently has duplicate/legacy logic in `automations/configuration.yaml` and the package file is potentially not loaded due to folder structure.
- **Mechanism**:
  - Automations trigger on Temp/Humidity changes.
  - Scripts evaluate conditions -> Set `patio_ac_reason` -> Execute Climate command.

### 2.2 Critical Constraints
- **Hardware Abstraction**: Must use `climate.patio_ac` (virtual/renamed) to avoid breaking on hardware swap.
- **Safety**: "Heat Guard" must override all other states to prevent equipment damage.

---

## 3. Configuration Management

| File | Purpose | Location |
|------|---------|----------|
| `patio_ac_control.v1.20.yaml` | Dashboard Layout | `patio-ac/` |
| `patio_ac.yaml` | Logic Package | `packages/patio_ac/` (Needs move to `ha-config/packages/`) |

---

## 4. Future Enhancements

- **Comfort Logic**: Implement "Thermal Comfort" (Dew Point based) triggers instead of raw temperature.
- **Window Opportunity**: Notification when outdoor dew point is lower than indoor (free cooling).
- **Fix Migration**: Complete the move to `ha-config/packages/` and remove legacy automations.