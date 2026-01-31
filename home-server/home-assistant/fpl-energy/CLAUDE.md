# FPL Energy Integration - Project Instructions

> **Inherits from:** [/Dev/CLAUDE.md](../../../CLAUDE.md) — Read root file for universal dev workflow (git sync, Chrome MCP, Tasks, /done)

## Overview

This project integrates Florida Power & Light (FPL) energy data with Home Assistant using the [hass-fpl HACS integration](https://github.com/dotKrad/hass-fpl). The integration provides daily energy usage monitoring, billing information, and projected costs.

## File Structure

```
fpl-energy/
├── CLAUDE.md                    # This file - project instructions
├── requirements.md              # Functional requirements document
├── configuration.v{X}.{Y}.yaml  # HA configuration additions
├── automations.v{X}.{Y}.yaml    # Energy automations
├── template_sensors.v{X}.{Y}.yaml  # Template sensors for calculations
├── lovelace.fpl-energy.v{X}.{Y}.yaml  # Dashboard cards
└── .archive/                    # Old versions
```

## Current Versions

| Component | Current Version | Last Updated |
|-----------|-----------------|--------------|
| Requirements | v1.0 | 2025-01-19 |
| Configuration | - | Not started |
| Automations | - | Not started |
| Template Sensors | - | Not started |
| Dashboard | - | Not started |

## Integration Details

### HACS Integration
- **Repository**: https://github.com/dotKrad/hass-fpl
- **Auth**: FPL.com account credentials
- **Update Frequency**: Daily (~4-5 AM)
- **Note**: NOT in default HACS - must add as custom repository:
  1. HACS → Integrations → 3-dot menu → Custom repositories
  2. Add URL: `https://github.com/dotKrad/hass-fpl`
  3. Category: Integration
  4. Then search for "FPL" in HACS

### Available Entities (Expected)

#### Sensors
| Entity | Description |
|--------|-------------|
| `sensor.fpl_daily_usage` | Daily kWh consumption |
| `sensor.fpl_daily_usage_kwh` | Daily usage in kWh |
| `sensor.fpl_bill_to_date` | Current bill amount ($) |
| `sensor.fpl_projected_bill` | End-of-month projection ($) |
| `sensor.fpl_daily_avg` | Average daily usage |
| `sensor.fpl_service_days` | Days in billing period |
| `sensor.fpl_as_of_days` | Days of data available |

### Energy Dashboard Integration
The FPL sensors can be integrated with Home Assistant's built-in Energy Dashboard for visualization.

## Deployment Process

### Initial Setup
1. Install HACS if not already installed
2. Add custom repository: `https://github.com/dotKrad/hass-fpl`
3. Install "FPL" integration
4. Restart Home Assistant
5. Add integration via UI with FPL.com credentials

### Configuration Changes
1. SSH to Docker VM: `ssh byrro@192.168.1.11`
2. Edit HA config: `nano /mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml`
3. Add template sensors for cost calculations
4. Reload configuration

### Template Sensors
Create derived sensors for:
- Cost per kWh calculation
- Month-to-date totals
- Comparison with previous billing period
- EV charging cost estimates (cross-reference with Kia EV9 data)

## Testing Checklist

- [ ] Integration connects successfully
- [ ] Daily usage sensor populates
- [ ] Bill data updates correctly
- [ ] Energy Dashboard shows FPL data
- [ ] Automations trigger on thresholds
- [ ] Dashboard cards render properly

## Troubleshooting

### Common Issues
1. **Auth fails**: Verify FPL.com credentials work in browser
2. **No data**: Wait until after 5 AM for daily update
3. **Stale data**: Check FPL account for any alerts or holds

### Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.fpl: debug
```

## FPL Rate Information

### 2026 Rate Changes
FPL approved rate changes for 2026. Monitor for:
- Base rate adjustments
- Time-of-use rate changes
- Demand charges (if applicable)

### Current Rate Structure
- Residential rate schedules available at [FPL Rate Schedules](https://www.fpl.com/rates/pdf/res-Sept-2023.pdf)
- Consider implementing time-of-use optimizations for EV charging

## Related Documentation

- [hass-fpl GitHub](https://github.com/dotKrad/hass-fpl)
- [Home Assistant Energy Dashboard](https://www.home-assistant.io/docs/energy/)
- [FPL Energy Manager](https://www.fpl.com/landing/energy-manager.html)
- [FPL Account Login](https://www.fpl.com/my-account.html)
