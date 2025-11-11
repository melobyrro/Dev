"""
Transcription orchestrator - 3-tier waterfall strategy
Tries: yt-dlp auto-CC → youtube-transcript-api → faster-whisper
"""
import os
import logging
import tempfile
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.worker.yt_dlp_service import YtDlpService
from app.worker.transcript_api_service import TranscriptApiService
from app.worker.whisper_service import WhisperService
from app.common.database import get_db
from app.common.models import Video, Transcript

logger = logging.getLogger(__name__)


def calculate_sermon_actual_date(published_at: Optional[datetime]):
    """
    Calculate the actual sermon date based on published_at.
    Rule: Use the most recent Sunday relative to the published date.
    """
    if not published_at:
        return None

    published_date = published_at.date()
    # Python weekday(): Monday=0 ... Sunday=6
    days_since_sunday = (published_date.weekday() + 1) % 7
    return published_date - timedelta(days=days_since_sunday)


def remove_existing_date_prefix(title: str) -> str:
    """
    Remove existing date prefixes from title to avoid duplication.

    Handles patterns like:
    - "15/03/2024 - Title"
    - "03/15/2024 - Title"
    - "2024-03-15 - Title"
    - "15/03/24 - Title"
    """
    import re

    patterns = [
        r'^\d{1,2}/\d{1,2}/\d{4}\s*-\s*',   # dd/mm/yyyy - or mm/dd/yyyy -
        r'^\d{4}-\d{1,2}-\d{1,2}\s*-\s*',    # yyyy-mm-dd -
        r'^\d{1,2}/\d{1,2}/\d{2}\s*-\s*',    # dd/mm/yy - or mm/dd/yy -
        r'^\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s*-\s*',  # "15 de março de 2024 -"
    ]

    for pattern in patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    return title.strip()


def format_title_with_date(title: str, sermon_date: Optional[datetime.date]) -> str:
    """
    Format title as 'MM/DD/YYYY - Title'.

    Args:
        title: Original video title (may already have date prefix)
        sermon_date: The sermon actual date to use for prefix

    Returns:
        Formatted title with date prefix

    Examples:
        >>> format_title_with_date("Culto de Domingo", date(2024, 3, 15))
        "03/15/2024 - Culto de Domingo"

        >>> format_title_with_date("15/03/2024 - Culto", date(2024, 3, 15))
        "03/15/2024 - Culto"
    """
    if not sermon_date:
        return title

    # Remove any existing date prefix to avoid duplication
    cleaned_title = remove_existing_date_prefix(title)

    # Format date as MM/DD/YYYY
    date_str = sermon_date.strftime('%m/%d/%Y')

    # Return formatted title
    return f"{date_str} - {cleaned_title}"


class TranscriptionService:
    """
    Main transcription service implementing 3-tier waterfall strategy:
    1. yt-dlp auto-CC (fastest, free, when available)
    2. youtube-transcript-api (fallback, free, unofficial)
    3. faster-whisper (slowest, most reliable, local)
    """

    def __init__(self):
        self.yt_dlp = YtDlpService()
        self.transcript_api = TranscriptApiService()
        self.whisper = WhisperService()

    def process_video(self, url: str, channel_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Process a YouTube video: extract info, validate, transcribe, save to DB

        Args:
            url: YouTube video URL
            channel_id: Optional channel ID to associate video with

        Returns:
            dict with processing results including video_id, status, transcript_source, etc.
        """
        result = {
            "success": False,
            "video_id": None,
            "status": None,
            "error": None,
            "transcript_source": None,
            "duration_sec": None
        }

        try:
            # Step 1: Extract video metadata
            logger.info(f"Extracting video info from: {url}")
            video_info = self.yt_dlp.extract_video_info(url)

            youtube_id = video_info["youtube_id"]
            duration_sec = video_info["duration_sec"]
            sermon_actual_date = calculate_sermon_actual_date(video_info["published_at"])
            # Format title with sermon date prefix
            formatted_title = format_title_with_date(video_info["title"], sermon_actual_date)
            result["duration_sec"] = duration_sec

            logger.info(f"Video {youtube_id}: {video_info['title']} ({duration_sec}s)")

            # Step 2: Validate duration
            is_valid, error_msg = self.yt_dlp.validate_video_duration(duration_sec)
            if not is_valid:
                # Determine status based on error message
                if "muito curto" in error_msg.lower():
                    video_status = "too_short"
                else:
                    video_status = "too_long"

                logger.warning(f"Video {youtube_id} rejected: {error_msg}")
                result["status"] = video_status
                result["error"] = error_msg

                # Save to DB with rejection status
                with get_db() as db:
                    video = Video(
                        channel_id=channel_id,
                        youtube_id=youtube_id,
                        title=formatted_title,
                        published_at=video_info["published_at"],
                        video_created_at=video_info["published_at"],
                        sermon_actual_date=sermon_actual_date,
                        duration_sec=duration_sec,
                        status=video_status,
                        language="pt",
                        error_message=error_msg
                    )
                    db.add(video)
                    db.commit()
                    result["video_id"] = video.id

                return result

            # Step 3: Try to get transcript using 3-tier strategy
            transcript_text, source = self._get_transcript_waterfall(url, youtube_id)

            if not transcript_text:
                logger.error(f"Failed to obtain transcript for video {youtube_id}")
                result["status"] = "failed"
                result["error"] = "Não foi possível obter transcrição por nenhum método"

                # Save to DB with failed status
                with get_db() as db:
                    video = Video(
                        channel_id=channel_id,
                        youtube_id=youtube_id,
                        title=formatted_title,
                        published_at=video_info["published_at"],
                        video_created_at=video_info["published_at"],
                        sermon_actual_date=sermon_actual_date,
                        duration_sec=duration_sec,
                        status="failed",
                        language="pt",
                        error_message=result["error"]
                    )
                    db.add(video)
                    db.commit()
                    result["video_id"] = video.id

                return result

            # Step 4: Save to database
            with get_db() as db:
                # Check if video already exists (for reprocessing)
                video = db.query(Video).filter(Video.youtube_id == youtube_id).first()

                if video:
                    # Update existing video
                    video.title = formatted_title
                    video.published_at = video_info["published_at"]
                    video.video_created_at = video_info["published_at"]
                    video.sermon_actual_date = sermon_actual_date
                    video.duration_sec = duration_sec
                    video.has_auto_cc = (source == "auto_cc")
                    video.status = "completed"
                    video.language = "pt"
                    video.ingested_at = datetime.now()
                    if channel_id:
                        video.channel_id = channel_id
                else:
                    # Create new video record
                    video = Video(
                        channel_id=channel_id,
                        youtube_id=youtube_id,
                        title=formatted_title,
                        published_at=video_info["published_at"],
                        video_created_at=video_info["published_at"],
                        sermon_actual_date=sermon_actual_date,
                        duration_sec=duration_sec,
                        has_auto_cc=(source == "auto_cc"),
                        status="completed",
                        language="pt",
                        ingested_at=datetime.now()
                    )
                    db.add(video)

                db.flush()  # Get video.id

                # Delete old transcript if exists, then create new one
                db.query(Transcript).filter(Transcript.video_id == video.id).delete()

                transcript = Transcript(
                    video_id=video.id,
                    source=source,
                    text=transcript_text,
                    word_count=len(transcript_text.split()),
                    char_count=len(transcript_text)
                )
                db.add(transcript)
                db.commit()

                result["success"] = True
                result["video_id"] = video.id
                result["status"] = "completed"
                result["transcript_source"] = source

                logger.info(f"Video {youtube_id} processed successfully (source: {source})")

            return result

        except Exception as e:
            logger.error(f"Error processing video {url}: {e}", exc_info=True)
            result["status"] = "failed"
            result["error"] = str(e)
            return result

    def _get_transcript_waterfall(self, url: str, youtube_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Try 3 methods in order to get transcript

        Returns:
            (transcript_text, source) where source is 'auto_cc', 'transcript_api', or 'whisper'
        """
        # Tier 1: yt-dlp auto-CC (fastest)
        logger.info("Tier 1: Trying yt-dlp auto-CC...")
        transcript = self.yt_dlp.extract_auto_caption(url)
        if transcript and len(transcript.strip()) > 100:
            logger.info("✓ Success with yt-dlp auto-CC")
            return transcript, "auto_cc"

        # Tier 2: youtube-transcript-api (fallback)
        logger.info("Tier 2: Trying youtube-transcript-api...")
        transcript = self.transcript_api.extract_transcript(youtube_id, languages=['pt', 'pt-BR'])
        if transcript and len(transcript.strip()) > 100:
            logger.info("✓ Success with youtube-transcript-api")
            return transcript, "transcript_api"

        # Tier 3: faster-whisper (most reliable, slowest)
        logger.info("Tier 3: Falling back to faster-whisper (local transcription)...")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Download audio
                logger.info("Downloading audio for Whisper transcription...")
                audio_path = self.yt_dlp.download_audio(url, tmpdir)

                # Transcribe
                logger.info("Transcribing with Whisper (this may take a few minutes)...")
                result = self.whisper.transcribe_audio(audio_path, language="pt")

                if result and result.get("text"):
                    logger.info("✓ Success with faster-whisper")
                    return result["text"], "whisper"

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")

        logger.error("All transcription methods failed")
        return None, None


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    service = TranscriptionService()

    # Example usage
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    result = service.process_video(test_url)
    print(f"Result: {result}")
