# Notifications Dashboard - Functional Requirements

## Dashboard Information
- **Dashboard ID**: ``notifications_logs``
- **Title**: Notifications
- **URL Path**: ``/notifications-logs``
- **Configuration Location**: ``/mnt/ByrroServer/docker-data/homeassistant/config/.storage/lovelace.notifications_logs``
- **Last Updated**: 2026-01-12

## Functional Requirements

### 1. Dashboard Display Requirements
- The dashboard shall display 14 entities across 10 different entity types
- The dashboard shall organize entities by functional area based on the dashboard structure
- The dashboard shall provide clear visualization and control interfaces for all entities

### 2. Entity Management Requirements
- **Automation Management**: Users shall be able to monitor and interact with 1 automation entities
- **Climate Management**: Users shall be able to monitor and interact with 1 climate entities
- **Fan Management**: Users shall be able to monitor and interact with 1 fan entities
- **Input Boolean Management**: Users shall be able to monitor and interact with 1 input_boolean entities
- **Input Select Management**: Users shall be able to monitor and interact with 1 input_select entities
- **Input Text Management**: Users shall be able to monitor and interact with 2 input_text entities
- **Light Management**: Users shall be able to monitor and interact with 4 light entities
- **Lock Management**: Users shall be able to monitor and interact with 1 lock entities
- **Switch Management**: Users shall be able to monitor and interact with 1 switch entities
- **Vacuum Management**: Users shall be able to monitor and interact with 1 vacuum entities

### 3. User Interaction Requirements
- Users shall be able to view current state of all displayed entities
- Users shall be able to interact with controllable entities (where applicable)
- Users shall be able to access historical data for relevant entities
- The dashboard shall provide intuitive navigation between different views/sections

## Complete Entity Inventory with Source Tracing

### Summary
| Entity Type | Count | Source Type |
|-------------|-------|-------------|
| Automation | 1 | Mixed |
| Climate | 1 | Integration |
| Fan | 1 | Integration |
| Input Boolean | 1 | YAML configuration |
| Input Select | 1 | YAML configuration |
| Input Text | 2 | YAML configuration |
| Light | 4 | Integration |
| Lock | 1 | Integration |
| Switch | 1 | Integration |
| Vacuum | 1 | Integration |
| **Total** | **14** | |

### Entity Details with Source References

#### Automation Entities (1)
- `automation.uptime_kuma_alert_handler`
  - **Source**: Unknown source

#### Climate Entities (1)
- `climate.150633095083490_climate`
  - **Source**: Device/integration
  - **Type**: device

#### Fan Entities (1)
- `fan.living_room_light`
  - **Source**: Device/integration
  - **Type**: device

#### Input Boolean Entities (1)
- `input_boolean.trivy_upgrade_only`
  - **Source**: configuration.yaml:203
  - **Type**: input

#### Input Select Entities (1)
- `input_select.falco_event_filter`
  - **Source**: configuration.yaml:121
  - **Type**: input

#### Input Text Entities (2)
- `input_text.last_tracker_signup`
  - **Source**: configuration.yaml:222
  - **Type**: input

- `input_text.last_uptime_alert`
  - **Source**: configuration.yaml:228
  - **Type**: input

#### Light Entities (4)
- `light.living_room_light_2`
  - **Source**: Device/integration
  - **Type**: device

- `light.master_fan`
  - **Source**: Device/integration
  - **Type**: device

- `light.master_light`
  - **Source**: Device/integration
  - **Type**: device

- `light.office_light`
  - **Source**: Device/integration
  - **Type**: device

#### Lock Entities (1)
- `lock.front_door`
  - **Source**: Device/integration
  - **Type**: device

#### Switch Entities (1)
- `switch.cinema_light`
  - **Source**: Device/integration
  - **Type**: device

#### Vacuum Entities (1)
- `vacuum.jose`
  - **Source**: Device/integration
  - **Type**: device

## Configuration Management

### Primary Configuration Files
1. **Dashboard Configuration**: ``/mnt/ByrroServer/docker-data/homeassistant/config/.storage/lovelace.notifications_logs``
2. **Entity Definitions**: Various YAML files and integrations as referenced above

### Maintenance Notes
- Changes to entity definitions should be made in the source files referenced above
- Dashboard layout changes should be made in the lovelace configuration
- Integration-based entities are managed by their respective integrations
- Regular validation of entity sources is recommended when making changes

## Dependencies and Integration Points

### Internal Dependencies
- Requires proper configuration of all referenced entities
- Depends on Home Assistant core functionality
- Relies on Lovelace dashboard system

### External Dependencies
- Various integrations for entity sources
- Home Assistant automation engine
- User interface components

## Update History
- **2026-01-12**: Documentation consolidated from multiple files
- **2026-01-12 14:30:29**: Initial documentation created
