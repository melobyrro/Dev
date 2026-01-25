# Home Assistant Package Standards

## Overview

This document establishes standards for migrating Home Assistant configurations to the Packages architecture. All projects under `home-assistant/` should follow these patterns.

## Directory Structure

```
config/packages/
├── patio_ac/
│   └── patio_ac.yaml       # All config for patio AC feature
├── kia_ev9/
│   └── kia_ev9.yaml        # All config for Kia EV9 integration
├── homelab/
│   └── prometheus.yaml     # Prometheus monitoring sensors
├── daikin/
│   └── daikin.yaml         # Daikin HVAC integration
├── jose/
│   └── jose.yaml           # Jose vacuum automation
└── dashboard/
    └── dashboard.yaml      # Shared dashboard automations
```

## Naming Conventions

### Package Folders and Files
- Package folders: `snake_case` (e.g., `patio_ac`, `kia_ev9`)
- Package files: Same as folder name (e.g., `patio_ac/patio_ac.yaml`)
- **NO underscore prefix** (e.g., NOT `_test_package.yaml` - causes slug errors)

### Entity IDs
- Format: `{domain}.{feature}_{name}`
- Examples:
  - `input_boolean.patio_ac_heat_guard_enabled`
  - `sensor.kia_ev9_battery_level`
  - `automation.patio_ac_heat_guard_on`

### Semantic Entity Names (Critical)
- **NEVER** use hardware IDs in entity names
- **BAD**: `climate.150633095083490_climate`
- **GOOD**: `climate.patio_ac`

## Package File Structure

```yaml
# packages/{feature}/{feature}.yaml

# ============================================
# {FEATURE NAME} PACKAGE
# ============================================
# Purpose: {brief description}
# Migrated from: {source files}
# Last Updated: {YYYY-MM-DD}
# FRD Reference: {path to FRD if applicable}
# ============================================

# --- INPUT BOOLEANS ---
input_boolean:
  {feature}_enabled:
    name: "{Feature} Enabled"
    icon: mdi:power

# --- INPUT NUMBERS ---
input_number:
  {feature}_threshold:
    name: "{Feature} Threshold"
    min: 0
    max: 100
    step: 1
    unit_of_measurement: "°F"
    icon: mdi:thermometer

# --- INPUT DATETIMES ---
input_datetime:
  {feature}_start_time:
    name: "{Feature} Start Time"
    has_time: true
    has_date: false

# --- INPUT SELECT ---
input_select:
  {feature}_mode:
    name: "{Feature} Mode"
    options:
      - option_1
      - option_2

# --- INPUT TEXT ---
input_text:
  {feature}_status:
    name: "{Feature} Status"
    max: 255

# --- INPUT BUTTONS ---
input_button:
  {feature}_reset:
    name: "Reset {Feature}"
    icon: mdi:restart

# --- TEMPLATE SENSORS ---
template:
  - sensor:
      - name: "{Feature} Status"
        unique_id: {feature}_status
        state: "{{ states('input_select.{feature}_mode') }}"

# --- TIMERS ---
timer:
  {feature}_timeout:
    name: "{Feature} Timeout"
    duration: "00:05:00"

# --- AUTOMATIONS ---
automation:
  - id: {feature}_trigger
    alias: "{Feature} - Trigger"
    description: "Triggers when condition is met"
    mode: single
    trigger:
      - platform: state
        entity_id: sensor.{feature}_source
    condition:
      - condition: state
        entity_id: input_boolean.{feature}_enabled
        state: "on"
    action:
      - service: script.{feature}_control
        data:
          action: "on"

# --- SCRIPTS ---
script:
  {feature}_control:
    alias: "{Feature} Control"
    mode: queued
    max: 3
    fields:
      action:
        description: "Action to perform"
        selector:
          select:
            options: ["on", "off"]
    sequence:
      - service: input_boolean.turn_on
        target:
          entity_id: input_boolean.{feature}_enabled
```

## Migration Checklist

Use this checklist when migrating a project to packages:

### Pre-Migration
- [ ] Backup current configuration
- [ ] Document all entity IDs being migrated
- [ ] Identify any hardware-based entity IDs that need renaming

### Migration
- [ ] Create package directory: `packages/{feature}/`
- [ ] Create package file: `packages/{feature}/{feature}.yaml`
- [ ] All automations have unique `id:` fields
- [ ] All entity IDs use semantic names (no hardware IDs)
- [ ] All helpers moved from main config to package
- [ ] Replace hardcoded entity IDs with semantic names

### Post-Migration
- [ ] Validate configuration: `ha core check`
- [ ] Package loads without errors
- [ ] All automations trigger correctly
- [ ] Dashboard still renders
- [ ] Old versioned files moved to `.archive/`
- [ ] Update project CLAUDE.md

## Versioning

### Use Git, NOT Filename Versioning
- **OLD**: `automations.v2.11.yaml`, `scripts.v2.8.yaml`
- **NEW**: Single `patio_ac.yaml` with Git history

### Git Tags for Releases
```bash
git tag -a ha-patio-ac-v2.0 -m "Migrated patio-ac to packages"
git push origin ha-patio-ac-v2.0
```

### Archive Old Files
```bash
mkdir -p {project}/.archive/pre-package-migration
mv automations.v2.11.yaml .archive/pre-package-migration/
mv configuration.v2.9.yaml .archive/pre-package-migration/
mv scripts.v2.8.yaml .archive/pre-package-migration/
```

## Error Handling Best Practices

### Script Timeout Handling
Always check if `wait_template` completed:

```yaml
script:
  example_control:
    sequence:
      - wait_template: "{{ is_state('switch.device', 'on') }}"
        timeout: "00:00:30"
      - if:
          - condition: template
            value_template: "{{ wait.completed == false }}"
        then:
          - service: persistent_notification.create
            data:
              title: "Command Failed"
              message: "Device did not respond in time"
          - stop: "Command timed out"
```

### Automation Debouncing
Prevent rapid-fire triggers:

```yaml
automation:
  - id: example_with_debounce
    alias: "Example with Debounce"
    mode: restart  # Cancels previous run if retriggered
    trigger:
      - platform: state
        entity_id: input_number.threshold
        for: "00:00:01"  # 1-second debounce
    action:
      - delay: "00:00:00.5"  # Additional settling time
      - service: input_number.set_value
        # ...
```

## Environment Reference

| Environment | Port | Config Path | Purpose |
|-------------|------|-------------|---------|
| Production | 8123 | `/config/` | Live system |
| Lab (Gemini) | 8126 | `/config-lab/` | Gemini testing |
| Claude Staging | 8127 | `/config-claude/` | Package migration testing |
| Test | varies | `/config-test/` | Other testing |

## References

- [Home Assistant Packages Documentation](https://www.home-assistant.io/docs/configuration/packages/)
- [Home Assistant Automation Best Practices](https://www.home-assistant.io/docs/automation/best-practices/)
- Project FRDs in respective folders (e.g., `patio-ac/Patio_AC_FRD_v1.8.md`)
