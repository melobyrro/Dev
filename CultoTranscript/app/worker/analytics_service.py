"""
Analytics service for sermon transcript analysis
Combines Bible reference detection and theme tagging
"""
import logging
from typing import Dict, Any

from app.common.database import get_db
from app.common.models import Video, Transcript, Verse, Theme
from app.common.bible_detector import BibleReferenceDetector
from app.common.theme_tagger import ThemeTagger

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analyzing sermon transcripts"""

    def __init__(self):
        self.bible_detector = BibleReferenceDetector()
        self.theme_tagger = ThemeTagger()

    def analyze_video(self, video_id: int) -> Dict[str, Any]:
        """
        Analyze a video transcript: detect Bible references and tag themes

        Args:
            video_id: Database ID of the video

        Returns:
            dict with analysis results
        """
        result = {
            "success": False,
            "video_id": video_id,
            "bible_references": 0,
            "themes_detected": 0,
            "error": None
        }

        try:
            with get_db() as db:
                # Get video and transcript
                video = db.query(Video).filter(Video.id == video_id).first()
                if not video:
                    result["error"] = "Vídeo não encontrado"
                    return result

                transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
                if not transcript:
                    result["error"] = "Transcrição não encontrada"
                    return result

                transcript_text = transcript.text

                # 1. Detect Bible references
                logger.info(f"Analyzing Bible references for video {video_id}")
                references = self.bible_detector.detect_references(transcript_text)

                # Save verses to database
                verse_data = self.bible_detector.extract_verses_for_db(references)

                for book, chapter, verse, count in verse_data:
                    verse_obj = Verse(
                        video_id=video_id,
                        book=book,
                        chapter=chapter,
                        verse=verse,
                        count=count
                    )
                    db.add(verse_obj)

                result["bible_references"] = len(references)
                logger.info(f"Saved {len(verse_data)} unique verse references")

                # 2. Tag themes
                logger.info(f"Tagging themes for video {video_id}")
                theme_result = self.theme_tagger.tag_with_details(transcript_text, min_score=2.0)

                # Save themes to database
                for theme_data in theme_result["themes"]:
                    theme_obj = Theme(
                        video_id=video_id,
                        tag=theme_data["tag"],
                        score=theme_data["score"]
                    )
                    db.add(theme_obj)

                result["themes_detected"] = len(theme_result["themes"])
                logger.info(f"Saved {len(theme_result['themes'])} themes")

                db.commit()

                result["success"] = True
                result["primary_theme"] = theme_result.get("primary_theme")

                logger.info(f"Analysis completed for video {video_id}")

            return result

        except Exception as e:
            logger.error(f"Error analyzing video {video_id}: {e}", exc_info=True)
            result["error"] = str(e)
            return result

    def get_video_analytics_summary(self, video_id: int) -> Dict[str, Any]:
        """
        Get analytics summary for a video

        Args:
            video_id: Database ID of the video

        Returns:
            dict with summary stats
        """
        try:
            with get_db() as db:
                video = db.query(Video).filter(Video.id == video_id).first()
                if not video:
                    return {"error": "Vídeo não encontrado"}

                transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
                verses = db.query(Verse).filter(Verse.video_id == video_id).all()
                themes = db.query(Theme).filter(Theme.video_id == video_id).all()

                # Aggregate Bible references
                bible_agg = self.bible_detector.aggregate_references([
                    {
                        "book": v.book,
                        "chapter": v.chapter,
                        "verse": v.verse,
                        "end_verse": None,
                        "raw_match": f"{v.book} {v.chapter}:{v.verse}" if v.verse else f"{v.book} {v.chapter}"
                    }
                    for v in verses
                ])

                return {
                    "video_id": video_id,
                    "title": video.title,
                    "duration_sec": video.duration_sec,
                    "word_count": transcript.word_count if transcript else 0,
                    "char_count": transcript.char_count if transcript else 0,
                    "transcript_source": transcript.source if transcript else None,
                    "bible_stats": {
                        "total_references": len(verses),
                        "unique_books": bible_agg.get("unique_books", 0),
                        "top_books": bible_agg.get("top_books", [])[:5],
                        "top_verses": bible_agg.get("top_verses", [])[:5]
                    },
                    "themes": [{"tag": t.tag, "score": t.score} for t in themes],
                    "primary_theme": themes[0].tag if themes else None
                }

        except Exception as e:
            logger.error(f"Error getting analytics summary for video {video_id}: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    service = AnalyticsService()

    # Example usage (requires existing video in database)
    # result = service.analyze_video(video_id=1)
    # print(f"Analysis result: {result}")
