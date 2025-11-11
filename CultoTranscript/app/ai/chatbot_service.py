"""
Channel Chatbot Service
Conversational AI for Q&A about channel sermons
"""
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy import text

from app.ai.cache_manager import CacheManager
from app.ai.embedding_service import EmbeddingService
from app.ai.llm_client import get_llm_client
from app.ai.query_classifier import QueryType, get_query_classifier
from app.ai.query_parser import (
    DateExtractionResult,
    DateRangeResult,
    extract_date_details,
    extract_date_range,
    format_date_for_display,
)
from app.ai.speaker_parser import get_speaker_parser
from app.ai.biblical_reference_parser import get_biblical_reference_parser
from app.ai.biblical_passage_service import get_biblical_passage_service
from app.ai.theme_parser import get_theme_parser
from app.ai.theme_service import get_theme_service
from app.common.database import get_db
from app.common.models import GeminiChatHistory, Video, ChatbotQueryMetrics

MONTH_NAMES_PT = [
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

logger = logging.getLogger(__name__)

# Configuration from environment
CHATBOT_DEDUP_ENABLED = os.getenv("CHATBOT_DEDUP_ENABLED", "true").lower() == "true"
CHATBOT_DEDUP_THRESHOLD = float(os.getenv("CHATBOT_DEDUP_THRESHOLD", "0.95"))
CHATBOT_MERGE_ADJACENT_SEC = int(os.getenv("CHATBOT_MERGE_ADJACENT_SEC", "30"))
CHATBOT_MAX_PER_VIDEO = int(os.getenv("CHATBOT_MAX_PER_VIDEO", "2"))


class ChatbotService:
    """
    Channel-specific chatbot using RAG (Retrieval-Augmented Generation)

    Features:
    - Retrieves relevant sermon segments using embeddings
    - Generates contextual answers with unified LLM client (Gemini or Ollama)
    - Maintains conversation history
    - Cites specific sermons and timestamps
    - Automatically falls back to local Ollama when Gemini quota is exhausted
    """

    def __init__(self):
        """Initialize chatbot service"""
        self.llm = get_llm_client()
        self.embedding_service = EmbeddingService()
        self.cache_manager = CacheManager()
        self.query_classifier = get_query_classifier()
        self.speaker_parser = get_speaker_parser()
        self.biblical_parser = get_biblical_reference_parser()
        self.passage_service = get_biblical_passage_service()
        self.theme_parser = get_theme_parser()
        self.theme_service = get_theme_service()
        logger.info(
            f"Chatbot service initialized with unified LLM client, caching, query classification, "
            f"speaker detection, biblical reference parsing, and theme extraction "
            f"(dedup_enabled={CHATBOT_DEDUP_ENABLED})"
        )

    @staticmethod
    def _normalize_query(query: str) -> str:
        """
        Normalize query for grouping similar questions

        Args:
            query: Original query text

        Returns:
            Normalized query (lowercase, no punctuation)
        """
        # Convert to lowercase
        normalized = query.lower()

        # Remove punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def _log_query_metrics(
        self,
        channel_id: int,
        session_id: str,
        query: str,
        segments_returned: int,
        response_time_ms: int,
        cache_hit: bool,
        date_filters_used: bool,
        speaker_filter_used: bool,
        biblical_filter_used: bool,
        theme_filter_used: bool,
        query_type: QueryType,
        backend_used: str,
        metadata: Dict = None
    ) -> None:
        """
        Log query metrics to database for analytics

        Args:
            channel_id: Channel ID
            session_id: Session ID
            query: User query
            segments_returned: Number of segments returned
            response_time_ms: Response time in milliseconds
            cache_hit: Whether response was cached
            date_filters_used: Whether date filters were applied
            speaker_filter_used: Whether speaker filter was applied
            biblical_filter_used: Whether biblical filter was applied
            theme_filter_used: Whether theme filter was applied
            query_type: Query type from classifier
            backend_used: LLM backend used
            metadata: Additional metadata
        """
        try:
            with get_db() as db:
                metrics = ChatbotQueryMetrics(
                    query=query,
                    query_normalized=self._normalize_query(query),
                    channel_id=channel_id,
                    session_id=session_id,
                    segments_returned=segments_returned,
                    response_time_ms=response_time_ms,
                    cache_hit=cache_hit,
                    date_filters_used=date_filters_used,
                    speaker_filter_used=speaker_filter_used,
                    biblical_filter_used=biblical_filter_used,
                    theme_filter_used=theme_filter_used,
                    query_type=query_type.value if query_type else None,
                    backend_used=backend_used,
                    metadata=metadata or {}
                )
                db.add(metrics)
                db.commit()
                logger.debug(f"Logged query metrics for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to log query metrics: {e}", exc_info=True)

    @staticmethod
    @lru_cache(maxsize=1000)
    def _calculate_similarity_cached(
        embedding1_tuple: Tuple[float, ...],
        embedding2_tuple: Tuple[float, ...]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings with caching

        Args:
            embedding1_tuple: First embedding as tuple (hashable)
            embedding2_tuple: Second embedding as tuple (hashable)

        Returns:
            Cosine similarity (0-1, higher = more similar)
        """
        # Convert tuples back to numpy arrays
        vec1 = np.array(embedding1_tuple)
        vec2 = np.array(embedding2_tuple)

        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _deduplicate_segments(
        self,
        segments: List[Dict],
        similarity_threshold: float = None,
        merge_adjacent: bool = True
    ) -> List[Dict]:
        """
        Remove duplicate and highly similar segments

        Strategy:
        1. Group segments by video_id
        2. Within each video:
           - Merge adjacent segments (if timestamps differ by <30 seconds)
           - Remove segments with >95% semantic similarity
           - Keep highest scoring unique segments
        3. Limit to max 2 segments per video (unless explicitly different topics)

        Args:
            segments: List of segment dictionaries from search
            similarity_threshold: Similarity threshold (default from config)
            merge_adjacent: Whether to merge adjacent segments

        Returns:
            Deduplicated list of segments
        """
        if not CHATBOT_DEDUP_ENABLED or not segments:
            return segments

        if similarity_threshold is None:
            similarity_threshold = CHATBOT_DEDUP_THRESHOLD

        original_count = len(segments)
        logger.debug(f"🔄 Starting deduplication: {original_count} segments")

        # First, fetch embeddings for all segments from database
        with get_db() as db:
            # Group segments by video
            segments_by_video = {}
            for seg in segments:
                video_id = seg['video_id']
                if video_id not in segments_by_video:
                    segments_by_video[video_id] = []
                segments_by_video[video_id].append(seg)

            # Fetch embeddings for all segments
            for video_id, video_segments in segments_by_video.items():
                # Get embeddings from database for this video's segments
                segment_starts = [s['segment_start'] for s in video_segments]

                result = db.execute(text("""
                    SELECT segment_start, embedding
                    FROM transcript_embeddings
                    WHERE video_id = :video_id
                      AND segment_start = ANY(:segment_starts)
                """), {
                    'video_id': video_id,
                    'segment_starts': segment_starts
                }).fetchall()

                # Map embeddings to segments
                embedding_map = {row[0]: row[1] for row in result}

                for seg in video_segments:
                    seg['_embedding'] = embedding_map.get(seg['segment_start'])

        # Process each video's segments
        deduplicated = []
        stats = {
            'merged_adjacent': 0,
            'removed_similar': 0,
            'limited_per_video': 0
        }

        for video_id, video_segments in segments_by_video.items():
            # Sort by timestamp for adjacent merging
            video_segments.sort(key=lambda x: x['segment_start_sec'])

            # Step 1: Merge adjacent segments
            if merge_adjacent:
                video_segments = self._merge_adjacent_segments(
                    video_segments,
                    max_gap_sec=CHATBOT_MERGE_ADJACENT_SEC,
                    stats=stats
                )

            # Step 2: Remove semantically similar segments
            video_segments = self._remove_similar_segments(
                video_segments,
                similarity_threshold=similarity_threshold,
                stats=stats
            )

            # Step 3: Limit per video (keep top N by relevance)
            if len(video_segments) > CHATBOT_MAX_PER_VIDEO:
                # Sort by relevance score
                video_segments.sort(key=lambda x: x['relevance'], reverse=True)
                removed_count = len(video_segments) - CHATBOT_MAX_PER_VIDEO
                video_segments = video_segments[:CHATBOT_MAX_PER_VIDEO]
                stats['limited_per_video'] += removed_count
                logger.debug(
                    f"📊 Limited video {video_id} to {CHATBOT_MAX_PER_VIDEO} segments "
                    f"(removed {removed_count} lower-scoring segments)"
                )

            deduplicated.extend(video_segments)

        # Clean up temporary embeddings
        for seg in deduplicated:
            if '_embedding' in seg:
                del seg['_embedding']

        # Sort by relevance score
        deduplicated.sort(key=lambda x: x['relevance'], reverse=True)

        final_count = len(deduplicated)
        reduction_pct = ((original_count - final_count) / original_count * 100) if original_count > 0 else 0

        logger.info(
            f"🔄 Deduplication complete: {original_count} → {final_count} segments "
            f"({reduction_pct:.1f}% reduction) | "
            f"Merged: {stats['merged_adjacent']}, Similar: {stats['removed_similar']}, "
            f"Limited: {stats['limited_per_video']}"
        )

        return deduplicated

    def _merge_adjacent_segments(
        self,
        segments: List[Dict],
        max_gap_sec: int,
        stats: Dict
    ) -> List[Dict]:
        """
        Merge segments that are within max_gap_sec of each other

        Args:
            segments: Sorted list of segments (by timestamp)
            max_gap_sec: Maximum gap in seconds to merge
            stats: Stats dictionary to update

        Returns:
            List of segments with adjacent ones merged
        """
        if len(segments) <= 1:
            return segments

        merged = []
        i = 0

        while i < len(segments):
            current = segments[i].copy()

            # Look ahead for adjacent segments
            j = i + 1
            while j < len(segments):
                next_seg = segments[j]

                # Check if within merge window
                gap = next_seg['segment_start_sec'] - current['segment_end_sec']

                if gap <= max_gap_sec:
                    # Merge segments
                    logger.debug(
                        f"🔗 Merging adjacent segments (gap={gap}s): "
                        f"[{current['segment_start_sec']}-{current['segment_end_sec']}] + "
                        f"[{next_seg['segment_start_sec']}-{next_seg['segment_end_sec']}]"
                    )

                    # Combine text with separator
                    current['segment_text'] = current['segment_text'] + " ... " + next_seg['segment_text']

                    # Extend timestamp range
                    current['segment_end'] = next_seg['segment_end']
                    current['segment_end_sec'] = next_seg['segment_end_sec']

                    # Keep higher relevance score
                    if next_seg['relevance'] > current['relevance']:
                        current['relevance'] = next_seg['relevance']
                        current['score_breakdown'] = next_seg.get('score_breakdown')
                        current['base_relevance'] = next_seg.get('base_relevance')

                    # Use embedding from higher-scoring segment
                    if next_seg.get('_embedding') is not None and next_seg['relevance'] > current['relevance']:
                        current['_embedding'] = next_seg['_embedding']

                    stats['merged_adjacent'] += 1
                    j += 1
                else:
                    # Gap too large, stop merging
                    break

            merged.append(current)
            i = j if j > i + 1 else i + 1

        return merged

    def _remove_similar_segments(
        self,
        segments: List[Dict],
        similarity_threshold: float,
        stats: Dict
    ) -> List[Dict]:
        """
        Remove segments that are semantically very similar (>threshold similarity)

        Args:
            segments: List of segments
            similarity_threshold: Similarity threshold (0-1)
            stats: Stats dictionary to update

        Returns:
            List with similar segments removed
        """
        if len(segments) <= 1:
            return segments

        # Filter out segments without embeddings
        segments_with_embeddings = [s for s in segments if s.get('_embedding') is not None]
        segments_without_embeddings = [s for s in segments if s.get('_embedding') is None]

        if not segments_with_embeddings:
            logger.debug("⚠️ No embeddings available for similarity comparison")
            return segments

        # Track which segments to keep
        keep = []
        removed = []

        for i, seg1 in enumerate(segments_with_embeddings):
            is_duplicate = False

            # Compare with already kept segments
            for seg2 in keep:
                if seg1.get('_embedding') is None or seg2.get('_embedding') is None:
                    continue

                # Convert embeddings to tuples for caching
                emb1_tuple = tuple(seg1['_embedding'])
                emb2_tuple = tuple(seg2['_embedding'])

                similarity = self._calculate_similarity_cached(emb1_tuple, emb2_tuple)

                if similarity >= similarity_threshold:
                    # High similarity - this is a duplicate
                    logger.debug(
                        f"🚫 Removing duplicate segment ({similarity:.1%} similar) from video {seg1['video_id']}: "
                        f"'{seg1['segment_text'][:50]}...' vs '{seg2['segment_text'][:50]}...'"
                    )
                    is_duplicate = True
                    stats['removed_similar'] += 1
                    removed.append(seg1)
                    break

            if not is_duplicate:
                keep.append(seg1)

        # Add back segments without embeddings (can't compare them)
        result = keep + segments_without_embeddings

        return result

    def chat(
        self,
        channel_id: int,
        user_message: str,
        session_id: str = None
    ) -> Dict:
        """
        Handle a chat message with caching (Phase 2: with metrics tracking)

        Args:
            channel_id: Channel ID
            user_message: User's question
            session_id: Optional session ID for conversation history

        Returns:
            Dictionary with response and cited videos
        """
        # Start time tracking for metrics
        start_time = time.time()

        # Generate or use existing session ID
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"Chat request for channel {channel_id}: {user_message[:100]}")

        # Classify query early to determine optimal response configuration
        query_type, response_config = self.query_classifier.classify_and_configure(user_message)
        logger.info(f"🎯 Query classified as {query_type.value}, using max_tokens={response_config.max_tokens}, temperature={response_config.temperature}, context_size={response_config.context_size}")

        # Use dynamic context size from response_config
        top_k = response_config.context_size

        # Phase 1.1: Extract speaker from query
        speaker_result = self.speaker_parser.extract_speaker(user_message)
        speaker_filter = None

        if speaker_result.found:
            # Convert speaker name to SQL ILIKE pattern for partial matching
            speaker_filter = self.speaker_parser.get_search_pattern(speaker_result.speaker_name)
            logger.info(f"🎤 Speaker filter applied: '{speaker_result.speaker_name}' (pattern: {speaker_filter})")

        # Phase 1.2: Extract biblical reference from query
        biblical_ref = self.biblical_parser.extract_reference(user_message)
        video_ids_filter = None

        if biblical_ref.found:
            # Get videos that reference this passage
            video_ids_filter = self.passage_service.find_sermons_by_reference(
                channel_id=channel_id,
                reference=biblical_ref,
                passage_types=None  # Search all types (citation, reading, mention)
            )

            if video_ids_filter:
                logger.info(f"📖 Biblical filter applied: {biblical_ref.osis_ref} ({len(video_ids_filter)} sermons found)")
            else:
                logger.warning(f"📖 No sermons found referencing {biblical_ref.osis_ref}")

        # Phase 1.3: Extract themes from query
        theme_result = self.theme_parser.extract_themes(user_message)
        theme_video_ids = None

        if theme_result.found:
            # Get videos that match these themes
            theme_video_ids = self.theme_service.find_sermons_by_themes(
                channel_id=channel_id,
                themes=theme_result.themes,
                min_confidence=0.5,  # Use themes with confidence >= 0.5
                use_and_logic=False  # OR logic: match ANY theme by default
            )

            if theme_video_ids:
                logger.info(f"🎨 Theme filter applied: {theme_result.themes} ({len(theme_video_ids)} sermons found)")
            else:
                logger.warning(f"🎨 No sermons found with themes {theme_result.themes}")

            # Combine theme filter with biblical filter if both exist
            if video_ids_filter is not None:
                # Intersection: sermons must match BOTH biblical reference AND themes
                combined_ids = set(video_ids_filter) & set(theme_video_ids)
                video_ids_filter = list(combined_ids)
                logger.info(f"🔗 Combined biblical + theme filters: {len(video_ids_filter)} sermons")
            else:
                # Use theme filter alone
                video_ids_filter = theme_video_ids

        # Phase 2: Use enhanced date range extraction
        date_range = extract_date_range(user_message)

        if date_range:
            if date_range.is_range and date_range.start_date and date_range.end_date:
                logger.info(
                    "📅 Date range detected: %s to %s (type=%s)",
                    date_range.start_date.date(),
                    date_range.end_date.date(),
                    date_range.query_type
                )
            elif date_range.query_type in ['last_sermon', 'second_last_sermon']:
                logger.info(f"🔍 Smart query detected: {date_range.query_type}")
            elif date_range.start_date:
                logger.info(
                    "📅 Single date detected: %s (type=%s)",
                    date_range.start_date.date(),
                    date_range.query_type
                )
        else:
            logger.debug("No date filter found in query - searching all videos")

        # Use Phase 2 search with date range support + Phase 1.1 speaker filter + Phase 1.2 biblical filter
        try:
            if date_range:
                relevant_segments = self._search_with_date_range(
                    channel_id=channel_id,
                    query=user_message,
                    date_range=date_range,
                    speaker_filter=speaker_filter,
                    video_ids_filter=video_ids_filter
                )
                if not relevant_segments and date_range.start_date:
                    logger.info("No segments from vector search; using chronological fallback for date %s", date_range.start_date.date())
                    relevant_segments = self._fallback_segments_for_date(
                        channel_id=channel_id,
                        date_range=date_range,
                        query=user_message,
                        speaker_filter=speaker_filter,
                        video_ids_filter=video_ids_filter,
                        top_k=top_k
                    )
            else:
                # No date filter - search all videos (with optional speaker and biblical filters)
                relevant_segments = self.embedding_service.search_similar_segments(
                    channel_id=channel_id,
                    query=user_message,
                    top_k=10,
                    speaker_filter=speaker_filter,
                    video_ids_filter=video_ids_filter
                )
        except ValueError as e:
            # Handle case when embeddings are unavailable (Gemini quota exhausted)
            if "embeddings unavailable" in str(e).lower() or "gemini" in str(e).lower():
                logger.error(f"❌ Chatbot unavailable due to embedding service failure: {e}")
                error_message = (
                    "Desculpe, o chatbot está temporariamente indisponível devido ao limite de uso da API do Google Gemini. "
                    "Por favor, tente novamente mais tarde (geralmente após 1 minuto)."
                )

                self._save_history_entry(
                    channel_id=channel_id,
                    session_id=session_id,
                    user_message=user_message,
                    assistant_response=error_message,
                    cited_videos=[]
                )

                return {
                    'response': error_message,
                    'cited_videos': [],
                    'session_id': session_id,
                    'relevance_scores': [],
                    'cached': False,
                    'error': 'quota_exceeded'
                }
            else:
                raise

        # Apply enhanced relevance scoring
        if relevant_segments:
            relevant_segments = self._apply_enhanced_scoring(
                relevant_segments,
                speaker_filter=speaker_result.speaker_name if speaker_result.found else None
            )

        # Apply semantic deduplication (Phase 1: Deduplication)
        if relevant_segments:
            relevant_segments = self._deduplicate_segments(relevant_segments)

        # Debug logging
        logger.info(f"📊 Found {len(relevant_segments)} relevant segments")
        if relevant_segments:
            logger.info(f"📚 Videos: {[s['video_title'] for s in relevant_segments]}")
            # Log speaker information
            speakers = set(s.get('speaker', 'Desconhecido') for s in relevant_segments)
            logger.info(f"🎤 Speakers in results: {speakers}")
            relevance_pcts = [f"{s['relevance']:.2%}" for s in relevant_segments]
            logger.info(f"🎯 Enhanced relevance scores: {relevance_pcts}")
            # Log scoring breakdown for top result
            if relevant_segments[0].get('score_breakdown'):
                logger.debug(f"🔍 Top result score breakdown: {relevant_segments[0]['score_breakdown']}")
        else:
            if speaker_filter:
                logger.warning(f"⚠️ No relevant segments found for query with speaker filter '{speaker_result.speaker_name}': {user_message[:100]}")
            else:
                logger.warning(f"⚠️ No relevant segments found for query: {user_message[:100]}")

        # Extract video IDs for cache key
        video_ids = [seg['video_id'] for seg in relevant_segments]

        # Check cache first
        cached_response = self.cache_manager.get_cached_response(
            user_message,
            video_ids
        )

        if cached_response:
            logger.info(f"Using cached chatbot response (age={cached_response['cache_age_hours']:.1f}h)")

            # Still save to history for conversation tracking
            self._save_history_entry(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=cached_response['response'],
                cited_videos=cached_response['cited_videos']
            )

            # Log metrics (cached response)
            response_time_ms = int((time.time() - start_time) * 1000)
            self._log_query_metrics(
                channel_id=channel_id,
                session_id=session_id,
                query=user_message,
                segments_returned=len(relevant_segments),
                response_time_ms=response_time_ms,
                cache_hit=True,
                date_filters_used=date_range is not None,
                speaker_filter_used=speaker_filter is not None,
                biblical_filter_used=biblical_ref.found if biblical_ref else False,
                theme_filter_used=theme_result.found if theme_result else False,
                query_type=query_type,
                backend_used='cache',
                metadata={
                    'cache_age_hours': cached_response.get('cache_age_hours'),
                    'hit_count': cached_response.get('hit_count')
                }
            )

            return {
                'response': cached_response['response'],
                'cited_videos': cached_response['cited_videos'],
                'session_id': session_id,
                'relevance_scores': cached_response['relevance_scores'],
                'cached': True,
                'cache_age_hours': cached_response['cache_age_hours'],
                'hit_count': cached_response['hit_count']
            }

        # Cache miss - generate new response
        logger.info(f"Generating new chatbot response with LLM")

        # Get conversation history
        conversation_context = self._get_conversation_history(
            channel_id, session_id, limit=3
        )

        # Build prompt with context and query-type specific instruction
        prompt = self._build_prompt(
            user_message,
            relevant_segments,
            conversation_context,
            query_type=query_type,
            response_instruction=response_config.instruction,
            biblical_ref=biblical_ref if biblical_ref.found else None,
            theme_result=theme_result if theme_result.found else None
        )

        # Generate response using unified LLM client with query-specific max_tokens and temperature
        llm_response = self.llm.generate(
            prompt=prompt,
            max_tokens=response_config.max_tokens,
            temperature=response_config.temperature  # Now dynamic!
        )
        response_text = llm_response["text"]
        backend_used = llm_response["backend"]

        logger.info(f"✅ Chatbot response generated using {backend_used} backend (query_type={query_type.value})")

        unique_sources = self._build_unique_citations(relevant_segments)
        cited_videos = [entry['citation'] for entry in unique_sources]
        relevance_scores = [entry['relevance'] for entry in unique_sources]

        # Store in cache
        self.cache_manager.store_response(
            user_message,
            video_ids,
            response_text,
            cited_videos,
            relevance_scores
        )

        # Save to history
        self._save_history_entry(
            channel_id=channel_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=response_text,
            cited_videos=cited_videos
        )

        # Log metrics (new response)
        response_time_ms = int((time.time() - start_time) * 1000)
        self._log_query_metrics(
            channel_id=channel_id,
            session_id=session_id,
            query=user_message,
            segments_returned=len(relevant_segments),
            response_time_ms=response_time_ms,
            cache_hit=False,
            date_filters_used=date_range is not None,
            speaker_filter_used=speaker_filter is not None,
            biblical_filter_used=biblical_ref.found if biblical_ref else False,
            theme_filter_used=theme_result.found if theme_result else False,
            query_type=query_type,
            backend_used=backend_used,
            metadata={
                'tokens_used': llm_response.get('tokens_used', 0),
                'max_tokens': response_config.max_tokens,
                'temperature': response_config.temperature
            }
        )

        return {
            'response': response_text,
            'cited_videos': cited_videos,
            'session_id': session_id,
            'relevance_scores': relevance_scores,
            'cached': False,
            'backend': backend_used,
            'tokens_used': llm_response.get('tokens_used', 0)
        }

    def _apply_enhanced_scoring(
        self,
        segments: List[Dict],
        speaker_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Apply multi-factor relevance scoring to segments

        Args:
            segments: List of segment dictionaries from search
            speaker_filter: Optional speaker name from query

        Returns:
            Re-ranked segments with enhanced scores
        """
        with get_db() as db:
            for seg in segments:
                video_id = seg['video_id']

                # Get theme confidence from database
                # Use average confidence of all themes for this video
                theme_confidence = db.execute(text("""
                    SELECT AVG(confidence_score) as avg_confidence
                    FROM sermon_themes_v2
                    WHERE video_id = :video_id
                """), {'video_id': video_id}).scalar()

                # Count biblical references in segment text
                # This is a simple word-based estimate
                biblical_keywords = [
                    'bíblia', 'escritura', 'palavra', 'versículo', 'capítulo',
                    'gênesis', 'êxodo', 'levítico', 'números', 'deuteronômio',
                    'josué', 'juízes', 'rute', 'samuel', 'reis', 'crônicas',
                    'esdras', 'neemias', 'ester', 'jó', 'salmos', 'provérbios',
                    'eclesiastes', 'cantares', 'isaías', 'jeremias', 'lamentações',
                    'ezequiel', 'daniel', 'oséias', 'joel', 'amós', 'obadias',
                    'jonas', 'miquéias', 'naum', 'habacuque', 'sofonias', 'ageu',
                    'zacarias', 'malaquias', 'mateus', 'marcos', 'lucas', 'joão',
                    'atos', 'romanos', 'coríntios', 'gálatas', 'efésios',
                    'filipenses', 'colossenses', 'tessalonicenses', 'timóteo',
                    'tito', 'filemom', 'hebreus', 'tiago', 'pedro', 'judas',
                    'apocalipse'
                ]

                segment_text_lower = seg['segment_text'].lower()
                biblical_ref_count = sum(
                    1 for keyword in biblical_keywords
                    if keyword in segment_text_lower
                )

                # Get sermon date (prefer sermon_actual_date, fallback to published_at)
                sermon_date = seg.get('sermon_actual_date')
                if not sermon_date and seg.get('published_at'):
                    sermon_date = seg['published_at']

                # Apply enhanced scoring
                base_score = seg['relevance']
                score_result = self.embedding_service.calculate_relevance_score(
                    base_score=base_score,
                    sermon_date=sermon_date,
                    theme_confidence=theme_confidence,
                    speaker=seg.get('speaker'),
                    requested_speaker=speaker_filter,
                    biblical_references=biblical_ref_count
                )

                # Update segment with enhanced score
                seg['relevance'] = score_result['enhanced_score']
                seg['score_breakdown'] = score_result['factors']
                seg['base_relevance'] = base_score

        # Re-sort by enhanced score
        segments.sort(key=lambda x: x['relevance'], reverse=True)

        return segments

    def _build_prompt(
        self,
        user_message: str,
        relevant_segments: List[Dict],
        conversation_context: List[Dict],
        query_type: QueryType = QueryType.GENERAL,
        response_instruction: str = "",
        biblical_ref = None,
        theme_result = None
    ) -> str:
        """Build prompt for Gemini with context and query-type specific instructions"""
        # Format relevant segments with dates and speaker for clear identification
        context_parts = []
        for seg in relevant_segments:
            # Use sermon_actual_date if available (actual sermon date), fallback to published_at (upload date)
            sermon_date = seg.get('sermon_actual_date')
            if not sermon_date and seg.get('published_at'):
                sermon_date = seg['published_at'].date()  # Convert datetime to date

            # Format date as "DD/MM/YYYY" to match Brazilian format
            date_str = sermon_date.strftime('%d/%m/%Y') if sermon_date else "Data desconhecida"
            speaker = seg.get('speaker', 'Desconhecido')
            sermon_header = f"[Sermão: {seg['video_title']} - {date_str} - Pregador: {speaker}]"
            context_parts.append(f"{sermon_header}\n{seg['segment_text']}")

        context_text = "\n\n---\n\n".join(context_parts)

        # Format conversation history
        history_text = ""
        if conversation_context:
            history_text = "\n\nConversa anterior:\n" + "\n".join([
                f"Usuário: {msg['user']}\nAssistente: {msg['assistant']}"
                for msg in conversation_context
            ])

        # Add query-type specific instruction
        type_specific_rule = ""
        if response_instruction:
            type_specific_rule = f"\n8. FORMATO DA RESPOSTA: {response_instruction}"

        # Add biblical reference context if present
        biblical_context = ""
        if biblical_ref:
            ref_display = biblical_ref.osis_ref
            if biblical_ref.is_whole_book:
                ref_display = f"todo o livro de {biblical_ref.book}"
            elif biblical_ref.is_whole_chapter:
                ref_display = f"{biblical_ref.book} capítulo {biblical_ref.chapter}"
            else:
                chapter = biblical_ref.chapter
                verse_start = biblical_ref.verse_start
                verse_end = biblical_ref.verse_end
                if verse_end and verse_end != verse_start:
                    ref_display = f"{biblical_ref.book} {chapter}:{verse_start}-{verse_end}"
                else:
                    ref_display = f"{biblical_ref.book} {chapter}:{verse_start}"

            biblical_context = f"\n\nCONTEXTO BÍBLICO:\nO usuário perguntou especificamente sobre {ref_display}. Os sermões abaixo foram selecionados porque citam, leem ou mencionam esta passagem bíblica."

        # Add theme context if present (Phase 1.3)
        theme_context = ""
        if theme_result and theme_result.found:
            themes_display = ", ".join(theme_result.themes)
            theme_context = f"\n\nCONTEXTO TEMÁTICO:\nO usuário perguntou especificamente sobre os temas teológicos: {themes_display}. Os sermões abaixo foram selecionados porque abordam estes temas."

        prompt = f"""
Você é um assistente teológico especializado em sermões desta igreja.
Responda a pergunta do usuário baseando-se nos sermões fornecidos abaixo como contexto principal.

REGRAS:
1. Cite o sermão específico ao responder (use o título fornecido entre colchetes)
2. Use os trechos fornecidos como base principal para sua resposta
3. Se não encontrar informação direta, ofereça contexto relacionado dos sermões disponíveis
4. Quando os sermões não cobrem o tema, seja honesto: "Nos sermões disponíveis, não encontrei referência direta a [tema], mas temas relacionados incluem..."
5. Seja conciso mas informativo (ajuste o tamanho conforme o tipo de pergunta)
6. Use linguagem pastoral e respeitosa
7. Quando relevante, conecte insights de diferentes sermões{type_specific_rule}{biblical_context}{theme_context}

SERMÕES RELEVANTES:
{context_text}

{history_text}

PERGUNTA DO USUÁRIO:
{user_message}

RESPOSTA:
"""
        return prompt

    def _get_conversation_history(
        self,
        channel_id: int,
        session_id: str,
        limit: int = 3
    ) -> List[Dict]:
        """Get recent conversation history"""
        with get_db() as db:
            history = db.query(GeminiChatHistory).filter(
                GeminiChatHistory.channel_id == channel_id,
                GeminiChatHistory.session_id == session_id
            ).order_by(
                GeminiChatHistory.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    'user': h.user_message,
                    'assistant': h.assistant_response
                }
                for h in reversed(history)
            ]

    def _should_try_date_fallback(
        self,
        date_info: Optional[DateExtractionResult],
        segments: List[Dict]
    ) -> bool:
        """Only fallback when the user omitted the year and no segments were found."""
        if not date_info or segments:
            return False

        if date_info.explicit_year:
            return False

        return date_info.source in {'numeric', 'day_month_name', 'month_day_name'}

    def _find_latest_matching_date(
        self,
        channel_id: int,
        reference_date: Optional[datetime]
    ) -> Optional[datetime]:
        """
        Look up the most recent year that has a sermon on the requested day/month.
        Ensures the video already has embeddings before falling back.
        """
        if not reference_date:
            return None

        target_date = reference_date.date()
        now = datetime.now(timezone.utc)

        with get_db() as db:
            result = db.execute(text("""
                SELECT COALESCE(v.sermon_actual_date, DATE(v.published_at)) AS sermon_date
                FROM videos v
                WHERE v.channel_id = :channel_id
                  AND COALESCE(v.sermon_actual_date, DATE(v.published_at)) = :target_date
                  AND v.published_at <= :search_limit
                  AND EXISTS (
                      SELECT 1
                      FROM transcript_embeddings te
                      WHERE te.video_id = v.id
                  )
                ORDER BY v.published_at DESC
                LIMIT 1
            """), {
                'channel_id': channel_id,
                'target_date': target_date,
                'search_limit': now
            }).scalar()

        if result:
            return datetime.combine(result, datetime.min.time())

        return None

    def _build_candidate_dates(
        self,
        date_info: Optional[DateExtractionResult]
    ) -> List[datetime]:
        """Return ordered unique list of candidate dates derived from parser info."""
        if not date_info:
            return []

        candidates: List[datetime] = []
        seen = set()
        for dt in [date_info.date] + (date_info.alternatives or []):
            if dt and dt.date() not in seen:
                candidates.append(dt)
                seen.add(dt.date())
        return candidates

    def _search_candidate_dates(
        self,
        channel_id: int,
        query: str,
        candidate_dates: Sequence[datetime]
    ) -> List[Tuple[Optional[datetime], List[Dict]]]:
        """Run embedding search for each candidate date (or all videos when empty)."""
        attempts: List[Tuple[Optional[datetime], List[Dict]]] = []

        if candidate_dates:
            for date_option in candidate_dates:
                segments = self.embedding_service.search_similar_segments(
                    channel_id=channel_id,
                    query=query,
                    top_k=10,
                    date_filter=date_option
                )
                attempts.append((date_option, segments))
        else:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                date_filter=None
            )
            attempts.append((None, segments))

        return attempts

    def _respond_with_ambiguity(
        self,
        channel_id: int,
        session_id: str,
        user_message: str,
        date_info: DateExtractionResult,
        successful_attempts: Sequence[Tuple[datetime, List[Dict]]]
    ) -> Dict:
        """Ask user to clarify when multiple ambiguous dates yield results."""
        options_text = []
        for dt, _ in successful_attempts:
            formatted = format_date_for_display(dt)
            human = self._format_portuguese_date(dt)
            options_text.append(f"- {formatted} ({human})")

        raw_text = date_info.raw_text or "essa data"
        clarification_message = (
            f"Percebi que \"{raw_text}\" pode se referir a mais de uma data. "
            "Pode confirmar qual delas você deseja consultar?\n\n"
            + "\n".join(options_text)
            + "\n\nExemplo: responda \"02/11/2025\" ou \"11/02/2025\"."
        )

        self._save_history_entry(
            channel_id=channel_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=clarification_message,
            cited_videos=[]
        )

        return {
            'response': clarification_message,
            'cited_videos': [],
            'session_id': session_id,
            'relevance_scores': [],
            'cached': False,
            'clarification_required': True
        }

    def _attempt_year_fallback(
        self,
        channel_id: int,
        query: str,
        date_info: Optional[DateExtractionResult],
        already_tried: Sequence[datetime]
    ) -> Tuple[Optional[datetime], List[Dict]]:
        """Search older sermons for the same day/month when year wasn't specified."""
        if not date_info:
            return None, []

        tried_dates = {dt.date() for dt in already_tried if dt}
        reference_dates = [date_info.date] + (date_info.alternatives or [])

        for reference in reference_dates:
            if not reference:
                continue

            fallback_date = self._find_latest_matching_date(channel_id, reference)
            if not fallback_date or fallback_date.date() in tried_dates:
                continue

            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                date_filter=fallback_date
            )

            if segments:
                logger.info(
                    "🔁 No sermons found for %s – falling back to available date %s",
                    reference.date(),
                    fallback_date.date()
                )
                return fallback_date, segments

        if reference_dates:
            logger.info("ℹ️ Date fallback unavailable for %s", reference_dates[0].date())
        else:
            logger.info("ℹ️ Date fallback unavailable")

        return None, []

    def _format_portuguese_date(self, value: datetime) -> str:
        """Return a human-readable Portuguese date string."""
        month_name = MONTH_NAMES_PT[value.month]
        return f"{value.day} de {month_name} de {value.year}"

    def _build_unique_citations(
        self,
        segments: List[Dict]
    ) -> List[Dict]:
        """
        Deduplicate citation list so each video appears once with MM/DD/YYYY date.
        Keeps the segment with the highest relevance score.
        Includes speaker information and YouTube timestamp links (Phase 1.1 + Timestamp Links).
        """
        unique: Dict[int, Dict] = {}

        for seg in segments:
            video_id = seg['video_id']
            sermon_date = seg.get('sermon_actual_date')
            if not sermon_date:
                published_at = seg.get('published_at')
                sermon_date = published_at.date() if published_at else None

            date_str = sermon_date.strftime('%m/%d/%Y') if sermon_date else "Unknown date"
            speaker = seg.get('speaker', 'Desconhecido')

            # Get timestamp for YouTube link
            start_sec = seg.get('segment_start_sec', 0)
            youtube_id = seg['youtube_id']

            # Create YouTube link with timestamp
            youtube_link = f"https://youtube.com/watch?v={youtube_id}"
            if start_sec > 0:
                youtube_link += f"&t={start_sec}s"

            # Include speaker in title: "MM/DD/YYYY - Title (Speaker)"
            title_with_date = f"{date_str} - {seg['video_title']}"
            if speaker and speaker != 'Desconhecido':
                title_with_date += f" ({speaker})"

            citation = {
                'video_id': video_id,
                'video_title': title_with_date,
                'youtube_id': youtube_id,
                'timestamp': seg['segment_start'],  # Word position (legacy)
                'timestamp_sec': start_sec,  # Timestamp in seconds
                'youtube_link': youtube_link,  # Full YouTube URL with timestamp
                'speaker': speaker  # Include speaker in citation metadata
            }

            if (
                video_id not in unique
                or seg['relevance'] > unique[video_id]['relevance']
            ):
                unique[video_id] = {
                    'citation': citation,
                    'relevance': seg['relevance']
                }

        return sorted(unique.values(), key=lambda entry: entry['relevance'], reverse=True)

    def _save_history_entry(
        self,
        channel_id: int,
        session_id: str,
        user_message: str,
        assistant_response: str,
        cited_videos: List[Dict]
    ) -> None:
        """Persist conversation turns for continuity."""
        with get_db() as db:
            history_entry = GeminiChatHistory(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=assistant_response,
                cited_videos=cited_videos
            )
            db.add(history_entry)
            db.commit()

    def _get_last_sermon(self, channel_id: int, offset: int = 0) -> Optional[Video]:
        """
        Get the most recent sermon with transcript from database.

        Args:
            channel_id: Channel ID
            offset: Offset for getting nth-last sermon (0=last, 1=second-last, etc.)

        Returns:
            Video object or None
        """
        with get_db() as db:
            sermon = db.query(Video).filter(
                Video.channel_id == channel_id,
                Video.status == 'completed'
            ).join(
                Video.transcript
            ).order_by(
                Video.published_at.desc()
            ).offset(offset).limit(1).first()

            return sermon

    def _search_with_date_range(
        self,
        channel_id: int,
        query: str,
        date_range: DateRangeResult,
        speaker_filter: Optional[str] = None,
        video_ids_filter: Optional[List[int]] = None
    ) -> List[Dict]:
        """Route date-aware queries to the embedding service."""
        if date_range.query_type == 'last_sermon':
            sermon = self._get_last_sermon(channel_id, offset=0)
            if not sermon:
                return []
            return self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=sermon.published_at,
                end_date=sermon.published_at,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )

        if date_range.query_type == 'second_last_sermon':
            sermon = self._get_last_sermon(channel_id, offset=1)
            if not sermon:
                return []
            return self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=sermon.published_at,
                end_date=sermon.published_at,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )

        if date_range.is_range and date_range.start_date and date_range.end_date:
            return self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=date_range.start_date,
                end_date=date_range.end_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )

        if date_range.start_date and not date_range.is_range:
            return self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                date_filter=date_range.start_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )

        return self.embedding_service.search_similar_segments(
            channel_id=channel_id,
            query=query,
            top_k=10,
            speaker_filter=speaker_filter,
            video_ids_filter=video_ids_filter
        )

    def _search_with_date_range(
        self,
        channel_id: int,
        query: str,
        date_range: DateRangeResult,
        speaker_filter: Optional[str] = None,
        video_ids_filter: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        Search segments using date range information from Phase 2 parser.

        Args:
            channel_id: Channel ID
            query: Search query
            date_range: Parsed date range result
            speaker_filter: Optional speaker filter pattern (Phase 1.1)
            video_ids_filter: Optional list of video IDs to restrict search (Phase 1.2)

        Returns:
            List of relevant segments
        """
    def _fallback_segments_for_date(
        self,
        channel_id: int,
        date_range: DateRangeResult,
        query: str,
        speaker_filter: Optional[str],
        video_ids_filter: Optional[List[int]],
        top_k: int
    ) -> List[Dict]:
        """
        Simple chronological retrieval when embeddings are unavailable.
        """
        if date_range.query_type == 'second_last_sermon':
            sermon = self._get_last_sermon(channel_id, offset=1)
            if not sermon:
                return []

            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=sermon.published_at,
                end_date=sermon.published_at,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(f"Found {len(segments)} segments in second-last sermon (video_id={sermon.id})")
            return segments

        # Handle date range queries
        if date_range.is_range and date_range.start_date and date_range.end_date:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=date_range.start_date,
                end_date=date_range.end_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(
                f"Found {len(segments)} segments in date range "
                f"{date_range.start_date.date()} to {date_range.end_date.date()}"
            )
            return segments

        # Handle single date queries
        if date_range.start_date and not date_range.is_range:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                date_filter=date_range.start_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(f"Found {len(segments)} segments for date {date_range.start_date.date()}")
            return segments

        # No valid date - search all
        else:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(f"Found {len(segments)} segments (no date filter)")
            return segments
