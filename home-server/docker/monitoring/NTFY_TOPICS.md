# ntfy Topics for Homelab Security

## Topics

### homelab-security
**Source**: Falco runtime security events via falco-ntfy-bridge
**Priority**: Warning or higher
**Frequency**: Real-time (as events occur)
**Example**: "Falco: Read sensitive file untrusted - Container: postgres, Process: pg_isready"

### homelab-vulns  
**Source**: Grafana alerts for Trivy vulnerability scans
**Priority**: High (critical) or Warning (high count)
**Frequency**: Hourly check, alert when > threshold
**Example**: "Trivy Security Alert - 5 critical vulnerabilities found"

## How to Subscribe

### Web
1. Go to https://ntfy.byrroserver.com
2. Click "Subscribe to topic"
3. Enter: `homelab-security` or `homelab-vulns`

### Mobile App
1. Install ntfy from App Store / Play Store
2. Add server: `https://ntfy.byrroserver.com`
3. Subscribe to both topics

### CLI
```bash
# Listen to all security events
ntfy subscribe https://ntfy.byrroserver.com/homelab-security

# Send test notification
curl -d "Test alert" https://ntfy.byrroserver.com/homelab-security
```

## Notification Priorities

- Priority 5 (Max): Critical Falco events
- Priority 4: Warning Falco events, Trivy critical vulns
- Priority 3: Notice events
- Priority 2: Info events

## Configuring Grafana Alerts for Trivy (Manual Setup)

Since alert provisioning requires specific datasource UIDs, alerts should be configured via Grafana UI:

### Step 1: Create Contact Point

1. Open Grafana: http://192.168.1.11:3030
2. Go to **Alerting** → **Contact points**
3. Click **+ Add contact point**
4. Configure:
   - **Name**: ntfy-homelab-vulns
   - **Integration**: Webhook
   - **URL**: `https://ntfy.byrroserver.com/homelab-vulns`
   - **HTTP Method**: POST
   - **Custom HTTP headers**:
     - Add header: `Title` = `Trivy Security Alert`
     - Add header: `Priority` = `4`
     - Add header: `Tags` = `security,trivy,warning`
5. Click **Test** to verify
6. Click **Save contact point**

### Step 2: Create Alert Rule for Critical Vulnerabilities

1. Go to **Alerting** → **Alert rules**
2. Click **+ New alert rule**
3. Configure:
   - **Alert name**: Trivy Critical Vulnerabilities
   - **Query**: 
     - Data source: Prometheus
     - Metric: `trivy_critical_vulnerabilities`
     - Condition: `last() > 0`
   - **Evaluation behavior**:
     - Folder: Create new "Security Alerts"
     - Evaluation group: "Trivy Scans"
     - Evaluation interval: 1h
     - For: 5m
   - **Labels**:
     - severity: critical
   - **Annotations**:
     - summary: `{{ $values.B }} critical vulnerabilities detected`
     - description: 
       ```
       Trivy found {{ $values.B }} critical vulnerabilities in container images.
       
       Open Grafana → Trivy - Actionable dashboard for details.
       Or query: curl http://192.168.1.11:8083/api/vulnerabilities
       ```
   - **Notifications**:
     - Contact point: ntfy-homelab-vulns
4. Click **Save rule and exit**

### Step 3: Create Alert Rule for High Vulnerabilities

1. Create another alert rule with similar settings
2. Configure:
   - **Alert name**: Trivy High Vulnerability Count
   - **Query**: 
     - Metric: `trivy_high_vulnerabilities`
     - Condition: `last() > 50`
   - **Labels**:
     - severity: high
   - **Annotations**:
     - summary: `{{ $values.B }} high-severity vulnerabilities detected`

## Architecture

```
Falco → Falcosidekick → [Webhook] → falco-ntfy-bridge → ntfy → Mobile App
Trivy → Grafana Alert → [Webhook] → ntfy → Mobile App
```

## Troubleshooting

### Notifications not arriving from Falco

Check bridge service logs:
```bash
docker logs falco-ntfy-bridge --tail 50
```

Check Falcosidekick configuration:
```bash
docker logs falcosidekick | grep -i webhook
```

### Notifications not arriving from Grafana

1. Test the contact point in Grafana UI
2. Check notification history in Alerting → Contact points
3. Verify ntfy topic permissions:
```bash
docker exec ntfy ntfy access
```

### Test notifications manually

```bash
# Test from command line
curl -d "Test from CLI" -H "Title: Test Notification" https://ntfy.byrroserver.com/homelab-security

# Test from within Docker network
docker run --rm --network byrro-net alpine/curl -d "Test from Docker" -H "Title: Test" http://ntfy:80/homelab-security
```
