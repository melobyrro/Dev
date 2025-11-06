"""
YouTube transcript extraction using youtube-transcript-api (fallback method)
"""
import logging
import html
from typing import Optional, List
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    TooManyRequests
)

logger = logging.getLogger(__name__)


class TranscriptApiService:
    """Service for fetching transcripts using youtube-transcript-api"""

    @staticmethod
    def extract_transcript(video_id: str, languages: List[str] = ['pt', 'pt-BR']) -> Optional[str]:
        """
        Extract transcript using youtube-transcript-api

        Args:
            video_id: YouTube video ID (not full URL)
            languages: List of language codes to try (default: Portuguese variants)

        Returns:
            Transcript text as string, or None if not available
        """
        try:
            # Try to get transcript list
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # First, try manually created transcripts in Portuguese
            for lang in languages:
                try:
                    transcript = transcript_list.find_manually_created_transcript([lang])
                    text = TranscriptApiService._format_transcript(transcript.fetch())
                    logger.info(f"Found manual transcript in language: {lang}")
                    return text
                except NoTranscriptFound:
                    continue

            # If no manual transcript, try auto-generated in Portuguese
            for lang in languages:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    text = TranscriptApiService._format_transcript(transcript.fetch())
                    logger.info(f"Found auto-generated transcript in language: {lang}")
                    return text
                except NoTranscriptFound:
                    continue

            logger.warning(f"No transcript found for video {video_id} in languages: {languages}")
            return None

        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video: {video_id}")
            return None

        except VideoUnavailable:
            logger.error(f"Video unavailable: {video_id}")
            return None

        except TooManyRequests:
            logger.error(f"Too many requests to YouTube API for video: {video_id}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error fetching transcript for {video_id}: {e}")
            return None

    @staticmethod
    def _format_transcript(transcript_data: List[dict]) -> str:
        """
        Format transcript data into clean text

        Args:
            transcript_data: List of transcript segments from youtube-transcript-api

        Returns:
            Concatenated text string
        """
        text_segments = [html.unescape(segment.get('text', '')).strip() for segment in transcript_data]
        return ' '.join(text_segments)

    @staticmethod
    def extract_video_id_from_url(url: str) -> Optional[str]:
        """
        Extract video ID from YouTube URL

        Args:
            url: YouTube URL (various formats supported)

        Returns:
            Video ID or None
        """
        import re

        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # If it's already just the ID
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
            return url

        logger.warning(f"Could not extract video ID from URL: {url}")
        return None


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    service = TranscriptApiService()

    # Example usage
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id = service.extract_video_id_from_url(test_url)

    if video_id:
        print(f"Video ID: {video_id}")
        transcript = service.extract_transcript(video_id)

        if transcript:
            print(f"Transcript preview: {transcript[:200]}...")
        else:
            print("No transcript available")
    else:
        print("Invalid URL")
