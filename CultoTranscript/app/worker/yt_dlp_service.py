"""
YouTube download and auto-caption extraction service using yt-dlp
"""
import os
import subprocess
import json
import tempfile
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import logging
import html

logger = logging.getLogger(__name__)

MAX_VIDEO_DURATION = int(os.getenv("MAX_VIDEO_DURATION", "7200"))  # 120 minutes default


class YtDlpService:
    """Service for YouTube video metadata and auto-caption extraction"""

    @staticmethod
    def extract_video_info(url: str) -> Dict[str, Any]:
        """
        Extract video metadata without downloading

        Returns:
            dict with keys: youtube_id, title, duration_sec, published_at, channel_id, channel_title
        Raises:
            Exception if video info cannot be extracted
        """
        try:
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--no-warnings",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "--extractor-args", "youtube:player_client=android",
                url
            ]

            # Suppress Python warnings that contaminate stdout
            env = os.environ.copy()
            env['PYTHONWARNINGS'] = 'ignore'

            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, env=env)
            info = json.loads(result.stdout)

            return {
                "youtube_id": info.get("id"),
                "title": info.get("title"),
                "duration_sec": int(info.get("duration", 0)),
                "published_at": datetime.strptime(info.get("upload_date", "20000101"), "%Y%m%d"),
                "channel_id": info.get("channel_id"),
                "channel_title": info.get("channel"),
                "uploader": info.get("uploader"),
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to extract video info: {e.stderr if e.stderr else str(e)}")
            raise Exception(f"Could not extract video info: {e.stderr if e.stderr else str(e)}")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse video info: {e}")
            raise Exception(f"Could not parse video info: {e}")

    @staticmethod
    def validate_video_duration(duration_sec: int) -> Tuple[bool, Optional[str]]:
        """
        Validate video duration against MAX_VIDEO_DURATION

        Returns:
            (is_valid, error_message)
        """
        if duration_sec > MAX_VIDEO_DURATION:
            minutes = duration_sec / 60
            max_minutes = MAX_VIDEO_DURATION / 60
            return False, f"Vídeo muito longo: {minutes:.1f} min (máximo: {max_minutes:.0f} min)"
        return True, None

    @staticmethod
    def extract_auto_caption(url: str, lang: str = "pt") -> Optional[str]:
        """
        Try to extract auto-generated captions in specified language

        Args:
            url: YouTube video URL
            lang: Language code (default: pt for Portuguese)

        Returns:
            Caption text as string, or None if not available
        """
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_template = os.path.join(tmpdir, "caption")

                cmd = [
                    "yt-dlp",
                    "--write-auto-sub",
                    "--sub-lang", lang,
                    "--sub-format", "vtt",
                    "--skip-download",
                    "--no-warnings",
                    "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "--extractor-args", "youtube:player_client=android",
                    "--output", output_template,
                    url
                ]

                # Suppress Python warnings
                env = os.environ.copy()
                env['PYTHONWARNINGS'] = 'ignore'

                result = subprocess.run(cmd, capture_output=True, text=True, env=env)

                # Check if caption file was created
                vtt_files = [f for f in os.listdir(tmpdir) if f.endswith('.vtt')]

                if not vtt_files:
                    logger.info(f"No auto-captions found for language: {lang}")
                    return None

                # Read and parse VTT file
                vtt_path = os.path.join(tmpdir, vtt_files[0])
                with open(vtt_path, 'r', encoding='utf-8') as f:
                    vtt_content = f.read()

                # Parse VTT and extract text only
                text = YtDlpService._parse_vtt(vtt_content)

                if text and len(text.strip()) > 100:  # Sanity check
                    logger.info(f"Successfully extracted auto-captions ({len(text)} chars)")
                    return text
                else:
                    logger.warning("Auto-captions too short or empty")
                    return None

        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp auto-caption extraction failed: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting auto-captions: {e}")
            return None

    @staticmethod
    def _parse_vtt(vtt_content: str) -> str:
        """
        Parse VTT subtitle format and extract clean text

        Args:
            vtt_content: Raw VTT file content

        Returns:
            Clean concatenated text
        """
        import re
        import unicodedata

        lines = vtt_content.split('\n')
        text_lines = []
        seen_lines = set()  # Deduplicate repeated captions

        for line in lines:
            line = line.strip()

            # Skip VTT metadata headers (Kind, Language, NOTE, etc.)
            if (line.startswith('Kind:') or
                line.startswith('Language:') or
                line.startswith('NOTE:') or
                line.startswith('Style:')):
                continue

            # Skip VTT header, timestamps, and empty lines
            if (line.startswith('WEBVTT') or
                '-->' in line or
                line.isdigit() or
                not line):
                continue

            # Remove VTT tags like <c>, <v>, <i>, etc.
            line = re.sub(r'<[^>]+>', '', line)

            # Decode HTML entities (YouTube encodes special chars in VTT)
            line = html.unescape(line)

            # Remove common sound annotations [Música], [Aplausos], etc.
            line = re.sub(r'\[.*?\]', '', line)
            line = re.sub(r'\(.*?\)', '', line)  # Also remove (...)

            # Clean up invalid Unicode characters (keep Latin, common punctuation)
            line = ''.join(
                char for char in line
                if unicodedata.category(char)[0] in ('L', 'N', 'P', 'Z', 'S')
                and (ord(char) < 0x0E00 or ord(char) > 0x0E7F)  # Exclude Thai
            )

            # Strip extra whitespace
            line = ' '.join(line.split())

            # Deduplicate and add if meaningful
            if line and line not in seen_lines and len(line) > 2:
                seen_lines.add(line)
                text_lines.append(line)

        return ' '.join(text_lines)

    @staticmethod
    def download_audio(url: str, output_dir: str) -> str:
        """
        Download audio from YouTube video for Whisper transcription

        Args:
            url: YouTube video URL
            output_dir: Directory to save audio file

        Returns:
            Path to downloaded audio file
        """
        try:
            output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",  # Best quality
                "--no-warnings",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "--extractor-args", "youtube:player_client=android",
                "--output", output_template,
                url
            ]

            # Suppress Python warnings
            env = os.environ.copy()
            env['PYTHONWARNINGS'] = 'ignore'

            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)

            # Find the downloaded file
            mp3_files = [f for f in os.listdir(output_dir) if f.endswith('.mp3')]

            if not mp3_files:
                raise Exception("Audio file not found after download")

            audio_path = os.path.join(output_dir, mp3_files[0])
            logger.info(f"Audio downloaded: {audio_path}")
            return audio_path

        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp audio download failed: {e.stderr}")
            raise Exception(f"Audio download failed: {e.stderr}")


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    service = YtDlpService()

    # Example usage
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    try:
        info = service.extract_video_info(test_url)
        print(f"Video info: {info}")

        is_valid, error = service.validate_video_duration(info["duration_sec"])
        print(f"Duration valid: {is_valid}, error: {error}")

        caption = service.extract_auto_caption(test_url)
        if caption:
            print(f"Caption preview: {caption[:200]}...")
        else:
            print("No auto-captions available")
    except Exception as e:
        print(f"Error: {e}")
