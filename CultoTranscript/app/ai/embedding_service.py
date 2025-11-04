"""
Embedding Service
Generates and manages vector embeddings for semantic search
"""
import logging
from typing import List
from sqlalchemy import text
from app.common.database import get_db
from app.common.models import Video, Transcript, TranscriptEmbedding
from app.ai.gemini_client import get_gemini_client

logger = logging.getLogger(__name__)


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
        logger.info("Embedding service initialized")

    def generate_embeddings_for_video(self, video_id: int):
        """
        Generate embeddings for a video's transcript

        Args:
            video_id: Video ID
        """
        with get_db() as db:
            transcript = db.query(Transcript).filter(
                Transcript.video_id == video_id
            ).first()

            if not transcript:
                raise ValueError(f"No transcript for video {video_id}")

            # Delete existing embeddings
            db.query(TranscriptEmbedding).filter(
                TranscriptEmbedding.video_id == video_id
            ).delete()

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
            logger.info(f"Embeddings generated for video {video_id}")

    def search_similar_segments(
        self,
        channel_id: int,
        query: str,
        top_k: int = 5
    ) -> List[dict]:
        """
        Search for semantically similar transcript segments

        Args:
            channel_id: Channel to search in
            query: Search query
            top_k: Number of results to return

        Returns:
            List of relevant segments with metadata
        """
        # Generate query embedding
        query_embedding = self.gemini.generate_embeddings(query)

        with get_db() as db:
            # Perform vector similarity search
            # Note: This uses pgvector's cosine distance operator
            results = db.execute(text("""
                SELECT
                    te.video_id,
                    te.segment_text,
                    te.segment_start,
                    te.segment_end,
                    v.title,
                    v.youtube_id,
                    (te.embedding <=> CAST(:query_emb AS vector)) AS distance
                FROM transcript_embeddings te
                JOIN videos v ON te.video_id = v.id
                WHERE v.channel_id = :channel_id
                ORDER BY distance
                LIMIT :top_k
            """), {
                'query_emb': query_embedding,
                'channel_id': channel_id,
                'top_k': top_k
            }).fetchall()

            return [
                {
                    'video_id': r[0],
                    'segment_text': r[1],
                    'segment_start': r[2],
                    'segment_end': r[3],
                    'video_title': r[4],
                    'youtube_id': r[5],
                    'relevance': 1 - r[6]  # Convert distance to relevance score
                }
                for r in results
            ]

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
