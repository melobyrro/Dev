import yaml

# Helper to format YAML nicely
class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)

def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)


# Data
services = [
    "Actualbudget", "Adguardhome", "Authelia", "Authelia Redis", "Blackbox Exporter",
    "Caddy", "Cadvisor", "Culto Caddy", "Culto DB", "Culto Redis", "Culto Scheduler",
    "Culto Web", "Culto Worker", "Dawarich App", "Dawarich DB", "Dawarich Redis",
    "Dawarich Sidekiq", "Falco", "Falco HA Bridge", "Falcosidekick", "Flaresolverr",
    "Gluetun", "Home Assistant", "Immich ML", "Immich Postgres", "Immich Redis",
    "Immich Server", "Immich Typesense", "Intel GPU Exporter", "Jellyseerr", "Loki",
    "Node Exporter", "Paperless", "Paperless DB", "Paperless Gotenberg",
    "Paperless Redis", "Paperless Tika", "Plex", "Portainer", "Process Exporter",
    "Prometheus", "Promtail", "Prowlarr", "Pushgateway", "PVE Exporter",
    "QB Port Sync", "QBit Safety Cleaner", "QBittorrent", "Radarr", "SNMP Exporter",
    "Sonarr", "Tautulli", "Telemetrygen", "Tempo", "Tracker Monitor", "Trivy API",
    "Trivy Runner", "Unpackerr", "Uptime Kuma", "Vaultwarden", "Wireguard"
]

def to_snake_case(name):
    mappings = {
        "Home Assistant": "ha_container"
    }
    if name in mappings:
        return mappings[name]
    return name.lower().replace(" ", "_")

# View 1: Overview
overview_cards = [
    {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "custom:mushroom-title-card",
                "title": "System Status",
                "subtitle": "Overview"
            },
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                    {
                        "type": "gauge",
                        "entity": "sensor.proxmox_cpu_usage",
                        "name": "Proxmox CPU",
                        "severity": {"green": 0, "yellow": 60, "red": 80}
                    },
                    {
                        "type": "gauge",
                        "entity": "sensor.vm_cpu_usage",
                        "name": "VM CPU",
                        "severity": {"green": 0, "yellow": 60, "red": 80}
                    },
                    {
                        "type": "gauge",
                        "entity": "sensor.proxmox_memory_usage",
                        "name": "PVE RAM",
                        "severity": {"green": 0, "yellow": 70, "red": 85}
                    },
                    {
                        "type": "gauge",
                        "entity": "sensor.vm_memory_usage",
                        "name": "VM RAM",
                        "severity": {"green": 0, "yellow": 70, "red": 85}
                    }
                ]
            },
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                     {
                        "type": "gauge",
                        "entity": "sensor.vm_root_fs_usage",
                        "name": "VM Root",
                        "severity": {"green": 0, "yellow": 70, "red": 85}
                    },
                    {
                        "type": "gauge",
                        "entity": "sensor.byrroserver_usage",
                        "name": "NAS",
                        "severity": {"green": 0, "yellow": 80, "red": 90}
                    }
                ]
            },
            {
                "type": "entities",
                "entities": [
                    {
                        "entity": "sensor.byrroserver_free_tb",
                        "name": "NAS Free Space",
                        "icon": "mdi:harddisk"
                    }
                ]
            },
            {
                "type": "custom:mini-graph-card",
                "name": "Disk I/O (VM)",
                "hours_to_show": 6,
                "points_per_hour": 12,
                "show": {"labels": True, "points": False, "legend": True},
                "entities": [
                    "sensor.vm_disk_read_mb_s",
                    "sensor.vm_disk_write_mb_s"
                ]
            },
            {
                "type": "entities",
                "title": "Quick Stats",
                "entities": [
                    "sensor.running_containers",
                    "sensor.proxmox_uptime_days",
                    "sensor.vm_uptime_days"
                ]
            }
        ]
    }
]

# View 2: Proxmox
proxmox_cards = [
    {
        "type": "vertical-stack",
        "cards": [
             {
                "type": "custom:mushroom-title-card",
                "title": "Proxmox Host",
                "subtitle": "192.168.1.10"
            },
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                    {
                        "type": "gauge",
                        "entity": "sensor.proxmox_cpu_usage",
                         "severity": {"green": 0, "yellow": 60, "red": 80}
                    },
                    {
                        "type": "gauge",
                        "entity": "sensor.proxmox_memory_usage",
                         "severity": {"green": 0, "yellow": 70, "red": 85}
                    }
                ]
            },
            {
                "type": "entities",
                "entities": [
                    "sensor.proxmox_memory_used_gb",
                    "sensor.proxmox_uptime_days"
                ]
            },
            {
                "type": "custom:mushroom-title-card",
                "title": "VM Summary",
                "subtitle": "qemu/100"
            },
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                     {
                        "type": "gauge",
                        "entity": "sensor.vm_cpu_from_proxmox",
                        "severity": {"green": 0, "yellow": 60, "red": 80}
                    },
                    {
                        "type": "entities",
                         "entities": ["sensor.vm_memory_from_proxmox_gb"]
                    }
                ]
            },
            {
                "type": "markdown",
                "content": "**Legend**\n\nQEMU/100 = Proxmox VM ID for Docker host"
            }
        ]
    }
]

# View 3: Docker VM
docker_vm_cards = [
    {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "custom:mushroom-title-card",
                "title": "VM Resources",
                "subtitle": "192.168.1.11"
            },
            {
                "type": "grid",
                "columns": 3,
                "square": False,
                "cards": [
                    {"type": "gauge", "entity": "sensor.vm_cpu_usage", "severity": {"green": 0, "yellow": 60, "red": 80}},
                    {"type": "gauge", "entity": "sensor.vm_memory_usage", "severity": {"green": 0, "yellow": 70, "red": 85}},
                    {"type": "gauge", "entity": "sensor.vm_root_fs_usage", "severity": {"green": 0, "yellow": 70, "red": 85}}
                ]
            },
            {
                "type": "entities",
                "entities": [
                    "sensor.vm_memory_used_gb",
                    "sensor.vm_memory_total_gb",
                    "sensor.vm_uptime_days"
                ]
            },
            {
                "type": "custom:mini-graph-card",
                "name": "CPU History",
                "hours_to_show": 24,
                "points_per_hour": 4,
                "show": {"labels": True, "legend": True},
                "entities": ["sensor.vm_cpu_usage"]
            },
            {
                "type": "custom:mini-graph-card",
                "name": "Memory History",
                "hours_to_show": 24,
                "points_per_hour": 4,
                "show": {"labels": True, "legend": True},
                "entities": ["sensor.vm_memory_usage"]
            },
             {
                "type": "custom:stack-in-card",
                "title": "Intel GPU",
                "cards": [
                    {
                        "type": "grid",
                        "columns": 2,
                        "square": False,
                        "cards": [
                            {"type": "entity", "entity": "sensor.intel_gpu_render"},
                            {"type": "entity", "entity": "sensor.intel_gpu_video"}
                        ]
                    },
                    {
                        "type": "entities",
                        "entities": [
                            "sensor.intel_gpu_frequency_mhz",
                            "sensor.intel_gpu_power_w"
                        ]
                    }
                ]
            },
            {
                "type": "custom:mini-graph-card",
                "name": "Network I/O",
                "hours_to_show": 6,
                "points_per_hour": 12,
                "show": {"labels": True, "legend": True},
                "entities": [
                    {"entity": "sensor.vm_network_rx_mb_s", "name": "RX"},
                    {"entity": "sensor.vm_network_tx_mb_s", "name": "TX"}
                ]
            }
        ]
    }
]

# View 4: Containers
containers_summary = {
    "type": "markdown",
    "title": "All Containers Summary",
    "content": "\n| Metric | Value |\n| :--- | :--- |\n| **CPU %** | {{ states('sensor.containers_cpu_usage') }}% |\n| **Cores** | {{ states('sensor.containers_cpu_cores') }} |\n| **Memory** | {{ states.sensor | selectattr('entity_id', 'search', '_memory_mb$') | map(attribute='state') | map('float', 0) | sum | round(1) }} MB |\n| **Storage** | {{ states.sensor | selectattr('entity_id', 'search', '_storage_gb$') | map(attribute='state') | map('float', 0) | sum | round(1) }} GB |\n| **I/O** | {{ states.sensor | selectattr('entity_id', 'search', '_storage_io_mb_s$') | map(attribute='state') | map('float', 0) | sum | round(1) }} MB/s |\n"
}

container_cards = [containers_summary]

for service in services:
    s_id = to_snake_case(service)
    
    # Base cards
    cards = [
        {
            "type": "grid",
            "columns": 2,
            "square": False,
            "cards": [
                {"type": "custom:mushroom-entity-card", "entity": f"sensor.{s_id}_cpu", "name": "CPU"},
                {"type": "custom:mushroom-entity-card", "entity": f"sensor.{s_id}_memory_mb", "name": "Mem"}
            ]
        },
        {
            "type": "grid",
            "columns": 2,
            "square": False,
            "cards": [
                {"type": "custom:mushroom-entity-card", "entity": f"sensor.{s_id}_storage_gb", "name": "Stor"},
                {"type": "custom:mushroom-entity-card", "entity": f"sensor.{s_id}_storage_io_mb_s", "name": "I/O"}
            ]
        }
    ]
    
    # Plex specific
    if service == "Plex":
        cards.insert(0, {
             "type": "grid",
            "columns": 2,
            "square": False,
            "cards": [
                {"type": "custom:mushroom-entity-card", "entity": "sensor.intel_gpu_render", "name": "iGPU Render"},
                {"type": "custom:mushroom-entity-card", "entity": "sensor.intel_gpu_video", "name": "iGPU Video"}
            ]
        })

    container_cards.append({
        "type": "custom:stack-in-card",
        "title": service,
        "cards": cards
    })

dashboard = {
    "title": "Homelab",
    "views": [
        {"title": "Overview", "path": "overview", "cards": overview_cards},
        {"title": "Proxmox", "path": "proxmox", "cards": proxmox_cards},
        {"title": "Docker VM", "path": "vm", "cards": docker_vm_cards},
        {"title": "Containers", "path": "containers", "cards": container_cards}
    ]
}

if __name__ == "__main__":
    print(yaml.dump(dashboard, Dumper=MyDumper, default_flow_style=False, sort_keys=False))
