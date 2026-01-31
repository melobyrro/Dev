# Patio AC Control System — Project Instructions

> **Inherits from:** [/Dev/CLAUDE.md](../../../CLAUDE.md) — Read root file for universal dev workflow (git sync, Chrome MCP, Tasks, /done)

## Overview

This folder is the **feature root** for the Patio AC automation system.

## File Structure

```
patio-ac/
├── REQUIREMENTS.md              # Feature requirements (binding)
├── CLAUDE.md                    # This file
├── dashboards/
│   └── patio_ac.v1.21.yaml     # Active dashboard
├── docs/
│   └── ...                     # Additional documentation
└── .archive/                   # Old versions

ha-config/packages/
└── patio_ac.yaml               # Active package (code)
```

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| **Requirements** | `patio-ac/REQUIREMENTS.md` | Binding requirements document |
| **Package** | `ha-config/packages/patio_ac.yaml` | All code (automations, scripts, helpers, sensors) |
| **Dashboard** | `patio-ac/dashboards/patio_ac.v1.21.yaml` | Lovelace UI |

## Why Split?

Home Assistant's `!include_dir_named` requires packages to be in `ha-config/packages/`.
The requirements and dashboard live here in the feature folder per the constitution (Section 3.9).

## Editing Guidelines

1. **Read `REQUIREMENTS.md` first** — it's binding
2. **Edit `ha-config/packages/patio_ac.yaml`** for code changes
3. **Edit `dashboards/patio_ac.v1.21.yaml`** for UI changes
4. **Update `REQUIREMENTS.md`** when changing behavior (per Section 2.7)

## Migration Notes (2026-01-31)

- Renamed `Patio_AC_FRD_v1.8.md` → `REQUIREMENTS.md`
- Moved dashboard from `ha-config/dashboards/` to `patio-ac/dashboards/`
- Archived old dashboard versions to `.archive/`
- Updated `configuration.yaml` to reference new dashboard path
