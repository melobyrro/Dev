# Dawarich Dynamic Trips (Home Assistant)

This folder contains the helper script and environment template for creating/updating Dawarich trips (visits) from Home Assistant.

## Behavior (area + distance bands + daytype)
- Area trips: `YYYY-MM|area` (monthly) and `YYYY|area` (yearly).
- Distance-band trips: `YYYY-MM|distance` and `YYYY|distance` (Local <= 5mi, Regional <= 25mi, Day Trip <= 100mi, Travel > 100mi).
- Daytype trips: `YYYY-MM|weekday|weekend` and `YYYY|weekday|weekend` (uses America/New_York).
- Leaving home after debounce resumes/creates the trips for the current area/band/daytype.
- While away, `extend` updates `ended_at` every interval; if any key changes, it closes the previous trip and switches.
- Arriving home finalizes the current trip state but keeps the maps for reuse.

## State file
- Stored in the HA config volume as `/mnt/ByrroServer/docker-data/homeassistant/config/dawarich_trips.json`.
- The helper script writes to `/config/dawarich_trips.json` inside the container.
- Keys in the file: `trips_monthly`, `trips_yearly`, `trips_distance_monthly`, `trips_distance_yearly`, `trips_daytype_monthly`, `trips_daytype_yearly`, and `geo_cache`.

## Setup
1) Dawarich env file
   - Create `.env`:
     - `DAWARICH_BASE_URL=https://dawarich.byrroserver.com`
     - `DAWARICH_API_KEY=<your token>`

2) Home Assistant secrets
   - File: `/mnt/ByrroServer/docker-data/homeassistant/config/secrets.yaml`
   - Add:
     - `ha_long_lived_token: <your HA token>`
     - `dawarich_api_bearer: "Bearer <your Dawarich token>"` (used by `rest_command`)

3) Home Assistant container mount
   - Ensure `/home/byrro/automation/dawarich-trips` is mounted into the HA container as `/dawarich-trips` (see `/home/byrro/docker/homeassistant/docker-compose.yml`).

4) Home Assistant configuration
   - Update `configuration.yaml` and `automations.yaml` (see changes in this repo).
   - Restart Home Assistant after config updates.

Optional env overrides (in `.env`):
- `HA_PERSON_ENTITY` (default `person.andre_byrro`)
- `HA_GEOCODE_ENTITY` (default `sensor.andre_iphone_geocoded_location`)
- `HA_HOME_ZONE` (default `zone.home`)
- `DAWARICH_STATE_PATH` (default `/config/dawarich_trips.json`)
- `DAWARICH_DISTANCE_LOCAL_MI` (default `5`)
- `DAWARICH_DISTANCE_REGIONAL_MI` (default `25`)
- `DAWARICH_DISTANCE_DAYTRIP_MI` (default `100`)

## Testing
1) Validate the helper script (no secrets printed):
   - `python3 /home/byrro/automation/dawarich-trips/dawarich_trip.py create`
   - `python3 /home/byrro/automation/dawarich-trips/dawarich_trip.py extend`
   - `python3 /home/byrro/automation/dawarich-trips/dawarich_trip.py finalize`

2) Trigger via Home Assistant
   - In Developer Tools → Services, call:
     - `shell_command.dawarich_trip_create`
     - `shell_command.dawarich_trip_extend`
     - `shell_command.dawarich_trip_finalize`

3) Confirm state map
   - Check `/mnt/ByrroServer/docker-data/homeassistant/config/dawarich_trips.json` for area, distance, and daytype keys (monthly/yearly).

## Rotate API Key
- Dawarich: update `DAWARICH_API_KEY` in `/home/byrro/automation/dawarich-trips/.env`.
- Home Assistant: update `ha_long_lived_token` in `/mnt/ByrroServer/docker-data/homeassistant/config/secrets.yaml`.

## Rollback
1) Revert `configuration.yaml` and `automations.yaml` to backups (or remove the Dawarich sections).
2) Remove `/home/byrro/automation/dawarich-trips` and `/mnt/ByrroServer/docker-data/homeassistant/config/dawarich_trips.json`.
3) Restart Home Assistant.
