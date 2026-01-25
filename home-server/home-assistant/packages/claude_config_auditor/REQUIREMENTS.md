# Claude Config Auditor — Requirements
**Version:** v1.0
**Last Updated:** 2026-01-24
**Owner:** Andre Byrro

## 1) Purpose
Monitor Claude Code configuration files across projects on the Mac, collect best practices from external sources (Claude docs, GitHub releases), and surface actionable recommendations through a Home Assistant dashboard with mobile notifications.

## 2) Inputs
- n8n REST API sensor polling `/webhook/status-api` every 5 minutes
- Local Mac agent pushes config data to n8n every 4 hours

## 3) Outputs
| Entity | Type | Description |
|--------|------|-------------|
| `sensor.claude_config_audit_status` | sensor | Overall status: healthy/warning/error/critical |
| `sensor.claude_config_projects_count` | sensor | Number of tracked projects |
| `sensor.claude_config_health_score` | sensor | Percentage of passing rules |
| `sensor.claude_config_critical_count` | sensor | Count of critical violations |
| `sensor.claude_config_error_count` | sensor | Count of error violations |
| `sensor.claude_config_warning_count` | sensor | Count of warning violations |
| `sensor.claude_config_info_count` | sensor | Count of info-level issues |
| `sensor.claude_config_pass_count` | sensor | Count of passing checks |
| `sensor.claude_config_last_sync` | sensor | Timestamp of last sync |
| `sensor.claude_config_pending_candidates` | sensor | Number of pending rule candidates |
| `sensor.claude_config_audit_age` | sensor | Hours since last sync |
| `binary_sensor.claude_config_audit_stale` | binary_sensor | True when audit data > 8 hours old |
| `binary_sensor.claude_config_has_critical` | binary_sensor | True when critical issues exist |

## 4) Controls
| Helper | Purpose |
|--------|---------|
| `input_boolean.claude_config_notify_critical` | Enable/disable critical issue notifications |
| `input_boolean.claude_config_notify_stale` | Enable/disable stale data notifications |
| `rest_command.claude_config_force_scan` | Trigger immediate config scan |

## 5) Safety and Guardrails
- REST sensor has 30-second timeout to prevent blocking
- Stale data warning triggers only after 30 minutes of being stale (avoids false alarms)
- Critical notifications use iOS critical alerts (bypass DND)
- All notifications are tagged for proper grouping/replacement

## 6) UI Contract
Dashboard location: `/lovelace/homelab` (tab or section)

**Observe:**
- Health score gauge
- Status chips (critical/error/warning/info/pass counts)
- Last sync time

**Understand:**
- Project breakdown table
- Rule categories and their status
- Pending candidates from external sources

**Act:**
- Force scan button
- n8n dashboard link
- Notification preference toggles

## 7) Acceptance Tests (Manual)
1. Verify REST sensor shows data in Developer Tools > States
2. Change a config to violate a critical rule, trigger scan, verify notification
3. Fix the violation, verify resolution notification
4. Stop Mac agent for 8+ hours, verify stale warning
5. Verify dashboard renders correctly on mobile/tablet/desktop

## 8) Rollback
```bash
# Remove package
rm -rf packages/claude_config_auditor/

# Reload HA
# Navigate to Developer Tools > YAML > Reload all YAML configuration

# Or restart HA container
docker restart homeassistant
```
