# Kia EV9 Shell Scripts

Shell scripts for Home Assistant automation of Kia EV9 integration recovery.

## Scripts

### ev9_recovery_with_otp.sh

**Purpose:** Handles the multi-step Kia UVO config flow up to OTP request.

**Usage:**
```bash
ev9_recovery_with_otp.sh <ha_token> <secrets_file>
```

**Parameters:**
- `ha_token` - Home Assistant long-lived access token
- `secrets_file` - Path to secrets.yaml (default: `/config/secrets.yaml`)

**Output:**
- On success: Returns `flow_id` (UUID string)
- On failure: Returns `ERROR: <message>`

**What it does:**
1. Finds and deletes existing `kia_uvo` config entry
2. Starts new config flow
3. Submits region (3 = USA) and brand (1 = Kia)
4. Submits credentials from secrets.yaml
5. Requests OTP via EMAIL method
6. Returns flow_id for OTP submission

**Required secrets:**
```yaml
kia_username: "your_email@gmail.com"
kia_password: "your_password"
kia_pin: "1234"
```

---

### ev9_submit_otp.sh

**Purpose:** Submits OTP code to complete the Kia UVO config flow.

**Usage:**
```bash
ev9_submit_otp.sh <ha_token> <flow_id> <otp_code>
```

**Parameters:**
- `ha_token` - Home Assistant long-lived access token
- `flow_id` - Config flow ID from ev9_recovery_with_otp.sh
- `otp_code` - 6-digit OTP code from Kia email

**Output:**
- On success: Returns `SUCCESS`
- On failure: Returns `ERROR: <message>`

**What it does:**
1. Submits the OTP code to the config flow endpoint
2. Verifies the integration was created successfully

---

## Home Assistant Configuration

Add to `configuration.yaml`:

```yaml
shell_command:
  ev9_recovery_start: "bash /config/scripts/ev9_recovery_with_otp.sh '{{ token }}' /config/secrets.yaml"
  ev9_submit_otp: "bash /config/scripts/ev9_submit_otp.sh '{{ token }}' '{{ flow_id }}' '{{ otp }}'"
```

---

## Deployment

```bash
# Copy to HA config directory
scp ev9_*.sh user@ha-server:/config/scripts/

# Make executable
ssh user@ha-server "chmod +x /config/scripts/ev9_*.sh"
```

---

## Testing

### Test recovery script (WARNING: will delete/recreate integration!)

```bash
# Get your HA token
TOKEN="your_long_lived_token"

# Run recovery (this will request an OTP email)
docker exec homeassistant bash /config/scripts/ev9_recovery_with_otp.sh "$TOKEN" /config/secrets.yaml
# Returns: flow_id (e.g., "a1b2c3d4e5f6...")
```

### Test OTP submission

```bash
# After receiving OTP email
FLOW_ID="a1b2c3d4e5f6..."
OTP="123456"

docker exec homeassistant bash /config/scripts/ev9_submit_otp.sh "$TOKEN" "$FLOW_ID" "$OTP"
# Returns: SUCCESS or ERROR
```

---

## Kia Connect API Flow

The scripts interact with Home Assistant's config entry API to navigate Kia's multi-step authentication:

```
POST /api/config/config_entries/flow
  {"handler": "kia_uvo"}
  → Returns flow_id, step_id: "user"

POST /api/config/config_entries/flow/{flow_id}
  {"region": 3, "brand": 1}
  → step_id: "credentials_password"

POST /api/config/config_entries/flow/{flow_id}
  {"username": "...", "password": "...", "pin": "..."}
  → step_id: "select_otp_method"

POST /api/config/config_entries/flow/{flow_id}
  {"method": "EMAIL"}
  → step_id: "enter_otp"
  → Kia sends OTP to email

POST /api/config/config_entries/flow/{flow_id}
  {"otp": "123456"}
  → type: "create_entry" (success!)
```

---

## Error Handling

Both scripts log to stderr with timestamps and return structured output to stdout.

**Common errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| `Could not read credentials` | Missing/invalid secrets.yaml | Check kia_username, kia_password, kia_pin |
| `Could not start config flow` | HA API unreachable | Check HA is running, token is valid |
| `Credentials step failed` | Wrong Kia credentials | Verify in Kia Connect app first |
| `OTP request failed` | Kia servers issue | Wait and retry |
| `OTP submission failed` | Invalid/expired OTP | Request new OTP |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.4 | 2026-01-21 | Initial release with email OTP support |
