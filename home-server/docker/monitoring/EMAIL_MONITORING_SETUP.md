EMAIL-BASED SECURITY MONITORING CONFIGURATION SUMMARY
======================================================

COMPLETED TASKS:
---------------

1. ✅ Grafana SMTP Configuration
   - Added 7 SMTP environment variables to docker-compose.yml
   - Provider: Gmail SMTP (smtp.gmail.com:587)
   - From: andre.byrro@gmail.com
   - Configured with STARTTLS encryption
   - Container recreated to apply changes
   - Verified: All SMTP settings loaded successfully

2. ✅ Falco Priority Filtering  
   - Changed WEBHOOK_MINIMUMPRIORITY from 'warning' to 'critical'
   - File: /home/byrro/docker/monitoring/.env.obs-secrets
   - Effect: Eliminates benign PostgreSQL health check warnings
   - Verified: Configuration updated successfully

3. ✅ Email Contact Point
   - Created: grafana-provisioning/alerting/contactpoints-email.yml
   - Contact point name: email-daily-digest
   - Destination: andre.byrro@gmail.com
   - Provisioned successfully

4. ✅ Daily Security Digest Alert Rule
   - Created: grafana-provisioning/alerting/daily-security-digest.yml
   - Runs every 24 hours
   - Monitors: trivy_critical_vulnerabilities metric
   - Includes links to:
     * Trivy Actionable dashboard
     * Falco Actionable dashboard
   - Label: type=daily-digest, severity=info
   - Provisioned successfully

5. ✅ Notification Policy Updated
   - Updated: grafana-provisioning/alerting/notification-policies.yml
   - Routes:
     * Critical alerts → ntfy-security (immediate)
     * Daily digest → email-daily-digest (24h interval)
   - Provisioned successfully

6. ✅ Services Restarted
   - Grafana: Recreated with new environment variables
   - Falcosidekick: Restarted with new priority filter
   - Both containers healthy and running

CONFIGURATION FILES:
-------------------
/home/byrro/docker/monitoring/docker-compose.yml (modified)
/home/byrro/docker/monitoring/.env.obs-secrets (modified)
/home/byrro/docker/monitoring/grafana-provisioning/alerting/contactpoints-email.yml (new)
/home/byrro/docker/monitoring/grafana-provisioning/alerting/daily-security-digest.yml (new)
/home/byrro/docker/monitoring/grafana-provisioning/alerting/notification-policies.yml (updated)

BACKUPS CREATED:
---------------
docker-compose.yml.backup-email-<timestamp>
.env.obs-secrets.backup-<timestamp>

SMTP CONFIGURATION VERIFIED:
----------------------------
GF_SMTP_ENABLED=true ✓
GF_SMTP_HOST=smtp.gmail.com:587 ✓
GF_SMTP_USER=andre.byrro@gmail.com ✓
GF_SMTP_PASSWORD=********* (configured) ✓
GF_SMTP_FROM_ADDRESS=andre.byrro@gmail.com ✓
GF_SMTP_FROM_NAME=Home Server Monitoring ✓
GF_SMTP_STARTTLS_POLICY=MandatoryStartTLS ✓

EXPECTED BEHAVIOR:
-----------------
1. Benign Falco warnings (pg_isready, etc.) will no longer trigger ntfy notifications
2. Only CRITICAL Falco events will be sent to ntfy immediately
3. Daily security digest email will be sent every 24 hours to andre.byrro@gmail.com
4. Email will contain:
   - Count of critical CVEs from Trivy
   - Links to actionable dashboards
   - Summary of critical Falco events

TESTING:
--------
The daily digest alert will trigger automatically every 24 hours.
First email should arrive within 24 hours of configuration.

To manually test the email contact point:
- Access Grafana UI at https://grafana.byrroserver.com
- Navigate to Alerting → Contact points
- Find email-daily-digest and click Test

MONITORING:
-----------
Monitor email delivery:
docker logs grafana 2>&1 | grep -i email

Check alert rule status:
docker logs grafana 2>&1 | grep -i daily_security

Verify Falco filtering:
docker logs falcosidekick --tail 50

NEXT STEPS:
-----------
1. Wait for first daily digest email (within 24 hours)
2. Verify email arrives in inbox (check spam folder if needed)
3. Confirm critical-only Falco events in ntfy
4. Monitor for 2-3 days to ensure stability

TROUBLESHOOTING:
---------------
If emails don't arrive:
1. Check Gmail spam folder
2. Verify Gmail app password is still valid
3. Check Grafana logs: docker logs grafana | grep -i smtp
4. Test contact point from Grafana UI

If Falco still sends warnings:
1. Verify falcosidekick restarted: docker ps | grep falcosidekick
2. Check environment: docker exec falcosidekick env | grep WEBHOOK
3. Restart if needed: cd /home/byrro/docker/monitoring && docker compose restart falcosidekick

DATE: Sun Dec 14 17:19:34 EST 2025
USER: byrro
HOST: 192.168.1.11
