# Network Monitoring Plan: GL.iNet Flint 2 + Home Assistant

## Executive Summary

This plan establishes comprehensive network visibility for your GL.iNet Flint 2 router through Home Assistant, leveraging your existing monitoring infrastructure (Prometheus, HA Homelab dashboard, MQTT).

**Goals:**
- Real-time visibility into all connected devices
- DNS query monitoring and blocking statistics
- Router health metrics (CPU, memory, VPN status)
- Service uptime monitoring
- New device alerts and intrusion detection
- Unified dashboard for easy consumption

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GL.iNet Flint 2 Router                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  AdGuard Home   │  │   GL.iNet API   │  │  SNMP (optional)│         │
│  │   (built-in)    │  │   (port 80)     │  │                 │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
└───────────┼─────────────────────┼─────────────────────┼─────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                        Docker VM (192.168.1.11)                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │    NetAlertX    │  │  Home Assistant │  │   Prometheus    │           │
│  │  (new container)│  │  (existing)     │  │   (existing)    │           │
│  │                 │  │                 │  │                 │           │
│  │  • ARP scan     │  │  • AdGuard Int. │  │  • SNMP Exporter│           │
│  │  • NMAP scan    │  │  • GL.iNet HACS │  │    (optional)   │           │
│  │  • Device track │  │  • Uptime Kuma  │  │                 │           │
│  └────────┬────────┘  │  • NetAlertX    │  └────────┬────────┘           │
│           │           │    (via MQTT)   │           │                    │
│           │           └────────┬────────┘           │                    │
│           │                    │                    │                    │
│           └────────────────────┼────────────────────┘                    │
│                    ┌───────────┴───────────┐                             │
│                    │    Mosquitto MQTT     │                             │
│                    │     (existing)        │                             │
│                    └───────────────────────┘                             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Component Comparison: What Each Tool Provides

| Capability | AdGuard Home | GL.iNet HACS | NetAlertX | Uptime Kuma |
|------------|--------------|--------------|-----------|-------------|
| DNS queries/blocks | ✅ Excellent | ❌ | ❌ | ❌ |
| Per-device DNS stats | ✅ Yes | ❌ | ❌ | ❌ |
| Router CPU/Memory | ❌ | ✅ Yes | ❌ | ❌ |
| VPN status/control | ❌ | ✅ Yes | ❌ | ❌ |
| Connected clients count | ❌ | ✅ Yes | ✅ Yes | ❌ |
| Device discovery | ❌ | ❌ | ✅ Excellent | ❌ |
| New device alerts | ❌ | ❌ | ✅ Excellent | ❌ |
| Device presence | ❌ | Partial | ✅ Excellent | ❌ |
| Service uptime | ❌ | ❌ | ❌ | ✅ Excellent |
| Historical data | Limited | ❌ | ✅ Yes | ✅ Yes |

**Recommendation:** Use all four for complete coverage. They're complementary, not redundant.

---

## Phase 1: AdGuard Home Integration (Easiest Win)

### What You Get
- Total DNS queries sensor
- Blocked queries count and percentage
- Safe browsing/parental control stats
- Average DNS response time
- Filter rules count
- Master on/off switch for protection

### Implementation Steps

#### 1.1 Find AdGuard Home Credentials
```bash
# SSH to Flint 2 or check router admin panel
# AdGuard Home typically runs on port 3000
# Default path: http://192.168.8.1:3000 (adjust to your router IP)
```

#### 1.2 Add Integration to Home Assistant
1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "AdGuard Home"
3. Enter:
   - Host: `192.168.8.1` (your Flint 2 IP)
   - Port: `3000`
   - Username/Password (from AdGuard Home setup)

#### 1.3 Available Entities
| Entity | Type | Description |
|--------|------|-------------|
| `sensor.adguard_dns_queries` | Sensor | Total queries today |
| `sensor.adguard_dns_queries_blocked` | Sensor | Blocked queries today |
| `sensor.adguard_dns_queries_blocked_ratio` | Sensor | Block percentage |
| `sensor.adguard_average_processing_speed` | Sensor | DNS response time (ms) |
| `sensor.adguard_rules_count` | Sensor | Active filter rules |
| `switch.adguard_protection` | Switch | Master on/off |
| `switch.adguard_filtering` | Switch | DNS filtering toggle |
| `switch.adguard_parental` | Switch | Parental controls |
| `switch.adguard_safe_search` | Switch | Safe search enforcement |

#### 1.4 Estimated Effort
- **Time:** 15 minutes
- **Difficulty:** Easy
- **Dependencies:** None

---

## Phase 2: GL.iNet Router Integration (HACS)

### What You Get
- Router health metrics (CPU, memory, temperature)
- Connected client counts (WiFi + Wired)
- VPN status and control (WireGuard/OpenVPN)
- WAN status monitoring
- Firewall/port forward info
- System uptime

### Implementation Steps

#### 2.1 Install via HACS
1. Open HACS in Home Assistant
2. Go to **Integrations → ⋮ → Custom Repositories**
3. Add: `https://github.com/angolo40/GLiNet_HomeAssistant`
4. Category: Integration
5. Click **Add**, then search "GLiNet" and install
6. Restart Home Assistant

#### 2.2 Configure Integration
1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "GLiNet"
3. Enter:
   - Host: `192.168.8.1` (your Flint 2 IP)
   - Username: `root`
   - Password: (your router admin password)

#### 2.3 Available Entities (Comprehensive List)

**System Sensors:**
| Entity | Description |
|--------|-------------|
| `sensor.glinet_system_uptime` | Router uptime in seconds |
| `sensor.glinet_cpu_load_1min` | CPU load (1 min average) |
| `sensor.glinet_cpu_load_5min` | CPU load (5 min average) |
| `sensor.glinet_cpu_temperature` | CPU temp in °C |
| `sensor.glinet_memory_usage` | Memory usage % |
| `sensor.glinet_memory_free` | Free RAM (MB) |
| `sensor.glinet_flash_usage` | Storage usage % |

**Network Sensors:**
| Entity | Description |
|--------|-------------|
| `sensor.glinet_wifi_clients` | Wireless device count |
| `sensor.glinet_wired_clients` | Ethernet device count |
| `sensor.glinet_total_clients` | Total connected devices |
| `sensor.glinet_wan_status` | Internet connection state |
| `sensor.glinet_system_mode` | Router/AP/Mesh mode |

**VPN Sensors:**
| Entity | Description |
|--------|-------------|
| `sensor.glinet_vpn_status` | VPN connection state |
| `sensor.glinet_wireguard_server_status` | WG server state |
| `sensor.glinet_wireguard_peers` | Connected WG peers |
| `sensor.glinet_openvpn_server_status` | OpenVPN state |

**Switches & Buttons:**
| Entity | Description |
|--------|-------------|
| `switch.glinet_wireguard_client` | Toggle WireGuard |
| `switch.glinet_openvpn_client` | Toggle OpenVPN |
| `button.glinet_reboot` | Reboot router |

#### 2.4 Known Limitations
- GL.iNet API is undocumented; may break with firmware updates
- Tested on GL-MT300N-V2; Flint 2 should work but verify
- No per-device bandwidth data

#### 2.5 Estimated Effort
- **Time:** 30 minutes
- **Difficulty:** Easy-Medium
- **Dependencies:** HACS installed

---

## Phase 3: NetAlertX Deployment (Device Discovery)

### What You Get
- Automatic device discovery via ARP/NMAP
- New device alerts (intrusion detection)
- Device presence tracking (online/offline)
- Device history and first-seen dates
- MAC vendor identification
- All devices as HA entities via MQTT

### Implementation Steps

#### 3.1 Create Docker Compose Configuration

Add to `/home/byrro/docker/monitoring/docker-compose.yml`:

```yaml
  netalertx:
    image: jokobsk/netalertx:latest
    container_name: netalertx
    network_mode: host  # REQUIRED for ARP scanning
    restart: unless-stopped
    volumes:
      - /home/byrro/docker/monitoring/netalertx/config:/app/config
      - /home/byrro/docker/monitoring/netalertx/db:/app/db
    environment:
      - TZ=America/New_York
      - PORT=20211
    cap_add:
      - NET_ADMIN
      - NET_RAW
```

#### 3.2 Create Directories
```bash
ssh byrro@192.168.1.11
mkdir -p /home/byrro/docker/monitoring/netalertx/{config,db}
```

#### 3.3 Deploy and Configure
```bash
cd /home/byrro/docker/monitoring
docker compose up -d netalertx
```

#### 3.4 Initial Configuration (Web UI)
1. Access NetAlertX at `http://192.168.1.11:20211`
2. Go to **Settings → General**:
   - Set your network: `192.168.1.0/24`
   - Set interface: `eth0` (verify with `ip a`)
3. Go to **Settings → Scan**:
   - Enable: `ARPSCAN` (primary)
   - Enable: `NMAPDEV` (supplementary)
   - Schedule: Every 5 minutes

#### 3.5 Configure MQTT for Home Assistant
1. In NetAlertX **Settings → Core → Loaded Plugins**, add `MQTT`
2. Go to **Settings → Publishers → MQTT**:
   ```
   MQTT_BROKER: 192.168.1.11
   MQTT_PORT: 1883
   MQTT_USER: (your mosquitto user)
   MQTT_PASSWORD: (your mosquitto password)
   MQTT_RUN: schedule
   ```
3. Save and restart NetAlertX

#### 3.6 Home Assistant MQTT Discovery
Devices will auto-appear in HA under **Settings → Devices & Services → MQTT**.

Each device gets:
- `binary_sensor.netalertx_<mac>` - Online/offline status
- `sensor.netalertx_<mac>_ip` - Current IP
- `sensor.netalertx_<mac>_name` - Device name
- Device attributes: MAC, vendor, first seen, last seen

#### 3.7 Create Alert Automation
```yaml
automation:
  - alias: "Network: New Device Alert"
    trigger:
      - platform: state
        entity_id: sensor.netalertx_new_devices
    condition:
      - condition: numeric_state
        entity_id: sensor.netalertx_new_devices
        above: 0
    action:
      - service: notify.mobile_app_andre_iphone
        data:
          title: "🚨 New Device on Network"
          message: "A new device was detected on your network. Check NetAlertX for details."
          data:
            url: "http://192.168.1.11:20211"
```

#### 3.8 Estimated Effort
- **Time:** 45-60 minutes
- **Difficulty:** Medium
- **Dependencies:** MQTT broker (Mosquitto)

---

## Phase 4: Uptime Kuma Integration (Service Monitoring)

### What You Get
- Monitor router admin panel availability
- Monitor AdGuard Home availability
- Monitor critical services (HA, Prometheus, Immich)
- Response time tracking
- Downtime alerts

### Implementation Steps

#### 4.1 Check if Uptime Kuma Exists
```bash
ssh byrro@192.168.1.11
docker ps | grep -i uptime
```

If not running, add to docker-compose:
```yaml
  uptime-kuma:
    image: louislam/uptime-kuma:1
    container_name: uptime-kuma
    restart: unless-stopped
    ports:
      - "3001:3001"
    volumes:
      - /home/byrro/docker/monitoring/uptime-kuma:/app/data
```

#### 4.2 Configure Monitors
Access Uptime Kuma at `http://192.168.1.11:3001` and add:

| Monitor | Type | Target | Interval |
|---------|------|--------|----------|
| Flint 2 Admin | HTTP | `http://192.168.8.1` | 60s |
| AdGuard Home | HTTP | `http://192.168.8.1:3000` | 60s |
| Home Assistant | HTTP | `http://192.168.1.11:8123` | 60s |
| Prometheus | HTTP | `http://192.168.1.11:9090` | 60s |
| Immich | HTTP | `http://192.168.1.11:2283` | 60s |
| DNS Resolution | DNS | `1.1.1.1` lookup `google.com` | 60s |

#### 4.3 Add HA Integration (Core)
1. Go to **Settings → Devices & Services → Add Integration**
2. Search "Uptime Kuma"
3. Enter:
   - URL: `http://192.168.1.11:3001`
   - API Key: (create in Uptime Kuma → Settings → API Keys)

#### 4.4 Available Entities
Each monitor creates:
- `binary_sensor.uptime_kuma_<monitor>` - Up/Down state
- `sensor.uptime_kuma_<monitor>_response_time` - Response time (ms)
- `sensor.uptime_kuma_<monitor>_cert_expiry` - SSL cert days remaining

#### 4.5 Estimated Effort
- **Time:** 30 minutes
- **Difficulty:** Easy
- **Dependencies:** None

---

## Phase 5: Home Assistant Dashboard

### Dashboard Structure

```
📊 Network Dashboard
├── 🏠 Overview (Top Row)
│   ├── Internet Status (WAN)
│   ├── Total Devices Online
│   ├── DNS Queries Today
│   └── Blocked Queries %
│
├── 🖥️ Router Health (Second Row)
│   ├── CPU Load Gauge
│   ├── Memory Usage Gauge
│   ├── CPU Temperature
│   └── Router Uptime
│
├── 🔒 Security & DNS (Third Row)
│   ├── AdGuard Stats Card
│   │   ├── Queries graph
│   │   ├── Blocked graph
│   │   └── Top blocked domains
│   └── New Devices Alert Card
│
├── 📡 Connected Devices (Fourth Row)
│   ├── WiFi Clients
│   ├── Wired Clients
│   └── Device List (from NetAlertX)
│
├── 🌐 VPN Status (Fifth Row)
│   ├── WireGuard Status
│   ├── WireGuard Toggle
│   └── Connected Peers
│
└── ⚡ Service Status (Bottom Row)
    ├── Uptime Kuma Status Grid
    └── Response Time Graph
```

### 5.1 Required Custom Cards (via HACS)
Install these from HACS → Frontend:
- **Mushroom Cards** - Modern, clean cards
- **Mini Graph Card** - Sparkline graphs
- **Auto Entities** - Dynamic device lists
- **Decluttering Card** - Reusable templates

### 5.2 Dashboard YAML

Create `/config/.storage/lovelace.network` or add via UI:

```yaml
title: Network
views:
  - title: Overview
    path: network
    type: sections
    sections:
      # === TOP ROW: Quick Stats ===
      - type: grid
        cards:
          - type: custom:mushroom-entity-card
            entity: sensor.glinet_wan_status
            name: Internet
            icon: mdi:web
            icon_color: green

          - type: custom:mushroom-entity-card
            entity: sensor.glinet_total_clients
            name: Devices Online
            icon: mdi:devices
            icon_color: blue

          - type: custom:mushroom-entity-card
            entity: sensor.adguard_dns_queries
            name: DNS Queries
            icon: mdi:dns
            icon_color: cyan

          - type: custom:mushroom-entity-card
            entity: sensor.adguard_dns_queries_blocked_ratio
            name: Blocked
            icon: mdi:shield-check
            icon_color: red

      # === ROUTER HEALTH ===
      - type: grid
        title: Router Health
        cards:
          - type: gauge
            entity: sensor.glinet_cpu_load_1min
            name: CPU Load
            min: 0
            max: 100
            severity:
              green: 0
              yellow: 50
              red: 80

          - type: gauge
            entity: sensor.glinet_memory_usage
            name: Memory
            min: 0
            max: 100
            severity:
              green: 0
              yellow: 70
              red: 90

          - type: custom:mushroom-entity-card
            entity: sensor.glinet_cpu_temperature
            name: CPU Temp
            icon: mdi:thermometer

          - type: custom:mushroom-entity-card
            entity: sensor.glinet_system_uptime
            name: Uptime
            icon: mdi:clock-outline

      # === DNS & SECURITY ===
      - type: grid
        title: DNS & Security
        cards:
          - type: custom:mini-graph-card
            entities:
              - entity: sensor.adguard_dns_queries
                name: Queries
              - entity: sensor.adguard_dns_queries_blocked
                name: Blocked
            hours_to_show: 24
            points_per_hour: 4
            line_width: 2
            show:
              legend: true

          - type: custom:mushroom-entity-card
            entity: sensor.netalertx_new_devices
            name: New Devices
            icon: mdi:alert-circle
            icon_color: "{{ 'red' if states('sensor.netalertx_new_devices') | int > 0 else 'green' }}"

      # === VPN STATUS ===
      - type: grid
        title: VPN
        cards:
          - type: custom:mushroom-entity-card
            entity: sensor.glinet_vpn_status
            name: VPN Status
            icon: mdi:vpn

          - type: custom:mushroom-entity-card
            entity: switch.glinet_wireguard_client
            name: WireGuard
            tap_action:
              action: toggle

          - type: custom:mushroom-entity-card
            entity: sensor.glinet_wireguard_peers
            name: WG Peers
            icon: mdi:account-multiple

      # === CONNECTED DEVICES ===
      - type: grid
        title: Connected Devices
        cards:
          - type: custom:mushroom-entity-card
            entity: sensor.glinet_wifi_clients
            name: WiFi
            icon: mdi:wifi
            icon_color: blue

          - type: custom:mushroom-entity-card
            entity: sensor.glinet_wired_clients
            name: Wired
            icon: mdi:ethernet
            icon_color: orange

          - type: custom:auto-entities
            card:
              type: entities
              title: Network Devices
            filter:
              include:
                - integration: mqtt
                  domain: binary_sensor
                  state: "on"
            sort:
              method: name

      # === SERVICE STATUS ===
      - type: grid
        title: Services
        cards:
          - type: custom:auto-entities
            card:
              type: glance
              title: Service Status
            filter:
              include:
                - integration: uptime_kuma
                  domain: binary_sensor
```

### 5.3 Estimated Effort
- **Time:** 60-90 minutes
- **Difficulty:** Medium
- **Dependencies:** All previous phases

---

## Phase 6 (Optional): SNMP Monitoring via Prometheus

### What You Get
- Deeper router metrics via SNMP
- Interface-level bandwidth statistics
- Integration with existing Prometheus stack
- Long-term metric retention

### Implementation Steps

#### 6.1 Enable SNMP on Flint 2
```bash
# SSH to router
ssh root@192.168.8.1

# Install SNMP daemon
opkg update
opkg install snmpd

# Configure /etc/config/snmpd
# Set community string, allowed hosts
```

#### 6.2 Add SNMP Exporter to Prometheus Stack
Add to docker-compose:
```yaml
  snmp-exporter:
    image: prom/snmp-exporter
    container_name: snmp-exporter
    restart: unless-stopped
    ports:
      - "9116:9116"
    volumes:
      - /home/byrro/docker/monitoring/snmp-exporter:/etc/snmp_exporter
```

#### 6.3 Configure Prometheus Scrape
Add to `prometheus.yml`:
```yaml
  - job_name: 'snmp-router'
    static_configs:
      - targets: ['192.168.8.1']
    metrics_path: /snmp
    params:
      module: [if_mib]
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: snmp-exporter:9116
```

#### 6.4 Estimated Effort
- **Time:** 2-3 hours
- **Difficulty:** Advanced
- **Dependencies:** Prometheus, OpenWrt knowledge

---

## Implementation Order & Timeline

| Phase | Component | Priority | Effort | Dependencies |
|-------|-----------|----------|--------|--------------|
| 1 | AdGuard Home | High | 15 min | None |
| 2 | GL.iNet HACS | High | 30 min | HACS |
| 3 | NetAlertX | High | 60 min | MQTT |
| 4 | Uptime Kuma | Medium | 30 min | None |
| 5 | Dashboard | Medium | 90 min | Phases 1-4 |
| 6 | SNMP (optional) | Low | 2-3 hrs | Prometheus |

**Recommended Order:** 1 → 2 → 3 → 4 → 5 → 6

---

## Quick Reference: All New Entities

### AdGuard Home
- `sensor.adguard_dns_queries`
- `sensor.adguard_dns_queries_blocked`
- `sensor.adguard_dns_queries_blocked_ratio`
- `sensor.adguard_average_processing_speed`
- `switch.adguard_protection`
- `switch.adguard_filtering`

### GL.iNet Router
- `sensor.glinet_cpu_load_*`
- `sensor.glinet_memory_usage`
- `sensor.glinet_cpu_temperature`
- `sensor.glinet_wifi_clients`
- `sensor.glinet_wired_clients`
- `sensor.glinet_total_clients`
- `sensor.glinet_wan_status`
- `sensor.glinet_vpn_status`
- `switch.glinet_wireguard_client`

### NetAlertX (via MQTT)
- `binary_sensor.netalertx_<device>` (per device)
- `sensor.netalertx_online_devices`
- `sensor.netalertx_new_devices`

### Uptime Kuma
- `binary_sensor.uptime_kuma_<monitor>`
- `sensor.uptime_kuma_<monitor>_response_time`

---

## Maintenance & Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| GL.iNet integration fails after firmware update | Check GitHub issues, may need to wait for update |
| NetAlertX not finding devices | Verify `network_mode: host` and correct interface |
| MQTT devices not appearing in HA | Check Mosquitto logs, verify credentials |
| AdGuard sensors show "unavailable" | Enable Query Log in AdGuard settings |

### Health Check Commands
```bash
# Check NetAlertX logs
docker logs netalertx --tail 50

# Test MQTT connection
mosquitto_sub -h 192.168.1.11 -u USER -P PASS -t "netalertx/#" -v

# Verify AdGuard API
curl http://192.168.8.1:3000/control/status

# Check GL.iNet API (basic)
curl http://192.168.8.1/cgi-bin/api/router/status
```

---

## Sources

- [AdGuard Home HA Integration](https://www.home-assistant.io/integrations/adguard/)
- [GLiNet_HomeAssistant GitHub](https://github.com/angolo40/GLiNet_HomeAssistant)
- [NetAlertX Documentation](https://docs.netalertx.com/)
- [NetAlertX Home Assistant Guide](https://docs.netalertx.com/HOME_ASSISTANT/)
- [Uptime Kuma HA Integration](https://www.home-assistant.io/integrations/uptime_kuma/)
- [GL.iNet Forum - Flint 2 Monitoring](https://forum.gl-inet.com/t/what-are-some-good-apps-to-put-on-the-flint-2-for-network-monitoring-besides-the-goodcloud/49482)
- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom)
