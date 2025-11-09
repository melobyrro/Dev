"""
Embedding Service
Generates and manages vector embeddings for semantic search
"""
import logging
import hashlib
import os
from typing import List, Optional
from datetime import datetime
from sqlalchemy import text
from app.common.database import get_db
from app.common.models import Video, Transcript, TranscriptEmbedding
from app.ai.gemini_client import get_gemini_client

logger = logging.getLogger(__name__)

# Feature flags from environment
ENABLE_EMBEDDING_DEDUP = os.getenv("ENABLE_EMBEDDING_DEDUP", "true").lower() == "true"


class EmbeddingService:
    """
    Manages transcript embeddings for semantic search

    Features:
    - Segments transcripts into chunks
    - Generates embeddings using Gemini
    - Stores in pgvector for similarity search
    - Retrieves relevant segments for chatbot context
    """

    SEGMENT_SIZE = 300  # Words per segment
    OVERLAP = 50  # Words of overlap

    def __init__(self):
        """Initialize embedding service"""
        self.gemini = get_gemini_client()
        self.embeddings_skipped = 0
        self.embeddings_generated = 0
        logger.info(f"Embedding service initialized (dedup_enabled={ENABLE_EMBEDDING_DEDUP})")

    @staticmethod
    def _hash_transcript(text: str) -> str:
        """
        Generate SHA-256 hash of transcript text

        Args:
            text: Transcript text

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def generate_embeddings_for_video(self, video_id: int, force: bool = False):
        """
        Generate embeddings for a video's transcript with deduplication

        Args:
            video_id: Video ID
            force: Force regeneration even if transcript unchanged
        """
        with get_db() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError(f"Video {video_id} not found")

            transcript = db.query(Transcript).filter(
                Transcript.video_id == video_id
            ).first()

            if not transcript:
                raise ValueError(f"No transcript for video {video_id}")

            # Calculate transcript hash
            current_hash = self._hash_transcript(transcript.text)

            # Check if embeddings need regeneration
            if not force and ENABLE_EMBEDDING_DEDUP:
                # Check if video has stored hash and embeddings exist
                stored_hash = video.transcript_hash if hasattr(video, 'transcript_hash') else None
                existing_embeddings_count = db.query(TranscriptEmbedding).filter(
                    TranscriptEmbedding.video_id == video_id
                ).count()

                if stored_hash == current_hash and existing_embeddings_count > 0:
                    self.embeddings_skipped += 1
                    logger.info(f"EMBEDDINGS SKIPPED: Transcript unchanged for video {video_id} "
                               f"({existing_embeddings_count} existing embeddings)")
                    logger.info(f"Embedding stats - Generated: {self.embeddings_generated}, "
                               f"Skipped: {self.embeddings_skipped}")
                    return

            # Transcript changed or force regeneration - delete old embeddings
            logger.info(f"Generating embeddings for video {video_id} (transcript_changed={stored_hash != current_hash}, force={force})")
            db.query(TranscriptEmbedding).filter(
                TranscriptEmbedding.video_id == video_id
            ).delete()

            # Update stored hash
            video.transcript_hash = current_hash

            # Segment transcript
            segments = self._segment_text(transcript.text)

            logger.info(f"Generating {len(segments)} embeddings for video {video_id}")

            for i, (segment_text, start_word, end_word) in enumerate(segments):
                # Generate embedding
                embedding = self.gemini.generate_embeddings(segment_text)

                # Save to database
                emb_obj = TranscriptEmbedding(
                    video_id=video_id,
                    segment_start=start_word,
                    segment_end=end_word,
                    segment_text=segment_text,
                    embedding=embedding
                )
                db.add(emb_obj)

                if (i + 1) % 10 == 0:
                    logger.debug(f"Generated {i+1}/{len(segments)} embeddings")

            db.commit()
            self.embeddings_generated += 1
            logger.info(f"Embeddings generated for video {video_id}")
            logger.info(f"Embedding stats - Generated: {self.embeddings_generated}, "
                       f"Skipped: {self.embeddings_skipped}")

    def search_similar_segments(
        self,
        channel_id: int,
        query: str,
        top_k: int = 5,
        date_filter: Optional[datetime] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        speaker_filter: Optional[str] = None,
        video_ids_filter: Optional[List[int]] = None
    ) -> List[dict]:
        """
        Search for semantically similar transcript segments

        Args:
            channel_id: Channel to search in
            query: Search query
            top_k: Number of results to return
            date_filter: Optional date to filter videos by (filters by published_at date) - legacy
            start_date: Optional start date for range filtering (Phase 2)
            end_date: Optional end date for range filtering (Phase 2)
            speaker_filter: Optional speaker name pattern for filtering (Phase 1.1)
            video_ids_filter: Optional list of video IDs to restrict search (Phase 1.2)

        Returns:
            List of relevant segments with metadata
        """
        # Generate query embedding
        query_embedding = self.gemini.generate_embeddings(query)

        with get_db() as db:
            # Log filters if present
            if speaker_filter:
                logger.info(f"Searching segments with speaker filter: '{speaker_filter}'")
            if video_ids_filter:
                logger.info(f"Searching segments with video IDs filter: {len(video_ids_filter)} videos")

            # Determine which date filtering to apply
            if start_date and end_date:
                # Phase 2: Date range filtering (with optional speaker and biblical filters)
                filter_desc = f"date range: {start_date.date()} to {end_date.date()}"
                if speaker_filter:
                    filter_desc += f" + speaker: '{speaker_filter}'"
                if video_ids_filter:
                    filter_desc += f" + biblical passages ({len(video_ids_filter)} videos)"
                logger.info(f"Searching segments with {filter_desc}")

                results = db.execute(text("""
                    SELECT
                        te.video_id,
                        te.segment_text,
                        te.segment_start,
                        te.segment_end,
                        v.title,
                        v.youtube_id,
                        v.published_at,
                        v.speaker,
                        (te.embedding <=> CAST(:query_emb AS vector)) AS distance
                    FROM transcript_embeddings te
                    JOIN videos v ON te.video_id = v.id
                    WHERE v.channel_id = :channel_id
                    AND v.published_at BETWEEN :start_date AND :end_date
                    AND (:speaker IS NULL OR v.speaker ILIKE :speaker)
                    AND (:video_ids::integer[] IS NULL OR v.id = ANY(:video_ids))
                    ORDER BY distance
                    LIMIT :top_k
                """), {
                    'query_emb': query_embedding,
                    'channel_id': channel_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'speaker': speaker_filter,
                    'video_ids': video_ids_filter,
                    'top_k': top_k
                }).fetchall()
            elif date_filter:
                # Legacy: Single date filtering (with optional speaker and biblical filters)
                filter_desc = f"date filter: {date_filter.date()}"
                if speaker_filter:
                    filter_desc += f" + speaker: '{speaker_filter}'"
                if video_ids_filter:
                    filter_desc += f" + biblical passages ({len(video_ids_filter)} videos)"
                logger.info(f"Searching segments with {filter_desc}")

                results = db.execute(text("""
                    SELECT
                        te.video_id,
                        te.segment_text,
                        te.segment_start,
                        te.segment_end,
                        v.title,
                        v.youtube_id,
                        v.published_at,
                        v.sermon_actual_date,
                        v.speaker,
                        (te.embedding <=> CAST(:query_emb AS vector)) AS distance
                    FROM transcript_embeddings te
                    JOIN videos v ON te.video_id = v.id
                    WHERE v.channel_id = :channel_id
                    AND COALESCE(v.sermon_actual_date, DATE(v.published_at)) = DATE(:date_filter)
                    AND (:speaker IS NULL OR v.speaker ILIKE :speaker)
                    AND (:video_ids::integer[] IS NULL OR v.id = ANY(:video_ids))
                    ORDER BY distance
                    LIMIT :top_k
                """), {
                    'query_emb': query_embedding,
                    'channel_id': channel_id,
                    'date_filter': date_filter,
                    'speaker': speaker_filter,
                    'video_ids': video_ids_filter,
                    'top_k': top_k
                }).fetchall()
            else:
                # No date filter - search all videos in channel (with optional speaker and biblical filters)
                filter_desc = "all videos"
                if speaker_filter:
                    filter_desc += f" with speaker filter: '{speaker_filter}'"
                if video_ids_filter:
                    filter_desc += f" + biblical passages ({len(video_ids_filter)} videos)"
                logger.info(f"Searching segments in {filter_desc}")

                results = db.execute(text("""
                    SELECT
                        te.video_id,
                        te.segment_text,
                        te.segment_start,
                        te.segment_end,
                        v.title,
                        v.youtube_id,
                        v.published_at,
                        v.sermon_actual_date,
                        v.speaker,
                        (te.embedding <=> CAST(:query_emb AS vector)) AS distance
                    FROM transcript_embeddings te
                    JOIN videos v ON te.video_id = v.id
                    WHERE v.channel_id = :channel_id
                    AND (:speaker IS NULL OR v.speaker ILIKE :speaker)
                    AND (:video_ids::integer[] IS NULL OR v.id = ANY(:video_ids))
                    ORDER BY distance
                    LIMIT :top_k
                """), {
                    'query_emb': query_embedding,
                    'channel_id': channel_id,
                    'speaker': speaker_filter,
                    'video_ids': video_ids_filter,
                    'top_k': top_k
                }).fetchall()

            # Handle different result column counts based on query type
            segments = []
            for r in results:
                segment = {
                    'video_id': r[0],
                    'segment_text': r[1],
                    'segment_start': r[2],
                    'segment_end': r[3],
                    'video_title': r[4],
                    'youtube_id': r[5],
                    'published_at': r[6],
                }

                # Handle variable columns based on query
                if len(r) == 10:  # date_filter or no filter (includes sermon_actual_date)
                    segment['sermon_actual_date'] = r[7]
                    segment['speaker'] = r[8] if r[8] else "Desconhecido"
                    segment['relevance'] = 1 - r[9]
                elif len(r) == 9:  # start_date/end_date (no sermon_actual_date)
                    segment['sermon_actual_date'] = None
                    segment['speaker'] = r[7] if r[7] else "Desconhecido"
                    segment['relevance'] = 1 - r[8]
                else:
                    # Fallback for old queries
                    segment['sermon_actual_date'] = None
                    segment['speaker'] = "Desconhecido"
                    segment['relevance'] = 1 - r[len(r)-1]

                segments.append(segment)

            return segments

    def _segment_text(self, text: str) -> List[tuple]:
        """Segment text into overlapping chunks"""
        words = text.split()
        segments = []

        start = 0
        while start < len(words):
            end = min(start + self.SEGMENT_SIZE, len(words))
            segment_words = words[start:end]
            segment_text = ' '.join(segment_words)

            segments.append((segment_text, start, end))

            start += (self.SEGMENT_SIZE - self.OVERLAP)

        return segments
