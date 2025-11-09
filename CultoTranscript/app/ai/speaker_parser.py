"""
Speaker Parser Module
Extracts speaker/preacher names from chatbot queries
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SpeakerExtractionResult:
    """Result of speaker extraction from query"""
    speaker_name: Optional[str]
    found: bool
    original_query: str
    pattern_matched: Optional[str] = None

    def __repr__(self):
        if self.found:
            return f"SpeakerExtractionResult(speaker='{self.speaker_name}', pattern='{self.pattern_matched}')"
        return "SpeakerExtractionResult(no speaker detected)"


class SpeakerParser:
    """
    Detects and extracts speaker/preacher names from Portuguese queries

    Features:
    - Recognizes common titles: Pastor, Pastora, Pr., Pra., Reverendo, Rev., Bispo, etc.
    - Handles various query patterns
    - Extracts full names or partial names
    - Case-insensitive matching

    Examples:
        "sermões do Pastor João Silva" → "João Silva"
        "pregações do Pr. Carlos" → "Carlos"
        "mensagens da Pastora Maria" → "Maria"
        "culto com o Rev. Pedro" → "Pedro"
    """

    # Common Portuguese titles for religious speakers
    TITLES = [
        'pastor',
        'pastora',
        'pr\\.?',  # Pr. or Pr
        'pra\\.?',  # Pra. or Pra
        'reverendo',
        'reverenda',
        'rev\\.?',  # Rev. or Rev
        'bispo',
        'bispa',
        'missionário',
        'missionária',
        'pregador',
        'pregadora',
        'ministro',
        'ministra',
        'padre',
        'irmão',
        'irmã'
    ]

    # Query patterns that indicate speaker-specific searches
    PATTERNS = [
        # "sermões do Pastor João", "pregações do Pr. Carlos"
        r'(?:serm[õô]es?|prega[çc][õô]es?|mensagens?|cultos?)\s+(?:do|da)\s+({titles})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)?)\b',

        # "pelo Pastor João", "pela Pastora Maria"
        r'(?:pelo|pela)\s+({titles})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)?)\b',

        # "com o Pastor João", "com a Pra. Ana"
        r'com\s+(?:o|a)\s+({titles})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)?)\b',

        # "falado pelo Pastor João"
        r'falado\s+(?:pelo|pela)\s+({titles})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)?)\b',

        # "pregado por Pastor João", "ministrado por Pr. Carlos"
        r'(?:pregado|ministrado|apresentado)\s+por\s+({titles})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)?)\b',

        # Just "Pastor João" or "Pr. Carlos" (more lenient) - limit to max 2 words
        r'\b({titles})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)?)\b',
    ]

    def __init__(self):
        """Initialize speaker parser with compiled regex patterns"""
        # Build title regex group
        titles_group = '|'.join(self.TITLES)

        # Compile all patterns with title placeholders replaced
        self.compiled_patterns = []
        for pattern in self.PATTERNS:
            full_pattern = pattern.replace('{titles}', titles_group)
            self.compiled_patterns.append(re.compile(full_pattern, re.IGNORECASE))

        logger.info(f"SpeakerParser initialized with {len(self.compiled_patterns)} patterns")

    def extract_speaker(self, query: str) -> SpeakerExtractionResult:
        """
        Extract speaker name from query

        Args:
            query: User query text

        Returns:
            SpeakerExtractionResult with speaker name if found

        Examples:
            >>> parser = SpeakerParser()
            >>> result = parser.extract_speaker("sermões do Pastor João Silva")
            >>> result.speaker_name
            'João Silva'
            >>> result.found
            True
        """
        if not query or not isinstance(query, str):
            return SpeakerExtractionResult(
                speaker_name=None,
                found=False,
                original_query=query or ""
            )

        # Try each pattern
        for i, pattern in enumerate(self.compiled_patterns):
            match = pattern.search(query)
            if match:
                # Extract the name (second capture group)
                title = match.group(1)
                name = match.group(2).strip()

                logger.info(f"🎤 Speaker detected: '{name}' (title='{title}', pattern={i})")

                return SpeakerExtractionResult(
                    speaker_name=name,
                    found=True,
                    original_query=query,
                    pattern_matched=f"pattern_{i}"
                )

        # No speaker found
        logger.debug(f"No speaker detected in query: {query[:100]}")
        return SpeakerExtractionResult(
            speaker_name=None,
            found=False,
            original_query=query
        )

    def normalize_speaker_name(self, name: str) -> str:
        """
        Normalize speaker name for matching

        Args:
            name: Speaker name

        Returns:
            Normalized name (trimmed, proper case)
        """
        if not name:
            return ""

        # Remove extra whitespace
        normalized = " ".join(name.split())

        return normalized

    def get_search_pattern(self, speaker_name: str) -> str:
        """
        Get SQL ILIKE pattern for speaker search

        Args:
            speaker_name: Speaker name to search for

        Returns:
            SQL ILIKE pattern (e.g., "%João%" for partial match)

        Examples:
            >>> parser.get_search_pattern("João")
            '%João%'
            >>> parser.get_search_pattern("João Silva")
            '%João Silva%'
        """
        if not speaker_name:
            return "%"

        # Normalize and create wildcard pattern
        normalized = self.normalize_speaker_name(speaker_name)
        return f"%{normalized}%"


# Module-level singleton
_speaker_parser = None


def get_speaker_parser() -> SpeakerParser:
    """Get or create singleton SpeakerParser instance"""
    global _speaker_parser
    if _speaker_parser is None:
        _speaker_parser = SpeakerParser()
    return _speaker_parser
