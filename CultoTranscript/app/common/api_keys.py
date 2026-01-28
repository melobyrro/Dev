"""
Helpers for managing per-church API keys and scoped usage.
"""
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.exc import ProgrammingError
from app.common.database import get_db
from app.common.models import ChurchApiKey

logger = logging.getLogger(__name__)

# Active API key for the current execution context (request/job)
_active_api_key: ContextVar[Optional[str]] = ContextVar("active_api_key", default=None)

# Simple in-memory cache for church API keys to reduce database hits
_key_cache: dict[int, dict] = {}
_CACHE_TTL = timedelta(seconds=60)


def set_active_api_key(api_key: Optional[str]):
    """Set the active API key for the current context."""
    return _active_api_key.set(api_key)


def get_active_api_key() -> Optional[str]:
    """Get the active API key for the current context (if any)."""
    return _active_api_key.get()


@contextmanager
def use_api_key(api_key: Optional[str]):
    """
    Context manager to temporarily set the active API key.

    Ensures nested operations share the same key without leaking to other requests.
    """
    token = _active_api_key.set(api_key)
    try:
        yield
    finally:
        _active_api_key.reset(token)


def mask_api_key(api_key: Optional[str], visible: int = 5) -> Optional[str]:
    """
    Mask an API key, showing only the last `visible` characters.
    """
    if not api_key:
        return None
    if len(api_key) <= visible:
        return "*" * len(api_key)
    return f"{'*' * (len(api_key) - visible)}{api_key[-visible:]}"


def invalidate_api_key_cache(channel_id: int):
    """Invalidate cached API key for a church."""
    _key_cache.pop(channel_id, None)


def _get_cached_key(channel_id: int) -> Optional[str]:
    entry = _key_cache.get(channel_id)
    if not entry:
        return None

    if entry["expires_at"] < datetime.utcnow():
        _key_cache.pop(channel_id, None)
        return None

    return entry["api_key"]


def _set_cached_key(channel_id: int, api_key: str):
    _key_cache[channel_id] = {
        "api_key": api_key,
        "expires_at": datetime.utcnow() + _CACHE_TTL
    }


def _get_session(db=None):
    """
    Return a tuple of (session, cleanup_callable) where cleanup will close the
    session only if it was created here.
    """
    if db is not None:
        return db, lambda: None

    ctx = get_db()
    session = ctx.__enter__()

    def cleanup():
        try:
            ctx.__exit__(None, None, None)
        except Exception:
            # __exit__ handles rollback/close; suppress to avoid masking caller errors
            pass

    return session, cleanup


def get_church_api_key(channel_id: int, db=None) -> Optional[str]:
    """
    Retrieve the API key for a specific church.

    Single source of truth: church_api_keys table. No global/env fallback.
    """
    cached = _get_cached_key(channel_id)
    if cached:
        return cached

    session, cleanup = _get_session(db)

    try:
        try:
            record = session.query(ChurchApiKey).filter(
                ChurchApiKey.channel_id == channel_id
            ).first()
        except ProgrammingError:
            session.rollback()
            logger.warning("church_api_keys table missing; no API key available")
            return None

        if record and record.api_key:
            _set_cached_key(channel_id, record.api_key)
            return record.api_key

        return None
    finally:
        cleanup()

def upsert_church_api_key(
    channel_id: int,
    api_key: str,
    updated_by: Optional[int] = None,
    db=None
) -> None:
    """
    Save or update the API key for a church and invalidate caches.
    """
    session, cleanup = _get_session(db)

    try:
        record = session.query(ChurchApiKey).filter(
            ChurchApiKey.channel_id == channel_id
        ).first()

        if record:
            record.api_key = api_key
            record.key_suffix = api_key[-5:] if len(api_key) >= 5 else api_key
            record.updated_at = datetime.utcnow()
            record.updated_by = updated_by
        else:
            record = ChurchApiKey(
                channel_id=channel_id,
                api_key=api_key,
                key_suffix=api_key[-5:] if len(api_key) >= 5 else api_key,
                updated_by=updated_by
            )
            session.add(record)

        session.commit()
        invalidate_api_key_cache(channel_id)
    except Exception:
        session.rollback()
        raise
    finally:
        cleanup()
