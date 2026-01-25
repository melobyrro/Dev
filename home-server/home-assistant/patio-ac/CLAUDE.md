# Patio AC Control System - Project Instructions

## Overview

This folder contains the Patio AC automation system for Home Assistant.
**CRITICAL:** This project has been migrated to the Home Assistant **Packages** architecture.

## 🚨 Active Configuration Location

**DO NOT EDIT FILES IN THIS FOLDER.**

The active configuration is now located at:
`home-assistant/packages/patio_ac/patio_ac.yaml`

This single file contains:
- All Input Helpers (selects, numbers, booleans, etc.)
- All Automations (Heat Guard, Humidity Control, etc.)
- All Scripts (Control logic with error handling)
- All Template Sensors

## File Structure

```
home-assistant/
├── packages/
│   └── patio_ac/
│       └── patio_ac.yaml        # <--- EDIT THIS FILE
└── patio-ac/                    # This folder (Documentation only)
    ├── CLAUDE.md                # This file
    ├── Patio_AC_FRD_v1.8.md     # Functional Requirements
    ├── patio_ac_control.v1.20.yaml # Dashboard (Lovelace)
    └── .archive/                # Old versioned files
```

## Migration Notes (2026-01-22)

- **Consolidation**: `automations.v2.11`, `configuration.v2.9`, and `scripts.v2.8` were merged into `packages/patio_ac/patio_ac.yaml`.
- **Entity Rename**: The hardware ID `climate.150633095083490_climate` was replaced with `climate.patio_ac`.
- **Logic Hardening**: The `patio_ac_control` script now checks for `wait_template` timeouts and aborts if the device is unresponsive, preventing false state updates.

## Deployment Process

1. **Edit**: Modify `packages/patio_ac/patio_ac.yaml`.
2. **Verify**: Run `ha core check` (if available) or check config via UI.
3. **Deploy**: Restart Home Assistant to load the package changes.
4. **Dashboard**: Update dashboard cards to use `climate.patio_ac`.

## Dashboard Updates

The dashboard file `patio_ac_control.v1.20.yaml` still references the old entity ID. It needs to be updated to `climate.patio_ac`.