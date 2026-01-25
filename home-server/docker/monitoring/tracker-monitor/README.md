# Tracker Enrollment Monitor

Automated Reddit monitoring system for private tracker enrollment announcements. Integrates with existing Prometheus/Grafana monitoring stack.

## Overview

This service monitors Reddit subreddits (r/trackers, r/OpenSignups, r/Invites) for private tracker enrollment announcements and sends immediate mobile push notifications via ntfy when matches are detected.

**Note:** Uses public Reddit RSS feeds - no authentication required!

## Features

- **Reddit Monitoring**: Checks configured subreddits every 30 minutes via RSS feeds
- **Keyword Matching**: Matches posts against configurable tracker keywords
- **Smart Filtering**: Ignores posts with "closed", "ended", etc.
- **Duplicate Prevention**: Tracks seen posts to avoid duplicate alerts
- **Mobile Notifications**: Instant push via ntfy.byrroserver.com
- **Metrics**: Pushes status to Prometheus Pushgateway
- **Dashboard**: Grafana dashboard for monitoring
- **Alerts**: Prometheus alerts for enrollments and service health
- **No Authentication**: Uses public RSS feeds, no Reddit API credentials needed

## Architecture

```
Reddit RSS Feeds (Public)
      ↓
Keyword Matcher → State Manager (SQLite)
      ↓                    ↓
   Notifier         Prometheus Metrics
      ↓                    ↓
    ntfy              Grafana Dashboard
```

## Files Structure

```
tracker-monitor/
├── app.py                    # Main application entry point
├── reddit_monitor.py         # Reddit RSS feed parser
├── keyword_matcher.py        # Keyword matching logic
├── state_manager.py          # SQLite database operations
├── notifier.py              # ntfy + Prometheus integration
├── config_loader.py         # YAML configuration parser
├── Dockerfile               # Alpine Linux + Python 3.11
├── requirements.txt         # Python dependencies
├── config.yml              # Tracker keywords and settings
├── .env.example            # Environment variable template
└── data/                    # SQLite database (created at runtime)
```

## Configuration

### Tracked Trackers (config.yml)

By default, the system monitors these trackers:

1. **PassThePopcorn (PTP)** - Priority: High
2. **Bibliotik** - Priority: High
3. **Redacted (RED)** - Priority: Medium
4. **Orpheus** - Priority: Medium
5. **BroadcastTheNet (BTN)** - Priority: High

### Adding More Trackers

Edit `/home/byrro/docker/monitoring/tracker-monitor/config.yml`:

```yaml
trackers:
  - name: "YourTracker"
    keywords:
      - "tracker-abbreviation"
      - "full tracker name"
      - "signup keyword"
    priority: "high"  # or "medium", "low"
```

Restart the service after changes:
```bash
docker-compose restart tracker-monitor
```

### Filtering

Ignore words (posts containing these are skipped):
- "closed"
- "ending soon"
- "ended"
- "deadline passed"
- "applications closed"

Minimum post score: 1 (ignore downvoted posts - note: RSS feeds don't include scores)

## Prerequisites

### No Reddit API Setup Required!

This service uses public Reddit RSS feeds which require no authentication or API credentials. Simply deploy and start monitoring!

## Deployment

### 1. Build and Start Service

```bash
cd /home/byrro/docker/monitoring
docker-compose build tracker-monitor
docker-compose up -d tracker-monitor
```

### 2. Verify Service is Running

```bash
docker-compose ps tracker-monitor
docker-compose logs -f tracker-monitor
```

You should see log messages like:
```
Configuration loaded: monitoring 5 trackers
Reddit RSS monitor initialized for 3 subreddits
Starting continuous monitoring (check interval: 30 minutes)
```

### 3. Subscribe to ntfy Topic

On your mobile device:

- **iOS**: Install "ntfy" app from App Store
- **Android**: Install "ntfy" app from Play Store
- Open app and subscribe to: `https://ntfy.byrroserver.com/tracker-enrollments`

### 4. Test Notification

Run a manual test check:

```bash
docker-compose exec tracker-monitor python app.py --test
```

This will:
- Fetch recent posts from Reddit RSS feeds
- Match against keywords
- Send test notification if matches found

## Monitoring & Alerts

### Grafana Dashboard

Access the dashboard at:
- URL: http://192.168.1.11:3030/d/tracker-enrollments
- Title: "Tracker Enrollment Monitor"

Dashboard panels:
1. **Tracker Status Overview** - Table showing all trackers (green/red status)
2. **Enrollment Status Timeline** - Historical status changes
3. **Total Checks Performed** - Gauge showing check count
4. **Total Errors** - Error accumulation gauge
5. **Check Rate** - Rate of checks per tracker
6. **Tracker Monitor Logs** - Live logs from Loki

### Prometheus Metrics

Exposed metrics:
- `tracker_enrollment_status{tracker="NAME"}` - Status (0=closed, 1=open, 2=unknown)
- `tracker_last_check_timestamp{tracker="NAME"}` - Unix timestamp of last check
- `tracker_check_errors_total{tracker="NAME"}` - Cumulative errors
- `tracker_check_count_total{tracker="NAME"}` - Total checks performed

### Alert Rules

Alert rules in `/home/byrro/docker/monitoring/tracker-enrollment-alerts.yml`:

1. **TrackerEnrollmentDetected** (Critical) - Enrollment opportunity detected
2. **TrackerStatusChanged** (Warning) - Status change detected
3. **TrackerCheckErrorsHigh** (Warning) - High error rate
4. **TrackerMonitorServiceDown** (Critical) - Service is down
5. **TrackerMonitorStale** (Warning) - No recent checks
6. **TrackerMonitorGlobalErrors** (Warning) - Too many total errors

## Notification Format

When an enrollment is detected, you'll receive:

```
🎯 Tracker Enrollment Detected!

PassThePopcorn (PTP) signup mentioned

Source: r/trackers
Title: "PTP Applications Open - 48 Hours Only"
Posted: 5 minutes ago

Link: https://reddit.com/r/trackers/abc123
```

## How It Works

### RSS Feed Parsing

The service fetches public RSS feeds from Reddit:
- `https://www.reddit.com/r/trackers/.rss`
- `https://www.reddit.com/r/OpenSignups/.rss`
- `https://www.reddit.com/r/Invites/.rss`

Each RSS feed provides:
- Post title
- Post body/summary
- Author
- Timestamp
- Post URL

The service parses these feeds and matches post content against configured tracker keywords.

### Advantages Over API

- **No Authentication**: No need to create Reddit apps or manage credentials
- **Instant Deployment**: Works immediately without waiting for Reddit API approval
- **Reliable**: RSS feeds are stable and public
- **Simple**: Fewer moving parts, easier to maintain

## Troubleshooting

### Service Won't Start

Check logs:
```bash
docker-compose logs tracker-monitor
```

Common issues:
- Missing config.yml file
- Invalid YAML syntax in config.yml
- Permission issues with data directory

### No Notifications Received

1. Verify service is running:
   ```bash
   docker-compose ps tracker-monitor
   ```

2. Check ntfy topic subscription on mobile device

3. Test notification manually:
   ```bash
   docker-compose exec tracker-monitor python app.py --test
   ```

4. Check logs for errors:
   ```bash
   docker-compose logs -f tracker-monitor
   ```

### RSS Feed Errors

If you see HTTP errors (404, 503):
- Verify subreddit names are correct in config.yml
- Check if Reddit is experiencing downtime
- RSS feeds are rate-limited but generous - typical usage won't hit limits

### False Positives

Edit `/home/byrro/docker/monitoring/tracker-monitor/config.yml`:

Add more ignore words:
```yaml
filters:
  ignore_words:
    - "your ignore word here"
```

Or adjust tracker keywords to be more specific.

### Database Issues

The SQLite database is stored in:
```
/home/byrro/docker/monitoring/tracker-monitor/data/tracker-monitor.db
```

To reset the database (clears all seen posts):
```bash
docker-compose stop tracker-monitor
rm /home/byrro/docker/monitoring/tracker-monitor/data/tracker-monitor.db
docker-compose start tracker-monitor
```

## Maintenance

### Cleanup Old Posts

The database automatically tracks seen posts. To prevent bloat, old posts (>30 days) are periodically cleaned up.

Manual cleanup:
```bash
docker-compose exec tracker-monitor python -c "
from state_manager import StateManager
sm = StateManager('/app/data/tracker-monitor.db')
deleted = sm.cleanup_old_posts(days=30)
print(f'Cleaned up {deleted} old posts')
sm.close()
"
```

### Update Configuration

After editing config.yml:
```bash
docker-compose restart tracker-monitor
```

### Update Code

After code changes:
```bash
docker-compose build tracker-monitor
docker-compose up -d tracker-monitor
```

## Performance

- **Memory Usage**: ~50-100 MB
- **CPU Usage**: Minimal (only active during checks)
- **Network**: 3 RSS feed requests every 30 minutes
- **Disk**: SQLite database grows ~1-2 MB per month

## Security

- No credentials required - uses public RSS feeds
- No sensitive data logged
- Read-only access to Reddit
- Respects rate limits with polite delays

## Support

For issues or questions:
1. Check logs: `docker-compose logs tracker-monitor`
2. Review Grafana dashboard for metrics
3. Verify RSS feeds are accessible
4. Ensure ntfy topic subscription is active

## License

Internal homelab use only.
