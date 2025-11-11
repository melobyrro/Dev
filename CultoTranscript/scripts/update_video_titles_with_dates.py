#!/usr/bin/env python3
"""
Migration script to update all existing video titles with sermon date prefix.

Format: MM/DD/YYYY - [Original Title]

Usage:
    python scripts/update_video_titles_with_dates.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.common.database import get_db
from app.common.models import Video
from app.worker.transcription_service import format_title_with_date
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Update all video titles with sermon date prefix"""

    logger.info("Starting video title migration...")

    with get_db() as db:
        # Get all videos
        videos = db.query(Video).all()
        total_videos = len(videos)

        logger.info(f"Found {total_videos} videos to process")

        updated_count = 0
        skipped_count = 0

        for i, video in enumerate(videos, 1):
            if not video.sermon_actual_date:
                logger.warning(f"Video {video.id} has no sermon_actual_date, skipping")
                skipped_count += 1
                continue

            # Format title with date
            old_title = video.title
            new_title = format_title_with_date(old_title, video.sermon_actual_date)

            # Only update if title changed
            if old_title != new_title:
                logger.info(f"[{i}/{total_videos}] Updating video {video.id}")
                logger.info(f"  Old: {old_title}")
                logger.info(f"  New: {new_title}")

                video.title = new_title
                updated_count += 1
            else:
                logger.debug(f"[{i}/{total_videos}] Video {video.id} already has correct format, skipping")
                skipped_count += 1

        # Commit all changes
        logger.info(f"\nCommitting changes to database...")
        db.commit()

        logger.info(f"\nMigration complete!")
        logger.info(f"  Total videos: {total_videos}")
        logger.info(f"  Updated: {updated_count}")
        logger.info(f"  Skipped: {skipped_count}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
