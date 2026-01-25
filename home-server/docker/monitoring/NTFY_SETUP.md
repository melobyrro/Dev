# ntfy Setup Guide

## Overview

ntfy is configured to receive security alerts from various monitoring systems in the homelab. It provides push notifications to mobile devices via the ntfy mobile app.

## Topics

### homelab-security
**Purpose**: Runtime security events from Falco
**Source**: Falco via falco-ntfy-bridge
**Alert Types**:
- Container anomalies
- Suspicious file access
- Network policy violations
- Privilege escalation attempts

**Subscription URL**: `https://ntfy.byrroserver.com/homelab-security`

### homelab-vulns
**Purpose**: Vulnerability scan alerts from Trivy
**Source**: Grafana Alerting
**Alert Types**:
- Critical CVE detections
- High-severity vulnerabilities
- Container image security issues

**Subscription URL**: `https://ntfy.byrroserver.com/homelab-vulns`

## Mobile App Setup

### iOS / Android

1. **Install the ntfy app**
   - iOS: Download from App Store
   - Android: Download from Google Play or F-Droid

2. **Subscribe to topics**
   - Open the app
   - Tap "+" to add a new subscription
   - For Falco alerts:
     - Topic: `homelab-security`
     - Server: `https://ntfy.byrroserver.com`
   - For Trivy alerts:
     - Topic: `homelab-vulns`
     - Server: `https://ntfy.byrroserver.com`

3. **Configure notification preferences**
   - Set priority levels for each topic
   - Enable/disable sound, vibration, etc.
   - Configure do-not-disturb schedules if needed

## Web Access

You can also view notifications in a web browser:
- Falco: https://ntfy.byrroserver.com/homelab-security
- Trivy: https://ntfy.byrroserver.com/homelab-vulns

## Technical Details

### Architecture
- **Server**: ntfy container running on Docker VM (192.168.1.11)
- **Authentication**: Enabled with default read-only access
- **Write Access**: Anonymous users can publish to homelab-security and homelab-vulns topics
- **Internal URL**: http://ntfy:80 (for Docker containers)
- **External URL**: https://ntfy.byrroserver.com (via Caddy reverse proxy)

### Message Format
- **Title**: Alert type (e.g., "Trivy Security Alert", "Falco Security: [rule]")
- **Priority**: 1-5 (5=critical, 4=high, 3=normal)
- **Tags**: Categorization (e.g., security, trivy, falco, warning)
- **Body**: Alert details and links to dashboards

### Integration Points

1. **Falco → ntfy**
   - Bridge: falco-ntfy-bridge (Flask app)
   - Internal endpoint: http://ntfy:80/homelab-security
   - No authentication required (internal network)

2. **Grafana → ntfy**
   - Contact Point: ntfy-security
   - Internal endpoint: http://ntfy:80/homelab-vulns
   - Configured via provisioning files
   - Alert rules trigger on critical Trivy findings

## Troubleshooting

### Not receiving notifications

1. **Check topic subscription**
   - Verify you're subscribed to the correct topic
   - Ensure server URL is `https://ntfy.byrroserver.com`

2. **Check app permissions**
   - iOS: Settings → ntfy → Notifications → Allow Notifications
   - Android: App Settings → Notifications → Enable

3. **Test the topic**
   ```bash
   # From Docker VM
   docker exec grafana curl -d "Test message" \
     -H "Title: Test" \
     -H "Priority: 3" \
     http://ntfy:80/homelab-vulns
   ```

4. **Check Grafana alert rules**
   - Navigate to https://grafana.byrroserver.com
   - Go to Alerting → Alert Rules
   - Verify "Critical Vulnerabilities Detected" rule status

5. **Check container logs**
   ```bash
   # ntfy server logs
   docker logs ntfy --tail 50

   # Grafana logs
   docker logs grafana --tail 50 | grep alert

   # Falco bridge logs
   docker logs falco-ntfy-bridge --tail 50
   ```

### External HTTPS POST returns 403

This is expected. External clients should only read notifications via HTTPS. Publishing (POST) should only happen from:
- Internal Docker services (http://ntfy:80)
- Authenticated API calls

## Access Control

Current permissions (as of setup):
- **Anonymous users**: Read-write to homelab-security and homelab-vulns, read-only to all other topics
- **Admin users**: Full read-write access to all topics

To modify access control:
```bash
docker exec ntfy ntfy access           # View current ACL
docker exec ntfy ntfy access * topic-name rw   # Grant anonymous write access
docker exec ntfy ntfy access * topic-name ro   # Revoke to read-only
```

## References

- ntfy Documentation: https://docs.ntfy.sh
- Grafana Alerting: https://grafana.com/docs/grafana/latest/alerting/
- Falco Rules: https://falco.org/docs/rules/
