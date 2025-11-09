"""
Theme Service
Searches for sermons based on theological themes
"""
import logging
from typing import List, Optional, Dict
from sqlalchemy import text, and_, or_

from app.common.database import get_db
from app.common.models import SermonThemeV2, Video
from app.ai.theme_parser import ThemeExtractionResult

logger = logging.getLogger(__name__)


class ThemeService:
    """
    Service for searching sermons by theological themes

    Features:
    - Find sermons matching specific themes
    - Use confidence scores to rank results
    - Support multi-theme queries (OR logic by default)
    - Return video IDs for integration with chatbot
    - Get all themes for a given sermon
    """

    # Minimum confidence score to consider a theme match
    # Themes with confidence < 0.5 are considered weak and filtered out
    MIN_CONFIDENCE = 0.5

    def __init__(self):
        """Initialize theme service"""
        logger.info("Theme service initialized")

    def find_sermons_by_themes(
        self,
        channel_id: int,
        themes: List[str],
        min_confidence: Optional[float] = None,
        use_and_logic: bool = False
    ) -> List[int]:
        """
        Find videos that match specific themes

        Args:
            channel_id: Channel ID to search in
            themes: List of canonical theme names (from ThemeParser)
            min_confidence: Minimum confidence score (default: MIN_CONFIDENCE)
            use_and_logic: If True, require ALL themes; if False, require ANY theme (default: False)

        Returns:
            List of video IDs that match the theme criteria, ordered by average confidence

        Examples:
            >>> service = ThemeService()
            >>> # Find sermons about grace OR faith
            >>> service.find_sermons_by_themes(1, ["Graça", "Fé"])
            [123, 456, 789]
            >>> # Find sermons about BOTH grace AND faith
            >>> service.find_sermons_by_themes(1, ["Graça", "Fé"], use_and_logic=True)
            [123]
        """
        if not themes:
            return []

        if min_confidence is None:
            min_confidence = self.MIN_CONFIDENCE

        with get_db() as db:
            if use_and_logic:
                # AND logic: sermon must have ALL themes
                video_ids = self._search_with_and_logic(
                    db, channel_id, themes, min_confidence
                )
            else:
                # OR logic: sermon must have ANY of the themes
                video_ids = self._search_with_or_logic(
                    db, channel_id, themes, min_confidence
                )

            logger.info(
                f"🎨 Found {len(video_ids)} sermons with themes {themes} "
                f"(logic={'AND' if use_and_logic else 'OR'}, min_confidence={min_confidence:.2f})"
            )

            return video_ids

    def _search_with_or_logic(
        self,
        db,
        channel_id: int,
        themes: List[str],
        min_confidence: float
    ) -> List[int]:
        """
        Search for sermons with ANY of the specified themes (OR logic)

        Returns video IDs ordered by average confidence score (highest first)
        """
        # Use raw SQL for better performance with aggregation
        result = db.execute(text("""
            SELECT
                st.video_id,
                AVG(st.confidence_score) as avg_confidence
            FROM sermon_themes_v2 st
            JOIN videos v ON st.video_id = v.id
            WHERE v.channel_id = :channel_id
            AND st.theme_tag = ANY(:themes)
            AND st.confidence_score >= :min_confidence
            GROUP BY st.video_id
            ORDER BY avg_confidence DESC
        """), {
            'channel_id': channel_id,
            'themes': themes,
            'min_confidence': min_confidence
        }).fetchall()

        return [r[0] for r in result]

    def _search_with_and_logic(
        self,
        db,
        channel_id: int,
        themes: List[str],
        min_confidence: float
    ) -> List[int]:
        """
        Search for sermons with ALL of the specified themes (AND logic)

        Returns video IDs ordered by average confidence score (highest first)
        """
        # Use raw SQL with HAVING clause to ensure all themes are present
        theme_count = len(themes)

        result = db.execute(text("""
            SELECT
                st.video_id,
                AVG(st.confidence_score) as avg_confidence
            FROM sermon_themes_v2 st
            JOIN videos v ON st.video_id = v.id
            WHERE v.channel_id = :channel_id
            AND st.theme_tag = ANY(:themes)
            AND st.confidence_score >= :min_confidence
            GROUP BY st.video_id
            HAVING COUNT(DISTINCT st.theme_tag) = :theme_count
            ORDER BY avg_confidence DESC
        """), {
            'channel_id': channel_id,
            'themes': themes,
            'min_confidence': min_confidence,
            'theme_count': theme_count
        }).fetchall()

        return [r[0] for r in result]

    def get_themes_for_sermon(
        self,
        video_id: int,
        min_confidence: Optional[float] = None
    ) -> List[Dict]:
        """
        Get all themes for a specific sermon

        Args:
            video_id: Video ID
            min_confidence: Minimum confidence score (default: MIN_CONFIDENCE)

        Returns:
            List of theme dictionaries with details

        Example:
            >>> service.get_themes_for_sermon(123)
            [
                {'theme_tag': 'Graça', 'confidence_score': 0.95, 'key_evidence': '...'},
                {'theme_tag': 'Fé', 'confidence_score': 0.82, 'key_evidence': '...'}
            ]
        """
        if min_confidence is None:
            min_confidence = self.MIN_CONFIDENCE

        with get_db() as db:
            themes = db.query(SermonThemeV2).filter(
                and_(
                    SermonThemeV2.video_id == video_id,
                    SermonThemeV2.confidence_score >= min_confidence
                )
            ).order_by(
                SermonThemeV2.confidence_score.desc()
            ).all()

            return [
                {
                    'theme_tag': t.theme_tag,
                    'confidence_score': t.confidence_score,
                    'segment_start': t.segment_start,
                    'segment_end': t.segment_end,
                    'key_evidence': t.key_evidence
                }
                for t in themes
            ]

    def get_theme_statistics(self, channel_id: int) -> Dict:
        """
        Get statistics about themes in a channel

        Args:
            channel_id: Channel ID

        Returns:
            Dictionary with theme statistics

        Example:
            >>> service.get_theme_statistics(1)
            {
                'total_themes': 42,
                'themes_per_sermon': 2.5,
                'top_themes': [
                    {'theme_tag': 'Graça', 'sermon_count': 15, 'avg_confidence': 0.87},
                    {'theme_tag': 'Fé', 'sermon_count': 12, 'avg_confidence': 0.82}
                ]
            }
        """
        with get_db() as db:
            # Get theme counts and average confidence
            theme_stats = db.execute(text("""
                SELECT
                    st.theme_tag,
                    COUNT(DISTINCT st.video_id) as sermon_count,
                    AVG(st.confidence_score) as avg_confidence
                FROM sermon_themes_v2 st
                JOIN videos v ON st.video_id = v.id
                WHERE v.channel_id = :channel_id
                AND st.confidence_score >= :min_confidence
                GROUP BY st.theme_tag
                ORDER BY sermon_count DESC, avg_confidence DESC
            """), {
                'channel_id': channel_id,
                'min_confidence': self.MIN_CONFIDENCE
            }).fetchall()

            # Get total counts
            total_themes = db.execute(text("""
                SELECT COUNT(*)
                FROM sermon_themes_v2 st
                JOIN videos v ON st.video_id = v.id
                WHERE v.channel_id = :channel_id
                AND st.confidence_score >= :min_confidence
            """), {
                'channel_id': channel_id,
                'min_confidence': self.MIN_CONFIDENCE
            }).scalar() or 0

            # Get sermon count
            sermon_count = db.execute(text("""
                SELECT COUNT(DISTINCT st.video_id)
                FROM sermon_themes_v2 st
                JOIN videos v ON st.video_id = v.id
                WHERE v.channel_id = :channel_id
                AND st.confidence_score >= :min_confidence
            """), {
                'channel_id': channel_id,
                'min_confidence': self.MIN_CONFIDENCE
            }).scalar() or 0

            themes_per_sermon = total_themes / sermon_count if sermon_count > 0 else 0

            return {
                'total_themes': total_themes,
                'sermon_count': sermon_count,
                'themes_per_sermon': round(themes_per_sermon, 2),
                'top_themes': [
                    {
                        'theme_tag': r[0],
                        'sermon_count': r[1],
                        'avg_confidence': round(r[2], 2)
                    }
                    for r in theme_stats
                ]
            }


def get_theme_service() -> ThemeService:
    """Get singleton theme service instance"""
    if not hasattr(get_theme_service, '_instance'):
        get_theme_service._instance = ThemeService()
    return get_theme_service._instance
