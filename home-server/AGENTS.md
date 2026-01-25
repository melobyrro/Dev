# Agents — home-server

## Orchestrator Role

This project operates as an **infrastructure orchestrator**, not a traditional development project:
- **No feature backlog**: There is no "todo list" of features to implement
- **Reactive operations**: Respond to user requests for infrastructure tasks
- **Delegation model**: Use skills/subagents for specialized work

When starting a session:
1. Summarize the current infrastructure state (not a feature roadmap)
2. List any known issues or pending maintenance (if any)
3. Wait for user instructions

## Default Operating Context

- Run all infra checks and changes on the remote host `byrro@192.168.1.11` via SSH
- Use `ssh root@192.168.1.10` for Proxmox hypervisor operations (SSH keys configured)
- Use the working directory on the remote that mirrors this repo
- If unsure of location, run `pwd` after SSH and adjust with `cd` accordingly

## Connectivity Assumptions

- Use `ssh byrro@192.168.1.11` for Docker VM commands, logs, or service restarts
- Use `ssh root@192.168.1.10` for Proxmox operations
- Prefer a single session and reuse it for multiple commands when possible
- No need to ask permission before SSHing into the VM or Proxmox host
- If SSH fails, stop and report the error; do not attempt retries with alternate hosts

## Safety & Scope

- Never run destructive commands (resets, wipes) unless explicitly asked
- Keep secrets/keys out of logs and responses
- Restart Home Assistant when required for config changes without asking first
- Host-level Caddy routes `church.byrroserver.com` via `byrro-net`; ensure `culto_web` stays attached to that network
- Preference: apply Home Assistant config changes directly (edit `configuration.yaml`) instead of asking the user to paste changes.
- Dashboard YAML preference: save full Lovelace YAML exports in `/Users/andrebyrro/Downloads` for copy/paste; if a dashboard has multiple tabs, always provide the full dashboard YAML (not per-tab snippets).

## Browser Automation (MCP)

- Use **chrome-devtools-mcp** via CDP; avoid `mcp-server-browser` unless explicitly requested.
- Start Chrome with remote debugging + repo profile using `./scripts/chrome-mcp-start.sh`.
- Verify CDP is live with `./scripts/chrome-mcp-check.sh` (expects `webSocketDebuggerUrl`).
- CDP endpoint: `http://127.0.0.1:9222` (Codex MCP config points `chrome-devtools-mcp@latest --browserUrl http://127.0.0.1:9222`).
- Persistent profile directory: `/Users/andrebyrro/Dev/home-server/.mcp/chrome-profile` (do not store credentials elsewhere).
- Screenshots (if captured) land in `/Users/andrebyrro/Dev/home-server/.mcp/screens`.
- When a login is required, pause and let the user authenticate in the visible Chrome window; then continue using the same tab/profile.

## Monitoring Stack Context

### Home Assistant (Primary Dashboard)
- **URL**: `http://192.168.1.11:8123`
- **Dashboard**: Sidebar → "Homelab" (4 views: Overview, Proxmox, Docker VM, Containers)
- **Sensors**: Prometheus metrics via `prometheus_sensor` HACS integration
- **Notifications**: Mobile app alerts for security, uptime, and performance

### Uptime Kuma
- **URL**: `http://192.168.1.11:3002`
- **Coverage**: Docker-type monitors for all running containers
- **HTTP checks**: `Home Assistant`, `Jellyseerr`, `Portainer`, `Tautulli`, `Radarr`, `Sonarr`, `Caddy (church)`
- **Status codes**: HTTP checks accept `200-399` to allow redirects
- **Notifications**: All monitors send to Email (`Email Uptime`) and HA webhook (`Home Assistant`)

### Key Services
| Service | Port | Purpose |
|---------|------|---------|
| Prometheus | 9090 | Metrics backend |
| pve-exporter | 9221 | Proxmox metrics |
| falco-ha-bridge | 5002 | Security alerts → HA |
| tracker-monitor | - | Reddit signup monitor |
| trivy-api | 8083 | Legacy HTML reports |

### Tracker Monitor HA Integration
- **API endpoints**: `http://192.168.1.11:5050/api/ha/open` and `http://192.168.1.11:5050/api/ha/history?limit=50` (stable hash + list payloads).
- **HA REST sensors**: Added to `/mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml` as
  `sensor.tracker_monitor_open_hash` and `sensor.tracker_monitor_history_hash` (15m polling, attributes `open`/`history`).
- **Dashboard delivery**: Provide full Lovelace YAML for copy/paste (current file: `/Users/andrebyrro/Downloads/tracker-monitor-ha.yaml`).
- **Formatting preference**:
  - Use Markdown tables (not raw HTML) with strict table formatting: no blank lines between header and rows.
  - One row per tracker; columns must match headers.
  - Sanitize tracker names to remove `|` if needed (pipes break Markdown tables).
  - Avoid Jinja list `append` in templates (blocked by HA security).
  - Latest Tracker Activity must be read-only (no interactive entity controls).
  - Cards should be wide (`column_span: 2`) for readability.
- **Token note**: Long-lived token named `logs` was not usable for API calls (401). Do not print tokens; request a fresh token if HA API checks are required.

### Secrets & Tokens
- **HA secrets**: `/mnt/ByrroServer/docker-data/homeassistant/config/secrets.yaml` (never print values).
- **HA long-lived tokens**: `/mnt/ByrroServer/docker-data/homeassistant/config/.storage/auth` (root-only; token names stored here).
- **Dawarich trips env**: `/home/byrro/automation/dawarich-trips/.env` (template: `/home/byrro/automation/dawarich-trips/.env.example`).
- **Dawarich trips HA token**: `ha_long_lived_token` stored in `/mnt/ByrroServer/docker-data/homeassistant/config/secrets.yaml` (token name in HA UI: `dawarich_trips`).
- **Dawarich API bearer**: `dawarich_api_bearer` stored in `/mnt/ByrroServer/docker-data/homeassistant/config/secrets.yaml`.

### Dawarich Dynamic Trips
- **API**: `https://dawarich.byrroserver.com/api/v1/trips` with `Authorization: Bearer <token>` (custom API overlay for trips).
- **API overrides**: `/home/byrro/docker/dawarich/overrides/routes.rb` and `/home/byrro/docker/dawarich/overrides/api_v1_trips_controller.rb` (mounted via `/home/byrro/docker/dawarich/docker-compose.yml`).
- **Helper script**: `/home/byrro/automation/dawarich-trips/dawarich_trip.py` (mounted in HA container as `/dawarich-trips`).
- **State file**: `/mnt/ByrroServer/docker-data/homeassistant/config/dawarich_trips.json` (synced to `/home/byrro/automation/dawarich-trips/dawarich_trips.json`; keys: `trips_monthly`, `trips_yearly`, `geo_cache`).
- **Trip keys**: monthly `YYYY-MM`, yearly `YYYY`.
- **Trip names**: `YYYY - MM` (monthly) and `YYYY` (yearly).
- **Series enabled**: monthly + yearly only; distance/daytype helpers are cleared each run.
- **HA config**: `/mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml` and `/mnt/ByrroServer/docker-data/homeassistant/config/automations.yaml`.
- **Automations**: `automation.dawarich_trip_start`, `automation.dawarich_trip_extend`, `automation.dawarich_trip_finalize`.
- **Helpers**: `input_boolean.dawarich_on_trip`, `input_text.dawarich_current_trip_id`, `input_text.dawarich_current_trip_key`, `input_text.dawarich_current_trip_id_yearly`, `input_text.dawarich_current_trip_key_yearly`, `input_text.dawarich_current_trip_id_distance`, `input_text.dawarich_current_trip_key_distance`, `input_text.dawarich_current_trip_id_distance_yearly`, `input_text.dawarich_current_trip_key_distance_yearly`, `input_text.dawarich_current_trip_id_daytype`, `input_text.dawarich_current_trip_key_daytype`, `input_text.dawarich_current_trip_id_daytype_yearly`, `input_text.dawarich_current_trip_key_daytype_yearly`, `input_datetime.dawarich_trip_start`, `input_datetime.dawarich_trip_last_update`, `input_number.dawarich_debounce_minutes`, `input_number.dawarich_extend_minutes`, `input_text.dawarich_last_error`, `input_datetime.dawarich_last_error` (distance/daytype helpers intentionally left blank).
- **Dashboard YAML export**: `/Users/andrebyrro/Downloads/automations-dashboard.yaml` (full dashboard YAML; includes Dawarich tab, Dynamic Trips explanation, and a Dawarich Automations entities card).
- **Dawarich app env**: `/home/byrro/docker/dawarich/.env` should include `TIME_ZONE=America/New_York`, `PHOTON_API_HOST=photon.komoot.io`, `PHOTON_API_USE_HTTPS=true`; apply via `docker compose up -d --force-recreate dawarich-app dawarich-sidekiq`.
- **Troubleshooting**: If the dashboard shows `Update trip failed: status=404 body={"error":"Record not found"}`, the HA helper trip IDs are stale (Dawarich API returns 404 for those ids). Clear the helper IDs (`input_text.dawarich_current_trip_id*`) and turn off `input_boolean.dawarich_on_trip`, then let the next `create`/`extend` regenerate fresh trip IDs. If trips show `Trip path is being calculated...`, confirm points ingestion (no `/api/v1/points` posts or `points_since_date = 0` in the DB means the iOS app is not uploading).

### Common Operations
```bash
# Check monitoring stack
ssh byrro@192.168.1.11 "docker ps | grep -E 'prometheus|pve-exporter|falco-ha-bridge'"

# Restart monitoring services
ssh byrro@192.168.1.11 "cd /home/byrro/docker/monitoring && docker compose restart prometheus pve-exporter falco-ha-bridge"

# Check HA sensor values
curl -s http://192.168.1.11:8123/api/states/sensor.vm_cpu_usage -H "Authorization: Bearer $HA_TOKEN"

# View Prometheus targets
curl -s http://192.168.1.11:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

### WireGuard + AdGuard Home Connectivity Issues
**Problem**: WireGuard clients lose internet connectivity or experience slow connections when using AdGuard Home as DNS.

**Root Cause**: IPv6 connectivity doesn't work through the WireGuard VPN, but AdGuard Home returns IPv6 addresses in DNS responses. Clients try to use IPv6 addresses, which fail, causing connection timeouts or failures.

**Why it was working before and broke**:
1. **Before**: Client OS (macOS) likely used "Happy Eyeballs" algorithm - tried IPv6 but quickly fell back to IPv4 when IPv6 failed
2. **Something changed**: Client OS update or network configuration change altered IPv6 fallback behavior (longer timeouts, different DNS sorting)
3. **After**: IPv6 attempts take longer or don't fall back properly, causing apparent loss of connectivity

**Solution Applied**:
1. Configure AdGuard Home to disable IPv6 DNS responses:
   - Set `aaaa_disabled: true` in `/opt/adguardhome/conf/AdGuardHome.yaml`
   - Use IPv4-only upstream DNS (1.1.1.1, 8.8.8.8, 9.9.9.9)
   - Remove IPv6 addresses from bootstrap DNS
2. **Verification**: AAAA queries now return empty responses, only A records returned

**Diagnostic Commands**:
```bash
# Test DNS resolution from WireGuard container
ssh byrro@192.168.1.11 "docker exec wireguard nslookup -type=A google.com 192.168.1.11"
ssh byrro@192.168.1.11 "docker exec wireguard nslookup -type=AAAA google.com 192.168.1.11"

# Check AdGuard Home config
ssh byrro@192.168.1.11 "docker exec adguardhome grep -A5 'aaaa_disabled:' /opt/adguardhome/conf/AdGuardHome.yaml"
ssh byrro@192.168.1.11 "docker exec adguardhome grep -A5 'upstream_dns:' /opt/adguardhome/conf/AdGuardHome.yaml"

# Test IPv6 connectivity
ssh byrro@192.168.1.11 "docker exec wireguard ping6 -c 1 google.com 2>&1"
```

**If issue recurs**:
1. Verify AdGuard Home config hasn't been reset
2. Check if AdGuard Home was updated (resets config)
3. Consider alternative: Configure WireGuard clients to use different DNS (1.1.1.1) instead of AdGuard Home

### qBittorrent Other Intake (Prowlarr/Other)
- **Downloads**: qBittorrent categories `prowlarr` and `other` land in `/mnt/ByrroServer/ByrroMedia/downloads/prowlarr` and `/mnt/ByrroServer/ByrroMedia/downloads/other`.
- **Hardlink sweep**: `/home/byrro/scripts/hardlink_other_sweep.sh` runs every 5 minutes (cron) and on-demand via HA `input_button.hardlink_other_run`. It hardlinks into `/mnt/ByrroServer/ByrroMedia/Other_Inbox` and tracks seen items in `/home/byrro/logs/hardlink_other_seen.txt` to avoid re-linking unchanged downloads. Logs: `/home/byrro/logs/hardlink_other_sweep.log`.
- **Filebot organize**: `/home/byrro/scripts/filebot_other.sh` runs every 15 minutes (cron) and on-demand via HA `input_button.filebot_other_run`. It processes `/mnt/ByrroServer/ByrroMedia/Other_Inbox` and moves/renames into `/mnt/ByrroServer/ByrroMedia/Other` (downloads remain untouched). Filebot logs: `/home/byrro/logs/filebot_other.log` and `/mnt/ByrroServer/docker-data/filebot/logs/amc.log`.
- **Filebot license**: store in `/mnt/ByrroServer/docker-data/filebot/.filebot/license.psm` (activation writes `/mnt/ByrroServer/docker-data/filebot/filebot/license.txt`).
- **Plex refresh**: hardlink sweep triggers a Plex library refresh after each run. Token is read from `/srv/docker-data/plex/Library/Application Support/Plex Media Server/Preferences.xml`; refresh targets library title `Other Videos` (fallback to `Other`, then all sections).
- **HA status JSON**: `/mnt/ByrroServer/docker-data/homeassistant/config/hardlink_other_status.json` and `/mnt/ByrroServer/docker-data/homeassistant/config/filebot_other_status.json` expose `recent_log` as a markdown table.
- **Dashboard**: Filebot automation tab is exported in `/Users/andrebyrro/Downloads/automations-dashboard.yaml`.

### AutoBRR Tracker Farming & Verification
**Goal:** Maximize Seeding/Ratio (Aggressive Racing) - **OPTIMIZED & VERIFIED**

#### **Optimization Strategy Applied:**
- **TorrentDay**: Large Freeleech files + Racing.
  - Rules: `Freeleech=True`, `Max Seeders=10`, `Size=5GB-200GB`, `Delay=0`.
  - Daily Cap: 10/day (Volume strategy).
  - **Status**: ✅ Active - IRC monitoring `#td.announce`

- **SportsCult**: Instant grab on popular sports.
  - Rules: `Max Seeders=5`, `Match Categories=[Football, NBA, F1]`.
  - Daily Cap: 10/day (Content expires fast).
  - **Status**: ✅ Enabled - RSS feed scheduled

- **YuScene**: High-demand resolutions.
  - Rules: `Resolution=[2160p, 1080p]`, `Year=[Current Year]`.
  - Daily Cap: 5/day.
  - **Status**: ✅ Enabled - RSS feed scheduled

- **HDSpace**: Quality over quantity.
  - Rules: `Freeleech=True`, `Max Seeders=12`.
  - Daily Cap: 5/day.
  - **Status**: ✅ Active - Matching freeleech content

#### **Verification Results (2026-01-10):**
1. **TorrentDay IRC**: ✅ Active and monitoring announcements
2. **All Indexers Enabled**: ✅ TorrentDay, SportsCult Farm, YuScene Farm, HDSpace Farm
3. **Successful Downloads**:
   - **TorrentDay**: "Dreaming Whilst Black S01 2160p WEB-DL DD5 1 H 265-NHTFS" (15.8GB FREELEECH) - FILTER_APPROVED
   - **HDSpace**: Multiple "Hell's Kitchen" episodes (2.3-2.4GB FREELEECH) - FILTER_APPROVED
4. **Filtering Working Correctly**:
   - ✅ TorrentDay rejects non-freeleech torrents
   - ✅ TorrentDay rejects torrents <5GB (2.85GB, 1.10GB, 1.38GB all rejected)
   - ✅ Freeleech requirement enforced for TorrentDay & HDSpace
   - ✅ Size filtering: 5GB minimum enforced

#### **Operational Commands:**
```bash
# Check autobrr status
ssh byrro@192.168.1.11 "docker logs --tail 20 autobrr | grep -i 'match\|download\|grabbed'"

# Check indexer status
ssh byrro@192.168.1.11 "sudo sqlite3 /mnt/ByrroServer/docker-data/autobrr/autobrr.db 'SELECT name, enabled FROM indexer WHERE name LIKE \"%Farm%\" OR name LIKE \"%TorrentDay%\";'"

# View recent matches
ssh byrro@192.168.1.11 "sudo sqlite3 /mnt/ByrroServer/docker-data/autobrr/autobrr.db 'SELECT filter, torrent_name, size, filter_status FROM release ORDER BY id DESC LIMIT 5;'"
```

#### **Expected Activity:**
- **SportsCult**: Should match Football/NBA/F1 content when RSS feed runs
- **YuScene**: Should match 2160p/1080p content from current year when RSS feed runs
- **HDSpace**: Already matching freeleech content
- **TorrentDay**: Continuously monitoring IRC for >5GB freeleech torrents

**All systems operational and actively downloading/seeding for ratio building.**

### Plex Dynamic Resource Prioritization
**Problem**: Plex buffering due to resource contention with qBittorrent (496 torrents, 5.5GB memory usage)
**Solution**: Dynamic priority system that gives Plex priority when playing, restores normal priorities when idle

#### **System Components:**
1. **plex_dynamic_priority.service** - Systemd service (`/etc/systemd/system/`)
2. **plex_dynamic_priority.sh** - Main script (`/usr/local/bin/`)
3. **plex_priority_immediate.sh** - Manual boost script (`/tmp/`)
4. **Logs**: `/var/log/plex_priority.log`

#### **How It Works:**
- **Monitors Plex activity**: Checks for active playback sessions every 10 seconds
- **Dynamic priority adjustment**:
  - **When Plex plays**: Priority -5 (high), I/O real-time
  - **When qBittorrent active**: Priority +10 (low), I/O idle  
  - **When idle**: Normal priorities (0)
- **System load consideration**: Also triggers when load > 8 or memory > 85%

#### **Manual Controls:**
```bash
# Service management
sudo systemctl status plex_dynamic_priority.service
sudo systemctl start|stop|restart plex_dynamic_priority.service
sudo journalctl -u plex_dynamic_priority.service -f

# View logs
sudo tail -f /var/log/plex_priority.log

# Manual priority boost
sudo /tmp/plex_priority_immediate.sh
```

#### **Files Created:**
- `/Users/andrebyrro/Dev/home-server/plex_dynamic_priority.sh` - Source script
- `/Users/andrebyrro/Dev/home-server/plex_dynamic_priority.service` - Systemd unit
- `/Users/andrebyrro/Dev/home-server/plex_priority_immediate.sh` - Manual boost
- `/Users/andrebyrro/Dev/home-server/plex_priority_manager.py` - Python API controller (future enhancement)

#### **Results Achieved:**
- **Load average**: Reduced from 111 → 5.62 (1-minute)
- **Swap usage**: From 99% full → 66% (2.7GB free)
- **I/O wait**: From 72% → 2.8%
- **Plex status**: `state=buffering` → `state=playing`

#### **Future Enhancements:**
1. **qBittorrent API integration** - Dynamic speed limiting
2. **More services** - Include Immich, other resource-heavy containers
3. **Web dashboard** - Real-time monitoring and control
4. **Machine learning** - Predictive resource allocation

### Trivy-API Legacy Reports
- **Index**: `http://192.168.1.11:8083/`
- **Watchtower**: Container image update status
- **Trivy**: CVE scan results by container
- **Falco**: Runtime security detections

Update `/home/byrro/scripts/generate_watchtower_summary.py` and rebuild the `trivy-api` image when changing report behavior.

### Security Dashboards (Trivy/Falco)
- **HA REST sensors**: Trivy summary/vulnerabilities and Falco events use `trivy-api` endpoints; Falco should be queried with `?include_suppressed=1` to avoid empty results.
- **trivy-api additions**: `/api/summary` includes `container_summary` with upgrade-fixable counts; `/api/falco` supports `include_suppressed` and returns `suppressed` flags per event.
- **Helpers**: `input_boolean.trivy_upgrade_only` and `input_select.falco_event_filter` are used for dashboard filtering (restart HA after adding).
- **Dashboard YAML exports** (copy/paste): `/Users/andrebyrro/Downloads/trivy-findings-dashboard.yaml`, `/Users/andrebyrro/Downloads/falco-events-dashboard.yaml`, `/Users/andrebyrro/Downloads/notifications_logs_dashboard_security_tabs.yaml`.

### Jose Vacuum Error Logs
- **Purpose**: capture last 10 error messages with timestamps for `vacuum.jose`.
- **Helpers**: `input_text.jose_error_log_1..10` stored in `/mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml`.
- **Automation**: `Jose Vacuum - Log Error Messages` (`id: jose_vacuum_error_log`) in `/mnt/ByrroServer/docker-data/homeassistant/config/automations.yaml`; shifts logs and writes `YYYY-MM-DD HH:MM - message`.
- **Dashboard**: Jose dashboard uses a markdown table card reading those helpers; local export in `/Users/andrebyrro/Downloads/jose_vacuum_dashboard_overview.yaml`.
- **Sensor note**: `sensor.jose_error` can be disabled by integration; if it does not exist in HA, stop HA, set `disabled_by: null` for `sensor.jose_error` in `/mnt/ByrroServer/docker-data/homeassistant/config/.storage/core.entity_registry`, then start HA.

## Paperless Classification

- **Remote location**: Paperless runs on `ssh byrro@192.168.1.11` in Docker; use `docker exec paperless` for inspections.
- **Policy files**: Rules live in `/home/byrro/docker/paperless/document_classification_policy.json` and are enforced by `/home/byrro/docker/paperless/classify_document.py`.
- **Reprocess**: Run `/home/byrro/docker/paperless/reprocess_policy.sh` after any policy change; it uses `/home/byrro/docker/paperless/reprocess_policy_code.py` with `PRESERVE_NON_POLICY_TAGS = False` (wipe non-policy tags on reprocess).
- **Identity requirements**:
  - Identity Document is strictly personal identifiers only: drivers license, passport, SSN card, birth certificate, state ID, voter registration.
  - Only these `id:*` tags should exist: `id:drivers-license`, `id:passport`, `id:ssn-card`, `id:birth-certificate`, `id:state-id`, `id:voter-registration`.
  - Remove unused identity tags (naturalization, etc.) if they appear.
- **Document types added**: `Paystub/Payroll`, `Government/Immigration`, `Education/School`, `Application/Form` (ensure decision order includes them before generic fallbacks).
- **Rule guardrails**:
  - Vehicle Document must not use generic `title` (use `certificate of title`, `title number`, `vehicle title`, etc.).
  - Vehicle Document must not match generic `inspection`; use `vehicle inspection`/`emissions inspection`/`safety inspection` and block home inspections/wind mitigation/mold analysis.
  - Bank Statement should not rely on generic `statement`; allow transaction export phrases.
  - Receipt should not use generic `item` or `change`.
  - Keep property/vehicle/insurance/ID rules from bleeding into each other using forbidden keywords.
- **QA**:
  - Spot check: `/usr/src/paperless/spot_check.py` inside container.
  - Full scan reports: `/usr/src/paperless/full_scan_report.json` and `/usr/src/paperless/full_scan_summary.json` inside container (used for regression assessment).