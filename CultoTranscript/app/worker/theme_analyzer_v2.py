"""
Theme Analyzer V2
ML-based thematic analysis using Google Gemini AI
"""
import logging
import re
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ThemeDetection:
    """Represents a detected theme with evidence"""
    theme_tag: str
    confidence_score: float  # 0-1
    segment_start: Optional[int] = None  # Timestamp in seconds
    segment_end: Optional[int] = None
    key_evidence: Optional[str] = None  # Key quotes/phrases


class ThemeAnalyzerV2:
    """
    ML-based theme analysis using Google Gemini

    Detects 17 theological themes:
    1. Christ-Centered (Cristo-cêntrica)
    2. Holiness (Santidade)
    3. Family (Família)
    4. Evangelism (Evangelismo)
    5. Prosperity (Prosperidade)
    6. Suffering (Sofrimento)
    7. Faith (Fé)
    8. Repentance (Arrependimento)
    9. Grace (Graça)
    10. Missions (Missões)
    11. Discipleship (Discipulado)
    12. Hope (Esperança)
    13. Justification (Justificação)
    14. Forgiveness (Perdão)
    15. Prayer (Oração)
    16. Adoration (Adoração)
    17. Holy Scriptures (Sagradas Escrituras)
    """

    THEMES = [
        'Cristo-cêntrica',
        'Santidade',
        'Família',
        'Evangelismo',
        'Prosperidade',
        'Sofrimento',
        'Fé',
        'Arrependimento',
        'Graça',
        'Missões',
        'Discipulado',
        'Esperança',
        'Justificação',
        'Perdão',
        'Oração',
        'Adoração',
        'Sagradas Escrituras'
    ]

    # Segment size for analysis (words)
    # Increased from 500 to 2500 to reduce Gemini API calls and stay within quota
    SEGMENT_SIZE = 2500
    OVERLAP = 50  # Words of overlap between segments (reduced from 100)

    def __init__(self, gemini_client):
        """
        Initialize theme analyzer

        Args:
            gemini_client: GeminiClient instance
        """
        self.gemini = gemini_client
        logger.info("Theme analyzer v2 initialized with Gemini AI")

    def analyze_themes(self, text: str, word_count: int) -> List[ThemeDetection]:
        """
        Analyze themes in sermon text

        Args:
            text: Full transcript text
            word_count: Total word count

        Returns:
            List of detected themes with confidence scores
        """
        # For shorter sermons, analyze as whole
        if word_count < 1000:
            return self._analyze_segment(text, 0, word_count)

        # For longer sermons, analyze in segments
        all_themes = []
        segments = self._split_into_segments(text)

        for i, (segment_text, start_word, end_word) in enumerate(segments):
            logger.debug(f"Analyzing segment {i+1}/{len(segments)}")

            segment_themes = self._analyze_segment(
                segment_text,
                start_word,
                end_word
            )
            all_themes.extend(segment_themes)

        # Aggregate themes across segments
        aggregated = self._aggregate_themes(all_themes)

        return aggregated

    def _split_into_segments(self, text: str) -> List[tuple]:
        """
        Split text into overlapping segments

        Args:
            text: Full text

        Returns:
            List of (segment_text, start_word, end_word) tuples
        """
        words = text.split()
        segments = []

        start = 0
        while start < len(words):
            end = min(start + self.SEGMENT_SIZE, len(words))
            segment_words = words[start:end]
            segment_text = ' '.join(segment_words)

            segments.append((segment_text, start, end))

            # Move forward with overlap
            start += (self.SEGMENT_SIZE - self.OVERLAP)

        return segments

    def _analyze_segment(
        self,
        text: str,
        start_word: int,
        end_word: int
    ) -> List[ThemeDetection]:
        """
        Analyze themes in a text segment using Gemini

        Args:
            text: Segment text
            start_word: Starting word position
            end_word: Ending word position

        Returns:
            List of detected themes
        """
        # Build prompt for Gemini
        prompt = f"""
Analise o seguinte segmento de sermão e identifique os temas teológicos presentes.

Para cada tema identificado, forneça:
1. Nome do tema (da lista abaixo)
2. Pontuação de confiança (0.0 a 1.0)
3. Evidência-chave (citação de 1-2 frases que suportam o tema)

TEMAS POSSÍVEIS:
{', '.join(self.THEMES)}

TEXTO DO SERMÃO:
{text[:3000]}

FORMATO DE RESPOSTA (JSON):
[
  {{
    "tema": "Cristo-cêntrica",
    "confianca": 0.85,
    "evidencia": "Citação relevante do texto"
  }},
  ...
]

Responda APENAS com o JSON, sem explicações adicionais.
Se nenhum tema forte for identificado, retorne lista vazia [].
"""

        try:
            response = self.gemini.generate_content(prompt)

            # Parse JSON response
            import json

            # Extract JSON from response (handle cases where AI adds extra text)
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in Gemini response")
                return []

            themes_data = json.loads(json_match.group())

            # Convert to ThemeDetection objects
            detections = []
            for item in themes_data:
                theme = item.get('tema', '')
                confidence = float(item.get('confianca', 0))
                evidence = item.get('evidencia', '')

                # Validate theme name
                if theme not in self.THEMES:
                    logger.warning(f"Unknown theme returned: {theme}")
                    continue

                # Estimate timestamps (simplified)
                # In real implementation, use actual timed transcripts
                segment_duration = (end_word - start_word) / 2.5  # ~150 wpm = 2.5 wps
                segment_start = int(start_word / 2.5)
                segment_end = int(end_word / 2.5)

                detection = ThemeDetection(
                    theme_tag=theme,
                    confidence_score=confidence,
                    segment_start=segment_start,
                    segment_end=segment_end,
                    key_evidence=evidence[:500]  # Limit length
                )
                detections.append(detection)

            return detections

        except Exception as e:
            error_str = str(e)
            # Check if it's a quota error (429)
            if "429" in error_str or "quota" in error_str.lower():
                logger.warning(f"Gemini API quota exhausted, using keyword-based fallback: {e}")
            else:
                logger.error(f"Error analyzing segment with Gemini: {e}")

            # Fallback to keyword-based detection
            return self._fallback_keyword_analysis(text, start_word, end_word)

    def _fallback_keyword_analysis(
        self,
        text: str,
        start_word: int,
        end_word: int
    ) -> List[ThemeDetection]:
        """
        Fallback keyword-based theme detection when AI fails

        Args:
            text: Text to analyze
            start_word: Starting word position
            end_word: Ending word position

        Returns:
            List of detected themes
        """
        # Simple keyword matching as fallback
        theme_keywords = {
            'Cristo-cêntrica': ['cristo', 'jesus', 'salvador', 'cruz', 'ressurreição'],
            'Santidade': ['santo', 'santidade', 'pureza', 'consagração', 'separação'],
            'Família': ['família', 'casamento', 'filhos', 'pais', 'lar'],
            'Evangelismo': ['evangelizar', 'testemunhar', 'missões', 'pregar'],
            'Fé': ['fé', 'confiança', 'crer', 'acreditar', 'confiar'],
            'Graça': ['graça', 'misericórdia', 'favor', 'bondade'],
            'Oração': ['oração', 'orar', 'súplica', 'interceder', 'clamar'],
        }

        text_lower = text.lower()
        detections = []

        for theme, keywords in theme_keywords.items():
            count = sum(1 for keyword in keywords if keyword in text_lower)

            if count > 0:
                # Simple confidence based on keyword frequency
                confidence = min(1.0, count * 0.2)

                segment_duration = (end_word - start_word) / 2.5
                segment_start = int(start_word / 2.5)
                segment_end = int(end_word / 2.5)

                detection = ThemeDetection(
                    theme_tag=theme,
                    confidence_score=confidence,
                    segment_start=segment_start,
                    segment_end=segment_end,
                    key_evidence=f"Palavras-chave encontradas: {', '.join(keywords[:3])}"
                )
                detections.append(detection)

        return detections

    def _aggregate_themes(
        self,
        theme_list: List[ThemeDetection]
    ) -> List[ThemeDetection]:
        """
        Aggregate themes detected across multiple segments

        Args:
            theme_list: List of all theme detections

        Returns:
            Aggregated list with combined confidence scores
        """
        # Group by theme tag
        theme_groups = {}
        for detection in theme_list:
            if detection.theme_tag not in theme_groups:
                theme_groups[detection.theme_tag] = []
            theme_groups[detection.theme_tag].append(detection)

        # Aggregate each group
        aggregated = []
        for theme_tag, detections in theme_groups.items():
            # Use maximum confidence score
            max_confidence = max(d.confidence_score for d in detections)

            # Combine evidence from top 2 detections
            sorted_detections = sorted(
                detections,
                key=lambda d: d.confidence_score,
                reverse=True
            )
            combined_evidence = ' | '.join(
                d.key_evidence for d in sorted_detections[:2]
                if d.key_evidence
            )

            # Use earliest segment start
            min_start = min(d.segment_start for d in detections if d.segment_start)
            max_end = max(d.segment_end for d in detections if d.segment_end)

            aggregated.append(ThemeDetection(
                theme_tag=theme_tag,
                confidence_score=max_confidence,
                segment_start=min_start,
                segment_end=max_end,
                key_evidence=combined_evidence[:1000]
            ))

        # Sort by confidence
        aggregated.sort(key=lambda d: d.confidence_score, reverse=True)

        # Return top themes only (confidence > 0.3)
        return [d for d in aggregated if d.confidence_score > 0.3]
