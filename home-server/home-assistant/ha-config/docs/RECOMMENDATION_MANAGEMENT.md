# Claude Code Recommendation Management Guide

## Overview

This system helps you manage Claude Code feature recommendations through interactive emails and a Home Assistant dashboard. Each recommendation can be dismissed, reminded later, or marked as complete.

---

## How to Use: Email Action Buttons

### Each Recommendation Has 3 Buttons

When you receive a Claude Code recommendations email, scroll down to any recommendation card. At the bottom of each card, you'll see three action buttons:

#### 1. ✓ Mark Complete (Green Button)
- **When to use**: You've successfully implemented the recommendation
- **What happens**: Recommendation is permanently removed from future emails
- **Example**: You added SessionStart hooks to your Claude config and it's working
- **Effect**: `state` → `completed`, timestamp saved

#### 2. ⏰ Remind in 7 Days (Yellow Button)
- **When to use**: The recommendation looks useful but you're not ready to implement it now
- **What happens**: Hidden for exactly 7 days, then reappears in emails
- **Example**: GitHub MCP server integration sounds great but you're busy this week
- **Effect**: `state` → `reminded`, will resurface after 7 days

#### 3. ✗ Dismiss (Gray Button)
- **When to use**: The recommendation isn't relevant for your workflow
- **What happens**: Permanently removed from future emails
- **Example**: You've decided deny rules don't fit your use case
- **Effect**: `state` → `dismissed`, never shown again

### What Happens When You Click

1. **Link opens** in your browser: `http://192.168.1.11:5678/webhook/recommendation-action?token=UUID&action=ACTION`
2. **Success page appears** with message: "✓ Recommendation [dismiss/remind/complete] successfully!"
3. **Confirmation text**: "This recommendation will no longer appear in future reports"
4. **Link to dashboard**: "View Dashboard" (goes to Home Assistant)

### Important Notes

- **Token expiration**: Action links expire after **72 hours** for security
  - If you get "Token expired", don't worry - the next email will have fresh links
- **One-time use**: Each link can only be clicked once
- **Instant effect**: Changes take effect immediately for the next email

---

## How to View: Home Assistant Dashboard

### Location

**Path**: Home Assistant → **Settings** → **Dashboards** → **Claude Config** → **Recommendations** tab

**Direct URL**: `http://192.168.1.11:8123/lovelace/claude-config` (then click Recommendations tab)

### What You'll See

The dashboard shows:

1. **Summary Card**
   - Total active recommendations (state = open)
   - Total dismissed
   - Total reminded (waiting to resurface)
   - Total completed

2. **Individual Recommendation Cards**
   - Each recommendation with its current state
   - Timestamps for actions (dismissed_at, reminded_at, completed_at)
   - Feature name and category

### Dashboard Action Buttons

Each recommendation row now has action buttons:
- **✓** (Complete) - Mark the recommendation as implemented
- **⏰** (Remind) - Set a 7-day reminder
- **✗** (Dismiss) - Permanently hide the recommendation

These buttons call the same webhook endpoint as the email buttons, allowing you to manage recommendations directly from the dashboard.

> **Note**: The n8n webhook must be configured to accept POST requests from Home Assistant for dashboard buttons to work. See Phase 4 of the implementation plan.

---

## Recommendation States Explained

| State | What it means | Will it reappear in emails? | Can be changed? |
|-------|---------------|----------------------------|-----------------|
| **Open** | New recommendation, no action taken yet | Yes, in every email | Yes, via email buttons |
| **Dismissed** | You marked it as not relevant | **No**, permanently hidden | No, permanent |
| **Completed** | You implemented it | **No**, permanently hidden | No, permanent |
| **Reminded** | You asked to see it again in 7 days | **Yes**, after 7 days from reminder date | Yes, will auto-return to "open" after 7 days |

### State Lifecycle Examples

**Example 1: Dismiss Flow**
```
Open (appears in every email)
  ↓ User clicks "✗ Dismiss"
Dismissed (never appears again)
```

**Example 2: Remind Later Flow**
```
Open (appears in email on Jan 1)
  ↓ User clicks "⏰ Remind in 7 Days" on Jan 1
Reminded (hidden from emails Jan 1-7)
  ↓ 7 days pass
Open (reappears in email on Jan 8)
```

**Example 3: Mark Complete Flow**
```
Open (appears in every email)
  ↓ User clicks "✓ Mark Complete"
Completed (never appears again)
```

---

## Home Assistant Sensors

The system creates these sensors for automation/monitoring:

### Summary Sensor
- **Entity**: `sensor.claude_recommendation_status`
- **State**: Text like "0 active" (number of open recommendations)
- **Attributes**:
  - `active`: count of open recommendations
  - `dismissed`: count of dismissed recommendations
  - `reminded`: count of reminded recommendations
  - `completed`: count of completed recommendations
  - `total_recommendations`: always 5 (number of possible recommendations)

### Individual Recommendation Sensors

Each recommendation has its own sensor:

1. **`sensor.claude_recommendation_sessionstart_hooks`**
   - Feature: SessionStart Hooks (Automation category)
   - Auto-run commands at session start

2. **`sensor.claude_recommendation_github_mcp`**
   - Feature: GitHub MCP Server (Integration category)
   - Live GitHub PR/issue access

3. **`sensor.claude_recommendation_tool_search`**
   - Feature: MCP Tool Search (Performance category)
   - Reduce context usage

4. **`sensor.claude_recommendation_deny_rules`**
   - Feature: Permission Deny Rules (Security category)
   - Block access to sensitive files

5. **`sensor.claude_recommendation_disable_model_invocation`**
   - Feature: Disable Model Invocation (Automation category)
   - Control automatic skill invocation

### Sensor Attributes

Each individual sensor has:
- `state`: Current state (open/dismissed/reminded/completed)
- `feature_name`: Human-readable name
- `category`: Feature category
- `dismissed_at`: ISO timestamp when dismissed (or null)
- `reminded_at`: ISO timestamp when reminded (or null)
- `completed_at`: ISO timestamp when completed (or null)
- `checked_at`: Last time state was checked

---

## Troubleshooting

### "Token expired or invalid" Error

**Cause**: You clicked a link from an email older than 72 hours, or the link was already used.

**Solution**:
1. Wait for the next scheduled email (or trigger one manually)
2. Use the fresh action links from the new email
3. Action links are generated fresh with every email

### Recommendation Still Appears After Dismissing

**Cause**: The email you're looking at was generated before you dismissed it.

**Solution**:
1. Check the email timestamp - is it from before you clicked dismiss?
2. Wait for the next email (or trigger manually)
3. Verify the state in Home Assistant dashboard
4. If state shows "dismissed" in HA but still appears in new emails, report as bug

### "Reminded" Recommendation Not Reappearing

**Cause**: It hasn't been 7 days yet.

**Solution**:
1. Check Home Assistant sensor for `reminded_at` timestamp
2. Add 7 days to that timestamp
3. Recommendation will reappear in the first email sent after that date

### Dashboard Not Showing Recommendations Tab

**Possible causes**:
1. Dashboard configuration not loaded
2. Sensors not created
3. Home Assistant needs restart

**Solution**:
```bash
# Check if sensors exist
ssh byrro@192.168.1.11
docker exec homeassistant ha core restart

# Verify sensors after restart
curl -s http://192.168.1.11:8123/api/states/sensor.claude_recommendation_status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Database Reference (For Advanced Users)

Recommendation states are stored in PostgreSQL database `n8n_auditor`:

**Table**: `audit_results`

**Key columns**:
- `rule_id`: Recommendation identifier (e.g., 'sessionstart-hooks')
- `project_id`: Associated project
- `state`: Current state (open/dismissed/reminded/completed)
- `dismissed_at`: Timestamp when dismissed
- `reminded_at`: Timestamp when reminded (for 7-day calculation)
- `completed_at`: Timestamp when completed
- `checked_at`: Last check timestamp

**Query current states**:
```sql
SELECT rule_id, state, dismissed_at, reminded_at, completed_at
FROM audit_results
WHERE state IN ('dismissed', 'reminded', 'completed')
ORDER BY checked_at DESC;
```

---

## API Reference

### Status API Endpoint

**URL**: `http://192.168.1.11:5678/webhook/status-api`

**Returns**: JSON with `recommendation_states` object

**Example response**:
```json
{
  "status": "healthy",
  "total_projects": 1,
  "recommendation_states": {
    "sessionstart-hooks": {
      "state": "dismissed",
      "dismissed_at": "2026-01-26T20:47:15.904Z",
      "reminded_at": null,
      "completed_at": null,
      "checked_at": "2026-01-26T20:47:15.904Z"
    },
    "github-mcp": {
      "state": "reminded",
      "dismissed_at": null,
      "reminded_at": "2026-01-26T20:47:35.368Z",
      "completed_at": null,
      "checked_at": "2026-01-26T20:47:35.368Z"
    }
  }
}
```

### Action Webhook Endpoint

**URL**: `http://192.168.1.11:5678/webhook/recommendation-action`

**Method**: GET

**Query Parameters**:
- `token`: UUID4 token (generated per-recommendation per-email)
- `action`: One of `dismiss`, `remind`, `complete`

**Example**:
```
http://192.168.1.11:5678/webhook/recommendation-action?token=123e4567-e89b-12d3-a456-426614174000&action=dismiss
```

**Response**: HTML success page with confirmation message

---

## Quick Reference Card

| Want to... | Do this... | Result... |
|------------|-----------|-----------|
| Never see this recommendation again | Click **✗ Dismiss** in email or dashboard | Permanent removal |
| Implement it but later | Click **⏰ Remind in 7 Days** in email or dashboard | Hidden for 7 days, then returns |
| Mark it as implemented | Click **✓ Mark Complete** in email or dashboard | Permanent removal |
| See and manage states | Open HA dashboard at `/lovelace/claude-config/recommendations` | View and action buttons |
| Check state via API | `curl http://192.168.1.11:5678/webhook/status-api` | JSON response |
| Manually trigger new email | See n8n workflow "Config Report Generator" | Fresh action links |

---

## Support

**Implementation files**:
- Email generator: n8n workflow `GS3fZ4qq6xqbVVtk` (Config Report Generator)
- Webhook handler: n8n workflow `recommendation-action-handler`
- HA sensors: `/mnt/ByrroServer/docker-data/homeassistant/config/packages/claude_config_auditor.yaml`
- HA dashboard: `/mnt/ByrroServer/docker-data/homeassistant/config/dashboards/claude_config_recommendations.yaml`

**Testing summary**: `/tmp/phase6_testing_complete.md`
