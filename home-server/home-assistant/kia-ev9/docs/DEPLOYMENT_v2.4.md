# Kia EV9 v2.4 Deployment Guide

**Version:** 2.4
**Date:** 2026-01-21
**Feature:** Email OTP Automation for Self-Healing Recovery

## Overview

Version 2.4 adds fully automated self-healing capability to the Kia EV9 integration. When the kia_uvo integration becomes unavailable, the system automatically:

1. Detects the failure (after 2 hours of unavailability)
2. Deletes the broken integration
3. Starts a new configuration flow
4. Requests an OTP code via email
5. Monitors Gmail for the OTP email
6. Extracts the 6-digit code and submits it
7. Completes the integration setup

No manual intervention required.

---

## Prerequisites

### 1. Gmail Account Setup

The automation monitors your Gmail inbox for Kia OTP emails. You need:

- **Gmail account** with 2FA enabled
- **Gmail App Password** (16-character password for IMAP access)

#### Creating a Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Under "Signing in to Google," click **2-Step Verification**
3. At the bottom, click **App passwords**
4. Select "Mail" and "Other (Custom name)"
5. Enter "Home Assistant" as the name
6. Click **Generate**
7. Copy the 16-character password (e.g., `ffvc cmaz lunc xeok`)

### 2. Kia Connect Credentials

You need your Kia Connect app credentials:
- Email address
- Password
- 4-digit PIN

---

## Deployment Steps

### Step 1: Add Secrets to Home Assistant

SSH to your HA server and edit `/config/secrets.yaml`:

```yaml
# Gmail IMAP access
gmail_app_password: "xxxx xxxx xxxx xxxx"

# Kia Connect credentials
kia_username: "your_email@gmail.com"
kia_password: "your_kia_password"
kia_pin: "1234"

# Existing HA token (should already exist)
ha_long_lived_token: "your_existing_token"
```

### Step 2: Configure IMAP Integration

In Home Assistant UI:

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **IMAP**
3. Configure:
   - **Server:** `imap.gmail.com`
   - **Port:** `993`
   - **Username:** Your Gmail address
   - **Password:** Your Gmail App Password
   - **Folder:** `INBOX`
   - **Search:** `FROM notification.kiausa.com UNSEEN`

This creates `sensor.imap_<your_email>_messages` which fires `imap_content` events when new Kia emails arrive.

### Step 3: Deploy Shell Scripts

Copy scripts to HA:

```bash
# From your local machine
scp scripts/ev9_recovery_with_otp.sh byrro@192.168.1.11:/home/byrro/
scp scripts/ev9_submit_otp.sh byrro@192.168.1.11:/home/byrro/

# SSH to HA server
ssh byrro@192.168.1.11

# Move to config directory
sudo mkdir -p /mnt/ByrroServer/docker-data/homeassistant/config/scripts
sudo mv /home/byrro/ev9_*.sh /mnt/ByrroServer/docker-data/homeassistant/config/scripts/
sudo chmod +x /mnt/ByrroServer/docker-data/homeassistant/config/scripts/ev9_*.sh
```

### Step 4: Add Shell Commands to configuration.yaml

Add to your `configuration.yaml`:

```yaml
shell_command:
  # EV9 Recovery (v2.4)
  ev9_recovery_start: "bash /config/scripts/ev9_recovery_with_otp.sh '{{ token }}' /config/secrets.yaml"
  ev9_submit_otp: "bash /config/scripts/ev9_submit_otp.sh '{{ token }}' '{{ flow_id }}' '{{ otp }}'"
```

### Step 5: Deploy Helper Package

Copy the package file:

```bash
# Create package content
cat << 'EOF' > /tmp/ev9_v2_4.yaml
# Kia EV9 v2.4 Package - Connection Watchdog + Email OTP Automation

input_boolean:
  ev9_connection_watchdog_enabled:
    name: "EV9 Connection Watchdog Enabled"
    icon: mdi:connection

input_text:
  ev9_last_recovery_attempt:
    name: "EV9 Last Recovery Attempt"
    max: 64
    icon: mdi:clock-alert

  ev9_last_recovery_result:
    name: "EV9 Last Recovery Result"
    max: 255
    icon: mdi:connection

  ev9_recovery_flow_id:
    name: "EV9 Recovery Flow ID"
    max: 64
    icon: mdi:identifier

  ev9_recovery_state:
    name: "EV9 Recovery State"
    max: 32
    icon: mdi:state-machine
    initial: "idle"

input_datetime:
  ev9_otp_requested_at:
    name: "EV9 OTP Requested At"
    has_date: true
    has_time: true
    icon: mdi:email-clock
EOF

# Copy to HA
scp /tmp/ev9_v2_4.yaml byrro@192.168.1.11:/home/byrro/
ssh byrro@192.168.1.11 "sudo mv /home/byrro/ev9_v2_4.yaml /mnt/ByrroServer/docker-data/homeassistant/config/packages/"
```

### Step 6: Deploy Automations

The three new automations need to be added to your `automations.yaml`. You can either:

**Option A:** Copy from `automations.v2.4.yaml` (lines 958-1268) and append to your HA automations.yaml

**Option B:** Use the HA Automation Editor to create them manually

The automations are:
1. `ev9_connection_watchdog` - Triggers recovery when integration unavailable
2. `ev9_otp_received` - Extracts OTP from email and completes config flow
3. `ev9_otp_timeout` - Handles timeout if email doesn't arrive

### Step 7: Reload Home Assistant

```bash
# Via API
TOKEN=$(grep ha_long_lived_token /config/secrets.yaml | cut -d: -f2 | tr -d ' "')
curl -X POST http://localhost:8123/api/services/homeassistant/reload_all \
  -H "Authorization: Bearer $TOKEN"
```

Or restart Home Assistant completely for shell_command changes.

---

## Verification

After deployment, verify all components are working:

### Check Helpers Exist

```bash
curl -s http://localhost:8123/api/states/input_text.ev9_recovery_state \
  -H "Authorization: Bearer $TOKEN"
# Should return state: "idle"
```

### Check Automations Exist

```bash
curl -s http://localhost:8123/api/states/automation.ev9_connection_watchdog \
  -H "Authorization: Bearer $TOKEN"
# Should return state: "on"
```

### Check IMAP Sensor

```bash
curl -s http://localhost:8123/api/states -H "Authorization: Bearer $TOKEN" | \
  python3 -c 'import sys,json; [print(e["entity_id"]) for e in json.load(sys.stdin) if "imap" in e["entity_id"]]'
# Should show your IMAP sensor
```

### Check Shell Commands

The shell commands are only verified when executed. You can test manually:

```bash
docker exec homeassistant bash -c "ls -la /config/scripts/ev9_*.sh"
# Should show both scripts with execute permissions
```

---

## How It Works

### Recovery Flow

```
┌─────────────────────────────────────────────────────────────┐
│ sensor.ev9_ev_battery_level unavailable for 2+ hours        │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ ev9_connection_watchdog triggers                            │
│ - Sets recovery_state = "starting"                          │
│ - Calls ev9_recovery_start shell command                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ ev9_recovery_with_otp.sh runs:                              │
│ 1. Deletes existing kia_uvo entry                           │
│ 2. Starts new config flow                                   │
│ 3. Submits region (USA) + brand (Kia)                       │
│ 4. Submits credentials                                      │
│ 5. Requests OTP via EMAIL                                   │
│ 6. Returns flow_id                                          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Automation stores flow_id, sets state = "awaiting_otp"      │
│ Records OTP request timestamp for timeout tracking          │
└─────────────────────────────┬───────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│ IMAP detects Kia email   │    │ 5 minutes pass           │
│ imap_content event fires │    │ ev9_otp_timeout triggers │
└────────────┬─────────────┘    └────────────┬─────────────┘
             │                               │
             ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│ ev9_otp_received:        │    │ Sets state = "failed"    │
│ - Extracts 6-digit OTP   │    │ Clears flow_id           │
│ - Calls ev9_submit_otp   │    │ Sends TIMEOUT notification│
│ - Waits 2 min for init   │    └──────────────────────────┘
│ - Checks sensor status   │
└────────────┬─────────────┘
             │
     ┌───────┴───────┐
     │               │
     ▼               ▼
┌──────────┐   ┌──────────┐
│ SUCCESS  │   │ FAILED   │
│ state=   │   │ state=   │
│ "idle"   │   │ "failed" │
└──────────┘   └──────────┘
```

### State Machine

| State | Description |
|-------|-------------|
| `idle` | Normal operation, no recovery in progress |
| `starting` | Recovery initiated, running shell script |
| `awaiting_otp` | OTP requested, waiting for email |
| `completing` | OTP received, submitting to config flow |
| `failed` | Recovery failed, manual intervention needed |

### Timing

| Step | Typical Duration |
|------|------------------|
| Delete old integration | ~10 seconds |
| Start config flow | ~3 seconds |
| Submit credentials | ~3 seconds |
| Request OTP | ~3 seconds |
| Email delivery | 1-2 minutes |
| IMAP poll interval | ≤60 seconds |
| OTP submission | ~3 seconds |
| Integration initialization | ~2 minutes |
| **Total** | **~5-7 minutes** |

### Cooldowns

- **Recovery cooldown:** 8 hours between attempts
- **Theft alert cooldown:** 15 minutes between alerts (separate feature)

---

## Troubleshooting

### Recovery Not Triggering

1. Check watchdog is enabled:
   ```yaml
   input_boolean.ev9_connection_watchdog_enabled: on
   ```

2. Check recovery state is idle:
   ```yaml
   input_text.ev9_recovery_state: idle
   ```

3. Check cooldown hasn't been hit:
   - Look at `input_text.ev9_last_recovery_attempt`
   - Must be >8 hours ago

### OTP Email Not Received

1. Check IMAP sensor is working:
   - Developer Tools → States → search for "imap"
   - Should show your sensor with state = number of unread messages

2. Check email filter in IMAP config:
   - Search should be: `FROM notification.kiausa.com UNSEEN`

3. Check spam folder - Kia emails might be filtered

4. Verify Gmail App Password is correct

### OTP Extraction Failed

The regex pattern looks for: `Verification code is:\s*(\d{6})`

If Kia changes their email format, the regex may need updating in `automations.v2.4.yaml`.

### Shell Script Errors

Test scripts manually:

```bash
# Check script exists and is executable
docker exec homeassistant ls -la /config/scripts/ev9_recovery_with_otp.sh

# Test recovery script (will actually delete/recreate integration!)
docker exec homeassistant bash /config/scripts/ev9_recovery_with_otp.sh "$TOKEN" /config/secrets.yaml
```

### Checking Logs

```bash
# View recent automation traces
# HA UI → Settings → Automations → ev9_connection_watchdog → Traces

# View event log
curl -s http://localhost:8123/api/states/input_text.ev9_event_1 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Event Log Reference

The automation logs events to `input_text.ev9_event_1` through `ev9_event_10`:

| Event Type | Description |
|------------|-------------|
| `WATCHDOG_START` | Recovery process initiated |
| `WATCHDOG_OTP_REQUESTED` | OTP email requested from Kia |
| `WATCHDOG_OTP_RECEIVED` | OTP extracted from email |
| `WATCHDOG_SUCCESS` | Full recovery completed |
| `WATCHDOG_TIMEOUT` | OTP email not received in time |
| `WATCHDOG_FAILED` | Recovery failed |

---

## Manual Testing

To test the full recovery flow without waiting for a real failure:

1. **Disable the kia_uvo integration** (Settings → Integrations → kia_uvo → Disable)

2. **Reset recovery state:**
   ```yaml
   # Developer Tools → Services
   service: input_text.set_value
   data:
     entity_id: input_text.ev9_recovery_state
     value: "idle"
   ```

3. **Trigger watchdog manually:**
   ```yaml
   # Developer Tools → Services
   service: automation.trigger
   data:
     entity_id: automation.ev9_connection_watchdog
   ```

4. **Monitor progress:**
   - Watch `input_text.ev9_recovery_state` change
   - Check your email for OTP
   - Watch for success/failure notification

---

## Rollback

To disable v2.4 features and revert to notification-only:

1. Disable the automations:
   ```yaml
   service: automation.turn_off
   target:
     entity_id:
       - automation.ev9_connection_watchdog
       - automation.ev9_otp_email_received
       - automation.ev9_otp_timeout
   ```

2. Optionally remove the IMAP integration if not needed elsewhere

3. The helpers and shell scripts can remain - they won't do anything if automations are disabled
