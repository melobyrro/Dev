# Constitutional Compliance Fixes - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical constitutional violations in Home Assistant automations and scripts to ensure robustness, self-healing, and fail-safe behavior

**Architecture:** Replace naked delays with bounded waits, convert event triggers to state triggers, add idempotency guards, implement deadline helpers for long waits

**Tech Stack:** Home Assistant YAML (automations, scripts, helpers), Constitutional patterns from `/Users/andrebyrro/Dev/home-server/home-assistant/CLAUDE.md`

**Code Review Source:** `/Users/andrebyrro/.claude/plans/enumerated-leaping-nova-agent-ab429f1.md`

---

## Phase 1: Critical Fixes (Must Do)

### Task 1: Create Deadline Helper for Precondition Long Delays

**Files:**
- Create: `kia-ev9/helpers.v2.9.yaml` (copy from v2.8, add deadline helper)
- Modify: `kia-ev9/automations.v2.7.yaml:647-815` (precondition automation - will become v2.8)

**Step 1: Add deadline helper to helpers file**

```yaml
# Add to helpers.v2.9.yaml in input_datetime section
input_datetime:
  ev9_climate_deadline:
    name: "EV9: Next Climate Start Time"
    has_date: true
    has_time: true
```

**Step 2: Update package.yaml to use new helpers version**

Modify: `kia-ev9/package.yaml`

```yaml
# Change helpers include
# FROM:
# !include helpers.v2.8.yaml
# TO:
!include helpers.v2.9.yaml
```

**Step 3: Test helper creation**

Run: `cd /Users/andrebyrro/Dev/home-server/home-assistant && git add . && git commit -m "test: Add climate deadline helper"`
Expected: GitOps hook triggers deployment, verify via logs

**Step 4: Verify helper deployed**

Run: `ssh byrro@192.168.1.11 "grep -A 3 'ev9_climate_deadline' /mnt/ByrroServer/docker-data/homeassistant/config/kia-ev9/helpers.v2.9.yaml"`
Expected: New `input_datetime.ev9_climate_deadline` entity appears in deployed config

**Step 5: Commit**

```bash
git add kia-ev9/helpers.v2.9.yaml kia-ev9/package.yaml
git commit -m "feat(kia-ev9): Add climate deadline helper for constitutional compliance"
```

---

### Task 2: Replace Precondition Naked Delay with Deadline Helper

**Files:**
- Modify: `kia-ev9/automations.v2.7.yaml:778-786` (delay block - will rename to v2.8 on commit)

**Step 1: Replace delay with deadline storage**

```yaml
# BEFORE (lines 778-786):
    - choose:
        - conditions:
            - condition: template
              value_template: "{{ delay_seconds | int > 0 }}"
          sequence:
            - delay:
                seconds: "{{ delay_seconds }}"

# AFTER:
    # Compute and store deadline instead of blocking delay
    - variables:
        deadline_datetime: >
          {% set dep_str = departure_time_str | trim %}
          {% set dep_time = today_at(dep_str) %}
          {% set start = dep_time - timedelta(minutes=runtime_minutes | int) %}
          {{ start.strftime('%Y-%m-%d %H:%M:%S') }}

    - service: input_datetime.set_datetime
      target:
        entity_id: input_datetime.ev9_climate_deadline
      data:
        datetime: "{{ deadline_datetime }}"

    - service: python_script.shift_event_log
      data:
        entity_prefix: input_text.ev9_event
        max_events: 10
        new_event: >
          {{ now().strftime('%H:%M') }} - PRECONDITION_SCHEDULED: Will start climate at {{ start_time_str }}

    # Stop here - separate time-triggered automation will handle actual start
    - stop: "Deadline stored, climate will start via time trigger"
```

**Step 2: Create new time-triggered automation**

Add new automation to `automations.v2.7.yaml`:

```yaml
- id: ev9_precondition_execute
  alias: "EV9: Execute Scheduled Pre-conditioning"
  description: "Starts climate when deadline helper reaches target time (survives HA restarts)"
  trigger:
    - platform: time
      at: input_datetime.ev9_climate_deadline
  condition:
    # Verify deadline is today and in past/now (not accidentally set to tomorrow)
    - condition: template
      value_template: >
        {% set deadline = states('input_datetime.ev9_climate_deadline') %}
        {% set deadline_dt = strptime(deadline, '%Y-%m-%d %H:%M:%S') %}
        {{ deadline_dt.date() == now().date() and deadline_dt <= now() }}
    # Climate must not already be running
    - condition: state
      entity_id: binary_sensor.ev9_air_conditioner
      state: "off"
  action:
    - variables:
        target_temp: "{{ states('input_number.ev9_target_temperature') | float(72) }}"
        device_id: "{{ states('input_text.ev9_device_id') }}"

    - service: kia_uvo.start_climate
      data:
        device_id: "{{ device_id }}"
        climate: true
        temperature: "{{ target_temp | int }}"
      continue_on_error: true

    - service: python_script.shift_event_log
      data:
        entity_prefix: input_text.ev9_event
        max_events: 10
        new_event: "{{ now().strftime('%H:%M') }} - PRECONDITION_START: Climate started via deadline trigger"

    - service: notify.mobile_app_andre_iphone
      data:
        title: "EV9 Pre-conditioning Started"
        message: "Climate started at scheduled deadline"
  mode: single
```

**Step 3: Rename to v2.8 and test**

Run:
```bash
cd /Users/andrebyrro/Dev/home-server/home-assistant/kia-ev9
mv automations.v2.7.yaml automations.v2.8.yaml
# Update package.yaml include reference
sed -i '' 's/automations.v2.7.yaml/automations.v2.8.yaml/' package.yaml
```

**Step 4: Test configuration via GitOps**

Commit will trigger auto-deploy via hook, monitor for errors

**Step 5: Verify with trace**

1. Set test schedule for 5 minutes in future
2. Wait for evaluation trigger
3. Check `input_datetime.ev9_climate_deadline` matches expected time
4. Check automation trace shows "Deadline stored" stop
5. Wait for deadline trigger
6. Verify climate starts

Expected: Two-phase execution works, survives HA restart during delay window

**Step 6: Commit and deploy**

```bash
git add kia-ev9/automations.v2.8.yaml kia-ev9/package.yaml
git commit -m "fix(kia-ev9): Replace naked delay with deadline helper (C-6 constitutional fix)

BEFORE: 30+ min delay blocked automation, died on HA restart
AFTER: Deadline helper + separate time trigger, survives restarts

Constitutional compliance: Section 4.3 Robust Waits"
```

---

### Task 3: Replace Naked Delays with Bounded Waits in Climate Script

**Files:**
- Modify: `kia-ev9/scripts.v2.6.yaml:34-142` (ev9_start_climate_with_timer)

**Step 1: Replace first delay with bounded wait**

```yaml
# BEFORE (lines 58-69):
    - delay:
        seconds: 45
    - service: kia_uvo.force_update
      data:
        device_id: "{{ device_id }}"
    - delay:
        seconds: 90

# AFTER:
    - wait_for_trigger:
        - platform: state
          entity_id: binary_sensor.ev9_air_conditioner
          to: "on"
      timeout: "00:01:30"
      continue_on_timeout: true

    - choose:
        - conditions: "{{ not wait.completed }}"
          sequence:
            - service: kia_uvo.force_update
              data:
                device_id: "{{ device_id }}"
              continue_on_error: true
            - wait_for_trigger:
                - platform: state
                  entity_id: binary_sensor.ev9_air_conditioner
                  to: "on"
              timeout: "00:01:00"
              continue_on_timeout: true
```

**Step 2: Add timeout handler with logging**

```yaml
# After first attempt verification (lines 72-92)
    - choose:
        - conditions: "{{ wait.completed }}"
          sequence:
            # SUCCESS - start timer and notify
            - service: timer.start
              data:
                duration: "{{ duration_min * 60 }}"
              target:
                entity_id: timer.ev9_climate_timer
            - service: python_script.shift_event_log
              data:
                entity_prefix: input_text.ev9_event
                max_events: 10
                new_event: "{{ now().strftime('%H:%M') }} - CLIMATE_SUCCESS: Climate verified running, {{ target_temp }}°F"
            - service: notify.mobile_app_andre_iphone
              data:
                title: "EV9 Climate Started"
                message: "Climate confirmed running. Target: {{ target_temp }}°F, Timer: {{ duration_min }} min"
        - conditions: "{{ not wait.completed }}"
          sequence:
            - service: persistent_notification.create
              data:
                title: "EV9 Climate Start Timeout"
                message: "Climate did not start after 2.5 minutes (attempt 1). Retrying..."
            # Continue to retry block
```

**Step 3: Fix retry block delays**

```yaml
# BEFORE retry (lines 100-111):
        - service: kia_uvo.start_climate
          data:
            device_id: "{{ device_id }}"
            climate: true
            temperature: "{{ target_temp }}"
        - delay:
            seconds: 120
        - service: kia_uvo.force_update
          data:
            device_id: "{{ device_id }}"
        - delay:
            seconds: 90

# AFTER retry:
        - service: kia_uvo.start_climate
          data:
            device_id: "{{ device_id }}"
            climate: true
            temperature: "{{ target_temp }}"
          continue_on_error: true

        - wait_for_trigger:
            - platform: state
              entity_id: binary_sensor.ev9_air_conditioner
              to: "on"
          timeout: "00:03:00"
          continue_on_timeout: true

        - choose:
            - conditions: "{{ not wait.completed }}"
              sequence:
                - service: kia_uvo.force_update
                  data:
                    device_id: "{{ device_id }}"
                  continue_on_error: true
                - wait_for_trigger:
                    - platform: state
                      entity_id: binary_sensor.ev9_air_conditioner
                      to: "on"
                  timeout: "00:01:00"
                  continue_on_timeout: true
```

**Step 4: Rename to v2.7 and test**

Run:
```bash
cd /Users/andrebyrro/Dev/home-server/home-assistant/kia-ev9
mv scripts.v2.6.yaml scripts.v2.7.yaml
sed -i '' 's/scripts.v2.6.yaml/scripts.v2.7.yaml/' package.yaml
```

**Step 5: Test execution**

1. Call `script.ev9_start_climate_with_timer`
2. Watch automation trace
3. Verify bounded waits replace delays
4. Confirm timeout handlers fire if climate fails

Expected: Script waits for actual state change, not fixed time

**Step 6: Commit and deploy**

```bash
git add kia-ev9/scripts.v2.7.yaml kia-ev9/package.yaml
git commit -m "fix(kia-ev9): Replace naked delays with bounded waits (C-3 constitutional fix)

BEFORE: Fixed 45s/90s/120s delays assumed car ready
AFTER: wait_for_trigger with timeouts, verify actual state

Constitutional compliance: Section 4.6 Safe Delays"
```

---

### Task 4: Add Idempotency Guards to Climate Script

**Files:**
- Modify: `kia-ev9/scripts.v2.6.yaml:39-50` (before first climate start)

**Step 1: Add state check before climate start**

```yaml
# BEFORE (lines 40-50):
    - variables:
        target_temp: "{{ states('input_number.ev9_target_temperature') | int(72) }}"
        duration_min: "{{ states('input_number.ev9_climate_duration') | int(15) }}"
        device_id: "{{ states('input_text.ev9_device_id') }}"

    # Attempt 1: Start climate
    - service: kia_uvo.start_climate
      data:
        device_id: "{{ device_id }}"
        climate: true
        temperature: "{{ target_temp }}"

# AFTER:
    - variables:
        target_temp: "{{ states('input_number.ev9_target_temperature') | int(72) }}"
        duration_min: "{{ states('input_number.ev9_climate_duration') | int(15) }}"
        device_id: "{{ states('input_text.ev9_device_id') }}"
        is_already_running: "{{ is_state('binary_sensor.ev9_air_conditioner', 'on') }}"

    # Idempotency check - skip if already running
    - choose:
        - conditions:
            - condition: template
              value_template: "{{ is_already_running }}"
          sequence:
            - service: python_script.shift_event_log
              data:
                entity_prefix: input_text.ev9_event
                max_events: 10
                new_event: "{{ now().strftime('%H:%M') }} - CLIMATE_SKIPPED: Already running, timer started"
            - service: timer.start
              data:
                duration: "{{ duration_min * 60 }}"
              target:
                entity_id: timer.ev9_climate_timer
            - stop: "Climate already running"

    # Attempt 1: Start climate
    - service: kia_uvo.start_climate
      data:
        device_id: "{{ device_id }}"
        climate: true
        temperature: "{{ target_temp }}"
      continue_on_error: true
```

**Step 2: Test idempotency**

1. Start climate manually
2. Call script while climate is running
3. Verify script logs "SKIPPED" and exits early
4. Verify no duplicate API call

Expected: Script is safe to re-run, no API rate limit errors

**Step 3: Commit and deploy**

```bash
git add kia-ev9/scripts.v2.7.yaml
git commit -m "fix(kia-ev9): Add idempotency guard to climate script (C-4 constitutional fix)

BEFORE: Sent duplicate API calls if climate already running
AFTER: Check state before action, skip if already running

Constitutional compliance: Section 4.4 Idempotency"
```

---

### Task 5: Convert Event Triggers to State Triggers

**Files:**
- Modify: `kia-ev9/automations.v2.8.yaml:598` (ev9_climate_timer_stop - already renamed in Task 2)

**Step 1: Replace event trigger with state trigger**

```yaml
# BEFORE (line 598):
  trigger:
    - platform: event
      event_type: timer.finished
      event_data:
        entity_id: timer.ev9_climate_timer

# AFTER:
  trigger:
    - platform: state
      entity_id: timer.ev9_climate_timer
      to: "idle"
      from: "active"
```

**Step 2: Test self-healing**

1. Start timer
2. Restart HA while timer is running
3. Wait for timer to finish after restart
4. Verify automation still triggers

Expected: State-based trigger catches up after restart

**Step 3: Find other event triggers**

Run: `grep -n "platform: event" kia-ev9/automations.v2.8.yaml`

Review each event trigger:
- `mobile_app_notification_action` → Keep as event (no state alternative)
- Other timer events → Convert to state

**Step 4: Commit and deploy**

```bash
git add kia-ev9/automations.v2.8.yaml
git commit -m "fix(kia-ev9): Convert timer event triggers to state triggers (C-2 constitutional fix)

BEFORE: Event triggers missed if HA down at trigger time
AFTER: State triggers self-heal after HA restart

Constitutional compliance: Section 4.8 Self-Healing"
```

---

## Phase 2: Important Fixes (Should Do)

### Task 6: Add Mode Justification Comments

**Files:**
- Modify: All automations in `kia-ev9/automations.v2.8.yaml`

**Step 1: Add comments to each mode declaration**

```yaml
# Example pattern:
- id: ev9_charging_complete
  alias: "EV9: Charging Complete Notification"
  description: "Notify when EV9 finishes charging"
  mode: single  # Prevents notification spam if charging state flaps
```

Apply to all 20+ automations in file.

**Step 2: Commit**

```bash
git add kia-ev9/automations.v2.8.yaml
git commit -m "docs(kia-ev9): Add mode justification comments (I-3 constitutional requirement)

All mode selections now have inline comments explaining WHY

Constitutional compliance: Section 4.5 Concurrency Rules"
```

---

### Task 7: Add Error Logging to continue_on_error

**Files:**
- Modify: `kia-ev9/scripts.v2.6.yaml:100+` (retry blocks)

**Step 1: Add error detection and logging**

```yaml
# AFTER each service call with continue_on_error:
- service: kia_uvo.start_climate
  data:
    device_id: "{{ device_id }}"
    climate: true
    temperature: "{{ target_temp }}"
  continue_on_error: true
  response_variable: climate_response

# Add logging if error detected
- choose:
    - conditions:
        - condition: template
          value_template: "{{ climate_response is not defined or climate_response.failed | default(false) }}"
      sequence:
        - service: persistent_notification.create
          data:
            title: "EV9 Climate Error"
            message: "Climate start command failed - check Kia API connectivity"
        - service: python_script.shift_event_log
          data:
            entity_prefix: input_text.ev9_event
            max_events: 10
            new_event: "{{ now().strftime('%H:%M') }} - CLIMATE_ERROR: API call failed"
```

**Step 2: Commit and deploy**

```bash
git add kia-ev9/scripts.v2.7.yaml
git commit -m "fix(kia-ev9): Add error logging for continue_on_error blocks (I-4)

BEFORE: Errors silently swallowed
AFTER: Errors logged to event log and notifications

Constitutional compliance: Section 4.7 Logging"
```

---

### Task 8: Add Cooldown to Connection Watchdog

**Files:**
- Modify: `ha-config/automations.v3.0.yaml:966-989` (wyze_bridge_recover_offline)

**Step 1: Add cooldown condition**

```yaml
# AFTER trigger, BEFORE action:
  condition:
    - condition: template
      value_template: >
        {% set last = state_attr('automation.wyze_bridge_recover_offline', 'last_triggered') %}
        {{ last is none or (now() - last).total_seconds() > 1800 }}
```

**Step 2: Test cooldown**

1. Trigger automation manually
2. Try to trigger again immediately
3. Verify condition blocks second trigger
4. Wait 31 minutes
5. Verify can trigger again

Expected: 30-minute cooldown prevents spam

**Step 3: Commit**

```bash
git add ha-config/automations.v3.0.yaml
git commit -m "fix(ha-config): Add 30min cooldown to Wyze recovery (I-7)

BEFORE: Could spam restart commands if camera stays offline
AFTER: 30-minute cooldown between recovery attempts

Constitutional compliance: Section 4.6 Throttling"
```

---

## Phase 3: Verification & Cleanup

### Task 9: Run End-to-End Tests

**Files:**
- Run: `kia-ev9/qa_tests.py`

**Step 1: Run full test suite**

Run: `cd /Users/andrebyrro/Dev/home-server/home-assistant/kia-ev9 && python qa_tests.py`

Expected: All 10 tests PASS

**Step 2: Manual verification checklist**

- [ ] Precondition schedule stores deadline helper
- [ ] Precondition execute triggers at deadline time
- [ ] Climate script waits for actual state (not fixed delay)
- [ ] Climate script skips if already running
- [ ] Timer stop uses state trigger
- [ ] All automations have mode comments
- [ ] Config check passes
- [ ] No new warnings in HA logs

**Step 3: Document verification**

Add to commit message:
```
Verification:
- qa_tests.py: 10/10 PASS
- Manual testing: All critical paths verified
- HA config check: PASS
- Logs: Clean, no new warnings
```

**Step 4: Final commit**

```bash
git commit --allow-empty -m "chore(kia-ev9): Verify Phase 1 constitutional compliance fixes complete

Verified:
- C-2: State triggers replace event triggers
- C-3: Bounded waits replace naked delays
- C-4: Idempotency guards added
- C-6: Deadline helpers replace long delays
- I-3: Mode justifications documented
- I-4: Error logging added
- I-7: Wyze cooldown added

Grade improvement: D+ → B-
Ready for production"
```

---

## Rollback Plan

### Rollback Artifacts

## STEP 0: Create Rollback Artifacts (DO THIS FIRST!)

**Before implementing ANY task:**

```bash
cd /Users/andrebyrro/Dev/home-server/home-assistant

# 1. Create git baseline tag
git tag -a "baseline-constitutional-fixes-$(date +%Y%m%d-%H%M)" -m "Before constitutional compliance fixes"

# 2. Record current commit
echo "Baseline commit: $(git rev-parse HEAD)" > /tmp/constitutional-fixes-rollback.txt

# 3. Request HA backup
echo "MANUAL STEP: Create HA backup via UI at http://192.168.1.11:8123"
echo "Settings → System → Backups → Create Backup"
echo "Record backup ID in /tmp/constitutional-fixes-rollback.txt"
```

**STOP HERE** - Get backup ID from user before proceeding to Task 1

**Rollback procedures:**

| Scenario | Command |
|----------|---------|
| Single task failed | `git revert <commit_sha>` |
| All Phase 1 failed | `git reset --hard baseline-constitutional-fixes-<date>` |
| HA broken | Restore backup via HA UI |

---

## Execution Estimates

| Phase | Tasks | Effort |
|-------|-------|--------|
| Phase 1 | Tasks 1-5 | 6-8 hours |
| Phase 2 | Tasks 6-8 | 3-4 hours |
| Phase 3 | Task 9 | 1-2 hours |
| **Total** | **9 tasks** | **10-14 hours** |

---

## Success Criteria

- [ ] All 7 Critical issues (C-1 through C-7) resolved
- [ ] All 3 Important issues (I-3, I-4, I-7) resolved
- [ ] `qa_tests.py` passes 10/10
- [ ] HA config check passes
- [ ] No new warnings in HA logs
- [ ] Manual test: Precondition survives HA restart during delay window
- [ ] Manual test: Climate script is idempotent
- [ ] Constitutional compliance grade: D+ → B- (minimum)