# Tracker Enrollment Monitor - Deployment Checklist

## Pre-Deployment Status

✅ All code files created (12 Python/config files)
✅ Docker image builds successfully
✅ docker-compose.yml updated
✅ Grafana dashboard provisioned
✅ Prometheus alert rules configured
✅ Documentation complete
✅ Uses public RSS feeds - no authentication required

---

## Phase 4: User Deployment Steps

### Step 1: Subscribe to ntfy Mobile Topic ⏱️ 2 minutes

On your mobile device:

**iOS**:
1. Install "ntfy" app from App Store
2. Open app
3. Tap "+" to add subscription
4. Enter: `https://ntfy.byrroserver.com/tracker-enrollments`
5. Tap "Subscribe"

**Android**:
1. Install "ntfy" app from Play Store
2. Open app
3. Tap "+" to add subscription
4. Enter: `https://ntfy.byrroserver.com/tracker-enrollments`
5. Tap "Subscribe"

You should now receive notifications when tracker enrollments are detected!

---

### Step 2: Deploy the Service ⏱️ 2 minutes

SSH into the Docker VM:
```bash
ssh byrro@192.168.1.11
```

Deploy the service:
```bash
cd /home/byrro/docker/monitoring
docker compose build tracker-monitor
docker compose up -d tracker-monitor
```

Expected output:
```
[+] Running 1/1
 ✔ Container tracker-monitor  Started
```

---

### Step 3: Verify Service is Running ⏱️ 3 minutes

Check container status:
```bash
docker compose ps tracker-monitor
```

Expected output:
```
NAME               IMAGE                              STATUS
tracker-monitor    monitoring-tracker-monitor         Up X seconds (healthy)
```

View logs in real-time:
```bash
docker compose logs -f tracker-monitor
```

You should see:
```
Configuration loaded: monitoring 5 trackers
Reddit RSS monitor initialized for 3 subreddits
All components initialized successfully
Starting continuous monitoring (check interval: 30 minutes)
```

Press Ctrl+C to exit log viewing.

---

### Step 4: Run Test Check ⏱️ 2 minutes

Execute a manual test:
```bash
docker compose exec tracker-monitor python app.py --test
```

This will:
- Fetch recent posts from RSS feeds (r/trackers, r/OpenSignups, r/Invites)
- Match against configured keywords
- Send notification if any matches found
- Exit after single check

Check the output for:
```
✅ Reddit RSS connection successful
Fetched X total posts from Reddit
Check complete: X posts checked, X matches found
```

---

### Step 5: Access Grafana Dashboard ⏱️ 1 minute

Open your browser and go to:
```
http://192.168.1.11:3030/d/tracker-enrollments
```

You should see:
- **Tracker Status Overview** table (all trackers listed)
- **Enrollment Status Timeline** graph
- **Total Checks Performed** gauge
- **Total Errors** gauge
- **Check Rate** graph
- **Tracker Monitor Logs** panel

The dashboard will auto-refresh every 30 seconds.

---

### Step 6: Verify Prometheus Metrics ⏱️ 1 minute

Open Prometheus UI:
```
http://192.168.1.11:9090
```

Run this query:
```
tracker_enrollment_status
```

You should see metrics for all 5 trackers (PTP, Bibliotik, RED, Orpheus, BTN).

---

## Troubleshooting

### Service Won't Start

**Check logs**:
```bash
docker compose logs tracker-monitor
```

**Common issues**:
- Config syntax error → Check config.yml YAML syntax
- Permission issues → Check data directory permissions
- Network issues → Verify Docker network connectivity

**Solution**: Fix the issue, then restart:
```bash
docker compose restart tracker-monitor
```

---

### No Notifications Received

**Verify service is running**:
```bash
docker compose ps tracker-monitor
```

**Check ntfy subscription**:
- Open ntfy app on phone
- Verify subscription to `https://ntfy.byrroserver.com/tracker-enrollments`
- Try sending test notification:
  ```bash
  curl -d "Test from server" https://ntfy.byrroserver.com/tracker-enrollments
  ```

**Manual test**:
```bash
docker compose exec tracker-monitor python app.py --test
```

---

### RSS Feed Errors

**Error**: HTTP 404 "Not Found"
- **Cause**: Subreddit name incorrect or doesn't exist
- **Solution**: Verify subreddit names in config.yml

**Error**: HTTP 503 "Service Unavailable"
- **Cause**: Reddit temporarily unavailable
- **Solution**: Wait and service will auto-recover

**Error**: "Failed to parse RSS feed"
- **Cause**: Malformed feed or network issue
- **Solution**: Check logs for details, usually auto-recovers

---

### Database Issues

**Reset database** (clears all seen posts):
```bash
docker compose stop tracker-monitor
rm /home/byrro/docker/monitoring/tracker-monitor/data/tracker-monitor.db
docker compose start tracker-monitor
```

---

## Post-Deployment Monitoring

### Check Service Health Daily

Quick health check:
```bash
docker compose ps tracker-monitor
docker compose logs tracker-monitor --tail=20
```

### Review Grafana Dashboard Weekly

Visit http://192.168.1.11:3030/d/tracker-enrollments to:
- Verify checks are running every 30 minutes
- Review error rates
- Check for any matches/alerts

### Adjust Configuration as Needed

Edit tracker keywords:
```bash
nano /home/byrro/docker/monitoring/tracker-monitor/config.yml
docker compose restart tracker-monitor
```

---

## Customization Guide

### Add More Trackers

Edit `/home/byrro/docker/monitoring/tracker-monitor/config.yml`:

```yaml
trackers:
  - name: "YourNewTracker"
    keywords:
      - "tracker abbreviation"
      - "full tracker name"
      - "signup keyword"
    priority: "high"
```

Restart service:
```bash
docker compose restart tracker-monitor
```

### Change Check Frequency

Edit `config.yml`:
```yaml
reddit:
  check_interval_minutes: 60  # Change from 30 to 60 minutes
```

Restart service.

### Add Ignore Words

Edit `config.yml`:
```yaml
filters:
  ignore_words:
    - "closed"
    - "ended"
    - "your new ignore word"
```

Restart service.

---

## Success Criteria

After deployment, you should have:

✅ Container running and healthy
✅ Logs showing successful RSS feed connection
✅ Checks running every 30 minutes
✅ Metrics visible in Prometheus
✅ Grafana dashboard displaying data
✅ Mobile notifications working
✅ No errors in logs

---

## Support Resources

**Documentation**:
- Full README: `/home/byrro/docker/monitoring/tracker-monitor/README.md`
- Implementation Summary: `/home/byrro/docker/monitoring/tracker-monitor/IMPLEMENTATION_SUMMARY.md`

**Useful Commands**:
```bash
# View logs
docker compose logs -f tracker-monitor

# Restart service
docker compose restart tracker-monitor

# Stop service
docker compose stop tracker-monitor

# Start service
docker compose start tracker-monitor

# Rebuild after code changes
docker compose build tracker-monitor && docker compose up -d tracker-monitor

# Manual test run
docker compose exec tracker-monitor python app.py --test
```

---

## Estimated Total Deployment Time: 11 minutes

- Step 1 (ntfy subscription): 2 min
- Step 2 (Deploy service): 2 min
- Step 3 (Verify running): 3 min
- Step 4 (Test check): 2 min
- Step 5 (Grafana dashboard): 1 min
- Step 6 (Prometheus metrics): 1 min

**Total: ~11 minutes from start to finish**

---

🎉 **Ready to deploy! No Reddit API setup required - just deploy and go!**
