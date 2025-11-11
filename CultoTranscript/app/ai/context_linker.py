"""
Context Linker Service
Find and link related sermon segments across different videos
"""
import logging
import os
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.gemini_client import get_gemini_client
from app.common.database import get_db

logger = logging.getLogger(__name__)

# Configuration
CONTEXT_LINKS_ENABLED = os.getenv("CONTEXT_LINKS_ENABLED", "true").lower() == "true"
CONTEXT_MIN_SIMILARITY = float(os.getenv("CONTEXT_MIN_SIMILARITY", "0.75"))
CONTEXT_MAX_LINKS = int(os.getenv("CONTEXT_MAX_LINKS", "5"))


class ContextLinker:
    """
    Find and link related sermon segments

    Link Types:
    - same_topic: Discussing same subject
    - contrasting_view: Different perspective on same topic
    - elaboration: More detail on same point
    - example: Practical example of a principle
    - related: Generally related content
    """

    def __init__(self, db: Session):
        """
        Initialize context linker

        Args:
            db: Database session
        """
        self.db = db
        self.gemini = get_gemini_client()
        logger.info(
            f"Context linker initialized (enabled={CONTEXT_LINKS_ENABLED}, "
            f"min_similarity={CONTEXT_MIN_SIMILARITY})"
        )

    def generate_links_for_segment(
        self,
        segment_id: int,
        min_similarity: float = None,
        max_links: int = None
    ) -> int:
        """
        Find related segments from other videos

        Args:
            segment_id: Segment ID to find links for
            min_similarity: Minimum similarity threshold (0-1)
            max_links: Maximum number of links to generate

        Returns:
            Number of links created
        """
        if min_similarity is None:
            min_similarity = CONTEXT_MIN_SIMILARITY

        if max_links is None:
            max_links = CONTEXT_MAX_LINKS

        # Get source segment details
        sql_source = """
            SELECT
                te.id,
                te.video_id,
                te.segment_text,
                te.embedding,
                v.channel_id
            FROM transcript_embeddings te
            JOIN videos v ON te.video_id = v.id
            WHERE te.id = :segment_id
        """

        source = self.db.execute(text(sql_source), {'segment_id': segment_id}).fetchone()

        if not source:
            logger.warning(f"Segment {segment_id} not found")
            return 0

        source_id, source_video_id, source_text, source_embedding, channel_id = source

        if not source_embedding:
            logger.warning(f"Segment {segment_id} has no embedding")
            return 0

        # Find similar segments from different videos
        sql_similar = """
            SELECT
                te.id,
                te.video_id,
                te.segment_text,
                (te.embedding <=> CAST(:source_embedding AS vector)) AS similarity_distance,
                1 - (te.embedding <=> CAST(:source_embedding AS vector)) AS similarity_score
            FROM transcript_embeddings te
            JOIN videos v ON te.video_id = v.id
            WHERE v.channel_id = :channel_id
              AND te.video_id != :source_video_id
              AND te.embedding IS NOT NULL
              AND (1 - (te.embedding <=> CAST(:source_embedding AS vector))) >= :min_similarity
            ORDER BY similarity_distance
            LIMIT :max_links
        """

        results = self.db.execute(text(sql_similar), {
            'source_embedding': source_embedding,
            'channel_id': channel_id,
            'source_video_id': source_video_id,
            'min_similarity': min_similarity,
            'max_links': max_links
        }).fetchall()

        if not results:
            logger.debug(f"No similar segments found for segment {segment_id}")
            return 0

        # Classify each link type using LLM
        links_created = 0
        for row in results:
            related_id, related_video_id, related_text, similarity_distance, similarity_score = row

            # Classify link type
            link_type, confidence = self._classify_link_type(
                source_text,
                related_text
            )

            # Store link
            try:
                self.db.execute(text("""
                    INSERT INTO sermon_context_links
                    (source_embedding_id, related_embedding_id, similarity_score, link_type, confidence_score)
                    VALUES (:source_id, :related_id, :similarity, :link_type, :confidence)
                    ON CONFLICT (source_embedding_id, related_embedding_id) DO NOTHING
                """), {
                    'source_id': source_id,
                    'related_id': related_id,
                    'similarity': similarity_score,
                    'link_type': link_type,
                    'confidence': confidence
                })

                links_created += 1

            except Exception as e:
                logger.error(f"Failed to create link: {e}", exc_info=True)

        self.db.commit()
        logger.info(f"Created {links_created} context links for segment {segment_id}")

        return links_created

    def _classify_link_type(
        self,
        source_text: str,
        related_text: str
    ) -> tuple[str, float]:
        """
        Classify relationship between segments using pattern matching and LLM

        Args:
            source_text: Source segment text
            related_text: Related segment text

        Returns:
            Tuple of (link_type, confidence_score)
        """
        # Quick pattern-based classification for efficiency
        source_lower = source_text.lower()
        related_lower = related_text.lower()

        # Check for contrasting indicators
        contrasting_words = [
            'mas', 'porém', 'contudo', 'entretanto', 'no entanto',
            'diferente', 'contrário', 'oposto', 'por outro lado'
        ]
        if any(word in related_lower for word in contrasting_words):
            return 'contrasting_view', 0.75

        # Check for elaboration indicators
        elaboration_words = [
            'ou seja', 'isto é', 'em outras palavras', 'explicando melhor',
            'mais especificamente', 'detalhando', 'aprofundando'
        ]
        if any(word in related_lower for word in elaboration_words):
            return 'elaboration', 0.8

        # Check for example indicators
        example_words = [
            'por exemplo', 'como exemplo', 'ilustrando', 'na prática',
            'aplicando', 'situação', 'caso', 'história'
        ]
        if any(word in related_lower for word in example_words):
            return 'example', 0.8

        # Check for biblical references (same topic if same book/passage)
        biblical_books = [
            'gênesis', 'êxodo', 'joão', 'mateus', 'marcos', 'lucas',
            'romanos', 'coríntios', 'gálatas', 'apocalipse'
        ]
        source_books = [book for book in biblical_books if book in source_lower]
        related_books = [book for book in biblical_books if book in related_lower]

        if source_books and related_books:
            # Check if they share books
            shared_books = set(source_books) & set(related_books)
            if shared_books:
                return 'same_topic', 0.85

        # Default: same topic (since they're already similar by embedding)
        return 'same_topic', 0.7

    def get_related_segments(
        self,
        segment_id: int,
        limit: int = 3
    ) -> List[Dict]:
        """
        Retrieve stored context links for a segment

        Args:
            segment_id: Source segment ID
            limit: Max number of related segments

        Returns:
            List of related segments with metadata
        """
        if not CONTEXT_LINKS_ENABLED:
            return []

        sql = """
            SELECT
                scl.related_embedding_id,
                scl.similarity_score,
                scl.link_type,
                scl.confidence_score,
                te.segment_text,
                te.segment_start_sec,
                te.segment_end_sec,
                v.id as video_id,
                v.title,
                v.youtube_id,
                v.speaker,
                v.published_at,
                v.sermon_actual_date
            FROM sermon_context_links scl
            JOIN transcript_embeddings te ON scl.related_embedding_id = te.id
            JOIN videos v ON te.video_id = v.id
            WHERE scl.source_embedding_id = :segment_id
            ORDER BY scl.similarity_score DESC
            LIMIT :limit
        """

        results = self.db.execute(text(sql), {
            'segment_id': segment_id,
            'limit': limit
        }).fetchall()

        related_segments = []
        for row in results:
            sermon_date = row[12] if row[12] else (row[11].date() if row[11] else None)
            date_str = sermon_date.strftime('%d/%m/%Y') if sermon_date else "Data desconhecida"
            speaker = row[10] if row[10] else "Desconhecido"

            # Create YouTube link with timestamp
            youtube_link = f"https://youtube.com/watch?v={row[9]}"
            if row[5] and row[5] > 0:
                youtube_link += f"&t={row[5]}s"

            related_segments.append({
                'embedding_id': row[0],
                'similarity_score': row[1],
                'link_type': row[2],
                'confidence_score': row[3],
                'segment_text': row[4],
                'segment_start_sec': row[5],
                'segment_end_sec': row[6],
                'video_id': row[7],
                'video_title': row[8],
                'youtube_id': row[9],
                'speaker': speaker,
                'sermon_date': date_str,
                'youtube_link': youtube_link
            })

        logger.debug(f"Found {len(related_segments)} related segments for segment {segment_id}")
        return related_segments

    def batch_generate_links(
        self,
        channel_id: int,
        batch_size: int = 100,
        max_segments: int = None
    ) -> Dict[str, int]:
        """
        Generate context links for all segments in a channel

        Args:
            channel_id: Channel ID
            batch_size: Number of segments to process per batch
            max_segments: Max segments to process (None = all)

        Returns:
            Statistics dictionary
        """
        # Get all segments for channel
        sql_count = """
            SELECT COUNT(DISTINCT te.id)
            FROM transcript_embeddings te
            JOIN videos v ON te.video_id = v.id
            WHERE v.channel_id = :channel_id
              AND te.embedding IS NOT NULL
        """

        total_segments = self.db.execute(text(sql_count), {'channel_id': channel_id}).scalar()

        if max_segments:
            total_segments = min(total_segments, max_segments)

        logger.info(f"Generating context links for {total_segments} segments in channel {channel_id}")

        stats = {
            'segments_processed': 0,
            'links_created': 0,
            'segments_with_links': 0,
            'segments_without_links': 0
        }

        # Process in batches
        offset = 0
        while offset < total_segments:
            # Get batch of segment IDs
            sql_batch = """
                SELECT te.id
                FROM transcript_embeddings te
                JOIN videos v ON te.video_id = v.id
                WHERE v.channel_id = :channel_id
                  AND te.embedding IS NOT NULL
                ORDER BY te.id
                LIMIT :batch_size OFFSET :offset
            """

            segment_ids = self.db.execute(text(sql_batch), {
                'channel_id': channel_id,
                'batch_size': batch_size,
                'offset': offset
            }).fetchall()

            # Process each segment
            for (segment_id,) in segment_ids:
                try:
                    links_created = self.generate_links_for_segment(segment_id)
                    stats['segments_processed'] += 1
                    stats['links_created'] += links_created

                    if links_created > 0:
                        stats['segments_with_links'] += 1
                    else:
                        stats['segments_without_links'] += 1

                    if stats['segments_processed'] % 10 == 0:
                        logger.info(
                            f"Progress: {stats['segments_processed']}/{total_segments} segments "
                            f"({stats['links_created']} links created)"
                        )

                except Exception as e:
                    logger.error(f"Failed to process segment {segment_id}: {e}", exc_info=True)

            offset += batch_size

        logger.info(f"Context linking complete: {stats}")
        return stats

    def refresh_materialized_view(self):
        """
        Refresh the popular_sermon_links materialized view

        This should be called after batch link generation
        """
        try:
            self.db.execute(text("REFRESH MATERIALIZED VIEW popular_sermon_links"))
            self.db.commit()
            logger.info("Refreshed popular_sermon_links materialized view")
        except Exception as e:
            logger.error(f"Failed to refresh materialized view: {e}", exc_info=True)


def get_context_linker() -> ContextLinker:
    """
    Factory function to create ContextLinker instance

    Returns:
        ContextLinker instance
    """
    db = next(get_db())
    return ContextLinker(db)
