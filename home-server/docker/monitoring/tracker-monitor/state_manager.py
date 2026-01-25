"""
State Manager Module

Handles SQLite database operations for tracking seen posts, enrollment events,
and check history.
"""

import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class StateManager:
    """Manages persistent state using SQLite database."""
    
    def __init__(self, db_path: str = '/app/data/tracker-monitor.db'):
        """Initialize state manager and create database schema.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection = None
        
        # Initialize database
        self._init_database()
        
        logger.info(f"State manager initialized with database: {db_path}")
    
    def _init_database(self) -> None:
        """Create database tables if they don't exist."""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            
            cursor = self.connection.cursor()
            
            # Create tracker_status table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tracker_status (
                    tracker_name TEXT PRIMARY KEY,
                    current_status TEXT,
                    last_checked TIMESTAMP,
                    last_changed TIMESTAMP,
                    check_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0
                )
            ''')
            
            # Create enrollment_events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS enrollment_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracker_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source TEXT,
                    source_url TEXT,
                    details TEXT
                )
            ''')
            
            # Create check_history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS check_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracker_name TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    success BOOLEAN,
                    error_message TEXT
                )
            ''')
            
            # Create seen_posts table (to prevent duplicate alerts)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS seen_posts (
                    post_id TEXT PRIMARY KEY,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_enrollment_events_tracker 
                ON enrollment_events(tracker_name, timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_check_history_tracker 
                ON check_history(tracker_name, timestamp)
            ''')
            
            self.connection.commit()
            logger.info("Database schema initialized successfully")
            
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    def is_post_seen(self, post_id: str) -> bool:
        """Check if a post has been seen before.
        
        Args:
            post_id: Reddit post ID
            
        Returns:
            True if post has been seen, False otherwise
        """
        cursor = self.connection.cursor()
        cursor.execute('SELECT 1 FROM seen_posts WHERE post_id = ?', (post_id,))
        return cursor.fetchone() is not None
    
    def mark_post_seen(self, post_id: str) -> None:
        """Mark a post as seen to prevent duplicate processing.
        
        Args:
            post_id: Reddit post ID
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO seen_posts (post_id) VALUES (?)',
                (post_id,)
            )
            self.connection.commit()
            
        except sqlite3.Error as e:
            logger.error(f"Error marking post as seen: {e}")
    
    def update_tracker_status(self, tracker_name: str, status: str,
                            check_count_increment: int = 0,
                            error_count_increment: int = 0) -> None:
        """Update or insert tracker status.
        
        Args:
            tracker_name: Name of tracker
            status: Current status ('detected', 'success', 'error')
            check_count_increment: Amount to increment check count
            error_count_increment: Amount to increment error count
        """
        try:
            cursor = self.connection.cursor()
            now = datetime.now().isoformat()
            
            # Check if tracker exists
            cursor.execute(
                'SELECT current_status FROM tracker_status WHERE tracker_name = ?',
                (tracker_name,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                status_changed = existing['current_status'] != status
                
                cursor.execute('''
                    UPDATE tracker_status
                    SET current_status = ?,
                        last_checked = ?,
                        last_changed = CASE WHEN ? THEN ? ELSE last_changed END,
                        check_count = check_count + ?,
                        error_count = error_count + ?
                    WHERE tracker_name = ?
                ''', (status, now, status_changed, now if status_changed else None,
                     check_count_increment, error_count_increment, tracker_name))
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO tracker_status 
                    (tracker_name, current_status, last_checked, last_changed, 
                     check_count, error_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (tracker_name, status, now, now, check_count_increment, 
                     error_count_increment))
            
            self.connection.commit()
            
        except sqlite3.Error as e:
            logger.error(f"Error updating tracker status: {e}")
    
    def record_enrollment_event(self, tracker_name: str, event_type: str,
                               source: str, source_url: str, details: str,
                               event_time: Optional[str] = None) -> None:
        """Record an enrollment event.
        
        Args:
            tracker_name: Name of tracker
            event_type: Type of event ('detected', 'opened', 'closed')
            source: Source of detection ('reddit', 'rss', 'scrape')
            source_url: URL where event was detected
            details: Additional details about the event
        """
        try:
            cursor = self.connection.cursor()
            if event_time:
                cursor.execute('''
                    INSERT INTO enrollment_events 
                    (tracker_name, event_type, timestamp, source, source_url, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (tracker_name, event_type, event_time, source, source_url, details))
            else:
                cursor.execute('''
                    INSERT INTO enrollment_events 
                    (tracker_name, event_type, source, source_url, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (tracker_name, event_type, source, source_url, details))
            
            self.connection.commit()
            logger.info(f"Recorded enrollment event for {tracker_name}: {event_type}")
            
        except sqlite3.Error as e:
            logger.error(f"Error recording enrollment event: {e}")

    def event_exists(self, tracker_name: str, event_type: str, source_url: str) -> bool:
        """Check if an enrollment event already exists for the same source URL."""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT 1
                FROM enrollment_events
                WHERE tracker_name = ?
                  AND event_type = ?
                  AND source_url = ?
                LIMIT 1
            ''', (tracker_name, event_type, source_url))
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking existing enrollment event: {e}")
            return False
    
    def get_open_candidates(self) -> List[Dict]:
        # Return latest open events per tracker that are still open.
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT tracker_name,
                       MAX(CASE WHEN event_type IN ('open', 'open_signup') THEN id END) as last_open_id,
                       MAX(CASE WHEN event_type IN ('closed', 'close') THEN id END) as last_closed_id
                FROM enrollment_events
                GROUP BY tracker_name
            ''')

            candidates = []
            for row in cursor.fetchall():
                tracker = row['tracker_name']
                last_open_id = row['last_open_id']
                last_closed_id = row['last_closed_id']

                if not last_open_id:
                    continue
                if last_closed_id and last_closed_id >= last_open_id:
                    continue

                since_id = last_closed_id or 0
                cursor.execute('''
                    SELECT id, source_url, details
                    FROM enrollment_events
                    WHERE tracker_name = ?
                      AND event_type IN ('open', 'open_signup')
                      AND id > ?
                    ORDER BY id DESC
                    LIMIT 1
                ''', (tracker, since_id))
                open_row = cursor.fetchone()
                if not open_row:
                    continue

                candidates.append({
                    'tracker': tracker,
                    'id': open_row['id'],
                    'url': open_row['source_url'],
                    'details': open_row['details']
                })

            return candidates
        except sqlite3.Error as e:
            logger.error(f"Error fetching open candidates: {e}")
            return []


    def update_event_details(self, event_id: int, details: str) -> None:
        # Update details for a stored enrollment event.
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE enrollment_events
                SET details = ?
                WHERE id = ?
            ''', (details, event_id))
            self.connection.commit()
        except sqlite3.Error as e:
            logger.error(f"Error updating enrollment event details: {e}")


    def record_check(self, tracker_name: str, status: str, success: bool,
                    error_message: Optional[str] = None) -> None:
        """Record a check attempt in history.
        
        Args:
            tracker_name: Name of tracker
            status: Status result ('success', 'error')
            success: Whether check was successful
            error_message: Error message if check failed
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO check_history 
                (tracker_name, status, success, error_message)
                VALUES (?, ?, ?, ?)
            ''', (tracker_name, status, success, error_message))
            
            self.connection.commit()
            
        except sqlite3.Error as e:
            logger.error(f"Error recording check history: {e}")
    
    def get_all_tracker_status(self) -> List[Dict]:
        """Get current status for all trackers.
        
        Returns:
            List of tracker status dictionaries
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT tracker_name, current_status, last_checked, 
                       last_changed, check_count, error_count
                FROM tracker_status
                ORDER BY tracker_name
            ''')
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            logger.error(f"Error fetching tracker status: {e}")
            return []
    
    def get_recent_events(self, tracker_name: Optional[str] = None,
                         limit: int = 100) -> List[Dict]:
        """Get recent enrollment events.
        
        Args:
            tracker_name: Optional tracker name filter
            limit: Maximum number of events to return
            
        Returns:
            List of enrollment event dictionaries
        """
        try:
            cursor = self.connection.cursor()
            
            if tracker_name:
                cursor.execute('''
                    SELECT * FROM enrollment_events
                    WHERE tracker_name = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (tracker_name, limit))
            else:
                cursor.execute('''
                    SELECT * FROM enrollment_events
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            logger.error(f"Error fetching recent events: {e}")
            return []
    
    def cleanup_old_posts(self, days: int = 30) -> int:
        """Clean up old seen posts to prevent database bloat.
        
        Args:
            days: Remove posts older than this many days
            
        Returns:
            Number of posts removed
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                DELETE FROM seen_posts
                WHERE first_seen < datetime('now', '-' || ? || ' days')
            ''', (days,))
            
            deleted = cursor.rowcount
            self.connection.commit()
            
            logger.info(f"Cleaned up {deleted} old seen posts")
            return deleted
            
        except sqlite3.Error as e:
            logger.error(f"Error cleaning up old posts: {e}")
            return 0
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")


# Example usage for testing
if __name__ == '__main__':
    import tempfile
    import os
    
    # Use temporary database for testing
    temp_db = tempfile.mktemp(suffix='.db')
    
    try:
        # Configure logging
        logging.basicConfig(level=logging.DEBUG)
        
        # Create state manager
        sm = StateManager(temp_db)
        
        # Test operations
        print("Testing state manager:\n")
        
        # Test post tracking
        print("1. Testing post tracking:")
        assert not sm.is_post_seen('test123'), "Post should not be seen initially"
        sm.mark_post_seen('test123')
        assert sm.is_post_seen('test123'), "Post should be marked as seen"
        print("   ✅ Post tracking works\n")
        
        # Test tracker status
        print("2. Testing tracker status:")
        sm.update_tracker_status('PTP', 'detected', check_count_increment=1)
        status = sm.get_all_tracker_status()
        assert len(status) == 1, "Should have one tracker"
        assert status[0]['tracker_name'] == 'PTP', "Tracker name should be PTP"
        print(f"   ✅ Tracker status: {status[0]}\n")
        
        # Test enrollment events
        print("3. Testing enrollment events:")
        sm.record_enrollment_event(
            tracker_name='PTP',
            event_type='detected',
            source='reddit',
            source_url='https://reddit.com/test',
            details='Test event'
        )
        events = sm.get_recent_events(limit=10)
        assert len(events) == 1, "Should have one event"
        print(f"   ✅ Event recorded: {events[0]}\n")
        
        # Test check history
        print("4. Testing check history:")
        sm.record_check('PTP', 'success', True)
        print("   ✅ Check history recorded\n")
        
        print("All tests passed! ✅")
        
    finally:
        # Cleanup
        if os.path.exists(temp_db):
            os.remove(temp_db)
