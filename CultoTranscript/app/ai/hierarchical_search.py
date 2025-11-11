"""
Hierarchical Search Service
Multi-level search: segment -> video -> channel
Enables finding sermons by topic even if specific segment doesn't match
"""
import logging
import os
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.embedding_service import EmbeddingService
from app.ai.gemini_client import get_gemini_client
from app.common.database import get_db
from app.common.models import Video

logger = logging.getLogger(__name__)

# Configuration
HIERARCHICAL_SEARCH_ENABLED = os.getenv("HIERARCHICAL_SEARCH_ENABLED", "true").lower() == "true"
VIDEO_SUMMARY_MAX_WORDS = int(os.getenv("VIDEO_SUMMARY_MAX_WORDS", "300"))
CHANNEL_SUMMARY_MAX_WORDS = int(os.getenv("CHANNEL_SUMMARY_MAX_WORDS", "500"))


class HierarchicalSearchService:
    """
    Multi-level search: segment -> video -> channel

    Query Scope Detection:
    - Broad queries ("what does this pastor teach?") -> video/channel level
    - Specific queries ("faith in James 2") -> segment level
    - Topical queries ("sermons about prayer") -> video level
    """

    def __init__(self, db: Session):
        """
        Initialize hierarchical search service

        Args:
            db: Database session
        """
        self.db = db
        self.embedding_service = EmbeddingService()
        self.gemini = get_gemini_client()
        logger.info(f"Hierarchical search initialized (enabled={HIERARCHICAL_SEARCH_ENABLED})")

    def search_with_hierarchy(
        self,
        query: str,
        channel_id: int,
        search_level: str = "auto",  # auto, segment, video, channel
        limit: int = 10
    ) -> List[Dict]:
        """
        Search at appropriate hierarchy level

        Args:
            query: User query
            channel_id: Channel to search
            search_level: Force specific level or auto-detect
            limit: Max results

        Returns:
            List of results from appropriate level
        """
        if not HIERARCHICAL_SEARCH_ENABLED:
            # Fallback to segment-level search
            logger.debug("Hierarchical search disabled, using segment-level search")
            return self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=limit
            )

        # Auto-detect query scope
        if search_level == "auto":
            search_level = self._detect_query_scope(query)
            logger.info(f"Auto-detected query scope: {search_level}")

        # Route to appropriate search level
        if search_level == "segment":
            return self._segment_search(query, channel_id, limit)
        elif search_level == "video":
            return self._video_search(query, channel_id, limit)
        else:  # channel
            return self._channel_search(query, channel_id, limit)

    def _detect_query_scope(self, query: str) -> str:
        """
        Detect query scope from user query

        Patterns:
        - Channel-level: "what does this pastor teach", "overall themes"
        - Video-level: "sermons about X", "topics covered", "main message"
        - Segment-level: specific verses, detailed questions, "where did he say"

        Args:
            query: User query

        Returns:
            "segment", "video", or "channel"
        """
        query_lower = query.lower()

        # Channel-level indicators
        channel_patterns = [
            'o pastor', 'o pregador', 'este canal', 'esta igreja',
            'ensina sobre', 'costuma pregar', 'estilo de pregação',
            'temas principais', 'no geral', 'geralmente'
        ]

        # Video-level indicators
        video_patterns = [
            'sermões sobre', 'pregações sobre', 'mensagens sobre',
            'tema principal', 'assunto tratado', 'falar sobre',
            'abordar o tema', 'mensagem sobre'
        ]

        # Segment-level indicators (specific)
        segment_patterns = [
            'versículo', 'capítulo', 'em que momento', 'quando ele disse',
            'onde menciona', 'o que disse sobre', 'específico'
        ]

        # Check for biblical references (segment-level)
        if any(book in query_lower for book in [
            'gênesis', 'êxodo', 'joão', 'mateus', 'marcos', 'lucas',
            'romanos', 'coríntios', 'gálatas', 'efésios', 'filipenses',
            'apocalipse', 'salmos', 'provérbios', 'isaías'
        ]):
            return "segment"

        # Check patterns
        if any(pattern in query_lower for pattern in channel_patterns):
            return "channel"

        if any(pattern in query_lower for pattern in video_patterns):
            return "video"

        if any(pattern in query_lower for pattern in segment_patterns):
            return "segment"

        # Default: segment-level (most specific)
        return "segment"

    def _segment_search(
        self,
        query: str,
        channel_id: int,
        limit: int
    ) -> List[Dict]:
        """
        Standard segment-level search

        Args:
            query: Search query
            channel_id: Channel ID
            limit: Max results

        Returns:
            List of segment results
        """
        logger.debug(f"Segment-level search: '{query[:50]}...'")
        return self.embedding_service.search_similar_segments(
            channel_id=channel_id,
            query=query,
            top_k=limit
        )

    def _video_search(
        self,
        query: str,
        channel_id: int,
        limit: int
    ) -> List[Dict]:
        """
        Video-level search using video embeddings

        Args:
            query: Search query
            channel_id: Channel ID
            limit: Max results

        Returns:
            List of video results (best segment from each video)
        """
        logger.debug(f"Video-level search: '{query[:50]}...'")

        # Generate query embedding
        query_embedding = self.gemini.generate_embeddings(query)
        if query_embedding is None:
            logger.error("Failed to generate query embedding for video search")
            return []

        # Search video embeddings
        sql = """
            SELECT
                ve.video_id,
                ve.summary,
                ve.main_topics,
                ve.key_scripture_refs,
                v.title,
                v.youtube_id,
                v.published_at,
                v.sermon_actual_date,
                v.speaker,
                (ve.embedding <=> CAST(:query_emb AS vector)) AS distance
            FROM video_embeddings ve
            JOIN videos v ON ve.video_id = v.id
            WHERE v.channel_id = :channel_id
            ORDER BY distance
            LIMIT :limit
        """

        try:
            results = self.db.execute(text(sql), {
                'query_emb': query_embedding,
                'channel_id': channel_id,
                'limit': limit
            }).fetchall()

            # For each video, get the best segment
            video_results = []
            for row in results:
                video_id = row[0]

                # Get best segment from this video
                segments = self.embedding_service.search_similar_segments(
                    channel_id=channel_id,
                    query=query,
                    top_k=1,
                    video_ids_filter=[video_id]
                )

                if segments:
                    segment = segments[0]
                    # Boost relevance since video-level match
                    segment['relevance'] = min(1.0, segment['relevance'] * 1.2)
                    segment['video_summary'] = row[1]
                    segment['main_topics'] = row[2]
                    video_results.append(segment)

            logger.info(f"Video-level search returned {len(video_results)} results")
            return video_results

        except Exception as e:
            logger.error(f"Video-level search failed: {e}", exc_info=True)
            return []

    def _channel_search(
        self,
        query: str,
        channel_id: int,
        limit: int
    ) -> List[Dict]:
        """
        Channel-level search using channel embeddings

        Args:
            query: Search query
            channel_id: Channel ID
            limit: Max results

        Returns:
            List of representative videos
        """
        logger.debug(f"Channel-level search: '{query[:50]}...'")

        # Get channel embedding
        sql_channel = """
            SELECT
                ce.teaching_summary,
                ce.common_themes,
                ce.style_notes
            FROM channel_embeddings ce
            WHERE ce.channel_id = :channel_id
        """

        try:
            channel_row = self.db.execute(text(sql_channel), {
                'channel_id': channel_id
            }).fetchone()

            if not channel_row:
                logger.warning(f"No channel embedding found for channel {channel_id}")
                # Fallback to video-level search
                return self._video_search(query, channel_id, limit)

            # Get top representative videos
            # Use video-level search but return multiple videos
            return self._video_search(query, channel_id, limit)

        except Exception as e:
            logger.error(f"Channel-level search failed: {e}", exc_info=True)
            return []

    def generate_video_embedding(self, video_id: int, force: bool = False):
        """
        Generate video-level embedding from transcript summary

        Args:
            video_id: Video ID
            force: Force regeneration even if exists

        Raises:
            ValueError: If video not found or has no transcript
        """
        # Check if already exists
        if not force:
            existing = self.db.execute(text("""
                SELECT id FROM video_embeddings WHERE video_id = :video_id
            """), {'video_id': video_id}).scalar()

            if existing:
                logger.info(f"Video embedding already exists for video {video_id}")
                return

        # Get video and transcript
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video or not video.transcript:
            raise ValueError(f"Video {video_id} not found or has no transcript")

        transcript_text = video.transcript.text

        # Generate summary using Gemini
        logger.info(f"Generating video-level summary for video {video_id}")

        summary_prompt = f"""
Analise este sermão e forneça:

1. RESUMO (200-300 palavras): Uma síntese narrativa do sermão, capturando a mensagem principal e os pontos-chave.

2. TEMAS PRINCIPAIS (3-5 temas): Liste os principais temas teológicos abordados.

3. REFERÊNCIAS BÍBLICAS CHAVE (até 5): Liste as passagens mais importantes citadas ou lidas.

TRANSCRIÇÃO DO SERMÃO:
{transcript_text[:5000]}...

Responda em JSON:
{{
    "summary": "resumo do sermão...",
    "main_topics": ["tema1", "tema2", "tema3"],
    "key_scripture_refs": ["João 3:16", "Romanos 8:28"]
}}
"""

        try:
            response = self.gemini.generate_text(
                prompt=summary_prompt,
                max_tokens=500
            )

            # Parse JSON response
            import json
            summary_data = json.loads(response)

            # Generate embedding from summary
            summary_embedding = self.gemini.generate_embeddings(summary_data['summary'])

            if summary_embedding is None:
                raise ValueError("Failed to generate embedding")

            # Store in database
            self.db.execute(text("""
                INSERT INTO video_embeddings (video_id, embedding, summary, main_topics, key_scripture_refs)
                VALUES (:video_id, :embedding, :summary, :main_topics, :key_scripture_refs)
                ON CONFLICT (video_id)
                DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    summary = EXCLUDED.summary,
                    main_topics = EXCLUDED.main_topics,
                    key_scripture_refs = EXCLUDED.key_scripture_refs,
                    generated_at = NOW()
            """), {
                'video_id': video_id,
                'embedding': summary_embedding,
                'summary': summary_data['summary'],
                'main_topics': summary_data['main_topics'],
                'key_scripture_refs': summary_data.get('key_scripture_refs', [])
            })

            self.db.commit()
            logger.info(f"Video embedding generated for video {video_id}")

        except Exception as e:
            logger.error(f"Failed to generate video embedding for video {video_id}: {e}", exc_info=True)
            raise

    def generate_channel_embedding(self, channel_id: int, force: bool = False):
        """
        Generate channel-level embedding from all video summaries

        Args:
            channel_id: Channel ID
            force: Force regeneration even if exists

        Raises:
            ValueError: If channel not found or has no videos
        """
        # Check if already exists
        if not force:
            existing = self.db.execute(text("""
                SELECT id FROM channel_embeddings WHERE channel_id = :channel_id
            """), {'channel_id': channel_id}).scalar()

            if existing:
                logger.info(f"Channel embedding already exists for channel {channel_id}")
                return

        # Get all video summaries for channel
        sql = """
            SELECT
                ve.summary,
                ve.main_topics
            FROM video_embeddings ve
            JOIN videos v ON ve.video_id = v.id
            WHERE v.channel_id = :channel_id
            ORDER BY v.published_at DESC
            LIMIT 50
        """

        results = self.db.execute(text(sql), {'channel_id': channel_id}).fetchall()

        if not results:
            raise ValueError(f"No video embeddings found for channel {channel_id}")

        # Aggregate summaries and topics
        all_summaries = [row[0] for row in results]
        all_topics = []
        for row in results:
            if row[1]:
                all_topics.extend(row[1])

        # Count topic frequencies
        from collections import Counter
        topic_counts = Counter(all_topics)
        common_themes = [topic for topic, count in topic_counts.most_common(10)]

        logger.info(f"Generating channel-level summary for channel {channel_id}")

        # Generate channel summary using Gemini
        channel_prompt = f"""
Analise estes resumos de sermões e forneça uma visão geral do ensino deste canal:

RESUMOS DOS SERMÕES:
{' | '.join(all_summaries[:10])}

Responda:
1. ESTILO DE ENSINO (100-200 palavras): Descreva o estilo geral de pregação e ênfases teológicas.
2. TEMAS MAIS FREQUENTES: {', '.join(common_themes[:10])}

Responda em JSON:
{{
    "teaching_summary": "descrição do estilo...",
    "style_notes": "observações sobre o estilo..."
}}
"""

        try:
            response = self.gemini.generate_text(
                prompt=channel_prompt,
                max_tokens=400
            )

            import json
            channel_data = json.loads(response)

            # Generate embedding from teaching summary
            channel_embedding = self.gemini.generate_embeddings(channel_data['teaching_summary'])

            if channel_embedding is None:
                raise ValueError("Failed to generate channel embedding")

            # Store in database
            self.db.execute(text("""
                INSERT INTO channel_embeddings (channel_id, embedding, teaching_summary, common_themes, style_notes, sermon_count)
                VALUES (:channel_id, :embedding, :teaching_summary, :common_themes, :style_notes, :sermon_count)
                ON CONFLICT (channel_id)
                DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    teaching_summary = EXCLUDED.teaching_summary,
                    common_themes = EXCLUDED.common_themes,
                    style_notes = EXCLUDED.style_notes,
                    sermon_count = EXCLUDED.sermon_count,
                    updated_at = NOW()
            """), {
                'channel_id': channel_id,
                'embedding': channel_embedding,
                'teaching_summary': channel_data['teaching_summary'],
                'common_themes': common_themes,
                'style_notes': channel_data.get('style_notes', ''),
                'sermon_count': len(results)
            })

            self.db.commit()
            logger.info(f"Channel embedding generated for channel {channel_id}")

        except Exception as e:
            logger.error(f"Failed to generate channel embedding for channel {channel_id}: {e}", exc_info=True)
            raise


def get_hierarchical_search_service() -> HierarchicalSearchService:
    """
    Factory function to create HierarchicalSearchService instance

    Returns:
        HierarchicalSearchService instance
    """
    db = next(get_db())
    return HierarchicalSearchService(db)
