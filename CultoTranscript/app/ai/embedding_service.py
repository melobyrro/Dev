"""
Embedding Service
Generates and manages vector embeddings for semantic search
"""
import logging
import hashlib
import os
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import text
from app.common.database import get_db
from app.common.models import Video, Transcript, TranscriptEmbedding
from app.ai.gemini_client import get_gemini_client
from app.ai.segmentation import get_text_segmenter

logger = logging.getLogger(__name__)

# Feature flags from environment
ENABLE_EMBEDDING_DEDUP = os.getenv("ENABLE_EMBEDDING_DEDUP", "true").lower() == "true"

# Segmentation mode: "none" (no overlap), "minimal" (small overlap), "legacy" (50-word overlap)
EMBEDDING_OVERLAP_MODE = os.getenv("EMBEDDING_OVERLAP_MODE", "none")

# Segment size configuration
EMBEDDING_TARGET_WORDS = int(os.getenv("EMBEDDING_TARGET_WORDS", "250"))
EMBEDDING_MIN_WORDS = int(os.getenv("EMBEDDING_MIN_WORDS", "150"))
EMBEDDING_MAX_WORDS = int(os.getenv("EMBEDDING_MAX_WORDS", "350"))


class EmbeddingService:
    """
    Manages transcript embeddings for semantic search

    Features:
    - Segments transcripts into chunks
    - Generates embeddings using Gemini
    - Stores in pgvector for similarity search
    - Retrieves relevant segments for chatbot context
    """

    SEGMENT_SIZE = 300  # Words per segment (legacy mode)
    OVERLAP = 50  # Words of overlap (legacy mode)

    def __init__(self):
        """Initialize embedding service"""
        self._gemini = None  # Lazy load to avoid startup failure if API key missing
        self.embeddings_skipped = 0
        self.embeddings_generated = 0

    @property
    def gemini(self):
        """Lazy load Gemini client only when needed"""
        if self._gemini is None:
            self._gemini = get_gemini_client()
        return self._gemini

        # Initialize segmenter based on mode
        self.overlap_mode = EMBEDDING_OVERLAP_MODE
        if self.overlap_mode == "none":
            self.segmenter = get_text_segmenter(
                target_words=EMBEDDING_TARGET_WORDS,
                min_words=EMBEDDING_MIN_WORDS,
                max_words=EMBEDDING_MAX_WORDS
            )
            logger.info(
                f"Embedding service initialized (mode=non-overlapping, "
                f"target={EMBEDDING_TARGET_WORDS} words, "
                f"dedup_enabled={ENABLE_EMBEDDING_DEDUP})"
            )
        else:
            self.segmenter = None
            logger.info(
                f"Embedding service initialized (mode={self.overlap_mode}, "
                f"size={self.SEGMENT_SIZE}, overlap={self.OVERLAP}, "
                f"dedup_enabled={ENABLE_EMBEDDING_DEDUP})"
            )

    @staticmethod
    def calculate_relevance_score(
        base_score: float,
        sermon_date: Optional[datetime] = None,
        theme_confidence: Optional[float] = None,
        speaker: Optional[str] = None,
        requested_speaker: Optional[str] = None,
        biblical_references: int = 0
    ) -> dict:
        """
        Calculate multi-factor relevance score

        Factors:
        - Recency boost: More recent sermons get higher scores (up to 10%)
        - Theme confidence: Higher confidence themes boost score (0.3-1.0x)
        - Speaker authority: Matching speaker boosts score (20%)
        - Biblical density: More references boost score (up to 25%)

        Args:
            base_score: Base similarity score from vector search (0-1)
            sermon_date: Date of the sermon (for recency boost)
            theme_confidence: Theme confidence from analytics (0.3-1.0)
            speaker: Sermon speaker name
            requested_speaker: Speaker filter from query
            biblical_references: Count of biblical references in segment

        Returns:
            Dictionary with enhanced score and breakdown of factors
        """
        score = base_score
        factors = {
            'base_score': base_score,
            'recency_boost': 0.0,
            'theme_confidence_multiplier': 1.0,
            'speaker_boost': 0.0,
            'biblical_density_boost': 0.0
        }

        # 1. Recency boost (10% max for videos from last 30 days)
        if sermon_date:
            try:
                # Handle both date and datetime objects
                if isinstance(sermon_date, datetime):
                    sermon_date_obj = sermon_date
                else:
                    sermon_date_obj = datetime.combine(sermon_date, datetime.min.time())
                    sermon_date_obj = sermon_date_obj.replace(tzinfo=timezone.utc)

                now = datetime.now(timezone.utc)
                days_old = (now - sermon_date_obj).days

                # Linear scaling: 10% boost for videos from last 30 days
                if days_old < 30:
                    recency_factor = max(0, (30 - days_old) / 30)
                    recency_boost = 0.1 * recency_factor
                    score *= (1 + recency_boost)
                    factors['recency_boost'] = recency_boost
            except Exception as e:
                logger.debug(f"Error calculating recency boost: {e}")

        # 2. Theme confidence multiplier (0.3-1.0)
        if theme_confidence is not None:
            # Clamp to valid range
            theme_conf = max(0.3, min(1.0, theme_confidence))
            score *= theme_conf
            factors['theme_confidence_multiplier'] = theme_conf
        else:
            # Default confidence if not available
            default_conf = 0.7
            score *= default_conf
            factors['theme_confidence_multiplier'] = default_conf

        # 3. Speaker authority boost (20% if matched)
        if speaker and requested_speaker:
            if speaker.lower().strip() == requested_speaker.lower().strip():
                speaker_boost = 0.2
                score *= (1 + speaker_boost)
                factors['speaker_boost'] = speaker_boost

        # 4. Biblical density boost (5% per reference, max 25% for 5+ refs)
        if biblical_references > 0:
            # Cap at 5 references for max boost
            capped_refs = min(biblical_references, 5)
            biblical_boost = 0.05 * capped_refs
            score *= (1 + biblical_boost)
            factors['biblical_density_boost'] = biblical_boost

        return {
            'enhanced_score': score,
            'factors': factors
        }

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

            # Calculate timestamps based on word positions
            word_count = transcript.word_count or len(transcript.text.split())
            duration_sec = video.duration_sec or 0

            for i, (segment_text, start_word, end_word) in enumerate(segments):
                # Generate embedding
                embedding = self.gemini.generate_embeddings(segment_text)

                if embedding is None:
                    logger.error(f"❌ Failed to generate embedding for video {video_id}, segment {i+1}/{len(segments)}")
                    raise ValueError(
                        f"Embedding generation failed for video {video_id}. "
                        "Gemini API quota may be exhausted. Please try again later."
                    )

                # Calculate timestamp in seconds based on word position
                if word_count > 0 and duration_sec > 0:
                    segment_start_sec = int((start_word / word_count) * duration_sec)
                    segment_end_sec = int((end_word / word_count) * duration_sec)
                else:
                    segment_start_sec = 0
                    segment_end_sec = 0

                # Save to database
                emb_obj = TranscriptEmbedding(
                    video_id=video_id,
                    segment_start=start_word,
                    segment_end=end_word,
                    segment_start_sec=segment_start_sec,
                    segment_end_sec=segment_end_sec,
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
        Search for transcript segments using semantic embeddings.

        Raises:
            ValueError: If embeddings are unavailable (Gemini quota exhausted)
        """
        query_embedding = self.gemini.generate_embeddings(query)

        if query_embedding is None:
            logger.error("❌ Embeddings unavailable - Gemini API quota likely exhausted")
            raise ValueError(
                "Chatbot embeddings unavailable. Gemini API quota may be exhausted. "
                "Please try again later."
            )

        use_vector_search = True

        def execute_query(db_session, conditions, params):
            select_distance = "(te.embedding <=> CAST(:query_emb AS vector)) AS distance" if use_vector_search else "0 AS distance"
            order_clause = "ORDER BY distance" if use_vector_search else "ORDER BY te.segment_start"
            sql = f"""
                SELECT
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
                    {select_distance}
                FROM transcript_embeddings te
                JOIN videos v ON te.video_id = v.id
                WHERE {' AND '.join(conditions)}
                {order_clause}
                LIMIT :top_k
            """
            if use_vector_search:
                params['query_emb'] = query_embedding
            return db_session.execute(text(sql), params).fetchall()

        with get_db() as db:
            if speaker_filter:
                logger.info(f"Searching segments with speaker filter: '{speaker_filter}'")
            if video_ids_filter:
                logger.info(f"Searching segments with video IDs filter: {len(video_ids_filter)} videos")

            if start_date and end_date:
                conditions = [
                    "v.channel_id = :channel_id",
                    "COALESCE(v.sermon_actual_date, DATE(v.published_at)) BETWEEN :start_date AND :end_date"
                ]
                params = {
                    'channel_id': channel_id,
                    'start_date': start_date.date(),
                    'end_date': end_date.date(),
                    'top_k': top_k
                }
                if speaker_filter:
                    conditions.append("v.speaker ILIKE :speaker")
                    params['speaker'] = speaker_filter
                if video_ids_filter:
                    conditions.append("v.id = ANY(:video_ids)")
                    params['video_ids'] = video_ids_filter
                results = execute_query(db, conditions, params)
            elif date_filter:
                conditions = [
                    "v.channel_id = :channel_id",
                    "COALESCE(v.sermon_actual_date, DATE(v.published_at)) = DATE(:date_filter)"
                ]
                params = {
                    'channel_id': channel_id,
                    'date_filter': date_filter.date(),
                    'top_k': top_k
                }
                if speaker_filter:
                    conditions.append("v.speaker ILIKE :speaker")
                    params['speaker'] = speaker_filter
                if video_ids_filter:
                    conditions.append("v.id = ANY(:video_ids)")
                    params['video_ids'] = video_ids_filter
                results = execute_query(db, conditions, params)
            else:
                conditions = ["v.channel_id = :channel_id"]
                params = {
                    'channel_id': channel_id,
                    'top_k': top_k
                }
                if speaker_filter:
                    conditions.append("v.speaker ILIKE :speaker")
                    params['speaker'] = speaker_filter
                if video_ids_filter:
                    conditions.append("v.id = ANY(:video_ids)")
                    params['video_ids'] = video_ids_filter
                results = execute_query(db, conditions, params)

            segments = []
            for row in results:
                segments.append({
                    'video_id': row[0],
                    'segment_text': row[1],
                    'segment_start': row[2],
                    'segment_end': row[3],
                    'segment_start_sec': row[4] if row[4] is not None else 0,
                    'segment_end_sec': row[5] if row[5] is not None else 0,
                    'video_title': row[6],
                    'youtube_id': row[7],
                    'published_at': row[8],
                    'sermon_actual_date': row[9],
                    'speaker': row[10] if row[10] else "Desconhecido",
                    'relevance': 1 - row[11]
                })

            return segments

    def _segment_text(self, text: str) -> List[tuple]:
        """
        Segment text into chunks

        Mode-aware segmentation:
        - "none": Non-overlapping segments at natural boundaries
        - "minimal": Small overlap (10 words)
        - "legacy": Original 50-word overlap

        Args:
            text: Text to segment

        Returns:
            List of (segment_text, start_word_pos, end_word_pos) tuples
        """
        if self.overlap_mode == "none" and self.segmenter:
            # Use intelligent segmenter with no overlap
            return self.segmenter.segment_text(text)

        elif self.overlap_mode == "minimal":
            # Minimal overlap mode (10 words)
            return self._segment_with_overlap(text, overlap=10)

        else:
            # Legacy mode (50-word overlap) - default
            return self._segment_with_overlap(text, overlap=self.OVERLAP)

    def _segment_with_overlap(self, text: str, overlap: int) -> List[tuple]:
        """
        Segment text with specified overlap (legacy algorithm)

        Args:
            text: Text to segment
            overlap: Number of overlapping words

        Returns:
            List of (segment_text, start_word_pos, end_word_pos) tuples
        """
        words = text.split()
        segments = []

        start = 0
        while start < len(words):
            end = min(start + self.SEGMENT_SIZE, len(words))
            segment_words = words[start:end]
            segment_text = ' '.join(segment_words)

            segments.append((segment_text, start, end))

            start += (self.SEGMENT_SIZE - overlap)

        return segments
