# Home Server Architecture

## Overview

This document describes the networking and VPN architecture for the home server infrastructure running on Docker VM (192.168.1.11).

---

## VPN & Torrenting Stack

### Architecture Diagram

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Gluetun Container                                  │
│  ┌─────────────────────────────────────────────┐   │
│  │  PIA VPN Tunnel (OpenVPN)                   │   │
│  │  - Regions: Mexico, Panama                  │   │
│  │  - Port Forwarding: ON                      │   │
│  │  - Forwarded Port: /tmp/gluetun/forwarded_port │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Shared Network Namespace:                         │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ qBittorrent  │  │ qb-port-sync │               │
│  │ :8181        │  │ (curl loop)  │               │
│  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────┘
```

### Components

| Container | Purpose | Network Mode |
|-----------|---------|--------------|
| `gluetun` | VPN client (PIA) with port forwarding | bridge (byrro-net) |
| `qbittorrent` | Torrent client | `service:gluetun` (shared) |
| `qb-port-sync` | Syncs forwarded port to qBittorrent | `service:gluetun` (shared) |

### Gluetun Configuration

**Location:** `/home/byrro/docker/docker-compose.yml`

```yaml
environment:
  - VPN_SERVICE_PROVIDER=private internet access
  - VPN_TYPE=openvpn
  - SERVER_REGIONS=Mexico,Panama
  - VPN_PORT_FORWARDING=on
```

**Key Settings:**
- `SERVER_REGIONS=Mexico,Panama` - Only regions that support PIA port forwarding and are geographically close to Florida
- `VPN_PORT_FORWARDING=on` - Required for torrent seeding

### PIA Port Forwarding

**Important:** Not all PIA servers support port forwarding. Only "Next Generation" servers in specific regions support it.

**Supported Regions (partial list):**
- Americas: Mexico, Panama, Venezuela, Bahamas, Greenland
- Europe: Netherlands, Germany, Switzerland, France, Italy, Spain, UK, Sweden, etc.
- Asia: Japan, Singapore, Taiwan, etc.

**NOT Supported:**
- United States (all locations)
- Canada (all locations)

**Source:** [PIA NextGen Port Forward Servers](https://github.com/fm407/PIA-NextGen-PortForwarding/blob/master/nextgen-portforward-servers.txt)

### qb-port-sync

Automatically syncs the VPN forwarded port to qBittorrent's listen port.

**How it works:**
1. Waits for `/gluetun/forwarded_port` to have content
2. Logs into qBittorrent API
3. Compares current `listen_port` with forwarded port
4. Updates if different and triggers reannounce
5. Loops every 60 seconds

**Healthcheck:** Container is healthy when port file exists and has content.

---

## WireGuard Remote Access

### Architecture Diagram

```
┌─────────────────┐     ┌─────────────────┐
│  iPhone         │     │  MacBook Air    │
│  10.13.13.2     │     │  10.13.13.4     │
│  On-Demand: ON  │     │  On-Demand: ON  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │ (external networks)   │
         │                       │
         ▼                       ▼
    ┌─────────────────────────────────┐
    │  wg.byrroserver.com:51820       │
    │  (Dynamic DNS → Home IP)        │
    └─────────────────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────┐
    │  WireGuard Container            │
    │  192.168.1.11:51820             │
    │  Internal: 10.13.13.1           │
    │  DNS: 172.18.0.14 (AdGuard)     │
    └─────────────────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────┐
    │  Home Network (192.168.1.0/24)  │
    │  + AdGuard DNS (ad blocking)    │
    │  + All local services           │
    └─────────────────────────────────┘
```

### Configuration

**Location:** `/home/byrro/docker/wireguard/docker-compose.yml`

```yaml
environment:
  - SERVERURL=wg.byrroserver.com
  - SERVERPORT=51820
  - PEERS=iphone,iphonedamaris,macbookair
  - PEERDNS=172.18.0.14  # AdGuard Home
  - INTERNAL_SUBNET=10.13.13.0/24
  - ALLOWEDIPS=0.0.0.0/0
```

### Peers

| Peer | IP | Purpose |
|------|-----|---------|
| iphone | 10.13.13.2 | Primary phone |
| iphonedamaris | 10.13.13.3 | Secondary phone |
| macbookair | 10.13.13.4 | Laptop |

### Client On-Demand Configuration

**Important:** Configure WireGuard clients to NOT connect when on home WiFi.

**macOS/iOS Settings:**
- Ethernet: Off
- Wi-Fi: On, **except SSIDs:** `[Your Home SSID]`
- Cellular: On

**Why:** Connecting to WireGuard from inside the home LAN causes routing issues (hairpin NAT). WireGuard is only needed when on external networks.

### Peer Config Location

Server-generated configs: `/mnt/ByrroServer/docker-data/wireguard/config/peer_*/`

---

## Troubleshooting

### Gluetun Unhealthy / Port Forwarding Failed

**Symptoms:**
- `docker ps` shows gluetun as `unhealthy`
- `/tmp/gluetun/forwarded_port` is empty
- qb-port-sync has nothing to sync

**Common Causes:**
1. Connected to a region that doesn't support port forwarding (e.g., US, Canada)
2. PIA port forwarding server timeout

**Fix:**
```bash
cd /home/byrro/docker
docker compose restart gluetun
# Wait 30 seconds, then verify:
docker exec gluetun cat /tmp/gluetun/forwarded_port
```

### WireGuard Connected but No Internet

**Symptoms:**
- Handshake succeeds (shown in `wg show`)
- No internet access on client

**Check peer endpoint:**
```bash
docker exec wireguard wg show
```

If endpoint shows `192.168.1.x` (local router IP), the client is connecting from inside the home LAN. This is unnecessary and can cause routing issues.

**Fix:** Enable on-demand with home SSID exception on the client.

### Verify All Services

```bash
# Container status
docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep -E 'gluetun|wireguard|qbittorrent|qb-port-sync'

# Gluetun port forwarding
docker exec gluetun cat /tmp/gluetun/forwarded_port

# qBittorrent listen port (should match above)
docker exec qb-port-sync sh -c 'curl -s -c /tmp/c -d "username=admin&password=PASSWORD" http://127.0.0.1:8181/api/v2/auth/login >/dev/null && curl -s -b /tmp/c http://127.0.0.1:8181/api/v2/app/preferences | grep -o "listen_port\":[0-9]*"'

# WireGuard peers
docker exec wireguard wg show
```

---

## References

- [Gluetun Wiki](https://github.com/qdm12/gluetun-wiki)
- [PIA Port Forwarding Servers](https://github.com/fm407/PIA-NextGen-PortForwarding)
- [LinuxServer WireGuard](https://docs.linuxserver.io/images/docker-wireguard)

---

*Last updated: 2026-01-22*
