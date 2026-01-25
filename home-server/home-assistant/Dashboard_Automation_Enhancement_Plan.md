# Home Assistant Enhancement Plan: Dashboards & Logic

**Date:** January 23, 2026
**Focus:** Conciseness, Robustness, and Missing Functionality

## 1. Executive Summary
Your system has evolved into distinct "design generations." 
- **Gen 1 (Homelab):** Dense, data-heavy, scrolling lists. Functional but high cognitive load.
- **Gen 2 (Daikin):** Educational, utilizing "Explainers" and high-density graphs. Excellent for deep dives.
- **Gen 3 (Kia EV9 / Jose):** **The Gold Standard.** Tabbed interfaces (Main/Config/Logs), Intent-Driven hierarchy ("Observe -> Act"), and responsive layouts.

**Goal:** Elevate all dashboards to "Gen 3" standards and implement "Exception-Based" monitoring to reduce noise.

---

## 2. Dashboard Design Strategy (The "Gen 3" Standard)

**Core Principle:** "Don't show me everything. Show me what matters."

### Standard Template for All Dashboards
1.  **Status Header (The "Glance"):**
    *   Top 10% of screen.
    *   Key KPIs only (Temp, Status, Battery, Error Count).
    *   *Design:* `tile` cards or `custom:button-card` with color-coded state.
2.  **Primary Actions (The "Controls"):**
    *   Big, tap-friendly targets.
    *   Immediate feedback (visual change).
    *   *Design:* `grid` card (2 columns mobile, 4 columns desktop).
3.  **Context (The "Graphs"):**
    *   Historical trend (last 24h).
    *   *Design:* `custom:mini-graph-card` or `apexcharts` (clean, minimal chrome).
4.  **Configuration Toggles (The "Fold"):**
    *   Hidden by default or moved to a "Config" tab.
    *   *Design:* `conditional` cards or separate Lovelace Views.

---

## 3. High-Value Functional Gaps & Additions

### 3.1 Homelab: From "Data Dump" to "Health Center"
**Current:** Shows CPU/RAM for every single container.
**Problem:** To find a problem, you have to read every number.
**Proposed Enhancement:** **"Exception-Based" Monitoring.**
*   **Feature:** "System Health" Traffic Light.
    *   **Green:** All systems nominal.
    *   **Yellow:** High resource usage (>90%) or Warnings.
    *   **Red:** Container down or Critical Error.
*   **Feature:** "Problem Child" Card.
    *   Using `auto-entities` (HACS), dynamically list *only* containers that are currently consuming >50% CPU or are Offline. If everything is fine, this card is empty (invisible).
*   **Feature:** Backup Age Monitor.
    *   Alert if last backup > 24 hours.

### 3.2 Patio AC: "Comfort" vs "Temperature"
**Current:** Controls based on raw Temp/Humidity.
**Problem:** 75°F at 40% humidity feels different than 75°F at 80%.
**Proposed Enhancement:** **Dew Point / Thermal Comfort.**
*   **Feature:** "Thermal Comfort" Sensor (Template).
    *   Calculates "Feels Like" based on humidity.
    *   Automation: "Turn on AC if Feels Like > 80°F" (more efficient than raw temp).
*   **Feature:** "Window Open" Opportunity.
    *   Compare Outdoor vs Indoor Dew Point.
    *   Notification: "It's nice outside! Open windows to save energy."

### 3.3 Vacuum (Jose): Maintenance Prediction
**Current:** Shows sensor lifespan %.
**Problem:** Reactive. You check it when it fails.
**Proposed Enhancement:** **Proactive Maintenance.**
*   **Feature:** "Bin Full" Probability.
    *   Track `sqft_cleaned` since last empty.
    *   Alert: "Bin likely full (cleaned 500 sqft)."
*   **Feature:** Zone Presets.
    *   Add "Quick Clean" buttons for high-traffic areas (Kitchen, Entryway) directly to the main view (bypassing the map selection).

### 3.4 System-Wide: The "Meta-Dashboard" (Admin Only)
**Missing:** A single view that answers "Is my Smart Home healthy?"
**Proposed Enhancement:** **Admin / Health View.**
*   **Dead Node Hunter:** List all entities with state `unavailable` or `unknown` for > 24h.
*   **Battery Triage:** List all battery devices < 15%, sorted by lowest first.
*   **Error Trap:** Show count of "Error" log entries in the last hour.
*   **Update Manager:** List pending HACS / Core updates.

---

## 4. Automation Logic Refactor Plan

**Current Issue:** `automations/configuration.yaml` is a 2,900-line monolith containing legacy logic that likely conflicts with your new Packages.

### 4.1 The "Migration & Murder" Strategy
1.  **Inventory:** Identify every active automation in the monolith.
2.  **Migrate:** Move valid logic to domain-specific packages (`packages/dawarich/`, `packages/plex/`).
3.  **Modernize:** Refactor legacy "State Machine" input_selects into modern `trigger_id` + `choose` blocks.
4.  **Murder:** Delete `automations/configuration.yaml`.

### 4.2 Robustness Upgrades (The "Dead Man" Pattern)
**Problem:** If HA crashes while a device is "On", it might stay "On" forever.
**Solution:**
*   **Time-Limited Actions:** For high-stakes devices (Heaters, Fill Valves), always use a `wait_for_trigger` with a `timeout` that triggers a "Safety Off" action.
*   **Self-Healing:** Run a "State Check" automation on HA Startup (`homeassistant.start`).
    *   *Example:* "If Sun is Down AND Outdoor Lights are Off -> Turn On."

---

## 5. Implementation Roadmap

### Phase 1: Clean Up & Consolidate (High Impact, Low Risk)
1.  **Refactor Homelab Dashboard:** Implement `auto-entities` to hide healthy containers.
2.  **Create "Health" View:** Build the Battery/Unavailable entity tracker.
3.  **Kill the Monolith:** Begin migrating `automations/configuration.yaml` logic to packages.

### Phase 2: Intelligence Upgrades
4.  **Patio AC Comfort Logic:** Implement Dew Point sensors and automation logic.
5.  **Vacuum Zone Presets:** Script specific zone coordinates for "Kitchen Clean" button.

### Phase 3: Visual Polish
6.  **Apply "Gen 3" Style:** Update `dashboard_room` and `notifications` to match the Kia/Jose aesthetic (Stack-in-cards, clean typography).

---

**Recommendation:** Start with **Phase 1, Step 3 (Kill the Monolith)**. The "Split-Brain" config identified in the audit is the biggest threat to robustness. Once the logic is clean, the dashboards will inherently become more reliable.
