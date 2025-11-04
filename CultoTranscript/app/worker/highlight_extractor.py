"""
Sermon Highlight Extractor
Identifies key moments in sermons
"""
import logging
import re
import json
from typing import List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Highlight:
    """Represents a highlighted sermon moment"""
    start_timestamp: int
    end_timestamp: int
    title: str
    summary: str
    highlight_reason: str


class HighlightExtractor:
    """
    Extracts key moments from sermons

    Highlights reasons:
    - Powerful quotes
    - Clear calls to action
    - Deep theological insights
    - Emotional peaks
    - Practical applications
    """

    def __init__(self, gemini_client):
        """Initialize with Gemini client"""
        self.gemini = gemini_client
        logger.info("Highlight extractor initialized")

    def extract_highlights(self, text: str, max_highlights: int = 5) -> List[Highlight]:
        """Extract key highlights from sermon"""
        prompt = f"""
Identifique os {max_highlights} momentos-chave mais importantes deste sermão:

SERMÃO:
{text[:4000]}

Para cada momento, forneça:
1. Título curto (máx 100 chars)
2. Resumo de uma linha
3. Razão do destaque (ex: "chamado à ação claro", "citação poderosa")

JSON format:
[{{
  "titulo": "...",
  "resumo": "...",
  "razao": "..."
}}]

Retorne APENAS o JSON com os {max_highlights} destaques mais impactantes.
"""

        try:
            response = self.gemini.generate_content(prompt)

            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []

            items = json.loads(json_match.group())

            highlights = []
            words = text.split()
            segment_size = len(words) // (len(items) + 1) if items else 0

            for i, item in enumerate(items):
                start_word = segment_size * i
                end_word = min(start_word + 100, len(words))

                start_ts = int(start_word / 2.5)
                end_ts = int(end_word / 2.5)

                highlights.append(Highlight(
                    start_timestamp=start_ts,
                    end_timestamp=end_ts,
                    title=item['titulo'][:200],
                    summary=item['resumo'][:500],
                    highlight_reason=item['razao'][:100]
                ))

            return highlights

        except Exception as e:
            logger.error(f"Error extracting highlights: {e}")
            return []
