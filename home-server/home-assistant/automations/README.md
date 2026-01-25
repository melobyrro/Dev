# Home Assistant Automations Dashboard

This directory contains configuration files and documentation for the Home Assistant automations dashboard at:
https://home.byrroserver.com/dashboard-automations

## Dashboard Tabs Overview

| Tab | Status | Description |
|-----|--------|-------------|
| Dawarich | Working | Trip tracking based on location zones |
| Immich | Working | Daily album maintenance (Portrait, Selfies, Videos) |
| Autobrr | Working | Hardlink sweep + Filebot organization pipeline |
| Plex Priority | Disabled | Dynamic resource allocation for Plex streaming |

---

## 1. Dawarich Trip Automation

**Purpose**: Automatically manages trips in Dawarich based on location. Rolls monthly trips (e.g., 2026-01) and yearly trips (2026) so movement events are correctly grouped.

### How It Works
1. **Start**: When you leave the `zone.home`, a trip is started/resumed
2. **Extend**: Every 10 minutes while away, the trip is extended
3. **Finalize**: When you return home, the trip is finalized

### Automation Entities
| Entity | Trigger | Action |
|--------|---------|--------|
| `automation.dawarich_trip_start` | Leave home zone | Turn on `input_boolean.dawarich_on_trip`, call `shell_command.dawarich_trip_create` |
| `automation.dawarich_trip_extend` | Every 10 minutes (while on trip) | Call `shell_command.dawarich_trip_extend` |
| `automation.dawarich_trip_finalize` | Enter home zone (while on trip) | Call `shell_command.dawarich_trip_finalize`, turn off trip boolean |

### Implementation Files
- **Script**: `/home/byrro/automation/dawarich-trips/dawarich_trip.py`
- **Config**: `/home/byrro/automation/dawarich-trips/.env`
- **State File**: `/mnt/ByrroServer/docker-data/homeassistant/config/dawarich_trips.json`
- **Status File**: `/mnt/ByrroServer/docker-data/homeassistant/config/dawarich_status.json`

### Shell Commands (in configuration.yaml)
```yaml
shell_command:
  dawarich_trip_create: '/usr/local/bin/python3 /dawarich-trips/dawarich_trip.py create'
  dawarich_trip_extend: '/usr/local/bin/python3 /dawarich-trips/dawarich_trip.py extend'
  dawarich_trip_finalize: '/usr/local/bin/python3 /dawarich-trips/dawarich_trip.py finalize'
```

### Cron Job (status updates)
```
*/5 * * * * /home/byrro/scripts/dawarich_status.py >> /home/byrro/logs/dawarich_status.log 2>&1
```

---

## 2. Immich Album Maintenance

**Purpose**: Automatically populates dynamic albums (Portrait, Selfies, Videos) based on metadata and filenames.

### Schedule
| Job | Time | Script |
|-----|------|--------|
| Videos Update | 04:00 daily | `/home/byrro/scripts/update_videos_album.py` |
| Selfies Update | 04:15 daily | `/home/byrro/scripts/update_selfies_album.py` |
| Portrait Update | 04:30 daily | `/home/byrro/scripts/update_portrait_album.py` |

### Implementation
- Scripts query the Immich database for new assets matching specific criteria
- Assets are added to designated albums via the Immich API
- Status displayed via `sensor.immich_status`

---

## 3. Autobrr (Hardlink + Filebot Pipeline)

**Purpose**: Periodically checks for new downloads, creates hardlinks to keep original files seeding, and uses Filebot to rename and organize them into the media library.

### Schedule
| Job | Interval | Script |
|-----|----------|--------|
| Hardlink Sweep | Every 5 minutes | `/home/byrro/scripts/hardlink_other_sweep.sh` |
| Filebot Organize | Every 15 minutes | `/home/byrro/scripts/filebot_other.sh` |

### Manual Triggers
- `input_button.hardlink_other_run` - Run Hardlink Now
- `input_button.filebot_other_run` - Run Filebot Now

### Notes
- Processes 'prowlarr' and 'sports' categories
- Unmatched files moved to `_unmatched` subfolder for manual review

---

## 4. Plex Priority (Dynamic Resource Allocation)

**Purpose**: Automatically re-allocates system resources when Plex is streaming to prevent buffering.

### Current Status: DISABLED

### Configuration Options
| Setting | Range | Description |
|---------|-------|-------------|
| Plex Priority (niceness) | -20 to 19 | Lower = higher priority |
| Torrent Throttling | -20 to 19 | Higher = lower priority |
| Plex I/O Class | 1-3 | 1=Realtime, 2=Best Effort, 3=Idle |
| qBittorrent I/O Class | 1-3 | Recommended: 3 (Idle) |

### Implementation Files
- **Manager Script**: `plex/plex_priority_manager.py`
- **Immediate Script**: `plex/plex_priority_immediate.sh`
- **Systemd Service**: `plex/plex_dynamic_priority.service`
- **Deploy Script**: `plex/deploy_plex_priority.sh`

---

## File Structure

```
automations/
├── README.md                      # This file
├── README_LOCAL_COPY.md           # Notes about symbolic links
├── configuration.yaml             # Full HA configuration (local copy)
├── dashboard_automations.v2.yaml  # Dashboard YAML (version 2)
├── dashboard_automations.v3.yaml  # Dashboard YAML (version 3)
└── plex/
    ├── plex_priority_manager.py
    ├── plex_priority_immediate.sh
    ├── plex_dynamic_priority.service
    ├── plex_dynamic_priority.sh
    └── deploy_plex_priority.sh
```

## Remote File Locations

| Local Path | Remote Path |
|------------|-------------|
| configuration.yaml | `/mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml` |
| automations.yaml | `/mnt/ByrroServer/docker-data/homeassistant/config/automations.yaml` |
| Dashboard storage | `/mnt/ByrroServer/docker-data/homeassistant/config/.storage/lovelace.dashboard_automations` |

---

## Troubleshooting

### Dawarich Not Running
1. Check automation states: `automation.dawarich_trip_*` should be "on"
2. Verify shell commands exist in configuration.yaml
3. Check `/home/byrro/logs/dawarich_status.log` for errors
4. Ensure `/home/byrro/automation/dawarich-trips/.env` has valid credentials

### Immich Albums Not Updating
1. Check cron logs: `/home/byrro/logs/`
2. Verify Immich API connectivity
3. Check album scripts for errors

### Filebot Not Matching
1. Check `_unmatched` folder for files needing manual intervention
2. Review filebot exit codes in logs
3. Verify Filebot license is active

---

## Maintenance Log

| Date | Change | Notes |
|------|--------|-------|
| 2026-01-19 | Major improvements | Added debounce logic, event-driven logging, error notifications, template sensors |
| 2026-01-19 | Fixed Dawarich automations | Added missing automation definitions to automations.yaml |
| 2026-01-12 | Created local copies | Set up symbolic links and documentation |

---

## Recent Improvements (2026-01-19)

### Dawarich Enhancements
1. **Debounce Logic**: Added `timer.dawarich_trip_debounce` to prevent rapid start/finalize cycles when quickly leaving and re-entering home zone
2. **Configurable Extend Interval**: Now uses `input_number.dawarich_extend_minutes` instead of hardcoded 10 minutes
3. **Event-Driven Logging**: New automations (`dawarich_log_start`, `dawarich_log_extend`, `dawarich_log_finalize`) log to `input_text.dawarich_activity_log`
4. **Error Notifications**: `dawarich_error_notify` sends mobile notification if automations become unavailable

### New Template Sensors
- `sensor.dawarich_trip_status` - Shows "Idle", "On Trip", "Debouncing", or error state
- `sensor.dawarich_last_activity` - Shows last automation trigger time and action
- `sensor.plex_priority_status` - Shows current Plex priority state

### New Helpers Added
- `input_text.dawarich_activity_log` - Stores last activity for dashboard display
- `input_text.plex_priority_activity_log` - Stores Plex priority changes
- `timer.dawarich_trip_debounce` - Prevents rapid re-triggering

---

*Last updated: 2026-01-19*
