# **CLAUDE.md - Home Assistant Engineering Playbook + Production Packages Migration Plan (Single Source of Truth)**

Last updated: 2026-01-23

This is the **root (parent HA folder) single source of truth** for how Codex / Claude Code must create and update Home Assistant dashboards, automations, scripts, helpers, and configuration with **zero regressions**.

This document contains:

- **Engineering Playbook (Best Practices + Workflow Gates)**
- **Production-Only Packages Migration Implementation Plan** (rewritten and cleaned)

No staging/sandbox/test environment is used. All changes happen in **production** with strict verification gates.

## **0) Non-Negotiables (Operating Contract)**

### **0.1 Definition of Done (DoD)**

A change is NOT "done" until ALL are true:

**Config + runtime**

- Configuration validation passes (UI check + CLI check where possible).
- No new repeating Home Assistant log errors attributable to the change.
- Any modified automation/script has at least one successful post-change TRACE or deliberate test run.

**UI + usability**

- Dashboard changes verified at mobile/tablet/desktop breakpoints with no layout regressions.
- Any "log/status/history" shown on dashboards is **READ-ONLY** (no editable inputs unless explicitly intended).
- Any table-like display has **aligned headers/rows** across breakpoints and after refresh.

**Rollback**

- Rollback path exists: HA backup reference + git commit hash (and revert instructions).

### **0.2 Execution Rules (How the agent must work)**

- No assumptions. Inspect current state before planning edits.
- One step at a time. Provide exactly **one** actionable step, then stop.
- Wait for confirmation. Do not proceed without user-provided output/logs/screenshots.
- Commands discipline:
  - Every command in its own fenced block.
  - First command in any sequence is always pwd.
  - Always show the working directory before acting.

### **0.3 Safety Rules**

- Prefer reloads over restarts when safe (automation/script/template reload).
- Do not mix refactors and feature changes unless explicitly requested.
- Keep diffs small and reversible. Commit early, commit often.

## **1) Requirements Inheritance and Discovery (Mandatory)**

### **1.1 Repo Root and Per-Project Requirements**

- This file lives at repo root as: CLAUDE.md.
- Each project/dashboard folder MUST contain a requirements file named exactly:
  - REQUIREMENTS.md (preferred) OR
  - requirements.md (acceptable)

Optional (per project):

- ENTITIES.md (entity IDs/services contracts)
- ACCEPTANCE.md (explicit pass/fail checks)
- CHANGELOG.md (human-readable history)

### **1.2 Nearest-Requirements Rule (Prevents Wrong Scope)**

Define **Project Root** as the nearest directory at or above the working directory that contains REQUIREMENTS.md or requirements.md, stopping at repo root.

If no requirements file exists before repo root:

- STOP and request the intended project folder + requirements file.

### **1.3 Mandatory Start-of-Task Algorithm**

Before planning or editing ANYTHING, the agent MUST run and report outputs for:

pwd  
git rev-parse --show-toplevel  

Then the agent MUST:

- Read \${REPO_ROOT}/CLAUDE.md (this file)
- Locate and read the nearest ./REQUIREMENTS.md or ./requirements.md (walking upward from pwd)
- If missing, STOP and request it (or create only if explicitly authorized)

## **2) Minimum State Capture (Before Planning Changes)**

### **2.1 Always (repo hygiene)**

pwd  
git status  
pwd  
git diff --stat  

### **2.2 Production HA health (containerized HA)**

pwd  
ssh byrro@192.168.1.11  
pwd  
docker ps --format "table {{.Names}}\\t{{.Image}}\\t{{.Status}}"  
pwd  
docker exec -it homeassistant /usr/local/bin/hass --script check_config -c /config  
pwd  
docker logs --tail 250 homeassistant  

### **2.3 Dashboard source-of-truth (prevents split-brain)**

The agent must explicitly confirm whether the dashboard config is:

- UI storage, or
- YAML mode (file path in repo)

Evidence required (pick one):

- The YAML file path + content excerpt, OR
- UI raw config export pasted, OR
- The repo file containing the dashboard YAML

## **3) Architecture Standards (Robust, Conflict-Aware, Low Regression)**

### **3.1 Packages as Feature Isolation**

Use Home Assistant Packages so each feature is self-contained.

Skeleton:

\# packages/&lt;domain&gt;\_&lt;feature&gt;.yaml  
homeassistant:  
customize: {}  
<br/>input_boolean: {}  
input_number: {}  
input_datetime: {}  
<br/>template: \[\]  
<br/>automation: \[\]  
script: \[\]  

Rules:

- Every automation/script has a stable unique id.
- Helpers and entities use domain prefixes: ev9_\*, patio_ac_\*, iaq_\*, etc.
- No duplicate entity IDs or duplicate unique_id across files.

### **3.2 Holistic Conflict Assessment (Required)**

Before edits, produce an Impact Map:

- Devices affected
- Entities affected (helpers/sensors/scripts/automations)
- Competing controllers (multiple automations controlling same device)
- Integration constraints (official vs HACS limitations)
- Dashboard views affected

If multiple automations can command the same device:

- Define precedence and guard conditions explicitly.

## **4) Automation Engineering Standards (Stable, Observable, Testable)**

### **4.1 Core Principles**

- Idempotent actions (safe if run twice).
- Explicit concurrency (mode chosen intentionally).
- Debounce + hysteresis to prevent flapping:
  - for: on triggers
  - deadbands for numeric thresholds
  - cooldown timers / "last_run" guards
- Separate "decide" vs "actuate" when complex.

### **4.2 Required Fields (Every automation)**

automation:  
\- id: "domain_feature_action"  
alias: "Domain - Feature - Action"  
description: "Purpose + constraints + concurrency assumptions."  
mode: restart  
max_exceeded: silent  
trigger: \[\]  
condition: \[\]  
action: \[\]  

### **4.3 Calculate-Only Test Harness (Required for complex logic)**

script:  
domain_calculate_only:  
alias: "Domain - Calculate Only"  
mode: single  
sequence:  
\- variables:  
outside_temp: "{{ states('sensor.outdoor_temperature') | float(0) }}"  
target_temp: "{{ states('input_number.domain_target_temp') | float(70) }}"  
delta: "{{ (outside_temp - target_temp) | abs }}"  
\- stop: "Calculated"  
response_variable: result  

### **4.4 Post-Change Validation (Required)**

- Config check passes.
- At least one trace/test run completes.
- Logs show no new repeating errors.

## **5) Dashboard Engineering Standards (Beautiful, Compact Where Needed, Deep Where Needed)**

### **5.1 UX Hierarchy: Observe → Understand → Act**

- **Observe**: key states, trends, warnings
- **Understand**: last decision, why it ran, next run, constraints
- **Act**: safe controls; advanced tuning behind tabs/subviews

### **5.2 "Finicky UI" Avoidance Rules**

Avoid:

- Fake tables made from multiple cards aligned in grids
- Multiple markdown cards acting as columns
- Editable text surfaces for operational output

Prefer:

- Single-surface cards for structured output
- Predictable responsive layout patterns

### **5.3 Read-Only Logs Rule (Hard Requirement)**

If it looks like a log/history/status stream, it must be READ-ONLY.

Hard bans for display:

- Text input cards
- Editable helpers presented as log surfaces

Allowed:

- Markdown card rendering template sensors (read-only)
- Entities card with simple-entity rows (read-only)
- Logbook/Activity cards (read-only)
- A single table card for multi-row operational history (read-only)

## **6) Tables That Never Break (Aligned Headers/Rows)**

### **6.1 Why "tables" break**

- Columns created by separate cards (drifts at breakpoints)
- Proportional fonts + wrapping differences
- Padding/margins differ across cards

### **6.2 Only Acceptable Table Approaches**

- **Option A (preferred, dynamic):** flex-table-card
  - Single card controls header + rows + alignment
  - Repository: <https://github.com/custom-cards/flex-table-card>
- **Option B (small/static):** Markdown table
  - Small row count
  - Short cells (no wrapping); truncate long values

### **6.3 Table Acceptance Tests (Must pass)**

- Desktop: aligned after refresh
- Mobile: aligned OR consistently stacked by design (no drifting columns)
- Header widths match row widths
- Rows do not disappear while header remains

## **7) Chrome Dev MCP UI Validation (Required)**

The agent must validate dashboards like a user:

- Open dashboard in Chrome via MCP tools
- Verify breakpoints:
  - Mobile ~390px
  - Tablet ~768px
  - Desktop >=1200px
- Confirm:
  - No console errors
  - No layout shifting after refresh
  - Logs are not editable
  - Tables align header/rows consistently

Evidence required:

- Screenshot per breakpoint
- Console output if warnings/errors appear

## **8) Git + Backup Discipline (Regression Control)**

### **8.1 Before any edits (mandatory)**

- Home Assistant backup created and documented (slug/time).
- Repo clean or checkpoint commit exists.
- Baseline config check and baseline log tail captured.

### **8.2 During edits**

- One logical change per commit
- Commit message: (&lt;domain&gt;) &lt;short summary&gt;

### **8.3 After each task**

Provide rollback steps:

- Git: git revert &lt;hash&gt;
- HA: restore backup reference + restart

# **PART B - Production Packages Migration Implementation Plan (Cleaned, Production Only)**

## **9) Objective and End State**

### **9.1 Objective**

Migrate all HA projects from scattered "versioned patch files" into a unified Packages architecture, eliminating split-brain config and maintenance debt, while addressing the known audit bugs (BUG-1..BUG-6) and eliminating dashboard finickiness (editable logs, misaligned tables).

### **9.2 Known Audit Bugs (Must be fixed)**

| **ID** | **Issue** | **Severity** | **Required Fix Outcome** |
| --- | --- | --- | --- |
| **BUG-1** | sensor.patio_ac_next_evaluation NotImplementedError | HIGH | Sensor renders without exceptions; no NotImplementedError in logs |
| --- | --- | --- | --- |
| **BUG-2** | script.patio_ac_control continues after wait_template timeout | CRITICAL | Script detects timeout, notifies, cleans up, and hard-stops |
| --- | --- | --- | --- |
| **BUG-3** | Duplicate unique_id plex_priority_status | MEDIUM | Only one unique_id remains; no duplicate warnings |
| --- | --- | --- | --- |
| **BUG-4** | Threshold validation ping-pong | HIGH | Add deadband + debounce; no thrashing loops |
| --- | --- | --- | --- |
| **BUG-5** | Hard-coded climate.150633095083490_climate | HIGH | Rename to climate.patio_ac and update all references |
| --- | --- | --- | --- |
| **BUG-6** | Recorder oversized attributes warnings | MEDIUM | Exclude or truncate; warnings stop repeating |
| --- | --- | --- | --- |

## **10) Production Execution Gate (Run before Phase 1)**

Purpose: lock down where production config lives and capture a baseline.

pwd  
ssh byrro@192.168.1.11  
pwd  
docker ps --format "table {{.Names}}\\t{{.Image}}\\t{{.Status}}"  
pwd  
docker exec -it homeassistant /usr/local/bin/hass --script check_config -c /config  
pwd  
docker logs --tail 250 homeassistant  

**Acceptance:**

- Config check passes
- Baseline log tail captured (for comparison)

## **11) Phase 1 - Enable Packages in Production (Foundation)**

### **Task 1.1 - Enable packages include**

**Files (production):**

- /config/configuration.yaml
- /config/packages/ (directory)

**Steps:**

pwd  
ssh byrro@192.168.1.11  
pwd  
cp /mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml \\  
/mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml.bak-\$(date +%Y%m%d-%H%M%S)  
pwd  
grep -n "homeassistant:" -n /mnt/ByrroServer/docker-data/homeassistant/config/configuration.yaml | head -50  

**Edit requirement (ensure under homeassistant:):**

homeassistant:  
packages: !include_dir_named packages  

pwd  
mkdir -p /mnt/ByrroServer/docker-data/homeassistant/config/packages  

**Validate:**

pwd  
docker exec -it homeassistant /usr/local/bin/hass --script check_config -c /config  

**Apply:**

pwd  
docker exec homeassistant ha core restart  

**Acceptance:**

- Restart clean
- No new repeating log errors

## **12) Phase 2 - Entity ID Standardization (Fix BUG-5)**

### **Task 2.1 - Rename patio climate entity to semantic ID**

**Rename:**

- From: climate.150633095083490_climate
- To: climate.patio_ac

**Steps:**

- Perform rename via HA UI (Settings → Devices & Services → Entities).
- Verify via API:

pwd  
curl -s \[<http://192.168.1.11:8123/api/states/climate.patio_ac\>](<http://192.168.1.11:8123/api/states/climate.patio_ac>) \\  
\-H "Authorization: Bearer \$HA_TOKEN" | jq '.state'  

**Acceptance:**

- New ID exists and returns state
- Old ID is no longer referenced in active YAML after migration phases

## **13) Phase 3 - Prometheus Consolidation into Package (Homelab)**

### **Task 3.1 - Extract prometheus sensors from monolithic config**

**Files (production):**

- Create: /config/packages/homelab/prometheus.yaml
- Modify: /config/configuration.yaml (remove extracted blocks)

**Steps:**

pwd  
ssh byrro@192.168.1.11  
pwd  
mkdir -p /mnt/ByrroServer/docker-data/homeassistant/config/packages/homelab  

**Implementation requirements:**

- Move prometheus sensor definitions into /mnt/ByrroServer/docker-data/homeassistant/config/packages/homelab/prometheus.yaml.
- Remove the same blocks from configuration.yaml to avoid split-brain.

**Validate:**

pwd  
docker exec -it homeassistant /usr/local/bin/hass --script check_config -c /config  

**Apply:**

pwd  
docker exec homeassistant ha core restart  

**Verify a representative sensor:**

pwd  
curl -s \[<http://192.168.1.11:8123/api/states/sensor.vm_cpu_usage\>](<http://192.168.1.11:8123/api/states/sensor.vm_cpu_usage>) \\  
\-H "Authorization: Bearer \$HA_TOKEN" | jq '.state'  

**Acceptance:**

- Sensors exist and update
- No new prometheus errors

## **14) Phase 4 - Patio AC Migration to Packages + Bug Fixes**

### **Task 4.1 - Create single consolidated package: /config/packages/patio_ac/patio_ac.yaml**

**Files (production):**

- Create: /config/packages/patio_ac/patio_ac.yaml

**Steps:**

pwd  
ssh byrro@192.168.1.11  
pwd  
mkdir -p /mnt/ByrroServer/docker-data/homeassistant/config/packages/patio_ac  

**Implementation requirements:**

- Consolidate helpers + scripts + automations + template sensors into one package.
- Replace ALL references: climate.150633095083490_climate → climate.patio_ac.
- During consolidation, implement fixes for:
  - **BUG-2** (script timeout handling)
  - **BUG-4** (deadband + debounce for validation)
- Ensure all automation/script IDs are stable and unique.

**Validate:**

pwd  
docker exec -it homeassistant /usr/local/bin/hass --script check_config -c /config  

**Apply:**

pwd  
docker exec homeassistant ha core restart  

**Acceptance:**

- Package loads; HA restarts cleanly
- Patio AC entities present
- Patio AC automations load (expected count)

### **Task 4.2 - Remove Patio AC from legacy sources (eliminate split-brain)**

**Files (production):**

- configuration.yaml
- automations.yaml
- scripts.yaml
- any versioned patch files currently included/merged

**Implementation requirements:**

- After package is confirmed loaded, remove/disable the legacy definitions so only the package remains authoritative.

**Validate + apply:**

pwd  
docker exec -it homeassistant /usr/local/bin/hass --script check_config -c /config  
pwd  
docker exec homeassistant ha core restart  

**Acceptance:**

- No duplicates/conflicts
- No missing entities after removal

### **Task 4.3 - Fix BUG-1: patio_ac_next_evaluation NotImplementedError**

**Implementation requirements:**

- Remove unsupported template operations that trigger NotImplementedError.
- Implement using supported timestamp math/filters (avoid unsupported timedelta patterns).

**Validate:**

pwd  
docker logs --tail 300 homeassistant | grep -i "notimplemented" || true  

**Acceptance:**

- No NotImplementedError after restart
- Sensor renders consistently

### **Task 4.4 - Fix BUG-2: patio_ac_control wait_template timeout handling**

**Implementation requirements (after every wait_template):**

- Detect timeout (wait.completed == false)
- Notify (persistent_notification or other)
- Cleanup any "expected signature" state
- Hard stop (stop:)

**Acceptance:**

- In forced-timeout scenario, script stops and signals failure (no false success)

### **Task 4.5 - Fix BUG-4: Threshold validation ping-pong**

**Implementation requirements:**

- Add deadband (e.g., 0.5) + debounce
- Use mode: restart where appropriate
- Prevent alternating updates due to rounding

**Acceptance:**

- Rapid slider changes do not cause loops/thrashing
- Logs remain clean

### **Task 4.6 - Patio AC dashboard hygiene (read-only logs + aligned tables)**

**Implementation requirements:**

- Replace editable log surfaces with read-only surfaces.
- Replace fake tables with one stable table surface (flex-table-card preferred).
- Validate via Chrome Dev MCP breakpoints and after refresh.

**Acceptance:**

- No log area is editable
- Tables align headers/rows across breakpoints

## **15) Phase 5 - Kia EV9 Migration to Packages**

### **Task 5.1 - Create /config/packages/kia_ev9/kia_ev9.yaml**

**Files (production):**

- Create: /config/packages/kia_ev9/kia_ev9.yaml

**Implementation requirements:**

- Consolidate EV9 helpers/automations/scripts into one package.
- Preserve IDs unless explicitly renamed and documented in project REQUIREMENTS.md.
- Organize sections by domain: Charging, Climate, Security, Watchdog.
- Validate key flows with traces and UI checks.

**Validate + apply:**

pwd  
docker exec -it homeassistant /usr/local/bin/hass --script check_config -c /config  
pwd  
docker exec homeassistant ha core restart  

**Acceptance:**

- EV9 entities present
- Automations load expected count
- Dashboard renders correctly (Chrome Dev MCP breakpoints)

## **16) Phase 6 - Remaining Projects Consolidation**

### **Task 6.1 - Daikin consolidate into /config/packages/daikin/daikin.yaml**

**Acceptance:** No duplicate sensors, no unique_id collisions, UI stable.

### **Task 6.2 - Jose consolidate into /config/packages/jose/jose.yaml**

**Acceptance:** Behavior preserved, no duplicates.

### **Task 6.3 - Shared automations into a package (if currently scattered)**

**Acceptance:** No lost functionality, no duplicate automation IDs.

## **17) Phase 7 - Global Bug Fixes + Cleanup**

### **Task 7.1 - Fix BUG-3 duplicate unique_id plex_priority_status**

**Steps:**

- Locate both definitions.
- Keep canonical sensor; rename other unique_id or remove redundancy.
- Validate + restart; check logs for duplicates.

**Validate:**

pwd  
docker logs --tail 300 homeassistant | grep -i "unique_id" || true  

**Acceptance:** No duplicate unique_id warnings/errors.

### **Task 7.2 - Fix BUG-6 recorder oversized attributes**

**Implementation options:**

- Exclude entities via recorder exclude
- Or truncate attributes upstream (bounded list/size)

**Acceptance:**

- Recorder oversized-attribute warnings stop repeating
- No unintended loss of critical history

### **Task 7.3 - Archive legacy versioned files (repo only)**

**Rules:**

- Move to .archive/&lt;date&gt;-pre-packages/
- Ensure runtime is not referencing them first
- Do not delete immediately

**Acceptance:**

- Versioned patch files no longer act as active source-of-truth
- Archived files remain for reference

## **18) Final System Validation (Must Pass Before Tag)**

### **18.1 Config and logs**

pwd  
docker exec -it homeassistant /usr/local/bin/hass --script check_config -c /config  
pwd  
docker logs --tail 300 homeassistant  

### **18.2 Unavailable entities**

pwd  
curl -s \[<http://192.168.1.11:8123/api/states\>](<http://192.168.1.11:8123/api/states>) \\  
\-H "Authorization: Bearer \$HA_TOKEN" | jq '\[.\[\] | select(.state=="unavailable")\] | .\[\].entity_id' | head -200  

### **18.3 Automation/script counts**

pwd  
curl -s \[<http://192.168.1.11:8123/api/states\>](<http://192.168.1.11:8123/api/states>) \\  
\-H "Authorization: Bearer \$HA_TOKEN" | jq '\[.\[\] | select(.entity_id|startswith("automation."))\] | length'  
pwd  
curl -s \[<http://192.168.1.11:8123/api/states\>](<http://192.168.1.11:8123/api/states>) \\  
\-H "Authorization: Bearer \$HA_TOKEN" | jq '\[.\[\] | select(.entity_id|startswith("script."))\] | length'  

### **18.4 UI regression validation (Chrome Dev MCP)**

**Dashboards:** Patio AC, Kia EV9, Homelab, Daikin. **Breakpoints:** Mobile ~390px, Tablet ~768px, Desktop >=1200px. **Pass criteria:**

- No console errors
- No layout shifting after refresh
- Logs are read-only
- Tables align headers/rows consistently

## **19) Documentation + Release**

### **19.1 Migration completion report**

**File:** docs/MIGRATION_COMPLETE.md **Include:**

- Before/after structure summary
- Package structure tree
- Audit bug fixes list + evidence pointers (log snippets, trace confirmations)
- Any known follow-ups

### **19.2 Release tag**

pwd  
cd /Users/andrebyrro/Dev/home-server/home-assistant  
pwd  
git tag -a ha-packages-v1.0 -m "Production migration to HA Packages complete  
<br/>Includes:  
\- Packages enabled and adopted across projects  
\- Patio AC migrated + BUG-1/2/4/5 addressed  
\- EV9 migrated  
\- Prometheus extracted  
\- Duplicate unique_id fixed (BUG-3)  
\- Recorder oversized attributes mitigated (BUG-6)  
\- UI validated via Chrome Dev MCP breakpoints  
"  
pwd  
git push origin ha-packages-v1.0  

## **20) Reference URLs (Implementation Guidance)**

- <https://www.home-assistant.io/docs/configuration/packages/>
- <https://www.home-assistant.io/docs/tools/check_config/>
- <https://www.home-assistant.io/dashboards/>
- <https://www.home-assistant.io/dashboards/entities/>
- <https://www.home-assistant.io/dashboards/markdown/>
- <https://www.home-assistant.io/dashboards/logbook/>
- <https://github.com/custom-cards/flex-table-card>

END