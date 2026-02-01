# Automations Tab Snippets for Storage-Mode Dashboards

**Created:** 2026-01-31
**Purpose:** YAML snippets to paste into HA's Raw Configuration Editor for Storage-mode dashboards

---

## How to Add These Tabs

1. Open Home Assistant → Dashboard you want to edit
2. Click the ⋮ menu (3 dots) → **Edit Dashboard**
3. Click ⋮ → **Raw configuration editor**
4. Find the `views:` section
5. Paste the relevant snippet at the end of the views array
6. Click **Save**

---

## Daikin Dashboard

Add this view to `/dashboard-daikn`:

```yaml
  - title: Automations
    path: automations
    icon: mdi:robot
    badges: []
    cards:
      - type: markdown
        title: Daikin Automations
        content: |
          **Goal:** Maintain HVAC comfort and efficiency through scheduled and condition-based control.

          **Method:**
          - Schedule-based temperature adjustments
          - Occupancy-aware climate control
          - Efficiency optimization

          **Triggers:**
          - Time-based: Schedule triggers
          - State-based: Occupancy changes

          **Settings:**
          - Configure schedules in Daikin integration settings
      - type: entities
        title: Automation Status
        entities:
          - entity: automation.daikin_morning_warmup
            name: Morning Warmup
            secondary_info: last-triggered
          - entity: automation.daikin_away_mode
            name: Away Mode
            secondary_info: last-triggered
          - entity: automation.daikin_night_setback
            name: Night Setback
            secondary_info: last-triggered
          - entity: automation.daikin_return_home
            name: Return Home
            secondary_info: last-triggered
          - entity: automation.daikin_efficiency_check
            name: Efficiency Check
            secondary_info: last-triggered
          - entity: automation.daikin_filter_reminder
            name: Filter Reminder
            secondary_info: last-triggered
      - type: markdown
        title: Activity Log
        content: |
          *Activity logging not yet configured for Daikin automations.*

          | Time | Action | Result |
          |------|--------|--------|
          | — | No events recorded | — |
        tap_action:
          action: none
```

---

## Trackers (Reddit) Dashboard

Add this view to `/notifications-logs/trackers`:

```yaml
  - title: Automations
    path: automations
    icon: mdi:robot
    badges: []
    cards:
      - type: markdown
        title: Tracker Automations
        content: |
          **Goal:** Monitor Reddit for private tracker signup announcements.

          **Method:**
          - Scrape specific subreddits for signup posts
          - Parse tracker names from post content
          - Send notifications when new signups detected
          - Track open/closed status history

          **Triggers:**
          - Time pattern: Periodic Reddit checks

          **Settings:**
          - Subreddit targets configured in automation
      - type: entities
        title: Automation Status
        entities:
          - entity: automation.tracker_reddit_monitor
            name: Reddit Monitor
            secondary_info: last-triggered
          - entity: automation.tracker_signup_notification
            name: Signup Notification
            secondary_info: last-triggered
          - entity: automation.tracker_status_update
            name: Status Update
            secondary_info: last-triggered
      - type: markdown
        title: Activity Log
        content: |
          *Activity logging not yet configured for Tracker automations.*

          | Time | Tracker | Status |
          |------|---------|--------|
          | — | No events recorded | — |
        tap_action:
          action: none
```

---

## Jose Vacuum Dashboard

Add this view to `/jose`:

```yaml
  - title: Automations
    path: automations
    icon: mdi:robot
    badges: []
    cards:
      - type: markdown
        title: Jose Vacuum Automations
        content: |
          **Goal:** Automate vacuum cleaning schedules with recovery from connectivity issues.

          **Method:**
          - Scheduled cleaning runs (daily/weekly patterns)
          - Automatic recovery when Ecovacs integration fails
          - Zone-based cleaning assignments

          **Triggers:**
          - Time-based: Scheduled cleaning times
          - State-based: Integration health checks, battery level

          **Settings:**
          - Schedules configured via jose_schedule package
          - Recovery toggle in System Health dashboard
      - type: entities
        title: Automation Status
        entities:
          - type: section
            label: Schedules
          - entity: automation.jose_daily_clean
            name: Daily Clean
            secondary_info: last-triggered
          - entity: automation.jose_weekly_deep_clean
            name: Weekly Deep Clean
            secondary_info: last-triggered
          - entity: automation.jose_zone_kitchen
            name: Zone: Kitchen
            secondary_info: last-triggered
          - entity: automation.jose_zone_living
            name: Zone: Living Room
            secondary_info: last-triggered
          - type: section
            label: Recovery
          - entity: automation.ecovacs_connection_watchdog
            name: Connection Watchdog
            secondary_info: last-triggered
          - entity: automation.ecovacs_recovery_reload
            name: Recovery Reload
            secondary_info: last-triggered
          - type: section
            label: Battery & Dock
          - entity: automation.jose_low_battery_alert
            name: Low Battery Alert
            secondary_info: last-triggered
          - entity: automation.jose_return_to_dock
            name: Return to Dock
            secondary_info: last-triggered
      - type: markdown
        title: Activity Log
        content: |
          *Activity logging not yet configured for Jose automations.*

          | Time | Action | Result |
          |------|--------|--------|
          | — | No events recorded | — |
        tap_action:
          action: none
```

---

## Kia EV9 Dashboard

Add this view to `/kia-ev9`:

```yaml
  - title: Automations
    path: automations
    icon: mdi:robot
    badges: []
    cards:
      - type: markdown
        title: Kia EV9 Automations
        content: |
          **Goal:** Optimize charging, climate, and vehicle connectivity.

          **Categories:**
          - **Charging:** TOU optimization, target SoC, charge scheduling
          - **Climate:** Pre-conditioning for departures
          - **Recovery:** OTP-based reauthentication when token expires
          - **Notifications:** Charge status, trip readiness

          **Triggers:**
          - Time-based: Departure schedules, TOU windows
          - State-based: SoC thresholds, plug status, token expiry

          **Settings:**
          - Configurable via EV9 dashboard Settings tab
      - type: entities
        title: Automation Status
        entities:
          - type: section
            label: Charging
          - entity: automation.ev9_charge_start_tou
            name: TOU Charge Start
            secondary_info: last-triggered
          - entity: automation.ev9_charge_stop_target
            name: Target SoC Stop
            secondary_info: last-triggered
          - entity: automation.ev9_charge_complete_notification
            name: Charge Complete Alert
            secondary_info: last-triggered
          - type: section
            label: Climate
          - entity: automation.ev9_climate_precondition
            name: Departure Pre-conditioning
            secondary_info: last-triggered
          - entity: automation.ev9_climate_cabin_protect
            name: Cabin Protection
            secondary_info: last-triggered
          - type: section
            label: Recovery
          - entity: automation.ev9_connection_watchdog
            name: Connection Watchdog
            secondary_info: last-triggered
          - entity: automation.ev9_otp_recovery
            name: OTP Recovery
            secondary_info: last-triggered
          - entity: automation.ev9_token_refresh
            name: Token Refresh
            secondary_info: last-triggered
          - type: section
            label: Notifications
          - entity: automation.ev9_low_battery_alert
            name: Low Battery Alert
            secondary_info: last-triggered
          - entity: automation.ev9_trip_ready_notification
            name: Trip Ready
            secondary_info: last-triggered
      - type: markdown
        title: Activity Log
        content: |
          | Time | Event |
          |:-----|:------|
          {%- for i in range(1, 11) %}
          {%- set val = states('input_text.ev9_event_' ~ i) %}
          {%- if val not in ['unknown', 'unavailable', '', None] %}
          {%- set parts = val.split(' - ', 1) %}
          | {{ parts[0] }} | {{ parts[1] | replace('|', '/') if parts | length > 1 else val | replace('|', '/') }} |
          {%- endif %}
          {%- endfor %}
          {%- if states('input_text.ev9_event_1') in ['unknown', 'unavailable', '', None] %}
          | — | _No recent activity_ |
          {%- endif %}
        tap_action:
          action: none
```

---

## Notes

- **Entity names are estimates** - verify actual automation entity IDs before pasting
- **Activity logs** - Most are placeholders; update with actual event sensors if available
- **tap_action: none** - Required for read-only logs per CLAUDE.md Section 6.3
