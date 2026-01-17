"""
Channel Chatbot Service
Conversational AI for Q&A about channel sermons
"""
import json
import logging
import os
import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from collections import OrderedDict
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy import text, func

from app.ai.cache_manager import CacheManager
from app.ai.embedding_service import EmbeddingService
from app.ai.hybrid_search import HybridSearchService
from app.ai.llm_client import get_llm_client
from app.ai.query_classifier import QueryType, QueryIntent, get_query_classifier
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
from app.ai.search_router import get_router
from app.ai.multi_layer_cache import get_cache
from app.common.database import get_db
from app.common.models import GeminiChatHistory, Video, ChatbotQueryMetrics, BiblicalPassage
from app.common.api_keys import get_church_api_key, use_api_key

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
DEFAULT_MAX_PER_VIDEO = int(os.getenv("CHATBOT_MAX_PER_VIDEO", "2"))


def _get_max_per_video(query_type: str, query_intent: str = 'content') -> int:
    """Get maximum segments per video based on query type and intent"""

    # List queries: maximize coverage (1 per video)
    if query_intent == 'list_all':
        return 1

    # Aggregation/comparison: need full coverage
    if query_intent in ['aggregation', 'comparison', 'statistics']:
        return 1

    # Highlights/questions: dedicated handlers
    if query_intent in ['highlights', 'questions']:
        return 1

    # Date range queries: maximize coverage
    date_range_queries = {
        'single_month', 'month_range', 'custom_range',
        'last_month', 'last_week', 'last_n_days',
        'quarter', 'year', 'multiple_specific_days'
    }
    if query_type in date_range_queries:
        return 1

    # Content queries: need depth (show more context)
    if query_intent in ['content', 'factual']:
        return 3  # Increased from 2

    # Default
    return DEFAULT_MAX_PER_VIDEO


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
        self.embedding_service = EmbeddingService()
        self.cache_manager = CacheManager()
        self.query_classifier = get_query_classifier()
        self.speaker_parser = get_speaker_parser()
        self.biblical_parser = get_biblical_reference_parser()
        self.passage_service = get_biblical_passage_service()
        self.theme_parser = get_theme_parser()
        self.theme_service = get_theme_service()

        # Phase 2: Query Router and Multi-Layer Cache
        self.router = get_router()
        self.multi_cache = get_cache()

        # Initialize hybrid search (Phase 1: Hybrid Search with BM25)
        self.hybrid_search = None  # Will be initialized per-request with DB session

        logger.info(
            f"Chatbot service initialized with unified LLM client, caching, query classification, "
            f"speaker detection, biblical reference parsing, theme extraction, hybrid search, "
            f"and Phase 2 query routing (dedup_enabled={CHATBOT_DEDUP_ENABLED})"
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
        query: str = "",
        query_type: str = 'general',
        query_intent: str = 'content',
        similarity_threshold: float = None,
        merge_adjacent: bool = True
    ) -> Tuple[List[Dict], Dict[str, int]]:
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
            query: User query (for logging)
            query_type: Query type from date range parsing
            similarity_threshold: Similarity threshold (default from config)
            merge_adjacent: Whether to merge adjacent segments

        Returns:
            Tuple of (deduplicated list of segments, deduplication stats)
        """
        stats = {
            'merged_adjacent': 0,
            'removed_similar': 0,
            'limited_per_video': 0
        }

        if not CHATBOT_DEDUP_ENABLED or not segments:
            return segments, stats

        if similarity_threshold is None:
            similarity_threshold = CHATBOT_DEDUP_THRESHOLD

        original_count = len(segments)
        logger.debug(f"🔄 Starting deduplication: {original_count} segments (query_type={query_type})")

        # Get dynamic max_per_video based on query type and intent
        # query_intent should be passed from the caller
        query_intent_str = query_intent if isinstance(query_intent, str) else 'content'
        max_per_video = _get_max_per_video(query_type, query_intent_str)
        logger.info(f"📊 Using max_per_video={max_per_video} for query_type={query_type}, query_intent={query_intent_str}")

        # First, fetch embeddings for all segments from database
        with get_db() as db:
            # Group segments by video
            segments_by_video = {}
            for seg in (segments or []):
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

                # Map embeddings to segments with proper conversion
                embedding_map = {}
                for row in result:
                    segment_start = row[0]
                    raw_embedding = row[1]

                    # Convert pgvector to numpy array
                    try:
                        if raw_embedding is None:
                            continue

                        # Handle different pgvector return types
                        if isinstance(raw_embedding, str):
                            # Parse string representation like "[0.1, 0.2, ...]"
                            if raw_embedding.startswith('['):
                                embedding_list = json.loads(raw_embedding)
                            else:
                                # Handle comma-separated format
                                embedding_list = [float(x.strip()) for x in raw_embedding.strip('[]').split(',')]
                            embedding_array = np.array(embedding_list, dtype=np.float32)
                        elif hasattr(raw_embedding, '__iter__'):
                            # Already iterable (list, tuple, or numpy array)
                            embedding_array = np.array(list(raw_embedding), dtype=np.float32)
                        else:
                            logger.warning(f"Unexpected embedding type: {type(raw_embedding)}")
                            continue

                        # Verify dimensions
                        if len(embedding_array) != 768:
                            logger.warning(
                                f"Embedding dimension mismatch for video {video_id}, segment {segment_start}: "
                                f"expected 768, got {len(embedding_array)}"
                            )
                            continue

                        embedding_map[segment_start] = embedding_array

                    except Exception as e:
                        logger.error(
                            f"Failed to convert embedding for video {video_id}, segment {segment_start}: {e}"
                        )
                        continue

                for seg in (video_segments or []):
                    seg['_embedding'] = embedding_map.get(seg['segment_start'])

        # Process each video's segments
        deduplicated = []

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
            if len(video_segments) > max_per_video:
                # Sort by relevance score
                video_segments.sort(key=lambda x: x['relevance'], reverse=True)
                removed_count = len(video_segments) - max_per_video
                video_segments = video_segments[:max_per_video]
                stats['limited_per_video'] += removed_count
                logger.debug(
                    f"📊 Limited video {video_id} to {max_per_video} segments "
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

        return deduplicated, stats

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

    def _format_video_list_response(self, videos: List[Dict], user_message: str) -> str:
        """Format a list of videos into a response"""

        if not videos:
            return "Não encontrei sermões que correspondam aos critérios especificados."

        # Build response
        response_lines = [f"Encontrei {len(videos)} sermões:"]

        for video in videos:
            # Format date as DD/MM/YYYY
            date_str = "Data desconhecida"
            if video.get('date'):
                try:
                    date_obj = datetime.fromisoformat(video['date'])
                    date_str = date_obj.strftime('%d/%m/%Y')
                except Exception:
                    date_str = video['date']

            speaker = video.get('speaker')
            line = f"- {date_str} — {video['title']}"
            if speaker:
                line += f" ({speaker})"
            line += f"  [▶️](https://youtube.com/watch?v={video['youtube_id']})"

            if video.get('summary'):
                summary = self._clean_summary(video['summary'], max_len=140)
                if summary:
                    line += f"\n  Resumo: {summary}"

            response_lines.append(line)

        return "\n".join(response_lines)

    def _handle_highlight_query(
        self,
        channel_id: int,
        user_message: str,
        date_range: Optional[DateRangeResult] = None
    ) -> str:
        """Handle queries for sermon highlights"""

        with get_db() as db:
            # Build query
            query = """
                SELECT
                    h.title,
                    h.summary,
                    h.start_timestamp,
                    h.end_timestamp,
                    v.title as video_title,
                    v.youtube_id,
                    v.sermon_actual_date,
                    v.published_at
                FROM sermon_highlights h
                JOIN videos v ON h.video_id = v.id
                WHERE v.channel_id = :channel_id
                  AND v.status = 'completed'
            """

            params = {'channel_id': channel_id}

            # Add date filter if present
            if date_range and date_range.start_date and date_range.end_date:
                query += """
                    AND COALESCE(v.sermon_actual_date, DATE(v.published_at))
                        BETWEEN :start_date AND :end_date
                """
                params['start_date'] = date_range.start_date.date() if isinstance(date_range.start_date, datetime) else date_range.start_date
                params['end_date'] = date_range.end_date.date() if isinstance(date_range.end_date, datetime) else date_range.end_date

            query += """
                ORDER BY v.sermon_actual_date DESC, h.start_timestamp
                LIMIT 20
            """

            results = db.execute(text(query), params).fetchall()

            if not results:
                return "Não encontrei destaques para este período."

            # Format response
            response = f"**Destaques encontrados ({len(results)}):**\n\n"

            for r in results:
                sermon_date = r.sermon_actual_date if r.sermon_actual_date else (r.published_at.date() if r.published_at else None)
                date_str = sermon_date.strftime('%d/%m/%Y') if sermon_date else 'Data desconhecida'
                timestamp_link = f"https://youtube.com/watch?v={r.youtube_id}&t={int(r.start_timestamp)}s"
                response += f"**{r.video_title}** ({date_str})\n"
                response += f"- {r.title}: {r.summary}\n"
                response += f"  [▶️ Ver momento]({timestamp_link})\n\n"

            return response

    def _handle_questions_query(
        self,
        channel_id: int,
        user_message: str,
        date_range: Optional[DateRangeResult] = None
    ) -> str:
        """Handle queries for discussion questions"""

        with get_db() as db:
            query = """
                SELECT
                    dq.question,
                    dq.linked_passage_osis,
                    v.title as video_title,
                    v.youtube_id,
                    v.sermon_actual_date,
                    v.published_at
                FROM discussion_questions dq
                JOIN videos v ON dq.video_id = v.id
                WHERE v.channel_id = :channel_id
                  AND v.status = 'completed'
            """

            params = {'channel_id': channel_id}

            if date_range and date_range.start_date and date_range.end_date:
                query += """
                    AND COALESCE(v.sermon_actual_date, DATE(v.published_at))
                        BETWEEN :start_date AND :end_date
                """
                params['start_date'] = date_range.start_date.date() if isinstance(date_range.start_date, datetime) else date_range.start_date
                params['end_date'] = date_range.end_date.date() if isinstance(date_range.end_date, datetime) else date_range.end_date

            query += """
                ORDER BY v.sermon_actual_date DESC, dq.question_order
                LIMIT 30
            """

            results = db.execute(text(query), params).fetchall()

            if not results:
                return "Não encontrei perguntas de discussão para este período."

            # Group by video
            questions_by_video = {}
            for r in results:
                sermon_date = r.sermon_actual_date if r.sermon_actual_date else (r.published_at.date() if r.published_at else None)
                date_str = sermon_date.strftime('%d/%m/%Y') if sermon_date else 'Data desconhecida'
                video_key = (r.video_title, date_str, r.youtube_id)
                if video_key not in questions_by_video:
                    questions_by_video[video_key] = []
                questions_by_video[video_key].append(r.question)

            # Format response
            response = f"**Perguntas para Discussão:**\n\n"

            for (title, date, youtube_id), questions in questions_by_video.items():
                response += f"**{title}** ({date})\n"
                for q in questions:
                    response += f"- {q}\n"
                response += f"  [▶️ Assistir sermão](https://youtube.com/watch?v={youtube_id})\n\n"

            return response

    def _search_with_hybrid(
        self,
        channel_id: int,
        query: str,
        top_k: int = 10,
        date_filter=None,
        start_date=None,
        end_date=None,
        speaker_filter: Optional[str] = None,
        video_ids_filter: Optional[List[int]] = None,
        use_reranking: bool = True
    ) -> List[Dict]:
        """
        Perform hybrid search combining BM25 and semantic search.

        Args:
            channel_id: Channel ID
            query: Search query
            top_k: Number of results to return
            date_filter: Single date filter
            start_date: Start date for range
            end_date: End date for range
            speaker_filter: Speaker pattern
            video_ids_filter: Video IDs to filter

        Returns:
            List of search results
        """
        # Initialize hybrid search with database session
        with get_db() as db:
            hybrid_search = HybridSearchService(db, self.embedding_service)

            # Build filter dictionary for hybrid search
            filters = {}
            if date_filter:
                filters['date_filter'] = date_filter
            if start_date:
                filters['start_date'] = start_date
            if end_date:
                filters['end_date'] = end_date
            if speaker_filter:
                filters['speaker_filter'] = speaker_filter
            if video_ids_filter:
                filters['video_ids_filter'] = video_ids_filter

            # Perform hybrid search
            try:
                results = hybrid_search.search(
                    query=query,
                    channel_id=channel_id,
                    limit=top_k,
                    filters=filters if filters else None,
                    use_reranking=use_reranking
                )
                logger.info(f"Hybrid search returned {len(results)} results")
                return results
            except Exception as e:
                logger.error(f"Hybrid search failed, falling back to semantic: {e}", exc_info=True)
                # Fallback to pure semantic search
                return self.embedding_service.search_similar_segments(
                    channel_id=channel_id,
                    query=query,
                    top_k=top_k,
                    date_filter=date_filter,
                    start_date=start_date,
                    end_date=end_date,
                    speaker_filter=speaker_filter,
                    video_ids_filter=video_ids_filter
                )

    def chat(
        self,
        channel_id: int,
        user_message: str,
        session_id: str = None,
        use_reranking: bool = True,
        knowledge_mode: str = "database_only",
        api_key: Optional[str] = None
    ) -> Dict:
        """
        Handle a chat message with caching (Phase 2: with metrics tracking)

        Args:
            channel_id: Channel ID
            user_message: User's question
            session_id: Optional session ID for conversation history
            use_reranking: Whether to apply cross-encoder reranking (Phase 1.2)
            knowledge_mode: 'database_only' or 'global'
            api_key: Optional explicit API key for this church

        Returns:
            Dictionary with response and cited videos
        """
        # Start time tracking for metrics
        start_time = time.time()

        # Generate or use existing session ID
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"Chat request for channel {channel_id}: {user_message[:100]}")

        # Validate mode and resolve API key
        knowledge_mode = knowledge_mode or "database_only"
        if knowledge_mode not in ("database_only", "global"):
            knowledge_mode = "database_only"

        effective_api_key = api_key or get_church_api_key(channel_id)
        if not effective_api_key:
            error_message = "Nenhuma chave de API está configurada para esta igreja. Peça a um administrador para adicionar a chave na área de configurações."
            self._save_history_entry(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=error_message,
                cited_videos=[]
            )
            return {
                "response": error_message,
                "error": "missing_api_key",
                "cited_videos": [],
                "session_id": session_id,
                "relevance_scores": [],
                "cached": False
            }

        # Classify query early to determine optimal response configuration
        query_type, response_config, query_intent = self.query_classifier.classify_and_configure(user_message)
        logger.info(f"🎯 Query classified as {query_type.value}, intent={query_intent.value}, using max_tokens={response_config.max_tokens}, temperature={response_config.temperature}, context_size={response_config.context_size}")

        # Use dynamic context size from response_config
        top_k = response_config.context_size

        # Phase 2: Extract date range early for routing
        date_range = extract_date_range(user_message)

        # Heuristic: force list intent for listing questions (e.g., "liste os temas", "lista de pregações")
        query_lower = user_message.lower()
        listing_cues = ["liste", "listar", "lista", "quais foram", "temas das prega", "temas das pregações", "temas das mensagens"]
        if any(cue in query_lower for cue in listing_cues):
            query_intent = QueryIntent.LIST_ALL

        # Phase 2: Route query to optimal search strategy (skip local retrieval for global mode)
        relevant_segments = []
        search_strategy = None
        search_params = {}

        if knowledge_mode != "global":
            search_strategy, search_params = self.router.route_query(
                query=user_message,
                query_type=query_type.value,
                query_intent=query_intent.value,
                channel_id=channel_id,
                filters={
                    'start_date': date_range.start_date.isoformat() if date_range and date_range.start_date else None,
                    'end_date': date_range.end_date.isoformat() if date_range and date_range.end_date else None
                }
            )

            logger.info(f"🚀 Search strategy: {search_strategy}")

            # Fast path for direct database queries (LIST_ALL intent)
            if search_strategy == 'direct_database' and query_intent == QueryIntent.LIST_ALL:
                videos = self.router.execute_direct_list_query(
                    channel_id=channel_id,
                    start_date=search_params['filters'].get('start_date'),
                    end_date=search_params['filters'].get('end_date')
                )

                # Format response
                response = self._format_video_list_response(videos, user_message)

                # Save to history
                self._save_history_entry(
                    channel_id=channel_id,
                    session_id=session_id,
                    user_message=user_message,
                    assistant_response=response,
                    cited_videos=[]
                )

                # Log metrics
                response_time_ms = int((time.time() - start_time) * 1000)
                self._log_query_metrics(
                    channel_id=channel_id,
                    session_id=session_id,
                    query=user_message,
                    segments_returned=len(videos),
                    response_time_ms=response_time_ms,
                    cache_hit=False,
                    date_filters_used=date_range is not None,
                    speaker_filter_used=False,
                    biblical_filter_used=False,
                    theme_filter_used=False,
                    query_type=query_type,
                    backend_used='direct_database',
                    metadata={'strategy': search_strategy, 'knowledge_mode': knowledge_mode}
                )

                return {
                    'response': response,
                    'cited_videos': [],
                    'session_id': session_id,
                    'relevance_scores': [],
                    'cached': False,
                    'backend': 'direct_database'
                }

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

        if theme_result.found and knowledge_mode != "global":
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

        # Pre-flight quota check: Verify we haven't exhausted daily limit
        try:
            from app.ai.gemini_usage_tracker import get_daily_quota_snapshot
            quota_stats = get_daily_quota_snapshot()
            # Check if we're at or near daily limit (leave buffer of 5 requests)
            if quota_stats['daily_requests_used'] >= (quota_stats['daily_requests_limit'] - 5):
                logger.warning(f"⚠️ Daily quota nearly exhausted: {quota_stats['daily_requests_used']}/{quota_stats['daily_requests_limit']}")
                error_message = (
                    "Desculpe, o limite diário de uso da API do Google Gemini foi atingido (250 requisições). "
                    "O chatbot voltará a funcionar amanhã após a meia-noite (horário do Pacífico). "
                    f"Requisições hoje: {quota_stats['daily_requests_used']}/{quota_stats['daily_requests_limit']}"
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
                    'error': 'daily_quota_exhausted',
                    'cited_videos': [],
                    'session_id': session_id,
                    'relevance_scores': [],
                    'cached': False
                }
        except Exception as e:
            # If quota check fails, log but continue (don't block chatbot)
            logger.warning(f"⚠️ Could not check quota: {e}")

        # Route to specialized handlers based on query intent
        if query_intent == QueryIntent.HIGHLIGHTS:
            response = self._handle_highlight_query(channel_id, user_message, date_range)
            # Save to history
            self._save_history_entry(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=response,
                cited_videos=[]
            )
            return {
                'response': response,
                'cited_videos': [],
                'session_id': session_id,
                'relevance_scores': [],
                'cached': False,
                'backend': 'structured_lookup'
            }

        if query_intent == QueryIntent.QUESTIONS:
            response = self._handle_questions_query(channel_id, user_message, date_range)
            # Save to history
            self._save_history_entry(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=response,
                cited_videos=[]
            )
            return {
                'response': response,
                'cited_videos': [],
                'session_id': session_id,
                'relevance_scores': [],
                'cached': False,
                'backend': 'structured_lookup'
            }

        # Continue with existing flow for other query types
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

            # Increase search depth for date range queries to ensure full coverage
            date_range_queries = {
                'single_month', 'month_range', 'custom_range',
                'last_month', 'last_week', 'last_n_days',
                'quarter', 'year', 'multiple_specific_days'
            }
        if date_range and date_range.query_type in date_range_queries:
            top_k = max(top_k, 50)  # Ensure we search at least 50 segments for date ranges
            logger.info(f"📈 Increased top_k to {top_k} for date range query (type={date_range.query_type})")

        # Short-circuit responses for last/penultimate when local mode
        if knowledge_mode != "global" and date_range and date_range.query_type in ['last_sermon', 'second_last_sermon']:
            offset = 0 if date_range.query_type == 'last_sermon' else 1
            sermon = self._get_last_sermon(channel_id, offset=offset)
            if sermon:
                sermon_date = sermon.sermon_actual_date or sermon.published_at
                date_str = sermon_date.strftime('%d/%m/%Y') if sermon_date else "Data desconhecida"
                summary = self._clean_summary(getattr(sermon, 'ai_summary', None), max_len=180)
                base = f"{'Último' if offset == 0 else 'Penúltimo'} sermão ({date_str}): {sermon.title}."
                if summary:
                    response = f"{base} Tema/resumo: {summary}"
                else:
                    response = f"{base} Tema não cadastrado ainda."

                self._save_history_entry(
                    channel_id=channel_id,
                    session_id=session_id,
                    user_message=user_message,
                    assistant_response=response,
                    cited_videos=[]
                )

                return {
                    'response': response,
                    'cited_videos': [],
                    'session_id': session_id,
                    'relevance_scores': [],
                    'cached': False,
                    'backend': 'direct_database'
                }
        else:
            logger.debug("No date filter found in query - searching all videos")

        # Structured response for “list bible texts” queries
        if self._is_bible_text_list_query(user_message):
            return self._handle_bible_text_list_query(
                channel_id=channel_id,
                user_message=user_message,
                session_id=session_id,
                date_range=date_range,
                knowledge_mode=knowledge_mode
            )

        # Use Phase 2 search with date range support + Phase 1.1 speaker filter + Phase 1.2 biblical filter
        if knowledge_mode == "global":
            relevant_segments = []
            logger.info("🌐 Global mode active - skipping local sermon retrieval")
        else:
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
                    # Use hybrid search (Phase 1: BM25 + Semantic + Phase 1.2: Reranking)
                    relevant_segments = self._search_with_hybrid(
                        channel_id=channel_id,
                        query=user_message,
                        top_k=10,
                        speaker_filter=speaker_filter,
                        video_ids_filter=video_ids_filter,
                        use_reranking=use_reranking
                    )
            except ValueError as e:
                # Handle case when embeddings are unavailable (Gemini quota exhausted)
                if "embeddings unavailable" in str(e).lower() or "gemini" in str(e).lower():
                    logger.error(f"❌ Chatbot unavailable due to embedding service failure: {e}")
                    error_message = (
                        "Desculpe, o chatbot está temporariamente indisponível devido ao limite de requisições por minuto da API do Google Gemini. "
                        "Por favor, aguarde 1 minuto e tente novamente. "
                        "Se o problema persistir, pode ser que o limite diário (250 requisições) tenha sido atingido."
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
            # Extract query_type from date_range if available
            dedup_query_type = date_range.query_type if date_range else 'general'
            # Convert QueryIntent enum to string
            query_intent_str = query_intent.value if isinstance(query_intent, QueryIntent) else 'content'
            relevant_segments, dedup_stats = self._deduplicate_segments(
                relevant_segments,
                query=user_message,
                query_type=dedup_query_type,
                query_intent=query_intent_str
            )

        # Debug logging
        logger.info(f"📊 Found {len(relevant_segments) if relevant_segments else 0} relevant segments")
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

        if knowledge_mode == "database_only" and not (relevant_segments and len(relevant_segments) > 0):
            fallback_response = (
                "Não encontrei trechos dos sermões deste canal que respondam diretamente a essa pergunta. "
                "Tente refinar o tema, escolher outra data ou formular de outra maneira."
            )

            self._save_history_entry(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=fallback_response,
                cited_videos=[]
            )

            response_time_ms = int((time.time() - start_time) * 1000)
            self._log_query_metrics(
                channel_id=channel_id,
                session_id=session_id,
                query=user_message,
                segments_returned=0,
                response_time_ms=response_time_ms,
                cache_hit=False,
                date_filters_used=date_range is not None,
                speaker_filter_used=speaker_filter is not None,
                biblical_filter_used=biblical_ref.found if biblical_ref else False,
                theme_filter_used=theme_result.found if theme_result else False,
                query_type=query_type,
                backend_used='database_only_no_context',
                metadata={
                    'knowledge_mode': knowledge_mode,
                }
            )

            return {
                'response': fallback_response,
                'cited_videos': [],
                'session_id': session_id,
                'relevance_scores': [],
                'cached': False,
                'backend': 'database_only_no_context'
            }

        # Extract video IDs for cache key
        video_ids = [seg['video_id'] for seg in relevant_segments] if relevant_segments else []

        # Check cache first (skip cache for global mode to avoid stale local-context answers)
        cached_response = None
        if knowledge_mode != "global":
            cached_response = self.cache_manager.get_cached_response(
                user_message,
                video_ids,
                knowledge_mode=knowledge_mode
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
                segments_returned=len(relevant_segments) if relevant_segments else 0,
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
                    'hit_count': cached_response.get('hit_count'),
                    'knowledge_mode': knowledge_mode
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
            theme_result=theme_result if theme_result.found else None,
            knowledge_mode=knowledge_mode
        )

        # Generate response using unified LLM client with query-specific max_tokens and temperature
        with use_api_key(effective_api_key):
            llm = get_llm_client(api_key=effective_api_key)
            llm_response = llm.generate(
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

        cited_videos, relevance_scores = self._ensure_date_range_citation_coverage(
            channel_id=channel_id,
            date_range=date_range,
            cited_videos=cited_videos,
            relevance_scores=relevance_scores,
            speaker_filter=speaker_filter,
            video_ids_filter=video_ids_filter
        )

        # Store in cache (skip for global mode)
        if knowledge_mode != "global":
            self.cache_manager.store_response(
                user_message,
                video_ids,
                response_text,
                cited_videos,
                relevance_scores,
                knowledge_mode=knowledge_mode
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
            segments_returned=len(relevant_segments) if relevant_segments else 0,
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
                'temperature': response_config.temperature,
                'knowledge_mode': knowledge_mode
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
            for seg in (segments or []):
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
        theme_result = None,
        knowledge_mode: str = "database_only"
    ) -> str:
        """Build prompt for Gemini with context and query-type specific instructions"""
        # Format relevant segments with dates and speaker for clear identification
        context_parts = []
        for seg in (relevant_segments or []):
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
        mode_instruction = "\n8. FONTES PERMITIDAS: use SOMENTE os trechos de sermões fornecidos. Se não houver contexto suficiente, diga claramente que os sermões disponíveis não trazem essa informação."
        if knowledge_mode == "global":
            mode_instruction = "\n8. FONTES PERMITIDAS: responda usando conhecimento geral/bíblico. Não cite nem resuma sermões locais; se o contexto de sermões estiver vazio, ignore-o. Seja transparente quando estiver usando conhecimento geral."

        type_specific_rule = ""
        if response_instruction:
            type_specific_rule = f"\n9. FORMATO DA RESPOSTA: {response_instruction}"

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
7. Quando relevante, conecte insights de diferentes sermões{mode_instruction}{type_specific_rule}{biblical_context}{theme_context}

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

    @staticmethod
    def _clean_summary(text: Optional[str], max_len: int = 160) -> str:
        """Strip simple markdown markers and trim length."""
        if not text:
            return ""
        cleaned = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)  # headings
        cleaned = re.sub(r"^[\-•]\s*", "", cleaned, flags=re.MULTILINE)  # bullets
        cleaned = re.sub(r"[•◆■▶️▪️📕📖📚📊💡]+\s*", "", cleaned)  # icons/emoji
        cleaned = re.sub(r"(?i)texto\(s\)? bíblico\(s\)?", "", cleaned)
        cleaned = re.sub(r"(?i)tema central", "", cleaned)
        cleaned = re.sub(r"(?i)pontos principais", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Keep only the first 2 short sentences to avoid walls of text
        sentences = re.split(r"(?<=[.!?])\\s+", cleaned)
        short = []
        for s in sentences:
            if s:
                short.append(s)
            if len(" ".join(short)) >= max_len or len(short) >= 2:
                break
        cleaned = " ".join(short).strip()
        if len(cleaned) > max_len:
            cleaned = cleaned[:max_len].rstrip() + "..."
        return cleaned

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

        for seg in (segments or []):
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

    def _ensure_date_range_citation_coverage(
        self,
        channel_id: int,
        date_range: Optional[DateRangeResult],
        cited_videos: List[Dict],
        relevance_scores: List[float],
        speaker_filter: Optional[str],
        video_ids_filter: Optional[List[int]]
    ) -> Tuple[List[Dict], List[float]]:
        """Ensure every sermon in the requested date range is referenced."""
        if (
            not date_range
            or not date_range.start_date
            or not date_range.end_date
            or (not date_range.is_range and not getattr(date_range, 'specific_dates', None))
        ):
            return cited_videos, relevance_scores

        if getattr(date_range, 'specific_dates', None):
            return cited_videos, relevance_scores

        if speaker_filter:
            # Speaker-filtered queries already run with strict filters
            return cited_videos, relevance_scores

        expected_video_ids = self._get_video_ids_in_range(
            channel_id=channel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date
        )

        query_type = getattr(date_range, 'query_type', None)
        period_queries = {
            'single_month', 'month_range', 'custom_range',
            'last_month', 'last_week', 'last_n_days',
            'multiple_specific_days'
        }

        if video_ids_filter is not None and query_type not in period_queries:
            allowed = set(video_ids_filter)
            expected_video_ids = [vid for vid in expected_video_ids if vid in allowed]

        logger.debug(
            "Date coverage target=%s filter_applied=%s expected_ids=%s cited_ids=%s",
            query_type,
            bool(video_ids_filter) and query_type not in period_queries,
            expected_video_ids,
            [entry.get('video_id') for entry in cited_videos]
        )

        if not expected_video_ids:
            return cited_videos, relevance_scores

        cited_ids = {entry.get('video_id') for entry in cited_videos if entry.get('video_id')}
        missing_ids = [vid for vid in expected_video_ids if vid not in cited_ids]

        if not missing_ids:
            return cited_videos, relevance_scores

        video_lookup = self._fetch_videos_by_ids(missing_ids)

        for video_id in missing_ids:
            video = video_lookup.get(video_id)
            if not video:
                continue

            sermon_date = video.get('sermon_actual_date')
            published_at = video.get('published_at')
            if not sermon_date and published_at:
                sermon_date = published_at.date()

            speaker_name = video.get('speaker') or 'Desconhecido'
            date_str = sermon_date.strftime('%m/%d/%Y') if sermon_date else 'Data desconhecida'
            youtube_id = video.get('youtube_id')
            youtube_link = f"https://youtube.com/watch?v={youtube_id}" if youtube_id else ''
            title = video.get('title') or f"Sermão {video_id}"

            entry = {
                'video_id': video_id,
                'video_title': f"{date_str} - {title}" + (f" ({speaker_name})" if speaker_name != 'Desconhecido' else ''),
                'youtube_id': youtube_id,
                'timestamp': 0,
                'timestamp_sec': 0,
                'youtube_link': youtube_link,
                'speaker': speaker_name
            }

            logger.info(
                "📋 Adding missing sermon %s to cited_videos to ensure full coverage",
                entry['video_title']
            )

            cited_videos.append(entry)
            relevance_scores.append(0.0)

        return cited_videos, relevance_scores

    def _fetch_videos_by_ids(self, video_ids: Sequence[int]) -> Dict[int, Video]:
        if not video_ids:
            return {}

        with get_db() as db:
            rows = db.query(
                Video.id,
                Video.title,
                Video.youtube_id,
                Video.sermon_actual_date,
                Video.published_at,
                Video.speaker
            ).filter(Video.id.in_(video_ids)).all()

            return {
                row.id: {
                    'id': row.id,
                    'title': row.title,
                    'youtube_id': row.youtube_id,
                    'sermon_actual_date': row.sermon_actual_date,
                    'published_at': row.published_at,
                    'speaker': row.speaker
                }
                for row in rows
            }

    def _get_video_ids_in_range(
        self,
        channel_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[int]:
        """Return video IDs for completed sermons within a period."""
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date

        with get_db() as db:
            rows = db.query(Video.id).filter(
                Video.channel_id == channel_id,
                Video.status == 'completed',
                func.coalesce(
                    Video.sermon_actual_date,
                    func.date(Video.published_at)
                ).between(start, end)
            ).order_by(
                func.coalesce(Video.sermon_actual_date, func.date(Video.published_at)).asc(),
                Video.published_at.asc()
            ).all()

            return [row.id for row in rows]

    def _get_all_channel_video_ids(self, channel_id: int) -> List[int]:
        with get_db() as db:
            rows = db.query(Video.id).filter(
                Video.channel_id == channel_id,
                Video.status == 'completed'
            ).order_by(
                func.coalesce(Video.sermon_actual_date, func.date(Video.published_at)).asc(),
                Video.published_at.asc()
            ).all()

            return [row.id for row in rows]

    def _is_bible_text_list_query(self, query: str) -> bool:
        q = query.lower()
        q_norm = self._strip_accents(q)

        keywords = [
            'texto bíblico',
            'textos bíblicos',
            'passagem bíblica',
            'passagens bíblicas',
            'leituras bíblicas'
        ]
        actions = [
            'foram lidos', 'foram lidas', 'lidos', 'lidas', 'leram',
            'liste', 'listar', 'lista', 'quais'
        ]

        normalized_keywords = [self._strip_accents(term) for term in keywords]
        normalized_actions = [self._strip_accents(term) for term in actions]

        keyword_match = any(term in q for term in keywords)
        if not keyword_match:
            keyword_match = any(term in q_norm for term in normalized_keywords)

        action_match = any(term in q for term in actions)
        if not action_match:
            action_match = any(term in q_norm for term in normalized_actions)

        return keyword_match and action_match

    def _handle_bible_text_list_query(
        self,
        channel_id: int,
        user_message: str,
        session_id: str,
        date_range: Optional[DateRangeResult],
        knowledge_mode: str = "database_only"
    ) -> Dict:
        target_start = date_range.start_date if date_range and date_range.start_date else None
        target_end = date_range.end_date if date_range and date_range.end_date else None

        if target_start and target_end:
            context_video_ids = self._get_video_ids_in_range(channel_id, target_start, target_end)
        else:
            context_video_ids = self._get_all_channel_video_ids(channel_id)

        cached_response = None
        if context_video_ids:
            cached_response = self.cache_manager.get_cached_response(
                user_message,
                context_video_ids,
                knowledge_mode=knowledge_mode
            )

        if cached_response:
            self._save_history_entry(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=cached_response['response'],
                cited_videos=cached_response['cited_videos']
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

        passages = self._fetch_bible_passages(channel_id, target_start, target_end)

        if not passages:
            response_text = (
                "Não encontrei leituras bíblicas registradas no período solicitado. "
                "Tente especificar outra data ou reformule a pergunta."
            )
            cited_videos: List[Dict] = []
        else:
            period_label = self._format_period_label(target_start, target_end)
            lines = []
            for entry in passages:
                date_label = entry['sermon_date'].strftime('%d/%m/%Y') if entry['sermon_date'] else 'Data desconhecida'
                refs = ', '.join(entry['references']) if entry['references'] else 'referências não especificadas'
                lines.append(f"- {date_label}: {refs}")

            response_text = f"Textos bíblicos lidos {period_label}:\n" + "\n".join(lines)
            cited_videos = [
                {
                    'video_id': entry['video_id'],
                    'video_title': entry['video_title'],
                    'youtube_id': entry['youtube_id'],
                    'timestamp': 0,
                    'timestamp_sec': 0,
                    'youtube_link': f"https://youtube.com/watch?v={entry['youtube_id']}",
                    'speaker': entry.get('speaker') or 'Desconhecido'
                }
                for entry in passages
            ]

        self._save_history_entry(
            channel_id=channel_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=response_text,
            cited_videos=cited_videos
        )

        self._log_query_metrics(
            channel_id=channel_id,
            session_id=session_id,
            query=user_message,
            segments_returned=0,
            response_time_ms=0,
            cache_hit=False,
            date_filters_used=bool(date_range),
            speaker_filter_used=False,
            biblical_filter_used=True,
            theme_filter_used=False,
            query_type=QueryType.GENERAL,
            backend_used='structured_lookup',
            metadata={'handler': 'bible_text_list', 'entries': len(passages)}
        )

        if passages and context_video_ids:
            self.cache_manager.store_response(
                user_message,
                context_video_ids,
                response_text,
                cited_videos,
                [],
                knowledge_mode=knowledge_mode
            )

        return {
            'response': response_text,
            'cited_videos': cited_videos,
            'session_id': session_id,
            'relevance_scores': [],
            'cached': False,
            'backend': 'structured_lookup'
        }

    def _fetch_bible_passages(
        self,
        channel_id: int,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[Dict]:
        date_clause = ""
        params = {'channel_id': channel_id}
        if start_date and end_date:
            date_clause = "AND COALESCE(v.sermon_actual_date, DATE(v.published_at)) BETWEEN :start_date AND :end_date"
            params['start_date'] = start_date.date()
            params['end_date'] = end_date.date()

        sql = text(f"""
            SELECT
                bp.video_id,
                bp.book,
                bp.chapter,
                bp.verse_start,
                bp.verse_end,
                v.title,
                v.youtube_id,
                v.speaker,
                COALESCE(v.sermon_actual_date, DATE(v.published_at)) AS sermon_date,
                bp.id
            FROM biblical_passages bp
            JOIN videos v ON bp.video_id = v.id
            WHERE v.channel_id = :channel_id
              AND v.status = 'completed'
              {date_clause}
            ORDER BY sermon_date ASC, bp.id ASC
        """)

        with get_db() as db:
            rows = db.execute(sql, params).fetchall()

        grouped: "OrderedDict[int, Dict]" = OrderedDict()
        for row in rows:
            video_id = row[0]
            entry = grouped.setdefault(video_id, {
                'video_id': video_id,
                'video_title': row[5],
                'youtube_id': row[6],
                'speaker': row[7],
                'sermon_date': row[8],
                'references': []
            })

            reference = self._format_bible_reference(row[1], row[2], row[3], row[4])
            if reference and reference not in entry['references']:
                entry['references'].append(reference)

        return list(grouped.values())

    def _format_bible_reference(
        self,
        book: Optional[str],
        chapter: Optional[int],
        verse_start: Optional[int],
        verse_end: Optional[int]
    ) -> Optional[str]:
        if not book:
            return None

        reference = book.strip()
        if chapter:
            if verse_start and verse_end and verse_end != verse_start:
                reference += f" {chapter}:{verse_start}-{verse_end}"
            elif verse_start:
                reference += f" {chapter}:{verse_start}"
            else:
                reference += f" {chapter}"
        return reference

    def _format_period_label(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> str:
        if start_date and end_date:
            start = start_date.date()
            end = end_date.date()
            if start.year == end.year:
                if start.month == 1 and start.day == 1 and end.month == 12 and end.day == 31:
                    return f"em {start.year}"
                return f"entre {start.strftime('%d/%m/%Y')} e {end.strftime('%d/%m/%Y')}"
            return f"entre {start.strftime('%d/%m/%Y')} e {end.strftime('%d/%m/%Y')}"
        return "nos sermões disponíveis"

    @staticmethod
    def _strip_accents(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize('NFD', value)
        return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')

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
            # Prefer the actual sermon date when available, otherwise fall back to publish/upload time
            sort_key = func.coalesce(Video.sermon_actual_date, Video.published_at, Video.created_at)
            sermon = db.query(Video).filter(
                Video.channel_id == channel_id,
                Video.status == 'completed'
            ).join(
                Video.transcript
            ).order_by(
                sort_key.desc()
            ).offset(offset).limit(1).first()

            return sermon

    def _build_transcript_fallback_segment(self, sermon: Video) -> Optional[Dict]:
        """Return a minimal segment from the full transcript when embeddings are missing."""
        from app.common.models import Transcript

        with get_db() as db:
            transcript = db.query(Transcript).filter(Transcript.video_id == sermon.id).first()
            if not transcript or not transcript.text:
                return None

            text = transcript.text.strip()
            if len(text) > 1500:
                text = text[:1500] + "..."

            sermon_date = sermon.sermon_actual_date or sermon.published_at
            return {
                'video_id': sermon.id,
                'segment_text': text,
                'segment_start': 0,
                'segment_end': min(len(text.split()), 300),
                'segment_start_sec': 0,
                'segment_end_sec': sermon.duration_sec or 0,
                'video_title': sermon.title,
                'youtube_id': sermon.youtube_id,
                'published_at': sermon.published_at,
                'sermon_actual_date': sermon.sermon_actual_date,
                'speaker': sermon.speaker or "Desconhecido",
                'relevance': 1.0,
            }

    def _search_with_date_range(
        self,
        channel_id: int,
        query: str,
        date_range: DateRangeResult,
        speaker_filter: Optional[str] = None,
        video_ids_filter: Optional[List[int]] = None
    ) -> List[Dict]:
        """Route date-aware queries to the embedding service."""
        specific_dates = getattr(date_range, 'specific_dates', None)
        if specific_dates:
            return self._search_specific_dates(
                channel_id=channel_id,
                query=query,
                specific_dates=specific_dates,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
        if date_range.query_type == 'last_sermon':
            sermon = self._get_last_sermon(channel_id, offset=0)
            if not sermon:
                return []
            sermon_date = sermon.sermon_actual_date or sermon.published_at
            if not sermon_date:
                return []
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=sermon_date,
                end_date=sermon_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            if not segments:
                fallback = self._build_transcript_fallback_segment(sermon)
                return [fallback] if fallback else []
            return segments

        if date_range.query_type == 'second_last_sermon':
            sermon = self._get_last_sermon(channel_id, offset=1)
            if not sermon:
                return []
            sermon_date = sermon.sermon_actual_date or sermon.published_at
            if not sermon_date:
                return []
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=sermon_date,
                end_date=sermon_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            if not segments:
                fallback = self._build_transcript_fallback_segment(sermon)
                return [fallback] if fallback else []
            return segments

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

    def _search_specific_dates(
        self,
        channel_id: int,
        query: str,
        specific_dates: Sequence[datetime],
        speaker_filter: Optional[str],
        video_ids_filter: Optional[List[int]]
    ) -> List[Dict]:
        """Search each explicit date individually and merge the best segments."""
        combined: List[Dict] = []
        seen = set()

        for date_value in specific_dates:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                date_filter=date_value,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )

            for seg in segments or []:
                dedupe_key = (
                    seg.get('video_id'),
                    seg.get('segment_start'),
                    seg.get('segment_end')
                )
                if dedupe_key in seen:
                    continue
                combined.append(seg)
                seen.add(dedupe_key)

        combined.sort(key=lambda seg: seg.get('relevance', 0), reverse=True)
        return combined[:10] if len(combined) > 10 else combined
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

            sermon_date = sermon.sermon_actual_date or sermon.published_at
            if not sermon_date:
                return []

            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=sermon_date,
                end_date=sermon_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(f"Found {len(segments)} segments in second-last sermon (video_id={sermon.id})")
            if not segments:
                fallback = self._build_transcript_fallback_segment(sermon)
                if fallback:
                    logger.warning(f"No embeddings found for video {sermon.id}; using transcript fallback")
                    return [fallback]
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
