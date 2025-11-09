"""
Biblical Passage Service
Searches for sermons that reference specific biblical passages
"""
import logging
from typing import List, Optional, Set
from sqlalchemy import text, and_, or_

from app.common.database import get_db
from app.common.models import BiblicalPassage, Video
from app.ai.biblical_reference_parser import BiblicalReferenceResult

logger = logging.getLogger(__name__)


class BiblicalPassageService:
    """
    Service for searching sermons by biblical references

    Features:
    - Find sermons citing specific passages
    - Filter by passage type (citation, reading, mention)
    - Support for whole books, chapters, and verse ranges
    - Return video IDs for integration with chatbot
    """

    def __init__(self):
        """Initialize biblical passage service"""
        logger.info("Biblical passage service initialized")

    def find_sermons_by_reference(
        self,
        channel_id: int,
        reference: BiblicalReferenceResult,
        passage_types: Optional[List[str]] = None
    ) -> List[int]:
        """
        Find videos that reference a specific biblical passage

        Args:
            channel_id: Channel ID to search in
            reference: Parsed biblical reference
            passage_types: Filter by passage types (citation, reading, mention)
                          None = search all types

        Returns:
            List of video IDs that match the reference
        """
        if not reference.found or not reference.book:
            return []

        with get_db() as db:
            # Build query based on reference type
            if reference.is_whole_book:
                # Search for any reference to this book
                video_ids = self._search_whole_book(
                    db, channel_id, reference.book, passage_types
                )
                logger.info(
                    f"📖 Found {len(video_ids)} sermons referencing book {reference.book}"
                )

            elif reference.is_whole_chapter:
                # Search for references to this chapter
                video_ids = self._search_chapter(
                    db, channel_id, reference.book, reference.chapter, passage_types
                )
                logger.info(
                    f"📖 Found {len(video_ids)} sermons referencing "
                    f"{reference.book} {reference.chapter}"
                )

            else:
                # Search for specific verses
                video_ids = self._search_verses(
                    db, channel_id, reference, passage_types
                )
                logger.info(
                    f"📖 Found {len(video_ids)} sermons referencing "
                    f"{reference.book} {reference.chapter}:{reference.verse_start}"
                    + (f"-{reference.verse_end}" if reference.verse_end and reference.verse_end != reference.verse_start else "")
                )

            return video_ids

    def _search_whole_book(
        self,
        db,
        channel_id: int,
        book: str,
        passage_types: Optional[List[str]]
    ) -> List[int]:
        """Search for any reference to a book"""
        query = db.query(BiblicalPassage.video_id).distinct()

        # Join with videos to filter by channel
        query = query.join(Video, BiblicalPassage.video_id == Video.id)
        query = query.filter(Video.channel_id == channel_id)

        # Filter by book (OSIS code stored in database)
        query = query.filter(BiblicalPassage.book == book)

        # Filter by passage types if specified
        if passage_types:
            query = query.filter(BiblicalPassage.passage_type.in_(passage_types))

        results = query.all()
        return [r[0] for r in results]

    def _search_chapter(
        self,
        db,
        channel_id: int,
        book: str,
        chapter: int,
        passage_types: Optional[List[str]]
    ) -> List[int]:
        """Search for references to a specific chapter"""
        query = db.query(BiblicalPassage.video_id).distinct()

        # Join with videos to filter by channel
        query = query.join(Video, BiblicalPassage.video_id == Video.id)
        query = query.filter(Video.channel_id == channel_id)

        # Filter by book and chapter
        query = query.filter(
            and_(
                BiblicalPassage.book == book,
                BiblicalPassage.chapter == chapter
            )
        )

        # Filter by passage types if specified
        if passage_types:
            query = query.filter(BiblicalPassage.passage_type.in_(passage_types))

        results = query.all()
        return [r[0] for r in results]

    def _search_verses(
        self,
        db,
        channel_id: int,
        reference: BiblicalReferenceResult,
        passage_types: Optional[List[str]]
    ) -> List[int]:
        """
        Search for references to specific verses

        Handles overlapping verse ranges:
        - Reference: John 3:16-18
        - Matches: John 3:16, John 3:17, John 3:16-20, John 3:15-17, etc.
        """
        query = db.query(BiblicalPassage.video_id).distinct()

        # Join with videos to filter by channel
        query = query.join(Video, BiblicalPassage.video_id == Video.id)
        query = query.filter(Video.channel_id == channel_id)

        # Filter by book and chapter
        query = query.filter(
            and_(
                BiblicalPassage.book == reference.book,
                BiblicalPassage.chapter == reference.chapter
            )
        )

        # Handle verse ranges - check for overlap
        # Reference: verses X-Y
        # Database: verses A-B
        # Overlap when: max(X,A) <= min(Y,B)
        verse_start = reference.verse_start
        verse_end = reference.verse_end if reference.verse_end else verse_start

        # Build overlap condition
        # Case 1: Database has verse_end (range)
        # Case 2: Database has only verse_start (single verse)
        overlap_condition = or_(
            # Range to range overlap
            and_(
                BiblicalPassage.verse_end.isnot(None),
                BiblicalPassage.verse_start <= verse_end,
                BiblicalPassage.verse_end >= verse_start
            ),
            # Single verse to range overlap
            and_(
                BiblicalPassage.verse_end.is_(None),
                BiblicalPassage.verse_start >= verse_start,
                BiblicalPassage.verse_start <= verse_end
            )
        )

        query = query.filter(overlap_condition)

        # Filter by passage types if specified
        if passage_types:
            query = query.filter(BiblicalPassage.passage_type.in_(passage_types))

        results = query.all()
        return [r[0] for r in results]

    def get_passage_details(
        self,
        video_id: int,
        reference: Optional[BiblicalReferenceResult] = None
    ) -> List[dict]:
        """
        Get details of biblical passages referenced in a video

        Args:
            video_id: Video ID
            reference: Optional filter by specific reference

        Returns:
            List of passage details with timestamps and types
        """
        with get_db() as db:
            query = db.query(BiblicalPassage).filter(
                BiblicalPassage.video_id == video_id
            )

            if reference and reference.found and reference.book:
                query = query.filter(BiblicalPassage.book == reference.book)
                if reference.chapter:
                    query = query.filter(BiblicalPassage.chapter == reference.chapter)

            passages = query.all()

            return [
                {
                    'osis_ref': p.osis_ref,
                    'book': p.book,
                    'chapter': p.chapter,
                    'verse_start': p.verse_start,
                    'verse_end': p.verse_end,
                    'passage_type': p.passage_type,
                    'start_timestamp': p.start_timestamp,
                    'end_timestamp': p.end_timestamp,
                    'application_note': p.application_note,
                    'count': p.count
                }
                for p in passages
            ]

    def get_passage_statistics(self, channel_id: int) -> dict:
        """
        Get statistics about biblical references in a channel

        Args:
            channel_id: Channel ID

        Returns:
            Dictionary with statistics
        """
        with get_db() as db:
            # Total passages by type
            type_counts = db.execute(text("""
                SELECT bp.passage_type, COUNT(DISTINCT bp.video_id) as sermon_count, COUNT(*) as reference_count
                FROM biblical_passages bp
                JOIN videos v ON bp.video_id = v.id
                WHERE v.channel_id = :channel_id
                GROUP BY bp.passage_type
            """), {'channel_id': channel_id}).fetchall()

            # Most referenced books
            book_counts = db.execute(text("""
                SELECT bp.book, COUNT(DISTINCT bp.video_id) as sermon_count
                FROM biblical_passages bp
                JOIN videos v ON bp.video_id = v.id
                WHERE v.channel_id = :channel_id
                GROUP BY bp.book
                ORDER BY sermon_count DESC
                LIMIT 10
            """), {'channel_id': channel_id}).fetchall()

            return {
                'by_type': [
                    {
                        'passage_type': r[0],
                        'sermon_count': r[1],
                        'reference_count': r[2]
                    }
                    for r in type_counts
                ],
                'top_books': [
                    {
                        'book': r[0],
                        'sermon_count': r[1]
                    }
                    for r in book_counts
                ]
            }


def get_biblical_passage_service() -> BiblicalPassageService:
    """Get singleton biblical passage service instance"""
    if not hasattr(get_biblical_passage_service, '_instance'):
        get_biblical_passage_service._instance = BiblicalPassageService()
    return get_biblical_passage_service._instance
