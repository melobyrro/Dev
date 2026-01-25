# FPL Energy Integration - Functional Requirements Document

**Version**: 1.1
**Last Updated**: 2025-01-19
**Status**: Draft

---

## 1. Executive Summary

Integrate Florida Power & Light (FPL) energy data with Home Assistant to provide:
- Daily energy consumption monitoring
- Bill tracking and projections
- Usage alerts and notifications
- Integration with EV charging tracking (Kia EV9)
- Energy Dashboard visualization

---

## 2. Goals & Objectives

### Primary Goals
1. **Visibility**: See daily energy usage and costs on HA dashboard
2. **Cost Tracking**: Monitor current bill and projected end-of-month costs
3. **Alerting**: Get notified of unusual usage patterns
4. **EV Integration**: Track and attribute EV charging costs

### Success Criteria
- Daily usage data visible in HA by 6 AM each day
- Bill projections within 10% accuracy
- High usage alerts trigger reliably
- Dashboard provides at-a-glance energy status

---

## 3. Functional Requirements

### 3.1 Monitoring Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| MON-01 | Display daily energy usage (kWh) | P0 |
| MON-02 | Display current bill-to-date amount ($) | P0 |
| MON-03 | Display projected end-of-month bill ($) | P0 |
| MON-04 | Display daily average usage (kWh) | P1 |
| MON-05 | Display comparison to previous billing period | P1 |
| MON-06 | Display billing period dates | P1 |
| MON-07 | Calculate and display cost per kWh | P1 |
| MON-08 | Track month-over-month usage trends | P2 |
| MON-09 | Display temperature correlation with usage | P2 |

### 3.2 Alert Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| ALT-01 | Alert when daily usage exceeds **UI-configurable** threshold | P1 |
| ALT-02 | Alert when projected bill exceeds **UI-configurable** budget | P1 |
| ALT-03 | Alert when usage is 20%+ higher than 7-day average | P2 |
| ALT-04 | Weekly usage summary notification | P2 |
| ALT-05 | End-of-billing-period summary | P2 |

**Note**: Thresholds are user-configurable via dashboard input helpers, not hardcoded.

### 3.3 Dashboard Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| DSH-01 | Today's usage gauge with daily target | P0 |
| DSH-02 | Current bill amount with projection | P0 |
| DSH-03 | 7-day usage history graph | P1 |
| DSH-04 | Bill-to-date progress bar | P1 |
| DSH-05 | Usage comparison cards (today vs avg) | P1 |
| DSH-06 | Monthly usage calendar heatmap | P2 |
| DSH-07 | EV charging attribution card | P2 |

### 3.4 Integration Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| INT-01 | Add FPL data to HA Energy Dashboard | P0 |
| INT-02 | Create utility_meter for monthly tracking | P1 |
| INT-03 | Cross-reference with Kia EV9 charging data | P2 |
| INT-04 | Estimate EV charging costs | P2 |
| INT-05 | Support time-of-use rate calculations | P2 |

---

## 4. Non-Functional Requirements

### 4.1 Performance
- Data refresh: Daily (API limitation)
- Dashboard load: <3 seconds
- Historical data retention: 12 months minimum

### 4.2 Reliability
- Integration should handle FPL API outages gracefully
- Persist historical data locally
- Alert if data not updated for >48 hours

### 4.3 Security
- FPL credentials stored securely in HA secrets
- No credentials in version-controlled files

---

## 5. Technical Architecture

### 5.1 Integration Flow

```
FPL.com Account API
        ↓
hass-fpl HACS Integration
        ↓
Home Assistant Core
        ↓
    ┌───┴───────────┐
    ↓               ↓
Sensors      Template Sensors
    ↓               ↓
Energy Dashboard    Custom Dashboard
    ↓               ↓
    └───────┬───────┘
            ↓
     Automations/Alerts
```

### 5.2 Dependencies
- HACS installed and configured
- FPL.com account with online access
- Active FPL service at residence

### 5.3 Known Limitations
- Data updates once daily (~4-5 AM)
- No real-time usage data
- Historical data limited to current billing period
- No hourly breakdown available via API

---

## 6. Template Sensors

### Cost Per kWh
```yaml
- platform: template
  sensors:
    fpl_cost_per_kwh:
      friendly_name: "FPL Cost per kWh"
      unit_of_measurement: "$/kWh"
      value_template: >
        {% if states('sensor.fpl_daily_usage_kwh') | float > 0 %}
          {{ (states('sensor.fpl_bill_to_date') | float /
              states('sensor.fpl_as_of_days') | float /
              states('sensor.fpl_daily_avg') | float) | round(3) }}
        {% else %}
          0.12
        {% endif %}
```

### EV Charging Cost Estimate
```yaml
- platform: template
  sensors:
    ev_charging_cost_estimate:
      friendly_name: "EV Charging Cost (Estimated)"
      unit_of_measurement: "$"
      value_template: >
        {# Estimate based on EV9 charging sessions #}
        {{ (states('sensor.ev9_charging_energy_added') | float *
            states('sensor.fpl_cost_per_kwh') | float) | round(2) }}
```

---

## 7. Implementation Phases

### Phase 1: Basic Integration (P0)
- Install hass-fpl integration
- Verify sensors populate correctly
- Add to HA Energy Dashboard
- Create basic dashboard card
- Implement high usage notification

### Phase 2: Enhanced Tracking (P1)
- Create template sensors for cost calculations
- Implement weekly summary automation
- Add 7-day history graph
- Create bill projection alerts

### Phase 3: Advanced Features (P2)
- Integrate with Kia EV9 charging data
- Calculate EV-specific energy costs
- Implement time-of-use optimizations
- Create monthly comparison reports

---

## 8. Testing Plan

### Unit Tests
- Verify daily usage sensor updates
- Verify bill-to-date accuracy
- Verify template sensor calculations

### Integration Tests
- Compare HA data with FPL.com dashboard
- Verify Energy Dashboard integration
- Test notification delivery

### Acceptance Criteria
- [ ] All P0 requirements implemented and tested
- [ ] Dashboard renders correctly on mobile and desktop
- [ ] Data matches FPL.com within reasonable tolerance
- [ ] Automations run reliably for 1 billing cycle

---

## 9. Configurable Alert Thresholds

All alert thresholds will be configurable via the dashboard using input helpers.

### Helper Entities Required

```yaml
# input_number for configurable thresholds
input_number:
  fpl_daily_usage_alert_threshold:
    name: "FPL Daily Usage Alert Threshold"
    min: 10
    max: 200
    step: 5
    unit_of_measurement: "kWh"
    icon: mdi:lightning-bolt

  fpl_monthly_budget_alert:
    name: "FPL Monthly Budget Alert"
    min: 50
    max: 1000
    step: 25
    unit_of_measurement: "$"
    icon: mdi:currency-usd

# input_boolean to enable/disable alerts
input_boolean:
  fpl_enable_daily_usage_alerts:
    name: "Enable FPL Daily Usage Alerts"
    icon: mdi:bell

  fpl_enable_budget_alerts:
    name: "Enable FPL Budget Alerts"
    icon: mdi:bell
```

### Dashboard Configuration Card

The dashboard will include a settings card allowing:
- Toggle alerts on/off
- Set daily usage threshold (kWh)
- Set monthly budget threshold ($)

---

## 10. Rate Plan Information

### API Availability
The FPL API (hass-fpl integration) does **NOT** expose rate plan or tariff information. Available data includes:
- Usage (daily, hourly, projected)
- Billing (bill-to-date, projected bill)
- Appliance breakdowns
- Net metering data (if applicable)

### Manual Configuration
Rate plan must be configured manually if needed for calculations:
```yaml
input_select:
  fpl_rate_plan:
    name: "FPL Rate Plan"
    options:
      - "RS-1 Residential"
      - "RST-1 Residential Time-of-Use"
      - "GSDT-1 General Service Demand"
    icon: mdi:file-document
```

---

## 11. Open Questions

| Question | Answer |
|----------|--------|
| Monthly budget threshold? | **Configurable via UI** (no default) |
| Daily usage alert threshold? | **Configurable via UI** (no default) |
| Rate plan via API? | **No** - not available in FPL API |
| Track individual circuits? | TBD (requires additional hardware) |
| Notification timing? | TBD |

---

## 12. Future Enhancements

### Smart Meter Integration
If FPL installs a smart meter with more granular data:
- Enable hourly usage tracking
- Implement real-time usage alerts
- Optimize EV charging for off-peak hours

### Solar Integration
If solar panels are added:
- Track solar production vs consumption
- Net metering visualization
- Grid export tracking

---

## 13. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-19 | Claude | Initial requirements document |
| 1.1 | 2025-01-19 | Claude | Made alert thresholds UI-configurable, noted rate plan not in API |
