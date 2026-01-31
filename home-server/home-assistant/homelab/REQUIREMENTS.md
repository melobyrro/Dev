# Homelab Dashboard - Functional Requirements

## Dashboard Information
- **Dashboard ID**: ``homelab``
- **Title**: Homelab
- **URL Path**: ``/homelab``
- **Source of Truth**: ``homelab/lovelace.homelab.yaml``
- **Last Updated**: 2026-01-23

## 1. Dashboard Design (Actual)

The dashboard provides a dense, "Control Room" style view of the infrastructure.

### 1.1 Overview View
- **System Status**: Gauges for Proxmox/VM CPU and RAM.
- **Storage**: Gauges for Root FS and NAS usage + "Free TB" entity.
- **Disk I/O**: `mini-graph-card` showing 6h read/write history.
- **Quick Stats**: Running Containers count, Uptime days.

### 1.2 Proxmox & VM Views
- **Proxmox**: Dedicated view for Host stats (192.168.1.10).
- **Docker VM**: Dedicated view for VM stats (192.168.1.11).
  - Includes **Intel GPU** stack (Render/Video load, Frequency, Power).
  - **Network I/O**: RX/TX history graph.

### 1.3 Containers View (The "Data Dump")
- **Summary Header**: Markdown table summing CPU%, Cores, Memory (MB), Storage (GB), and I/O (MB/s) across all containers.
- **Per-Container Cards**:
  - Uses `custom:stack-in-card` combining `mushroom-entity-card`s.
  - **Metrics**: CPU, Memory, Storage, I/O for ~50 containers.
  - **List**: Actualbudget, Adguard, Authelia, Caddy, Immich (all services), Paperless, Plex, etc.

## 2. Automation & Logic Requirements

- **Aggregation**: The "All Containers Summary" relies on Jinja2 templates to sum state values from groups of sensors (e.g., matching `_memory_mb$`).
- **Entity Naming**: Relies on strict naming convention `sensor.<container_name>_<metric>`.

## 3. Configuration Management

| File | Purpose | Location |
|------|---------|----------|
| `lovelace.homelab.yaml` | Dashboard Layout | `homelab/` |
| `ha-config/configuration.yaml` | Prometheus/Sensor Config | `ha-config/` |

## 4. Future Enhancements (Gap Analysis)

- **Exception-Based Monitoring**: The "Containers" view is overwhelming. It needs a "Problem Child" card (using `auto-entities`) that *only* lists containers with high CPU/Error states, hiding healthy ones.
- **Health Traffic Light**: A top-level status indicator (Green/Yellow/Red) summarizing the entire lab's health.
- **Backup Monitor**: Add visibility for backup age/status.