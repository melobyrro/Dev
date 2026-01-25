"""
API Module for Tracker Monitor

Provides REST API endpoints for Home Assistant integration.
Runs on a separate thread alongside the main monitor.
"""

import os
import sqlite3
import logging
import json
import re
import hashlib
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from threading import Thread

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
DB_PATH = '/app/data/tracker-monitor.db'
CHECK_INTERVAL_MINUTES = int(os.environ.get('CHECK_INTERVAL', 15))

# Track last run time (updated by main app)
last_run_time = None
last_run_matches = []


def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_source(source: str) -> str:
    """Normalize source labels for HA output."""
    if not source:
        return 'rss'
    normalized = source.lower()
    if normalized in ('rss', 'reddit_json'):
        return normalized
    if normalized == 'reddit':
        return 'rss'
    return source



DETAIL_LABELS = ['Keyword', 'Flair', 'Language', 'Title', 'Removed']


def _extract_detail(details: str, label: str) -> str:
    if not details:
        return None
    labels = '|'.join(DETAIL_LABELS)
    pattern = rf"{label}:\s*(.*?)(?:\s\|\s(?:{labels}):|$)"
    match = re.search(pattern, details)
    if match:
        value = match.group(1).strip()
        return value or None
    return None

def _extract_title(details: str) -> str:
    # Extract title from details string if present.
    return _extract_detail(details, 'Title')


def _extract_keyword(details: str) -> str:
    # Extract keyword from details string if present.
    return _extract_detail(details, 'Keyword')


def _extract_flair(details: str) -> str:
    # Extract flair from details string if present.
    return _extract_detail(details, 'Flair')


def _extract_language(details: str) -> str:
    # Extract language from details string if present.
    return _extract_detail(details, 'Language')


def _extract_match(details: str) -> str:
    """Extract flair when available, otherwise fallback to keyword."""
    flair = _extract_flair(details)
    if flair:
        return flair
    return _extract_keyword(details)


def _normalize_timestamp(value) -> str:
    """Return timestamp as string without changing stored semantics."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _compute_hash(payload: dict) -> str:
    """Compute a stable SHA-256 hash for the payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _fetch_event_by_id(cursor, event_id: int):
    cursor.execute('''
        SELECT id, tracker_name, event_type, timestamp, source, source_url, details
        FROM enrollment_events
        WHERE id = ?
        LIMIT 1
    ''', (event_id,))
    return cursor.fetchone()


def _normalize_event_type(event_type: str) -> str:
    if not event_type:
        return None
    normalized = event_type.lower()
    if normalized == 'open_signup':
        return 'open'
    if normalized == 'close':
        return 'closed'
    return normalized


def _get_open_items(cursor):
    cursor.execute('''
        SELECT tracker_name,
               MAX(CASE WHEN event_type IN ('open', 'open_signup') THEN id END) as last_open_id,
               MAX(CASE WHEN event_type IN ('closed', 'close') THEN id END) as last_closed_id
        FROM enrollment_events
        GROUP BY tracker_name
    ''')

    open_items = []
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
            SELECT timestamp, source, source_url, details
            FROM enrollment_events
            WHERE tracker_name = ?
              AND event_type IN ('open', 'open_signup')
              AND id > ?
            ORDER BY id ASC
            LIMIT 1
        ''', (tracker, since_id))
        open_row = cursor.fetchone()
        if not open_row:
            continue

        open_items.append({
            'tracker': tracker,
            'url': open_row['source_url'],
            'opened_at': _normalize_timestamp(open_row['timestamp']),
            'source': _normalize_source(open_row['source']),
            'title': _extract_title(open_row['details']),
            'language': _extract_language(open_row['details']),
            'flair': _extract_flair(open_row['details'])
        })

    open_items.sort(key=lambda item: (item.get('tracker') or '').lower())
    return open_items


def _get_history_items(cursor, limit: int):
    cursor.execute('''
        SELECT tracker_name,
               MAX(CASE WHEN event_type IN ('open', 'open_signup') THEN id END) as last_open_id,
               MAX(CASE WHEN event_type IN ('closed', 'close') THEN id END) as last_closed_id
        FROM enrollment_events
        GROUP BY tracker_name
    ''')

    history_items = []
    for row in cursor.fetchall():
        tracker = row['tracker_name']
        last_open_id = row['last_open_id']
        last_closed_id = row['last_closed_id']

        if not last_open_id and not last_closed_id:
            continue

        if last_open_id and (not last_closed_id or last_open_id > last_closed_id):
            open_row = _fetch_event_by_id(cursor, last_open_id)
            if not open_row:
                continue
            opened_at = _normalize_timestamp(open_row['timestamp'])
            history_items.append({
                'tracker': tracker,
                'opened_at': opened_at,
                'opened_url': open_row['source_url'],
                'closed_at': None,
                'closed_url': None,
                'last_event_type': _normalize_event_type(open_row['event_type']),
                'last_event_at': opened_at,
                'language': _extract_language(open_row['details']),
                'flair': _extract_flair(open_row['details'])
            })
        else:
            closed_row = _fetch_event_by_id(cursor, last_closed_id)
            if not closed_row:
                continue
            cursor.execute('''
                SELECT timestamp, source_url
                FROM enrollment_events
                WHERE tracker_name = ?
                  AND event_type IN ('open', 'open_signup')
                  AND id < ?
                ORDER BY id DESC
                LIMIT 1
            ''', (tracker, last_closed_id))
            opened_row = cursor.fetchone()
            opened_at = _normalize_timestamp(opened_row['timestamp']) if opened_row else None
            history_items.append({
                'tracker': tracker,
                'opened_at': opened_at,
                'opened_url': opened_row['source_url'] if opened_row else None,
                'closed_at': _normalize_timestamp(closed_row['timestamp']),
                'closed_url': closed_row['source_url'],
                'last_event_type': 'closed',
                'last_event_at': _normalize_timestamp(closed_row['timestamp']),
                'language': _extract_language(closed_row['details']),
                'flair': _extract_flair(closed_row['details'])
            })

    history_items.sort(key=lambda item: (item.get('tracker') or '').lower())
    history_items.sort(key=lambda item: item.get('last_event_at') or '', reverse=True)

    if limit is not None:
        history_items = history_items[:limit]

    return history_items


@app.route('/api/status')
def get_status():
    """Get current monitor status."""
    global last_run_time

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get total events count
        cursor.execute('SELECT COUNT(*) as count FROM enrollment_events')
        total_events = cursor.fetchone()['count']

        # Get events in last 24h
        cursor.execute('''
            SELECT COUNT(*) as count FROM enrollment_events
            WHERE timestamp > datetime('now', '-24 hours')
        ''')
        events_24h = cursor.fetchone()['count']

        conn.close()

        # Calculate next run
        next_run = None
        if last_run_time:
            next_run = (last_run_time + timedelta(minutes=CHECK_INTERVAL_MINUTES)).isoformat()

        return jsonify({
            'last_run': last_run_time.isoformat() if last_run_time else None,
            'next_run': next_run,
            'check_interval_minutes': CHECK_INTERVAL_MINUTES,
            'total_events': total_events,
            'events_24h': events_24h,
            'last_run_matches': last_run_matches
        })

    except Exception as e:
        logger.error(f"Error in /api/status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/events')
def get_events():
    """Get recent enrollment events (match history)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, tracker_name, event_type, timestamp, source, source_url, details
            FROM enrollment_events
            ORDER BY timestamp DESC
            LIMIT 50
        ''')

        events = []
        for row in cursor.fetchall():
            events.append({
                'id': row['id'],
                'tracker': row['tracker_name'],
                'type': row['event_type'],
                'timestamp': row['timestamp'],
                'source': row['source'],
                'url': row['source_url'],
                'details': row['details']
            })

        conn.close()
        return jsonify({'events': events})

    except Exception as e:
        logger.error(f"Error in /api/events: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/open')
def get_open_signups():
    """Get currently open signups based on latest open/closed events."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT tracker_name,
                   MAX(CASE WHEN event_type IN ('open', 'open_signup') THEN id END) as last_open_id,
                   MAX(CASE WHEN event_type IN ('closed', 'close') THEN id END) as last_closed_id
            FROM enrollment_events
            GROUP BY tracker_name
        ''')

        open_signups = []
        for row in cursor.fetchall():
            tracker = row['tracker_name']
            last_open_id = row['last_open_id']
            last_closed_id = row['last_closed_id']

            if not last_open_id:
                continue
            if last_closed_id and last_closed_id >= last_open_id:
                continue

            if last_closed_id:
                cursor.execute('''
                    SELECT COUNT(*) as count
                    FROM enrollment_events
                    WHERE tracker_name = ?
                      AND event_type IN ('open', 'open_signup')
                      AND id > ?
                ''', (tracker, last_closed_id))
                mentions = cursor.fetchone()['count']

                cursor.execute('''
                    SELECT MIN(timestamp) as first_seen
                    FROM enrollment_events
                    WHERE tracker_name = ?
                      AND event_type IN ('open', 'open_signup')
                      AND id > ?
                ''', (tracker, last_closed_id))
                first_seen = cursor.fetchone()['first_seen']

                cursor.execute('''
                    SELECT source_url, details, timestamp
                    FROM enrollment_events
                    WHERE tracker_name = ?
                      AND event_type IN ('open', 'open_signup')
                      AND id > ?
                    ORDER BY id DESC
                    LIMIT 1
                ''', (tracker, last_closed_id))
                last_open_row = cursor.fetchone()
            else:
                cursor.execute('''
                    SELECT COUNT(*) as count
                    FROM enrollment_events
                    WHERE tracker_name = ?
                      AND event_type IN ('open', 'open_signup')
                ''', (tracker,))
                mentions = cursor.fetchone()['count']

                cursor.execute('''
                    SELECT MIN(timestamp) as first_seen
                    FROM enrollment_events
                    WHERE tracker_name = ?
                      AND event_type IN ('open', 'open_signup')
                ''', (tracker,))
                first_seen = cursor.fetchone()['first_seen']

                cursor.execute('''
                    SELECT source_url, details, timestamp
                    FROM enrollment_events
                    WHERE tracker_name = ?
                      AND event_type IN ('open', 'open_signup')
                    ORDER BY id DESC
                    LIMIT 1
                ''', (tracker,))
                last_open_row = cursor.fetchone()

            open_signups.append({
                'tracker': tracker,
                'first_seen': first_seen or last_open,
                'last_seen': last_open_row['timestamp'] if last_open_row else None,
                'url': last_open_row['source_url'] if last_open_row else None,
                'details': last_open_row['details'] if last_open_row else None,
                'mentions': mentions
            })

        conn.close()
        open_signups = sorted(open_signups, key=lambda item: item['last_seen'] or '', reverse=True)
        return jsonify({'open_signups': open_signups})

    except Exception as e:
        logger.error(f"Error in /api/open: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ha/open')
def get_ha_open_signups():
    """Get HA-friendly open signup list with stable hash."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        open_items = _get_open_items(cursor)

        payload = {'open': open_items}
        response = {
            'hash': _compute_hash(payload),
            'generated_at': datetime.now().astimezone().isoformat(),
            'open': open_items
        }
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in /api/ha/open: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/ha/history')
def get_ha_history():
    """Get HA-friendly history list with stable hash."""
    conn = None
    try:
        limit_param = request.args.get('limit', '50')
        try:
            limit = int(limit_param)
        except ValueError:
            limit = 50
        if limit < 1:
            limit = 1

        conn = get_db_connection()
        cursor = conn.cursor()
        history_items = _get_history_items(cursor, limit)

        payload = {'history': history_items}
        response = {
            'hash': _compute_hash(payload),
            'generated_at': datetime.now().astimezone().isoformat(),
            'history': history_items
        }
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in /api/ha/history: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


def update_run_status(run_time: datetime, matches: list):
    """Update the last run status (called by main app)."""
    global last_run_time, last_run_matches
    last_run_time = run_time
    last_run_matches = matches


def start_api_server(port: int = 5000):
    """Start the API server in a background thread."""
    def run():
        # Disable Flask's default logging
        import logging as flask_logging
        flask_logging.getLogger('werkzeug').setLevel(flask_logging.WARNING)

        logger.info(f"Starting API server on port {port}")
        app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)

    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=5000, debug=True)
