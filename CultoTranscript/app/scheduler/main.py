"""
Scheduler service - checks channels for new videos on a schedule
"""
import os
import sys
import logging
import json
import redis
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.worker.yt_dlp_service import YtDlpService
from app.worker.rollup_service import MonthlyRollupService
from app.common.database import get_db
from app.common.models import Channel, Video, Job, ScheduleConfig
from app.scheduler.email_notifier import send_scheduler_alert

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Services
yt_dlp = YtDlpService()

# Global scheduler reference for health checks
scheduler = None


def check_channel_for_new_videos(channel_id: int):
    """
    Check a channel for new videos and queue transcription jobs

    Args:
        channel_id: Database ID of channel to check
    """
    logger.info(f"Checking channel {channel_id} for new videos")

    try:
        with get_db() as db:
            channel = db.query(Channel).filter(Channel.id == channel_id).first()

            if not channel or not channel.active:
                logger.info(f"Channel {channel_id} not found or inactive")
                return

            logger.info(f"Checking channel: {channel.title} ({channel.youtube_url})")

            # Determine date range to check
            if channel.last_checked_at:
                since_date = channel.last_checked_at
            else:
                # First check: look back 7 days
                since_date = datetime.now() - timedelta(days=7)

            # Get channel's uploaded videos using yt-dlp
            # This uses yt-dlp's playlist features to list videos
            import subprocess

            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end", "20",  # Limit to most recent 20 videos
                f"{channel.youtube_url}/videos"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Failed to list videos for channel {channel_id}: {result.stderr}")
                return

            # Parse video entries with duration filtering
            # Get duration thresholds
            min_duration, max_duration = yt_dlp.get_duration_thresholds()
            logger.info(f"Applying duration filter: {min_duration}s - {max_duration}s")

            new_videos_count = 0
            skipped_short = 0
            skipped_long = 0

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                try:
                    video_info = json.loads(line)
                    youtube_id = video_info.get("id")
                    title = video_info.get("title", "Untitled")
                    duration = video_info.get("duration", 0)

                    # Check if we already have this video
                    existing = db.query(Video).filter(Video.youtube_id == youtube_id).first()

                    if existing:
                        logger.debug(f"Video {youtube_id} already exists, skipping")
                        continue

                    # Early duration validation
                    if duration < min_duration:
                        logger.info(f"Skipping short video {youtube_id} - {duration}s")
                        skipped_short += 1
                        continue

                    if duration > max_duration:
                        logger.info(f"Skipping long video {youtube_id} - {duration}s")
                        skipped_long += 1
                        continue

                    # Queue job to transcribe this video
                    video_url = f"https://www.youtube.com/watch?v={youtube_id}"

                    job = Job(
                        job_type="transcribe_video",
                        status="queued",
                        channel_id=channel_id,
                        meta={"url": video_url, "channel_id": channel_id}
                    )
                    db.add(job)
                    db.flush()

                    # Queue in Redis
                    job_data = {
                        "job_id": job.id,
                        "url": video_url,
                        "channel_id": channel_id
                    }
                    redis_client.rpush("transcription_queue", json.dumps(job_data))

                    new_videos_count += 1
                    logger.info(f"Queued new video: {title} ({youtube_id})")

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse video JSON: {line[:100]}")
                    continue

            # Update channel's last_checked_at
            channel.last_checked_at = datetime.now()
            db.commit()

            logger.info(f"Duration filtering: {skipped_short} too short, {skipped_long} too long")
            logger.info(f"Channel check completed. Queued {new_videos_count} new videos")

    except Exception as e:
        logger.error(f"Error checking channel {channel_id}: {e}", exc_info=True)
        send_scheduler_alert(
            subject=f"Channel Check Failed: {channel_id}",
            body=f"Error checking channel {channel_id} for new videos:\n\n{str(e)}\n\nCheck scheduler logs for full traceback."
        )


def refresh_monthly_rollups():
    """Refresh current month rollups for all channels"""
    logger.info("Starting monthly rollup refresh")

    rollup_service = MonthlyRollupService()

    try:
        with get_db() as db:
            channels = db.query(Channel).filter(Channel.active == True).all()

            logger.info(f"Found {len(channels)} active channels")

            for channel in channels:
                try:
                    rollup = rollup_service.refresh_current_month(channel.id)
                    if rollup:
                        logger.info(f"✅ Refreshed rollup for channel {channel.id} ({channel.title})")
                    else:
                        logger.info(f"No videos for current month in channel {channel.id}")
                except Exception as e:
                    logger.error(f"❌ Error refreshing rollup for channel {channel.id}: {e}")

            logger.info("Monthly rollup refresh complete")

    except Exception as e:
        logger.error(f"Error in refresh_monthly_rollups: {e}", exc_info=True)


def check_all_active_channels():
    """Check all active channels for new videos"""
    logger.info(f"Starting scheduled channel check at {datetime.utcnow().isoformat()}")

    try:
        with get_db() as db:
            channels = db.query(Channel).filter(Channel.active == True).all()

            logger.info(f"Found {len(channels)} active channels to check")

            total_queued = 0
            for channel in channels:
                # Get initial queue count
                before = redis_client.llen("transcription_queue")
                check_channel_for_new_videos(channel.id)
                after = redis_client.llen("transcription_queue")
                total_queued += (after - before)

            logger.info(f"Completed channel check. Queued {total_queued} new videos")

            # Log next run time if scheduler is available and running
            global scheduler
            if scheduler and scheduler.get_jobs():
                try:
                    job = scheduler.get_jobs()[0]
                    # next_run_time only exists after scheduler.start() is called
                    if hasattr(job, 'next_run_time') and job.next_run_time:
                        logger.info(f"Next scheduled check: {job.next_run_time.isoformat()}")
                except Exception as e:
                    logger.debug(f"Could not get next run time: {e}")

    except Exception as e:
        logger.error(f"Error in check_all_active_channels: {e}", exc_info=True)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint"""

    def do_GET(self):
        global scheduler

        if self.path == '/health':
            try:
                # Build status response
                status = {
                    'status': 'healthy',
                    'scheduler': 'running',
                    'timestamp': datetime.utcnow().isoformat(),
                    'next_run': None
                }

                # Get next run time if scheduler is available
                if scheduler and scheduler.get_jobs():
                    jobs = scheduler.get_jobs()
                    if jobs:
                        next_run = jobs[0].next_run_time
                        status['next_run'] = next_run.isoformat() if next_run else None

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(status).encode())
            except Exception as e:
                logger.error(f"Error in health check: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default HTTP logging to avoid clutter
        pass


def start_health_server():
    """Start HTTP health check server in background thread"""
    try:
        server = HTTPServer(('0.0.0.0', 8001), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info("Health check server started on port 8001")
    except Exception as e:
        logger.error(f"Failed to start health check server: {e}")


def load_channel_schedules(max_retries=5, retry_delay=10):
    """
    Load all per-channel schedules from database with retry logic

    Args:
        max_retries: Maximum number of database connection attempts
        retry_delay: Seconds to wait between retries

    Returns:
        List of schedule dicts with channel_id, channel_name, day_of_week, hour, minute
    """
    for attempt in range(max_retries):
        try:
            with get_db() as db:
                # Query for enabled schedules on active channels
                schedules = db.query(ScheduleConfig).join(Channel).filter(
                    ScheduleConfig.enabled == True,
                    Channel.active == True,
                    ScheduleConfig.schedule_type == 'weekly_check'
                ).all()

                if not schedules:
                    logger.warning("No enabled channel schedules found in database")
                    return []

                # Convert to list of dicts for APScheduler
                day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
                result = []

                for schedule in schedules:
                    channel = schedule.channel
                    result.append({
                        'channel_id': channel.id,
                        'channel_name': channel.title,
                        'day_of_week': day_names[schedule.day_of_week],
                        'hour': schedule.time_of_day.hour,
                        'minute': schedule.time_of_day.minute
                    })

                logger.info(f"Loaded {len(result)} channel schedules from database")
                return result

        except Exception as e:
            logger.error(f"Error loading channel schedules (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("Failed to load schedules after all retry attempts")
                return []

    return []


def main():
    """Main scheduler entry point"""
    global scheduler

    logger.info("Starting CultoTranscript Scheduler...")

    # Start health check server
    start_health_server()

    # Load per-channel schedules from database (with retry logic)
    schedules = load_channel_schedules(max_retries=5, retry_delay=10)

    scheduler = BlockingScheduler()

    # Add per-channel scheduled jobs
    if not schedules:
        logger.warning("No enabled channel schedules found. Will check for channels periodically...")
        send_scheduler_alert(
            subject="No Channel Schedules Loaded",
            body=f"Scheduler started but failed to load channel schedules.\n"
                 f"Time: {datetime.utcnow().isoformat()}\n"
                 f"Fallback daily check activated.\n"
                 f"Check scheduler logs for details."
        )

        # Add fallback daily check for all channels
        scheduler.add_job(
            check_all_active_channels,
            CronTrigger(hour=2, minute=0),
            id='fallback_daily_check',
            name='Fallback daily check (no channel schedules configured)'
        )
    else:
        # Create one job per channel
        for config in schedules:
            # Use lambda with default argument to capture channel_id correctly
            scheduler.add_job(
                lambda ch_id=config['channel_id']: check_channel_for_new_videos(ch_id),
                CronTrigger(
                    day_of_week=config['day_of_week'],
                    hour=config['hour'],
                    minute=config['minute']
                ),
                id=f"check_channel_{config['channel_id']}",
                name=f"Check '{config['channel_name']}' ({config['day_of_week']} at {config['hour']:02d}:{config['minute']:02d})"
            )

    # Add monthly rollup refresh job (runs daily at 2 AM)
    scheduler.add_job(
        lambda: refresh_monthly_rollups(),
        CronTrigger(hour=2, minute=0),
        id='monthly_rollup_refresh',
        name='Refresh monthly sermon rollups'
    )

    logger.info(f"Scheduler configured with {len(scheduler.get_jobs())} jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}")

    # Run initial channel check on startup
    logger.info("Running initial channel check for all active channels...")
    check_all_active_channels()

    # Start scheduler - this will block indefinitely
    logger.info("Scheduler started. Waiting for scheduled jobs...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down...")


if __name__ == "__main__":
    main()
