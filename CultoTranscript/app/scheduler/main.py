"""
Scheduler service - checks channels for new videos on a schedule
"""
import os
import sys
import logging
import json
import redis
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.worker.yt_dlp_service import YtDlpService
from app.common.database import get_db
from app.common.models import Channel, Video, Job, ScheduleConfig

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

            # Parse video entries
            new_videos_count = 0

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                try:
                    video_info = json.loads(line)
                    youtube_id = video_info.get("id")
                    title = video_info.get("title", "Untitled")

                    # Check if we already have this video
                    existing = db.query(Video).filter(Video.youtube_id == youtube_id).first()

                    if existing:
                        logger.debug(f"Video {youtube_id} already exists, skipping")
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

            logger.info(f"Channel check completed. Queued {new_videos_count} new videos")

    except Exception as e:
        logger.error(f"Error checking channel {channel_id}: {e}", exc_info=True)


def check_all_active_channels():
    """Check all active channels for new videos"""
    logger.info("Checking all active channels")

    try:
        with get_db() as db:
            channels = db.query(Channel).filter(Channel.active == True).all()

            logger.info(f"Found {len(channels)} active channels")

            for channel in channels:
                check_channel_for_new_videos(channel.id)

    except Exception as e:
        logger.error(f"Error in check_all_active_channels: {e}", exc_info=True)


def get_schedule_config():
    """
    Get schedule configuration from database

    Returns:
        dict with day_of_week, hour, minute, enabled or None if not configured
    """
    try:
        with get_db() as db:
            config = db.query(ScheduleConfig).filter(
                ScheduleConfig.schedule_type == 'weekly_check'
            ).first()

            if not config or not config.enabled:
                # Default: Monday at 2 AM
                logger.info("No schedule config found or disabled, using default: Monday 2 AM")
                return {
                    'day_of_week': 0,  # Monday
                    'hour': 2,
                    'minute': 0,
                    'enabled': True
                }

            # Parse time_of_day (datetime.time object from database)
            hour = config.time_of_day.hour
            minute = config.time_of_day.minute

            # Convert PostgreSQL day_of_week (0-6, 0=Monday) to APScheduler format
            # APScheduler uses: mon, tue, wed, thu, fri, sat, sun
            day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            day_name = day_names[config.day_of_week] if config.day_of_week is not None else None

            return {
                'day_of_week': day_name,
                'hour': hour,
                'minute': minute,
                'enabled': config.enabled
            }

    except Exception as e:
        logger.error(f"Error loading schedule config: {e}", exc_info=True)
        # Fallback to default
        return {
            'day_of_week': 'mon',  # Monday
            'hour': 2,
            'minute': 0,
            'enabled': True
        }


def main():
    """Main scheduler entry point"""
    logger.info("Starting CultoTranscript Scheduler...")

    # Load schedule configuration from database
    config = get_schedule_config()

    if not config['enabled']:
        logger.warning("Scheduler is disabled in configuration. Exiting...")
        return

    scheduler = BlockingScheduler()

    # Schedule weekly check using database configuration
    logger.info(f"Configuring scheduler: Day {config['day_of_week']}, Time {config['hour']:02d}:{config['minute']:02d}")

    scheduler.add_job(
        check_all_active_channels,
        CronTrigger(
            day_of_week=config['day_of_week'],
            hour=config['hour'],
            minute=config['minute']
        ),
        id='weekly_channel_check',
        name=f"Check all channels (configured: {config['day_of_week']} at {config['hour']:02d}:{config['minute']:02d})"
    )

    logger.info("Scheduler configured. Jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}")

    # Run once on startup
    logger.info("Running initial channel check...")
    check_all_active_channels()

    # Start scheduler
    try:
        logger.info("Scheduler started. Waiting for scheduled jobs...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down...")


if __name__ == "__main__":
    main()
