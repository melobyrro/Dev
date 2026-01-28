# HA Packages — Requirements
**Last Updated:** 2026-01-28
**Scope:** /home/byrro/Dev/home-server/home-assistant/ha-config/packages

## Purpose
This directory contains Home Assistant package files loaded by `configuration.yaml`.

## Rules
- Each package must reference a feature-local requirements document under `/home/byrro/Dev/home-server/home-assistant/<feature>/requirements.md`.
- Do not duplicate entity IDs across packages.
- All new automations must follow CLAUDE.md rules (id/alias/description/mode, decision→actuation split).

## Jose Schedule Package (jose_schedule_v2_0.yaml)
- **Purpose:** Provide two configurable schedules for Jose (vacuum-only) with robust, idempotent execution.
- **Inputs:** `helper_jose_schedule_*` helpers, `vacuum.jose`, `select.jose_work_mode`, `switch.jose_clean_preference`, `sensor.jose_*`.
- **Outputs:** `input_text.helper_jose_schedule_*_last_run` and `_last_result`, logbook entries, and failure notifications.
- **Safety:** No direct device IDs in automations; bounded waits; guardrails for availability/battery; failure notifications.
- **UI Contract:** Jose dashboard “Schedules” view; Observe → Understand → Act; log display is read-only (markdown).
