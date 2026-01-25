#!/usr/bin/env python3
"""
Tracker Open Signup Monitor v2

Monitors Reddit for ANY torrent tracker open signup announcements.
Sends notifications to Home Assistant and ntfy.
Supports language filtering (English + Portuguese).

Usage:
    python app.py           # Normal operation (continuous monitoring)
    python app.py --test    # Single test run
"""

import sys
import time
import signal
import logging
import argparse
from typing import Optional
from datetime import datetime

from config_loader import load_config
from reddit_monitor import RedditMonitor
from keyword_matcher import KeywordMatcher
from language_extractor import extract_language
from state_manager import StateManager
from notifier import Notifier
from api import start_api_server, update_run_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TrackerMonitorApp:
    """Main application for tracker open signup monitoring."""

    def __init__(self, config_path: str = '/app/config.yml'):
        """Initialize the tracker monitor application."""
        self.config_path = config_path
        self.config = None
        self.reddit_monitor = None
        self.keyword_matcher = None
        self.state_manager = None
        self.notifier = None
        self.running = True

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def initialize(self) -> bool:
        """Initialize all components."""
        try:
            logger.info(f"Loading configuration from {self.config_path}")
            self.config = load_config(self.config_path)

            mode = self.config.get('detection_mode', 'all')
            logger.info(f"Detection mode: {mode}")

            # Initialize state manager
            logger.info("Initializing state manager...")
            self.state_manager = StateManager('/app/data/tracker-monitor.db')

            # Initialize Reddit monitor
            logger.info("Initializing Reddit monitor...")
            self.reddit_monitor = RedditMonitor(
                subreddits=self.config['reddit']['subreddits'],
                max_posts=self.config['reddit']['max_posts_per_check']
            )

            # Initialize keyword matcher (v2)
            logger.info("Initializing keyword matcher...")
            self.keyword_matcher = KeywordMatcher(self.config)

            # Initialize notifier (v2)
            logger.info("Initializing notifier...")
            self.notifier = Notifier(self.config)

            logger.info("All components initialized successfully")

            # Start API server
            logger.info("Starting API server...")
            start_api_server(port=5000)
            logger.info("API server started on port 5000")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize: {e}", exc_info=True)
            return False

    def run_single_check(self) -> None:
        """Execute a single monitoring check cycle."""
        run_start = datetime.now()
        logger.info("=" * 80)
        logger.info(f"Starting check at {run_start.isoformat()}")
        logger.info("=" * 80)

        matches_this_run = []

        try:
            # Fetch posts from Reddit
            posts = self.reddit_monitor.fetch_recent_posts()
            logger.info(f"Fetched {len(posts)} posts from Reddit")

            posts_checked = 0
            matches_found = 0
            notifications_sent = 0

            for post in posts:
                posts_checked += 1

                already_seen = self.state_manager.is_post_seen(post['id'])

                # Check for matches
                match_result = self.keyword_matcher.match_post(post)

                if match_result:
                    tracker_name, matched_keyword, event_type = match_result

                    post = self.reddit_monitor.enrich_post(post)
                    language = extract_language(post.get('body', ''), post.get('title'))
                    removed_reason = self._get_removed_reason(post)
                    flair = post.get('flair')

                    if event_type == 'open' and removed_reason:
                        event_type = 'closed'
                        matched_keyword = removed_reason
                    elif event_type == 'open' and flair and flair.lower() in self.keyword_matcher.close_flairs:
                        event_type = 'closed'
                        matched_keyword = flair

                    if event_type == 'open' and already_seen:
                        continue
                    if event_type == 'closed' and self.state_manager.event_exists(
                        tracker_name, event_type, post['url']
                    ):
                        continue

                    matches_found += 1

                    logger.info(f"MATCH FOUND: {tracker_name} - '{matched_keyword}' ({event_type})")
                    logger.info(f"  Title: {post['title']}")
                    logger.info(f"  URL: {post['url']}")

                    # Track match for API
                    matches_this_run.append({
                        'tracker': tracker_name,
                        'keyword': matched_keyword,
                        'event_type': event_type,
                        'title': post['title'],
                        'url': post['url']
                    })

                    event_time = None
                    created = post.get('created_utc')
                    if isinstance(created, datetime):
                        event_time = created.isoformat()

                    # Record event
                    detail_parts = [f"Keyword: {matched_keyword}"]
                    if flair:
                        detail_parts.append(f"Flair: {flair}")
                    if removed_reason:
                        detail_parts.append(f"Removed: {removed_reason}")
                    if language:
                        detail_parts.append(f"Language: {language}")
                    detail_parts.append(f"Title: {post['title']}")
                    self.state_manager.record_enrollment_event(
                        tracker_name=tracker_name,
                        event_type=event_type,
                        source=post.get('source', 'reddit'),
                        source_url=post['url'],
                        details=" | ".join(detail_parts),
                        event_time=event_time
                    )

                    # Send notification
                    if event_type == 'open':
                        if self.notifier.send_signup_alert(tracker_name, post):
                            notifications_sent += 1

                # Mark post as seen
                if not already_seen:
                    self.state_manager.mark_post_seen(post['id'])

            # Reconcile open items with removed/closed posts
            self._reconcile_open_signups()

            # Push metrics if enabled
            self.notifier.push_metrics([])

            logger.info("=" * 80)
            logger.info(f"Check complete: {posts_checked} posts, "
                       f"{matches_found} matches, {notifications_sent} notifications")
            logger.info("=" * 80)

            # Update API status
            update_run_status(run_start, matches_this_run)

        except Exception as e:
            logger.error(f"Error during check: {e}", exc_info=True)
            # Still update run time even on error
            update_run_status(run_start, [])

    def _insert_detail_field(self, details: str, label: str, value: str) -> str:
        if not value:
            return details
        if not details:
            return f"{label}: {value}"
        marker = f"{label}: "
        if marker in details:
            return details
        parts = [seg.strip() for seg in details.split('|') if seg.strip()]
        insert_at = len(parts)
        for idx, seg in enumerate(parts):
            if seg.startswith('Title:'):
                insert_at = idx
                break
        parts.insert(insert_at, f"{label}: {value}")
        return " | ".join(parts)


    def _get_removed_reason(self, post: dict) -> str:
        removed_by = post.get('removed_by_category')
        if removed_by:
            return f"removed ({removed_by})"
        body = (post.get('body') or '').strip().lower()
        if body in ('[removed]', '[deleted]'):
            return 'removed'
        title = (post.get('title') or '').strip().lower()
        if title.startswith('[ removed by moderator'):
            return 'removed'
        return None

    def _reconcile_open_signups(self) -> None:
        try:
            candidates = self.state_manager.get_open_candidates()
            if not candidates:
                return
            close_flairs = set(self.keyword_matcher.close_flairs)
            for candidate in candidates:
                tracker = candidate.get('tracker')
                url = candidate.get('url')
                if not tracker or not url:
                    continue
                if self.state_manager.event_exists(tracker, 'closed', url):
                    continue
                status = self.reddit_monitor.get_post_status(url)
                if not status:
                    continue
                flair = (status.get('flair') or '').strip()
                removed_reason = self._get_removed_reason(status)
                details = candidate.get('details') or ''

                if flair and 'Flair:' not in details:
                    updated = self._insert_detail_field(details, 'Flair', flair)
                    if updated != details:
                        self.state_manager.update_event_details(candidate.get('id'), updated)
                        details = updated

                closed_by_flair = bool(flair) and flair.lower() in close_flairs
                if not removed_reason and not closed_by_flair:
                    continue

                reason = removed_reason or f"flair:{flair}"
                detail_parts = [f"Keyword: {reason}"]
                if flair:
                    detail_parts.append(f"Flair: {flair}")
                title = status.get('title')
                if title:
                    detail_parts.append(f"Title: {title}")

                self.state_manager.record_enrollment_event(
                    tracker_name=tracker,
                    event_type='closed',
                    source='reddit_json',
                    source_url=url,
                    details=" | ".join(detail_parts)
                )

                time.sleep(0.6)
        except Exception as e:
            logger.warning(f"Error reconciling open signups: {e}")


    def run_continuous(self, check_interval_minutes: int) -> None:
        """Run monitoring in continuous loop."""
        logger.info(f"Starting continuous monitoring (interval: {check_interval_minutes}m)")

        while self.running:
            try:
                self.run_single_check()

                if self.running:
                    wait_seconds = check_interval_minutes * 60
                    logger.info(f"Waiting {check_interval_minutes} minutes...")

                    for _ in range(wait_seconds):
                        if not self.running:
                            break
                        time.sleep(1)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(60)

        logger.info("Monitoring stopped")

    def shutdown(self) -> None:
        """Cleanup resources."""
        logger.info("Shutting down...")

        if self.state_manager:
            self.state_manager.close()

        if self.reddit_monitor:
            self.reddit_monitor.close()

        logger.info("Shutdown complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Tracker Open Signup Monitor')
    parser.add_argument('--test', action='store_true',
                       help='Run single test check and exit')
    parser.add_argument('--config', default='/app/config.yml',
                       help='Path to configuration file')
    args = parser.parse_args()

    app = TrackerMonitorApp(config_path=args.config)

    if not app.initialize():
        logger.error("Failed to initialize, exiting")
        sys.exit(1)

    try:
        if args.test:
            logger.info("Running in TEST mode")
            app.run_single_check()
        else:
            check_interval = app.config['reddit']['check_interval_minutes']
            app.run_continuous(check_interval)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        app.shutdown()


if __name__ == '__main__':
    main()
