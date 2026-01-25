# Home Assistant Automation Script Links

This directory contains configuration files and documentation for the Home Assistant
automations dashboard at: https://home.byrroserver.com/dashboard-automations

**See README.md for comprehensive documentation.**

## Quick Reference

### Remote File Locations
| File | Remote Path |
|------|-------------|
| automations.yaml | `/mnt/ByrroServer/docker-data/homeassistant/config/automations.yaml` |
| configuration.yaml | `/mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml` |
| scripts.yaml | `/mnt/ByrroServer/docker-data/homeassistant/config/scripts.yaml` |
| Dashboard storage | `/mnt/ByrroServer/docker-data/homeassistant/config/.storage/lovelace.dashboard_automations` |

### Dashboard Tabs (4 total)
1. **Dawarich** - Trip tracking automations (zone-based)
2. **Immich** - Photo album scheduling (daily cron)
3. **Autobrr** - Hardlink sweep + Filebot organization pipeline
4. **Plex Priority** - Dynamic resource allocation (currently disabled)

### Local Files
- `README.md` - Full documentation
- `dawarich_automations.yaml` - Dawarich automation definitions (backup)
- `configuration.yaml` - Local copy of HA configuration
- `dashboard_automations.v2.yaml` / `v3.yaml` - Dashboard YAML definitions
- `plex/` - Plex priority scripts and service files

## Maintenance Log

| Date | Change |
|------|--------|
| 2026-01-19 | Fixed Dawarich automations - added missing definitions |
| 2026-01-12 | Initial setup with symbolic links |
