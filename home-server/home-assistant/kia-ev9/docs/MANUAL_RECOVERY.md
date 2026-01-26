# Kia EV9 Manual Recovery Guide

**Last Updated:** 2026-01-26
**Purpose:** Manual recovery procedure when the automated OTP flow fails

---

## When to Use This Guide

Use this manual recovery process when:
1. The `ev9_connection_watchdog` automation fails to complete
2. The IMAP automation doesn't trigger on OTP emails
3. You need to quickly restore the integration

---

## Prerequisites

### Required Credentials (in `/config/secrets.yaml`)

```yaml
ha_long_lived_token: "eyJ..."  # HA Long-Lived Access Token
kia_username: "your_email@gmail.com"
kia_password: "your_kia_password"
kia_pin: "123456"
gmail_app_password: "xxxx xxxx xxxx xxxx"  # Gmail App Password for IMAP
```

### Required Shell Scripts (in `/config/scripts/`)

- `ev9_recovery_with_otp.sh` - Starts config flow and requests OTP
- `ev9_submit_otp.sh` - Submits OTP to complete config flow

---

## Recovery Steps

### Step 1: Start Config Flow and Request OTP

SSH to the VM and run the recovery script inside the HA container:

```bash
ssh byrro@192.168.1.11

# Run inside the HA container
docker exec homeassistant bash -c 'cd /config && bash scripts/ev9_recovery_with_otp.sh "<HA_TOKEN>" /config/secrets.yaml'
```

Expected output:
```
[timestamp] === EV9 Recovery with OTP Started ===
[timestamp] No existing kia_uvo entry found (or deleted existing)
[timestamp] Starting config flow...
[timestamp] Config flow started (flow_id: 01KFXXXXX...)
[timestamp] Submitting region and brand...
[timestamp] Submitting credentials...
[timestamp] Requesting OTP via EMAIL...
01KFXXXXX...
[timestamp] OTP requested successfully. Waiting for email...
```

**Save the flow_id** - you'll need it in Step 3.

### Step 2: Extract OTP from Gmail

**IMPORTANT:** Kia OTPs expire in ~3-5 minutes. Do this quickly!

Wait ~60 seconds for the email to arrive, then extract the OTP:

```bash
docker exec homeassistant python3 -c "
import imaplib
import email
import re

mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login('andre.byrro@gmail.com', 'ffvc cmaz lunc xeok')
mail.select('INBOX')

status, messages = mail.search(None, 'FROM', 'notification.kiausa.com')
email_ids = messages[0].split()

if email_ids:
    latest_id = email_ids[-1]
    status, msg_data = mail.fetch(latest_id, '(RFC822)')
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)

    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in ['text/plain', 'text/html']:
                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                break
    else:
        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

    # Find 6-digit OTP (excluding 797979 which is a static template ID)
    codes = re.findall(r'\b(\d{6})\b', body)
    codes = [c for c in codes if c != '797979']

    if codes:
        print(f'OTP: {codes[0]}')
        print(f'Date: {msg[\"Date\"]}')
    else:
        print('No OTP found')
else:
    print('No Kia emails found')

mail.logout()
"
```

### Step 3: Submit OTP (Within 3 Minutes!)

Submit the OTP immediately using the flow_id from Step 1:

```bash
curl -s -X POST 'http://localhost:8123/api/config/config_entries/flow/<FLOW_ID>' \
  -H 'Authorization: Bearer <HA_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"otp": "<6_DIGIT_OTP>"}'
```

Example:
```bash
curl -s -X POST 'http://localhost:8123/api/config/config_entries/flow/01KFX55Q0ZFS02WNH6RCMWA11K' \
  -H 'Authorization: Bearer eyJhbGciOi...' \
  -H 'Content-Type: application/json' \
  -d '{"otp": "967513"}'
```

**Success response:**
```json
{
  "type": "create_entry",
  "flow_id": "01KFX55Q0ZFS02WNH6RCMWA11K",
  "handler": "kia_uvo",
  "title": "Kia USA andre.byrro@gmail.com",
  "result": {
    "entry_id": "01KFX58CD9AP4N17GBMFA1R1FR",
    "state": "loaded"
  }
}
```

### Step 4: Update Device ID Helper

Update the device ID helper so automations continue to work:

```bash
curl -s -X POST 'http://localhost:8123/api/services/input_text/set_value' \
  -H 'Authorization: Bearer <HA_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"entity_id": "input_text.ev9_device_id", "value": "<NEW_ENTRY_ID>"}'
```

### Step 5: Verify Success

Check that entities are working:

```bash
# Battery level should show a percentage
curl -s 'http://localhost:8123/api/states/sensor.ev9_ev_battery_level' \
  -H 'Authorization: Bearer <HA_TOKEN>' | jq -r '.state'

# Integration status should be "online"
curl -s 'http://localhost:8123/api/states/sensor.ev9_integration_status' \
  -H 'Authorization: Bearer <HA_TOKEN>' | jq -r '.state'
```

---

## Troubleshooting

### "OTP verification failed: Invalid code"

The OTP expired. You must submit within ~3 minutes of the email timestamp. Restart from Step 1.

### "500 Internal Server Error"

Usually means the OTP expired or the flow was cancelled. Restart from Step 1.

### "No existing kia_uvo entry found"

This is normal - means there's no old integration to delete. The script will continue with creating a new one.

### OTP Email Not Arriving

1. Check spam folder
2. Verify Gmail app password is correct
3. Try logging into Kia Connect app manually - may need to re-authenticate there first

---

## Quick Reference

| Step | Time Limit | Command |
|------|------------|---------|
| 1. Start flow | - | `docker exec homeassistant bash -c 'bash /config/scripts/ev9_recovery_with_otp.sh ...'` |
| 2. Wait for email | ~60 sec | - |
| 3. Extract OTP | - | Python script above |
| 4. Submit OTP | **<3 min** | `curl -X POST .../flow/<FLOW_ID> -d '{"otp":"..."}' ` |
| 5. Update helper | - | `curl -X POST .../input_text/set_value ...` |

---

## Recovery Success Log

| Date | Entry ID | Notes |
|------|----------|-------|
| 2026-01-26 | `01KFX58CD9AP4N17GBMFA1R1FR` | Manual recovery successful, OTP submitted within 2 min |
