"""
Transcription orchestrator - 3-tier waterfall strategy
Tries: yt-dlp auto-CC → youtube-transcript-api → faster-whisper
"""
import os
import logging
import tempfile
from typing import Optional, Dict, Any
from datetime import datetime

from app.worker.yt_dlp_service import YtDlpService
from app.worker.transcript_api_service import TranscriptApiService
from app.worker.whisper_service import WhisperService
from app.common.database import get_db
from app.common.models import Video, Transcript

logger = logging.getLogger(__name__)


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
            result["duration_sec"] = duration_sec

            logger.info(f"Video {youtube_id}: {video_info['title']} ({duration_sec}s)")

            # Step 2: Validate duration
            is_valid, error_msg = self.yt_dlp.validate_video_duration(duration_sec)
            if not is_valid:
                logger.warning(f"Video {youtube_id} rejected: {error_msg}")
                result["status"] = "too_long"
                result["error"] = error_msg

                # Save to DB with too_long status
                with get_db() as db:
                    video = Video(
                        channel_id=channel_id,
                        youtube_id=youtube_id,
                        title=video_info["title"],
                        published_at=video_info["published_at"],
                        video_created_at=video_info["published_at"],
                        duration_sec=duration_sec,
                        status="too_long",
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
                        title=video_info["title"],
                        published_at=video_info["published_at"],
                        video_created_at=video_info["published_at"],
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
                    video.title = video_info["title"]
                    video.published_at = video_info["published_at"]
                    video.video_created_at = video_info["published_at"]
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
                        title=video_info["title"],
                        published_at=video_info["published_at"],
                        video_created_at=video_info["published_at"],
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
