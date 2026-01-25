# Kia EV9 Email OTP Automation Design

**Date**: 2026-01-21
**Status**: Approved
**Version**: 2.4

## Overview

Fully automated self-healing system that monitors Gmail for Kia OTP verification codes and automatically completes integration recreation without manual intervention.

## Problem Statement

The Kia Connect API now requires OTP (one-time password) verification when setting up the integration. The v2.3 watchdog could only notify users to manually reconnect. This design adds email monitoring to extract OTP codes automatically.

## Solution

Extend the watchdog with:
1. Gmail IMAP integration to monitor for Kia OTP emails
2. Template sensor to extract 6-digit OTP from email body
3. Automation to submit OTP and complete config flow
4. Timeout handling if email doesn't arrive

## Architecture

```
[Watchdog detects integration down]
    ↓
[Delete old integration if exists]
    ↓
[Start config flow → select region/brand → submit credentials]
    ↓
[Request OTP via EMAIL]
    ↓
[Store flow_id, set state to "awaiting_otp"]
    ↓
[IMAP sensor detects new Kia email (polls every 60s)]
    ↓
[Template sensor extracts 6-digit OTP code]
    ↓
[Automation submits OTP to complete config flow]
    ↓
[Notify success/failure, reset state]
```

## Email Details

**Sender:** `no-reply@notification.kiausa.com`
**Subject:** Contains "Verification Code"
**OTP Format:** 6-digit code after "Your Kia Connect Email Verification code is:"

**Example email body:**
```
Your Kia Connect Email Verification code is:

624443
```

## IMAP Configuration

```yaml
# configuration.yaml
imap:
  - server: imap.gmail.com
    port: 993
    username: andre.byrro@gmail.com
    password: !secret gmail_app_password
    folder: INBOX
    search: "FROM notification.kiausa.com UNSEEN SUBJECT Verification"
```

## Template Sensor

```yaml
template:
  - sensor:
      - name: "Kia OTP Code"
        unique_id: kia_otp_code
        state: >
          {% set body = state_attr('sensor.imap_kia_otp', 'body') | default('') %}
          {% set match = body | regex_findall('Verification code is:\\s*(\\d{6})') %}
          {{ match[0] if match else 'none' }}
        attributes:
          received_at: "{{ now().isoformat() }}"
```

## New Helpers

```yaml
input_text:
  ev9_recovery_flow_id:
    name: "EV9 Recovery Flow ID"
    max: 64

  ev9_recovery_state:
    name: "EV9 Recovery State"
    max: 32
    initial: "idle"
    # Values: idle, starting, awaiting_otp, completing, failed

input_datetime:
  ev9_otp_requested_at:
    name: "EV9 OTP Requested At"
    has_date: true
    has_time: true
```

## Automations

### 1. ev9_connection_watchdog (modified)

**Trigger:**
- Sensor unavailable for 2+ hours
- Periodic check every 8 hours

**Action:**
1. Set state to "starting"
2. Call shell script to:
   - Delete existing integration
   - Start config flow
   - Submit region/brand
   - Submit credentials
   - Request OTP via EMAIL
   - Return flow_id
3. Store flow_id
4. Set state to "awaiting_otp"
5. Record OTP request timestamp
6. Notify "Recovery started, waiting for OTP email..."

### 2. ev9_otp_received (new)

**Trigger:**
- `sensor.kia_otp_code` changes from "none" to a 6-digit value

**Condition:**
- `input_text.ev9_recovery_state` is "awaiting_otp"

**Action:**
1. Set state to "completing"
2. Submit OTP to config flow via API
3. Wait 2 minutes for integration to initialize
4. Check if sensor is available
5. If success: notify, set state to "idle"
6. If failure: notify, set state to "failed"

### 3. ev9_otp_timeout (new)

**Trigger:**
- Time pattern every minute

**Condition:**
- State is "awaiting_otp"
- More than 5 minutes since OTP requested

**Action:**
1. Set state to "failed"
2. Clear flow_id
3. Send critical notification: "OTP email not received within 5 minutes"

## Shell Script: ev9_recovery_with_otp.sh

Handles the multi-step API flow:

```bash
#!/bin/bash
# Steps:
# 1. Find and delete existing kia_uvo entry
# 2. Start new config flow
# 3. Submit region (3=USA) and brand (1=Kia)
# 4. Submit credentials
# 5. Request OTP via EMAIL
# 6. Return flow_id for OTP submission

# Output: flow_id on success, "ERROR: message" on failure
```

## Secrets Required

```yaml
# secrets.yaml
gmail_app_password: "ffvc cmaz lunc xeok"
kia_username: "andre.byrro@gmail.com"
kia_password: "Dsenhasenha11"
kia_pin: "8560"
```

## Timing

| Step | Duration |
|------|----------|
| Delete old integration | 10 seconds |
| Start config flow | 2-3 seconds |
| Submit credentials | 2-3 seconds |
| Request OTP | 2-3 seconds |
| Email delivery | 1-2 minutes typical |
| IMAP poll interval | 60 seconds |
| OTP submission | 2-3 seconds |
| Integration init | 2 minutes |
| **Total** | **~5-7 minutes** |

## Error Handling

| Scenario | Handling |
|----------|----------|
| Config flow fails to start | Notify failure, reset state |
| Credentials rejected | Notify failure, reset state |
| OTP email not received (5 min) | Timeout automation triggers, notify, reset |
| OTP submission fails | Notify failure with error details |
| Integration still unavailable after OTP | Notify partial failure |

## Event Log Types

- `WATCHDOG_START` - Recovery initiated
- `WATCHDOG_OTP_REQUESTED` - OTP email requested
- `WATCHDOG_OTP_RECEIVED` - OTP extracted from email
- `WATCHDOG_OTP_SUBMITTED` - OTP submitted to config flow
- `WATCHDOG_SUCCESS` - Full recovery completed
- `WATCHDOG_TIMEOUT` - OTP email not received in time
- `WATCHDOG_FAILED` - Recovery failed

## File Changes

| File | Change |
|------|--------|
| `secrets.yaml` (HA) | Add `gmail_app_password` |
| `configuration.yaml` (HA) | Add IMAP integration |
| `helpers.v2.4.yaml` | Add recovery state helpers |
| `automations.v2.4.yaml` | Full recovery automations |
| `scripts/ev9_recovery_with_otp.sh` | Multi-step API script |
| `CLAUDE.md` | Document v2.4 changes |

## Testing Plan

1. Verify IMAP connection works (check sensor in HA)
2. Send test email from Kia format, verify OTP extraction
3. Manually trigger watchdog with integration working (should skip)
4. Delete integration, verify full recovery flow
5. Test timeout by blocking email (should notify after 5 min)
6. Verify cooldown prevents rapid retries

## Security Considerations

- Gmail App Password stored in secrets.yaml (git-ignored)
- App Password has limited scope (only IMAP access)
- OTP codes are short-lived and single-use
- IMAP marks emails as read to prevent re-processing
