"""
Chatbot Cache Manager
Manages caching of chatbot responses to reduce Gemini API usage
"""
import logging
import hashlib
import os
from typing import Optional, Dict, List
from datetime import datetime, timedelta, timezone

from app.common.database import get_db
from app.common.models import ChatbotCache

logger = logging.getLogger(__name__)

# Feature flags from environment
ENABLE_CHATBOT_CACHE = os.getenv("ENABLE_CHATBOT_CACHE", "true").lower() == "true"
CHATBOT_CACHE_TTL_HOURS = int(os.getenv("CHATBOT_CACHE_TTL_HOURS", "48"))


class CacheManager:
    """
    Manages chatbot response caching with TTL and automatic cleanup

    Features:
    - SHA-256 hash-based cache keys (question + video context)
    - 48-hour TTL by default
    - Hit count tracking
    - Automatic cleanup of expired entries
    - Cache statistics
    """

    def __init__(self):
        """Initialize cache manager"""
        self.cache_hits = 0
        self.cache_misses = 0
        logger.info(f"Cache manager initialized (enabled={ENABLE_CHATBOT_CACHE}, TTL={CHATBOT_CACHE_TTL_HOURS}h)")

    @staticmethod
    def _generate_cache_key(question: str, video_ids: List[int]) -> str:
        """
        Generate cache key from question and video context

        Args:
            question: User's question text
            video_ids: List of video IDs in context (sorted)

        Returns:
            SHA-256 hash string
        """
        # Sort video IDs for consistent hashing
        sorted_ids = sorted(video_ids)
        cache_input = f"{question.lower().strip()}|{','.join(map(str, sorted_ids))}"
        return hashlib.sha256(cache_input.encode('utf-8')).hexdigest()

    def get_cached_response(
        self,
        question: str,
        video_ids: List[int]
    ) -> Optional[Dict]:
        """
        Retrieve cached response if available and valid

        Args:
            question: User's question
            video_ids: Video IDs in context

        Returns:
            Cached response dict or None if not found/expired
        """
        if not ENABLE_CHATBOT_CACHE:
            return None

        cache_key = self._generate_cache_key(question, video_ids)

        with get_db() as db:
            cache_entry = db.query(ChatbotCache).filter(
                ChatbotCache.question_hash == cache_key
            ).first()

            if not cache_entry:
                self.cache_misses += 1
                logger.info(f"CACHE MISS: No cached response for question hash {cache_key[:8]}...")
                return None

            # Check if expired
            now_utc = datetime.now(timezone.utc)
            if cache_entry.expires_at and now_utc > cache_entry.expires_at:
                self.cache_misses += 1
                logger.info(f"CACHE MISS: Expired cache entry for question hash {cache_key[:8]}...")
                # Delete expired entry
                db.delete(cache_entry)
                db.commit()
                return None

            # Update access statistics
            cache_entry.hit_count += 1
            cache_entry.last_accessed = now_utc
            db.commit()

            self.cache_hits += 1
            logger.info(f"CACHE HIT: Using cached response (hit_count={cache_entry.hit_count})")
            logger.info(f"Cache statistics - Hits: {self.cache_hits}, Misses: {self.cache_misses}")

            return {
                'response': cache_entry.response,
                'cited_videos': cache_entry.cited_videos,
                'relevance_scores': cache_entry.relevance_scores,
                'cached': True,
                'cache_age_hours': (datetime.now(timezone.utc) - cache_entry.created_at).total_seconds() / 3600,
                'hit_count': cache_entry.hit_count
            }

    def store_response(
        self,
        question: str,
        video_ids: List[int],
        response: str,
        cited_videos: List[Dict],
        relevance_scores: List[float]
    ):
        """
        Store response in cache with TTL

        Args:
            question: User's question
            video_ids: Video IDs in context
            response: Generated response text
            cited_videos: List of cited video metadata
            relevance_scores: Relevance scores from embedding search
        """
        if not ENABLE_CHATBOT_CACHE:
            return

        cache_key = self._generate_cache_key(question, video_ids)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=CHATBOT_CACHE_TTL_HOURS)

        with get_db() as db:
            # Check if entry already exists (shouldn't happen, but handle gracefully)
            existing = db.query(ChatbotCache).filter(
                ChatbotCache.question_hash == cache_key
            ).first()

            if existing:
                logger.warning(f"Overwriting existing cache entry for hash {cache_key[:8]}...")
                db.delete(existing)

            # Create new cache entry
            cache_entry = ChatbotCache(
                question_hash=cache_key,
                question_text=question,
                response=response,
                video_ids=video_ids,
                cited_videos=cited_videos,
                relevance_scores=relevance_scores,
                expires_at=expires_at,
                hit_count=0
            )
            db.add(cache_entry)
            db.commit()

            logger.info(f"Stored response in cache (expires in {CHATBOT_CACHE_TTL_HOURS}h)")

    def cleanup_expired_entries(self) -> int:
        """
        Remove all expired cache entries

        Returns:
            Number of entries deleted
        """
        with get_db() as db:
            deleted_count = db.query(ChatbotCache).filter(
                ChatbotCache.expires_at < datetime.now(timezone.utc)
            ).delete()
            db.commit()

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired cache entries")

            return deleted_count

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics

        Returns:
            Dictionary with cache statistics
        """
        with get_db() as db:
            total_entries = db.query(ChatbotCache).count()
            expired_entries = db.query(ChatbotCache).filter(
                ChatbotCache.expires_at < datetime.now(timezone.utc)
            ).count()

            # Calculate average hit count
            avg_hit_count = db.query(ChatbotCache).with_entities(
                db.func.avg(ChatbotCache.hit_count)
            ).scalar() or 0

            return {
                'total_entries': total_entries,
                'expired_entries': expired_entries,
                'active_entries': total_entries - expired_entries,
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
                'avg_hit_count_per_entry': float(avg_hit_count)
            }

    def clear_all_cache(self) -> int:
        """
        Clear all cache entries (for testing/debugging)

        Returns:
            Number of entries deleted
        """
        with get_db() as db:
            deleted_count = db.query(ChatbotCache).delete()
            db.commit()

            logger.warning(f"Cleared all cache entries ({deleted_count} deleted)")
            return deleted_count
