#!/usr/bin/env python3
"""
Backfill Suggested Titles Script

This script generates AI-suggested titles for all existing videos
that don't have a suggested_title set.

Usage:
    python scripts/backfill_suggested_titles.py [--limit N] [--dry-run]

Options:
    --limit N        Process only N videos (default: all)
    --batch-size N   Process N videos per batch (default: 10)
    --dry-run        Show what would be processed without making changes
    --force          Regenerate titles even for videos that already have one
    --channel ID     Process only videos from specific channel ID
    --start-date     Process videos published after this date (YYYY-MM-DD)
    --end-date       Process videos published before this date (YYYY-MM-DD)
    --delay N        Seconds to wait between API calls (default: 6)
    --retries N      Number of retries for failed API calls (default: 3)
    --verbose        Enable verbose logging

Examples:
    # Dry run to see what would be processed
    python scripts/backfill_suggested_titles.py --dry-run

    # Process 5 videos with verbose output
    python scripts/backfill_suggested_titles.py --limit 5 --verbose

    # Process videos from specific channel
    python scripts/backfill_suggested_titles.py --channel 1

    # Process videos from date range
    python scripts/backfill_suggested_titles.py --start-date 2024-01-01 --end-date 2024-12-31

    # Process in batches of 5 with custom delay
    python scripts/backfill_suggested_titles.py --batch-size 5 --delay 3
"""

import sys
import os
import time
import argparse
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.common.database import get_db
from app.common.models import Video, BiblicalPassage, SermonThemeV2
from app.worker.ai_summarizer import generate_suggested_title

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_videos_without_titles(
    db,
    limit: int = None,
    force: bool = False,
    channel_id: int = None,
    start_date: datetime = None,
    end_date: datetime = None
):
    """
    Get all videos that need suggested titles

    Args:
        db: Database session
        limit: Maximum number of videos to return
        force: If True, return all completed videos (including those with titles)
        channel_id: Filter by specific channel ID
        start_date: Filter videos published after this date
        end_date: Filter videos published before this date

    Returns:
        List of Video objects
    """
    query = db.query(Video).filter(
        Video.status == 'completed',
        Video.ai_summary.isnot(None),
        Video.ai_summary != '',
        ~Video.ai_summary.like('Erro%')
    )

    if not force:
        query = query.filter(
            (Video.suggested_title.is_(None)) | (Video.suggested_title == '')
        )

    # Apply channel filter
    if channel_id:
        query = query.filter(Video.channel_id == channel_id)

    # Apply date range filters
    if start_date:
        query = query.filter(Video.published_at >= start_date)
    if end_date:
        query = query.filter(Video.published_at <= end_date)

    query = query.order_by(Video.published_at.desc())

    if limit:
        query = query.limit(limit)

    return query.all()


def get_video_themes(db, video_id: int) -> list:
    """Get theme tags for a video"""
    themes = db.query(SermonThemeV2).filter(
        SermonThemeV2.video_id == video_id
    ).order_by(
        SermonThemeV2.confidence_score.desc()
    ).limit(5).all()

    return [t.theme_tag for t in themes]


def get_video_passages(db, video_id: int) -> list:
    """Get OSIS refs for a video"""
    passages = db.query(BiblicalPassage).filter(
        BiblicalPassage.video_id == video_id
    ).limit(5).all()

    return [p.osis_ref for p in passages]


def generate_title_with_retry(
    video,
    themes: list,
    passages: list,
    max_retries: int = 3,
    retry_delay: int = 10
) -> tuple:
    """
    Generate title with retry logic for transient errors

    Args:
        video: Video object
        themes: List of theme tags
        passages: List of OSIS refs
        max_retries: Maximum number of retry attempts
        retry_delay: Seconds to wait between retries

    Returns:
        Tuple of (suggested_title, error_message)
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            suggested_title = generate_suggested_title(
                summary=video.ai_summary,
                themes=themes,
                passages=passages
            )

            if suggested_title:
                return (suggested_title, None)
            else:
                return (None, "Empty response from LLM")

        except Exception as e:
            last_error = str(e)

            # Check if it's a rate limit error
            if "429" in str(e) or "rate" in str(e).lower() or "quota" in str(e).lower():
                if attempt < max_retries:
                    wait_time = retry_delay * attempt  # Exponential backoff
                    logger.warning(f"  Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                    continue

            # For other errors, retry with shorter delay
            if attempt < max_retries:
                logger.warning(f"  Attempt {attempt} failed: {e}, retrying...")
                time.sleep(retry_delay)
                continue

    return (None, last_error)


def backfill_titles(
    limit: int = None,
    dry_run: bool = False,
    force: bool = False,
    batch_size: int = 10,
    channel_id: int = None,
    start_date: datetime = None,
    end_date: datetime = None,
    delay: int = 6,
    max_retries: int = 3
):
    """
    Main backfill function

    Args:
        limit: Maximum number of videos to process
        dry_run: If True, don't make any changes
        force: If True, regenerate all titles
        batch_size: Number of videos to process per batch
        channel_id: Filter by specific channel ID
        start_date: Filter videos published after this date
        end_date: Filter videos published before this date
        delay: Seconds to wait between API calls
        max_retries: Number of retries for failed API calls
    """
    start_time = datetime.now()
    processed = 0
    success = 0
    failed = 0
    skipped = 0
    generated_titles = []  # Store sample of generated titles

    logger.info("=" * 60)
    logger.info("Suggested Title Backfill Script")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"Force regenerate: {force}")
    logger.info(f"Limit: {limit if limit else 'No limit'}")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Delay between calls: {delay}s")
    logger.info(f"Max retries: {max_retries}")
    if channel_id:
        logger.info(f"Channel ID filter: {channel_id}")
    if start_date:
        logger.info(f"Start date filter: {start_date.strftime('%Y-%m-%d')}")
    if end_date:
        logger.info(f"End date filter: {end_date.strftime('%Y-%m-%d')}")
    logger.info("=" * 60)

    with get_db() as db:
        # Get videos to process
        videos = get_videos_without_titles(
            db, limit, force, channel_id, start_date, end_date
        )
        total = len(videos)

        if total == 0:
            logger.info("No videos found that need suggested titles.")
            return

        logger.info(f"Found {total} videos to process")

        # Calculate batch info
        num_batches = (total + batch_size - 1) // batch_size
        logger.info(f"Processing in {num_batches} batch(es) of {batch_size}")
        logger.info("-" * 60)

        for i, video in enumerate(videos, 1):
            processed += 1

            # Show batch progress
            current_batch = (i - 1) // batch_size + 1
            batch_position = (i - 1) % batch_size + 1

            logger.info(f"[{i}/{total}] (Batch {current_batch}/{num_batches}) Processing video {video.id}: {video.title[:50]}...")

            # Skip if already has title and not forcing
            if video.suggested_title and not force:
                logger.info(f"  Skipping - already has title: {video.suggested_title[:50]}...")
                skipped += 1
                continue

            # Get themes and passages
            themes = get_video_themes(db, video.id)
            passages = get_video_passages(db, video.id)

            logger.debug(f"  Themes: {', '.join(themes[:3]) if themes else 'None'}")
            logger.debug(f"  Passages: {', '.join(passages[:3]) if passages else 'None'}")

            if dry_run:
                logger.info(f"  [DRY RUN] Would generate title using summary ({len(video.ai_summary)} chars)")
                success += 1
                continue

            # Generate title with retry logic
            suggested_title, error = generate_title_with_retry(
                video, themes, passages, max_retries, delay * 2
            )

            if suggested_title:
                video.suggested_title = suggested_title
                db.commit()
                logger.info(f"  SUCCESS: {suggested_title}")
                success += 1

                # Store for summary (keep last 10)
                generated_titles.append({
                    'video_id': video.id,
                    'original': video.title[:40],
                    'suggested': suggested_title[:60]
                })
                if len(generated_titles) > 10:
                    generated_titles.pop(0)
            else:
                logger.warning(f"  FAILED: {error}")
                failed += 1

            # Rate limiting
            if i < total:
                logger.debug(f"  Waiting {delay} seconds for rate limit...")
                time.sleep(delay)

            # Pause between batches
            if batch_position == batch_size and i < total:
                logger.info(f"  Batch {current_batch} complete. Pausing for 5 seconds...")
                time.sleep(5)

    # Print summary
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total processed: {processed}")
    logger.info(f"Successful: {success}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"Elapsed time: {elapsed:.1f} seconds")

    # Show sample of generated titles
    if generated_titles and not dry_run:
        logger.info("-" * 60)
        logger.info("Sample of generated titles:")
        for item in generated_titles[-5:]:
            logger.info(f"  Video {item['video_id']}:")
            logger.info(f"    Original:  {item['original']}...")
            logger.info(f"    Suggested: {item['suggested']}")

    logger.info("=" * 60)


def parse_date(date_str: str) -> datetime:
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser(
        description='Backfill suggested titles for existing videos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run                           # Preview what would be processed
  %(prog)s --limit 5 --verbose                 # Process 5 videos with detailed output
  %(prog)s --channel 1                         # Process only videos from channel 1
  %(prog)s --start-date 2024-01-01             # Videos published since Jan 2024
  %(prog)s --batch-size 5 --delay 3            # Custom batch and delay settings
        """
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of videos to process'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of videos to process per batch (default: 10)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without making changes'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Regenerate titles even for videos that already have one'
    )
    parser.add_argument(
        '--channel',
        type=int,
        default=None,
        dest='channel_id',
        help='Process only videos from this channel ID'
    )
    parser.add_argument(
        '--start-date',
        type=parse_date,
        default=None,
        help='Process videos published after this date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=parse_date,
        default=None,
        help='Process videos published before this date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--delay',
        type=int,
        default=6,
        help='Seconds to wait between API calls (default: 6)'
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=3,
        dest='max_retries',
        help='Number of retries for failed API calls (default: 3)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )

    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    backfill_titles(
        limit=args.limit,
        dry_run=args.dry_run,
        force=args.force,
        batch_size=args.batch_size,
        channel_id=args.channel_id,
        start_date=args.start_date,
        end_date=args.end_date,
        delay=args.delay,
        max_retries=args.max_retries
    )


if __name__ == '__main__':
    main()
