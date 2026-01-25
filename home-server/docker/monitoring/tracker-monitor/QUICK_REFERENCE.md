# Tracker Enrollment Monitor - Quick Reference Card

## Essential Paths

```
Service Directory: /home/byrro/docker/monitoring/tracker-monitor/
Docker Compose:    /home/byrro/docker/monitoring/docker-compose.yml
Configuration:     /home/byrro/docker/monitoring/tracker-monitor/config.yml
Database:          /home/byrro/docker/monitoring/tracker-monitor/data/tracker-monitor.db
```

## Common Commands

```bash
# Deploy
cd /home/byrro/docker/monitoring
docker compose build tracker-monitor
docker compose up -d tracker-monitor

# Status
docker compose ps tracker-monitor
docker compose logs -f tracker-monitor

# Test
docker compose exec tracker-monitor python app.py --test

# Restart
docker compose restart tracker-monitor

# Stop
docker compose stop tracker-monitor

# Rebuild
docker compose build tracker-monitor
docker compose up -d tracker-monitor

# Verify Installation
/home/byrro/docker/monitoring/tracker-monitor/verify-installation.sh
```

## Access Points

```
Grafana Dashboard: http://192.168.1.11:3030/d/tracker-enrollments
Prometheus:        http://192.168.1.11:9090
ntfy Topic:        https://ntfy.byrroserver.com/tracker-enrollments
```

## Key Metrics

```
tracker_enrollment_status{tracker="NAME"}       - Status (0=closed, 1=open, 2=unknown)
tracker_last_check_timestamp{tracker="NAME"}    - Last check Unix timestamp
tracker_check_errors_total{tracker="NAME"}      - Error count
tracker_check_count_total{tracker="NAME"}       - Total checks
```

## Default Trackers

1. PassThePopcorn (PTP) - High Priority
2. Bibliotik (BIB) - High Priority
3. Redacted (RED) - Medium Priority
4. Orpheus (OPS) - Medium Priority
5. BroadcastTheNet (BTN) - High Priority

Check Interval: 30 minutes
Subreddits: r/trackers, r/OpenSignups, r/Invites
Method: Public RSS feeds (no authentication)

## Quick Customization

```bash
# Add tracker
nano /home/byrro/docker/monitoring/tracker-monitor/config.yml
# Edit trackers section, then:
docker compose restart tracker-monitor

# Change check frequency
nano /home/byrro/docker/monitoring/tracker-monitor/config.yml
# Edit check_interval_minutes, then:
docker compose restart tracker-monitor

# Add ignore words
nano /home/byrro/docker/monitoring/tracker-monitor/config.yml
# Edit filters.ignore_words, then:
docker compose restart tracker-monitor
```

## Troubleshooting Quick Fixes

```bash
# Check logs
docker compose logs tracker-monitor --tail=50

# Test RSS connection
docker compose exec tracker-monitor python app.py --test

# Reset database (clears seen posts)
docker compose stop tracker-monitor
rm /home/byrro/docker/monitoring/tracker-monitor/data/tracker-monitor.db
docker compose start tracker-monitor

# Test RSS feeds manually
docker compose exec tracker-monitor python reddit_monitor.py
```

## Documentation

```
README:                    tracker-monitor/README.md
Implementation Summary:    tracker-monitor/IMPLEMENTATION_SUMMARY.md
Deployment Checklist:      tracker-monitor/DEPLOYMENT_CHECKLIST.md
Quick Reference:           tracker-monitor/QUICK_REFERENCE.md (this file)
```

## Quick Deployment (User Actions)

1. Subscribe to ntfy: https://ntfy.byrroserver.com/tracker-enrollments
2. Deploy: `docker compose build tracker-monitor && docker compose up -d tracker-monitor`
3. Test: `docker compose exec tracker-monitor python app.py --test`
4. Monitor: http://192.168.1.11:3030/d/tracker-enrollments

## Support

All documentation available in: `/home/byrro/docker/monitoring/tracker-monitor/`
