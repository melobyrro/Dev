"""
Sensitivity Analyzer
Flags potentially sensitive content for pastor review
"""
import logging
import re
from typing import List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SensitivityFlagData:
    """Represents a sensitivity flag"""
    term: str
    context_before: str
    context_after: str
    flag_reason: str


class SensitivityAnalyzer:
    """
    Analyzes sermons for potentially sensitive content

    Categories:
    - Political references
    - Controversial topics
    - Cultural sensitivity
    - Gender/identity topics
    - Potentially offensive language
    """

    # Terms that warrant review
    SENSITIVE_PATTERNS = [
        # Political
        (r'\b(governo|político|partido|eleição|voto)\b', 'Referência política'),
        # Controversial
        (r'\b(aborto|homossexual|lgbt|gay)\b', 'Tópico controverso'),
        # Money/prosperity
        (r'\b(dinheiro|rico|pobre|riqueza.*material)\b', 'Referência financeira'),
        # Denominational
        (r'\b(católico|protestante|evangélico.*outro)\b', 'Referência denominacional'),
    ]

    def __init__(self):
        """Initialize sensitivity analyzer"""
        self.patterns = [(re.compile(p, re.IGNORECASE), reason)
                        for p, reason in self.SENSITIVE_PATTERNS]
        logger.info("Sensitivity analyzer initialized")

    def analyze(self, text: str, max_flags: int = 10) -> List[SensitivityFlagData]:
        """
        Analyze text for sensitive content

        Args:
            text: Sermon text
            max_flags: Maximum flags to return

        Returns:
            List of sensitivity flags
        """
        flags = []

        for pattern, reason in self.patterns:
            for match in pattern.finditer(text):
                if len(flags) >= max_flags:
                    break

                pos = match.start()
                term = match.group()

                # Get context (25 words before and after)
                words = text.split()
                text_words = ' '.join(words)

                # Find word position
                word_pos = len(text[:pos].split())

                context_before = ' '.join(words[max(0, word_pos-25):word_pos])
                context_after = ' '.join(words[word_pos+1:word_pos+26])

                flags.append(SensitivityFlagData(
                    term=term,
                    context_before=context_before,
                    context_after=context_after,
                    flag_reason=reason
                ))

        return flags[:max_flags]
