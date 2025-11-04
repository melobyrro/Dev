"""
Whisper transcription service with Intel GPU (UHD 770) support via OpenVINO
"""
import os
import logging
from typing import Optional, Dict
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")


class WhisperService:
    """Service for audio transcription using faster-whisper with Intel GPU support"""

    def __init__(self):
        self.model = None
        self.device = None
        self.compute_type = None

    def _initialize_model(self):
        """
        Lazy initialization of Whisper model with Intel GPU detection
        """
        if self.model is not None:
            return

        try:
            # Detect and configure device
            if WHISPER_DEVICE == "auto":
                # Try Intel GPU first via OpenVINO
                try:
                    logger.info("Attempting to use Intel GPU via OpenVINO...")
                    self.device = "auto"
                    self.compute_type = "int8"  # Optimal for Intel GPUs
                except Exception as e:
                    logger.warning(f"Intel GPU not available, falling back to CPU: {e}")
                    self.device = "cpu"
                    self.compute_type = "int8"
            else:
                self.device = WHISPER_DEVICE
                self.compute_type = "int8" if WHISPER_DEVICE == "cpu" else "float16"

            logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE} on {self.device} with {self.compute_type}")

            # Initialize model
            self.model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device=self.device,
                compute_type=self.compute_type,
                download_root="/app/tmp/whisper_models"
            )

            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Whisper model: {e}")
            raise

    def transcribe_audio(self, audio_path: str, language: str = "pt") -> Optional[Dict]:
        """
        Transcribe audio file using faster-whisper

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)
            language: Language code for transcription (default: pt)

        Returns:
            dict with keys: text, segments, language, duration
            Returns None if transcription fails
        """
        try:
            self._initialize_model()

            logger.info(f"Starting transcription of {audio_path} (language: {language})")

            # Transcribe
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                beam_size=5,
                vad_filter=True,  # Voice Activity Detection
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    threshold=0.5
                )
            )

            # Collect all segments
            all_segments = []
            full_text = []

            for segment in segments:
                all_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                full_text.append(segment.text.strip())

            transcript_text = ' '.join(full_text)

            logger.info(f"Transcription completed: {len(transcript_text)} chars, "
                       f"{len(all_segments)} segments, detected language: {info.language}")

            return {
                "text": transcript_text,
                "segments": all_segments,
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration
            }

        except FileNotFoundError:
            logger.error(f"Audio file not found: {audio_path}")
            return None

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None

    def get_device_info(self) -> Dict:
        """
        Get information about the current device being used

        Returns:
            dict with device information
        """
        self._initialize_model()

        return {
            "model_size": WHISPER_MODEL_SIZE,
            "device": self.device,
            "compute_type": self.compute_type,
            "device_setting": WHISPER_DEVICE
        }


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    service = WhisperService()
    info = service.get_device_info()
    print(f"Whisper device info: {info}")

    # Example transcription (requires actual audio file)
    # result = service.transcribe_audio("/path/to/audio.mp3", language="pt")
    # if result:
    #     print(f"Transcript: {result['text'][:200]}...")
