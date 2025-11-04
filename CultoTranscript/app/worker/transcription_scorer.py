"""
Transcription Quality Scorer
Estimates transcription accuracy and audio quality
"""
import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class TranscriptionScorer:
    """
    Estimates transcription quality on a 0-1 scale

    Factors considered:
    1. Source (auto-CC=0.6, transcript API=0.8, Whisper=0.7)
    2. Audio quality indicators (background noise, clarity)
    3. Linguistic complexity
    4. Repeated words/stuttering patterns
    5. Unusual character sequences
    """

    # Base scores by source
    SOURCE_SCORES = {
        'auto_cc': 0.60,
        'transcript_api': 0.80,
        'whisper': 0.70
    }

    # Audio quality keywords (lowercases quality when found)
    NOISE_INDICATORS = [
        '[música]', '[ruído]', '[aplausos]', '[inaudível]',
        '[incompreensível]', '***', '[?]', '[...]'
    ]

    # Patterns indicating transcription errors
    ERROR_PATTERNS = [
        r'(\w)\1{3,}',  # Repeated characters (e.g., "eeee")
        r'\b(\w{1,3})\s+\1\s+\1\b',  # Repeated short words
        r'[^\w\s\.,!?;:\-\'"áéíóúâêôãõç]{2,}',  # Unusual character sequences
    ]

    def __init__(self):
        """Initialize transcription scorer"""
        self.error_pattern = re.compile('|'.join(self.ERROR_PATTERNS), re.IGNORECASE)
        logger.info("Transcription scorer initialized")

    def score_transcript(
        self,
        text: str,
        source: str,
        word_count: int
    ) -> Dict[str, any]:
        """
        Score transcript quality

        Args:
            text: Transcript text
            source: Transcription source ('auto_cc', 'transcript_api', 'whisper')
            word_count: Total word count

        Returns:
            Dictionary with:
            - confidence_score: 0-1 float
            - audio_quality: 'low', 'medium', or 'high'
            - factors: Dict of contributing factors
        """
        # Start with base score from source
        base_score = self.SOURCE_SCORES.get(source, 0.5)

        factors = {
            'source_score': base_score,
            'noise_penalty': 0.0,
            'error_penalty': 0.0,
            'length_bonus': 0.0,
            'complexity_score': 0.0
        }

        # Factor 1: Noise indicators
        noise_count = sum(1 for indicator in self.NOISE_INDICATORS if indicator in text.lower())
        if noise_count > 0:
            # Penalize 0.1 per noise indicator, max 0.3
            factors['noise_penalty'] = min(0.3, noise_count * 0.1)

        # Factor 2: Error patterns
        error_matches = self.error_pattern.findall(text)
        if error_matches:
            # Penalize based on error density
            error_density = len(error_matches) / max(1, word_count / 100)
            factors['error_penalty'] = min(0.2, error_density * 0.05)

        # Factor 3: Length (longer transcripts usually indicate better quality)
        if word_count > 1000:
            factors['length_bonus'] = 0.05
        elif word_count < 100:
            factors['error_penalty'] += 0.1  # Very short might indicate failure

        # Factor 4: Linguistic complexity (vocabulary diversity)
        unique_words = len(set(text.lower().split()))
        word_diversity = unique_words / max(1, word_count)

        if word_diversity > 0.4:  # Good diversity
            factors['complexity_score'] = 0.05
        elif word_diversity < 0.2:  # Poor diversity (repetitive)
            factors['error_penalty'] += 0.05

        # Calculate final score
        confidence_score = (
            base_score
            - factors['noise_penalty']
            - factors['error_penalty']
            + factors['length_bonus']
            + factors['complexity_score']
        )

        # Clamp to 0-1 range
        confidence_score = max(0.0, min(1.0, confidence_score))

        # Determine audio quality category
        if confidence_score >= 0.75:
            audio_quality = 'high'
        elif confidence_score >= 0.55:
            audio_quality = 'medium'
        else:
            audio_quality = 'low'

        return {
            'confidence_score': round(confidence_score, 3),
            'audio_quality': audio_quality,
            'factors': factors,
            'noise_indicators_found': noise_count,
            'error_patterns_found': len(error_matches),
            'word_diversity': round(word_diversity, 3)
        }

    def identify_likely_errors(self, text: str, max_errors: int = 10) -> list:
        """
        Identify likely transcription errors

        Args:
            text: Transcript text
            max_errors: Maximum number of errors to return

        Returns:
            List of dictionaries with error information
        """
        errors = []

        # Find error patterns
        for match in self.error_pattern.finditer(text):
            if len(errors) >= max_errors:
                break

            # Get context
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end]

            errors.append({
                'position': match.start(),
                'error_text': match.group(),
                'context': context,
                'suggested_correction': None  # Could be enhanced with AI
            })

        # Find noise indicators
        for indicator in self.NOISE_INDICATORS:
            if len(errors) >= max_errors:
                break

            for match in re.finditer(re.escape(indicator), text, re.IGNORECASE):
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end]

                errors.append({
                    'position': match.start(),
                    'error_text': match.group(),
                    'context': context,
                    'suggested_correction': '[verificar áudio]'
                })

        return errors[:max_errors]
