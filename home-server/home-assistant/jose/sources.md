# Source Reference Map: Jose (Vacuum)

## Source File Summary

| Source | Entities | Percentage |
|--------|----------|------------|
| Dreame Integration | 21 | 65.6% |
| Home Assistant Helpers | 10 | 31.3% |
| Home Assistant Automations | 1 | 3.1% |
| **Total** | **32** | **100%** |

## Entity → Source Mapping

### Dreame Integration Entities (21)

**Vacuum:**
- `vacuum.jose` → Dreame Integration

**Buttons:**
- `button.jose_empty_dustbin` → Dreame Integration
- `button.jose_relocate` → Dreame Integration

**Selects:**
- `select.jose_auto_empty_frequency` → Dreame Integration
- `select.jose_water_flow_level` → Dreame Integration
- `select.jose_active_map` → Dreame Integration

**Sensors:**
- `sensor.jose_area_cleaned` → Dreame Integration
- `sensor.jose_cleaning_duration` → Dreame Integration
- `sensor.jose_error` → Dreame Integration
- `sensor.jose_total_area_cleaned` → Dreame Integration
- `sensor.jose_total_cleaning_duration` → Dreame Integration
- `sensor.jose_total_cleanings` → Dreame Integration
- `sensor.jose_filter_lifespan` → Dreame Integration
- `sensor.jose_main_brush_lifespan` → Dreame Integration
- `sensor.jose_side_brush_lifespan` → Dreame Integration
- `sensor.jose_hand_filter_lifespan` → Dreame Integration
- `sensor.jose_unit_care_lifespan` → Dreame Integration
- `sensor.jose_battery` → Dreame Integration
- `sensor.jose_station_state` → Dreame Integration

**Binary Sensors:**
- `binary_sensor.jose_mop_attached` → Dreame Integration

**Events:**
- `event.jose_last_job` → Dreame Integration

**Images:**
- `image.jose_map` → Dreame Integration

### Home Assistant Helper Entities (10)

**Input Text (Error Logging):**
- `input_text.jose_error_log_1` → Home Assistant Helper
- `input_text.jose_error_log_2` → Home Assistant Helper
- `input_text.jose_error_log_3` → Home Assistant Helper
- `input_text.jose_error_log_4` → Home Assistant Helper
- `input_text.jose_error_log_5` → Home Assistant Helper
- `input_text.jose_error_log_6` → Home Assistant Helper
- `input_text.jose_error_log_7` → Home Assistant Helper
- `input_text.jose_error_log_8` → Home Assistant Helper
- `input_text.jose_error_log_9` → Home Assistant Helper
- `input_text.jose_error_log_10` → Home Assistant Helper

### Home Assistant Automation Entities (1)

- `automation.jose_vacuum_log_error_messages` → Home Assistant Automation

## Integration Details

### Dreame Integration
- **Type**: HACS Custom Integration
- **Purpose**: Connects Dreame robot vacuums to Home Assistant
- **Provides**: Vacuum control, sensors, map, consumable tracking

### Error Logging System
- **Components**: 10 input_text helpers + 1 automation
- **Purpose**: Maintains rolling log of last 10 vacuum errors
- **Log 1**: Most recent error
- **Log 10**: Oldest error in history

## Last Updated
2026-01-18
