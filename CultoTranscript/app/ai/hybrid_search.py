"""
Hybrid Search Service
Combines semantic (vector) search with keyword (full-text) search for optimal results
"""
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.embedding_service import EmbeddingService
from app.common.database import get_db

logger = logging.getLogger(__name__)

# Configuration from environment
HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() == "true"
HYBRID_SEMANTIC_WEIGHT = float(os.getenv("HYBRID_SEMANTIC_WEIGHT", "0.7"))
HYBRID_KEYWORD_WEIGHT = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.3"))
HYBRID_MIN_KEYWORD_MATCH = int(os.getenv("HYBRID_MIN_KEYWORD_MATCH", "2"))


class HybridSearchService:
    """
    Combines semantic and keyword search for optimal results

    Strategy:
    - Semantic search: Find conceptually similar content
    - Keyword search: Find exact matches for specific terms
    - Fusion: Combine results with weighted scoring

    Best for queries with:
    - Specific biblical references (João 3:16)
    - Theological terms (justificação, santificação)
    - Names (Moisés, Paulo, Jesus)
    - Dates or events (páscoa, pentecostes)
    """

    def __init__(self, db: Session, embedding_service: EmbeddingService):
        """
        Initialize hybrid search service

        Args:
            db: Database session
            embedding_service: Embedding service for semantic search
        """
        self.db = db
        self.embedding_service = embedding_service
        logger.info(
            f"Hybrid search initialized (enabled={HYBRID_SEARCH_ENABLED}, "
            f"semantic_weight={HYBRID_SEMANTIC_WEIGHT}, "
            f"keyword_weight={HYBRID_KEYWORD_WEIGHT})"
        )

    def search(
        self,
        query: str,
        channel_id: int,
        limit: int = 10,
        semantic_weight: float = None,
        keyword_weight: float = None,
        filters: Dict = None
    ) -> List[Dict]:
        """
        Hybrid search combining semantic and keyword approaches

        Args:
            query: User query
            channel_id: Channel to search
            limit: Max results
            semantic_weight: Weight for semantic scores (0-1)
            keyword_weight: Weight for keyword scores (0-1)
            filters: Date, speaker, theme filters

        Returns:
            Ranked list of segments with combined scores
        """
        if not HYBRID_SEARCH_ENABLED:
            # Fallback to pure semantic search
            logger.debug("Hybrid search disabled, using pure semantic search")
            return self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=limit,
                **self._extract_embedding_filters(filters)
            )

        # Use configured weights if not provided
        if semantic_weight is None:
            semantic_weight = HYBRID_SEMANTIC_WEIGHT
        if keyword_weight is None:
            keyword_weight = HYBRID_KEYWORD_WEIGHT

        # Normalize weights to sum to 1.0
        total_weight = semantic_weight + keyword_weight
        if total_weight > 0:
            semantic_weight /= total_weight
            keyword_weight /= total_weight

        logger.info(
            f"Hybrid search: query='{query[:50]}...', channel={channel_id}, "
            f"limit={limit}, semantic_w={semantic_weight:.2f}, keyword_w={keyword_weight:.2f}"
        )

        # 1. Semantic search (get 2x results for better fusion)
        try:
            semantic_results = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=limit * 2,
                **self._extract_embedding_filters(filters)
            )
        except Exception as e:
            logger.error(f"Semantic search failed: {e}", exc_info=True)
            semantic_results = []

        # 2. Keyword search (PostgreSQL full-text search)
        try:
            keyword_results = self._keyword_search(
                query, channel_id, limit=limit * 2, filters=filters
            )
        except Exception as e:
            logger.error(f"Keyword search failed: {e}", exc_info=True)
            keyword_results = []

        logger.info(
            f"Search results: semantic={len(semantic_results)}, "
            f"keyword={len(keyword_results)}"
        )

        # 3. Combine and re-rank
        combined = self._merge_and_rerank(
            semantic_results,
            keyword_results,
            semantic_weight,
            keyword_weight
        )

        logger.info(f"Hybrid search returned {len(combined)} combined results")

        return combined[:limit]

    def _keyword_search(
        self,
        query: str,
        channel_id: int,
        limit: int,
        filters: Dict
    ) -> List[Dict]:
        """
        PostgreSQL full-text search with Portuguese language support

        Args:
            query: Search query
            channel_id: Channel ID
            limit: Max results
            filters: Additional filters (date, speaker, video_ids)

        Returns:
            List of matching segments with keyword scores
        """
        # Prepare query for PostgreSQL tsquery
        # Replace special chars and combine words with AND
        search_terms = query.lower().split()

        # Filter out common Portuguese stop words that might interfere
        stop_words = {'o', 'a', 'de', 'da', 'do', 'e', 'que', 'em', 'na', 'no'}
        search_terms = [t for t in search_terms if t not in stop_words and len(t) > 2]

        if not search_terms:
            logger.debug("No valid search terms for keyword search")
            return []

        # Build tsquery: word1 & word2 & word3
        search_query = ' & '.join(search_terms)

        logger.debug(f"Keyword search query: '{search_query}'")

        # Build SQL query with filters
        conditions = [
            "v.channel_id = :channel_id",
            "te.text_searchable @@ to_tsquery('portuguese', :search_query)"
        ]
        params = {
            'channel_id': channel_id,
            'search_query': search_query,
            'limit': limit
        }

        # Apply filters
        if filters:
            if filters.get('date_filter'):
                conditions.append("COALESCE(v.sermon_actual_date, DATE(v.published_at)) = DATE(:date_filter)")
                params['date_filter'] = filters['date_filter'].date()

            if filters.get('start_date') and filters.get('end_date'):
                conditions.append("COALESCE(v.sermon_actual_date, DATE(v.published_at)) BETWEEN :start_date AND :end_date")
                params['start_date'] = filters['start_date'].date()
                params['end_date'] = filters['end_date'].date()

            if filters.get('speaker_filter'):
                conditions.append("v.speaker ILIKE :speaker")
                params['speaker'] = filters['speaker_filter']

            if filters.get('video_ids_filter'):
                conditions.append("v.id = ANY(:video_ids)")
                params['video_ids'] = filters['video_ids_filter']

        # Execute query with ts_rank for relevance scoring
        sql = f"""
            SELECT
                te.id,
                te.video_id,
                te.segment_text,
                te.segment_start,
                te.segment_end,
                te.segment_start_sec,
                te.segment_end_sec,
                v.title,
                v.youtube_id,
                v.published_at,
                v.sermon_actual_date,
                v.speaker,
                ts_rank(te.text_searchable, to_tsquery('portuguese', :search_query)) AS keyword_score
            FROM transcript_embeddings te
            JOIN videos v ON te.video_id = v.id
            WHERE {' AND '.join(conditions)}
            ORDER BY keyword_score DESC
            LIMIT :limit
        """

        try:
            results = self.db.execute(text(sql), params).fetchall()

            segments = []
            for row in results:
                segments.append({
                    'embedding_id': row[0],
                    'video_id': row[1],
                    'segment_text': row[2],
                    'segment_start': row[3],
                    'segment_end': row[4],
                    'segment_start_sec': row[5] if row[5] is not None else 0,
                    'segment_end_sec': row[6] if row[6] is not None else 0,
                    'video_title': row[7],
                    'youtube_id': row[8],
                    'published_at': row[9],
                    'sermon_actual_date': row[10],
                    'speaker': row[11] if row[11] else "Desconhecido",
                    'keyword_score': float(row[12])
                })

            logger.debug(f"Keyword search found {len(segments)} matches")
            return segments

        except Exception as e:
            logger.error(f"Keyword search query failed: {e}", exc_info=True)
            return []

    def _merge_and_rerank(
        self,
        semantic_results: List[Dict],
        keyword_results: List[Dict],
        semantic_weight: float,
        keyword_weight: float
    ) -> List[Dict]:
        """
        Combine results with weighted scoring (Reciprocal Rank Fusion)

        Args:
            semantic_results: Results from vector search
            keyword_results: Results from keyword search
            semantic_weight: Weight for semantic scores
            keyword_weight: Weight for keyword scores

        Returns:
            Combined and re-ranked results
        """
        # Build a map of all unique segments
        segment_map = {}

        # Normalize semantic scores (already 0-1 from relevance)
        for i, seg in enumerate(semantic_results):
            embedding_id = seg.get('embedding_id')
            if not embedding_id:
                # Generate from video_id + segment_start if not present
                embedding_id = f"{seg['video_id']}_{seg['segment_start']}"

            # Rank-based score: position in results matters
            rank_score = 1.0 / (i + 1)  # 1, 0.5, 0.33, 0.25, ...

            segment_map[embedding_id] = {
                **seg,
                'semantic_score': seg.get('relevance', 0.0),
                'semantic_rank_score': rank_score,
                'keyword_score': 0.0,
                'keyword_rank_score': 0.0
            }

        # Normalize keyword scores
        if keyword_results:
            max_keyword_score = max(r.get('keyword_score', 0) for r in keyword_results)

            for i, seg in enumerate(keyword_results):
                embedding_id = seg.get('embedding_id')
                if not embedding_id:
                    embedding_id = f"{seg['video_id']}_{seg['segment_start']}"

                # Normalize keyword score to 0-1
                normalized_kw_score = (
                    seg.get('keyword_score', 0) / max_keyword_score
                    if max_keyword_score > 0 else 0
                )

                # Rank-based score
                rank_score = 1.0 / (i + 1)

                if embedding_id in segment_map:
                    # Update existing entry
                    segment_map[embedding_id]['keyword_score'] = normalized_kw_score
                    segment_map[embedding_id]['keyword_rank_score'] = rank_score
                else:
                    # Add new entry (keyword-only match)
                    segment_map[embedding_id] = {
                        **seg,
                        'semantic_score': 0.0,
                        'semantic_rank_score': 0.0,
                        'keyword_score': normalized_kw_score,
                        'keyword_rank_score': rank_score
                    }

        # Calculate combined scores using Reciprocal Rank Fusion
        # RRF = semantic_rank + keyword_rank (weighted)
        for seg_id, seg in segment_map.items():
            # Rank fusion (better than raw score fusion for handling different scales)
            semantic_rrf = seg['semantic_rank_score']
            keyword_rrf = seg['keyword_rank_score']

            # Combined score: weighted RRF
            combined_score = (
                semantic_weight * semantic_rrf +
                keyword_weight * keyword_rrf
            )

            # Store both combined and component scores
            seg['hybrid_score'] = combined_score
            seg['relevance'] = combined_score  # Use for compatibility with chatbot
            seg['score_breakdown'] = {
                'semantic': seg['semantic_score'],
                'keyword': seg['keyword_score'],
                'semantic_rank': semantic_rrf,
                'keyword_rank': keyword_rrf,
                'hybrid': combined_score
            }

        # Sort by combined score
        combined_results = sorted(
            segment_map.values(),
            key=lambda x: x['hybrid_score'],
            reverse=True
        )

        logger.debug(
            f"Hybrid fusion: {len(semantic_results)} semantic + "
            f"{len(keyword_results)} keyword → {len(combined_results)} combined"
        )

        return combined_results

    def _extract_embedding_filters(self, filters: Dict) -> Dict:
        """
        Extract filters compatible with embedding_service.search_similar_segments

        Args:
            filters: Hybrid search filters

        Returns:
            Dictionary with embedding service compatible filters
        """
        if not filters:
            return {}

        embedding_filters = {}

        if 'date_filter' in filters:
            embedding_filters['date_filter'] = filters['date_filter']

        if 'start_date' in filters:
            embedding_filters['start_date'] = filters['start_date']

        if 'end_date' in filters:
            embedding_filters['end_date'] = filters['end_date']

        if 'speaker_filter' in filters:
            embedding_filters['speaker_filter'] = filters['speaker_filter']

        if 'video_ids_filter' in filters:
            embedding_filters['video_ids_filter'] = filters['video_ids_filter']

        return embedding_filters


def get_hybrid_search_service() -> HybridSearchService:
    """
    Factory function to create HybridSearchService instance

    Returns:
        HybridSearchService instance
    """
    db = next(get_db())
    embedding_service = EmbeddingService()
    return HybridSearchService(db, embedding_service)
