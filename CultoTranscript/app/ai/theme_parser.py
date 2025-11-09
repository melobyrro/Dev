"""
Theme Parser Module
Extracts theme keywords from Portuguese chatbot queries
"""
import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ThemeExtractionResult:
    """Result of theme extraction from query"""
    themes: List[str]
    found: bool
    original_query: str
    pattern_matched: Optional[str] = None
    confidence: float = 1.0

    def __repr__(self):
        if self.found:
            return f"ThemeExtractionResult(themes={self.themes}, confidence={self.confidence:.2f})"
        return "ThemeExtractionResult(no themes detected)"


class ThemeParser:
    """
    Detects and extracts theological themes from Portuguese queries

    Features:
    - Recognizes 17 theological themes from ThemeAnalyzerV2
    - Handles synonyms and variations
    - Supports multi-theme queries
    - Case-insensitive matching

    Examples:
        "sermões sobre graça" → ["Graça"]
        "pregações sobre fé e esperança" → ["Fé", "Esperança"]
        "mensagens sobre família" → ["Família"]
        "cultos sobre a cruz de Cristo" → ["Cristo-cêntrica"]
    """

    # Map from ThemeAnalyzerV2.THEMES - canonical theme names
    CANONICAL_THEMES = [
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

    # Synonyms and variations mapping to canonical themes
    THEME_SYNONYMS = {
        # Cristo-cêntrica
        'cristo': 'Cristo-cêntrica',
        'cristocêntrica': 'Cristo-cêntrica',
        'cristocentrica': 'Cristo-cêntrica',
        'jesus': 'Cristo-cêntrica',
        'messias': 'Cristo-cêntrica',
        'salvador': 'Cristo-cêntrica',
        'cruz': 'Cristo-cêntrica',
        'ressurreição': 'Cristo-cêntrica',
        'ressurreicao': 'Cristo-cêntrica',
        'crucificação': 'Cristo-cêntrica',
        'crucificacao': 'Cristo-cêntrica',
        'redenção': 'Cristo-cêntrica',
        'redencao': 'Cristo-cêntrica',

        # Santidade
        'santidade': 'Santidade',
        'santo': 'Santidade',
        'santa': 'Santidade',
        'pureza': 'Santidade',
        'santificação': 'Santidade',
        'santificacao': 'Santidade',
        'consagração': 'Santidade',
        'consagracao': 'Santidade',

        # Família
        'família': 'Família',
        'familia': 'Família',
        'casamento': 'Família',
        'filhos': 'Família',
        'pais': 'Família',
        'maternidade': 'Família',
        'paternidade': 'Família',
        'matrimônio': 'Família',
        'matrimonio': 'Família',

        # Evangelismo
        'evangelismo': 'Evangelismo',
        'evangelização': 'Evangelismo',
        'evangelizacao': 'Evangelismo',
        'testemunho': 'Evangelismo',
        'testemunhar': 'Evangelismo',
        'proclamação': 'Evangelismo',
        'proclamacao': 'Evangelismo',
        'anúncio': 'Evangelismo',
        'anuncio': 'Evangelismo',

        # Prosperidade
        'prosperidade': 'Prosperidade',
        'prosperou': 'Prosperidade',
        'prosperar': 'Prosperidade',
        'bênção': 'Prosperidade',
        'bencao': 'Prosperidade',
        'bênçãos': 'Prosperidade',
        'bencaos': 'Prosperidade',

        # Sofrimento
        'sofrimento': 'Sofrimento',
        'sofrer': 'Sofrimento',
        'dor': 'Sofrimento',
        'aflição': 'Sofrimento',
        'aflicao': 'Sofrimento',
        'tribulação': 'Sofrimento',
        'tribulacao': 'Sofrimento',
        'provação': 'Sofrimento',
        'provacao': 'Sofrimento',
        'perseguição': 'Sofrimento',
        'perseguicao': 'Sofrimento',

        # Fé
        'fé': 'Fé',
        'fe': 'Fé',
        'confiança': 'Fé',
        'confianca': 'Fé',
        'crer': 'Fé',
        'crença': 'Fé',
        'crenca': 'Fé',

        # Arrependimento
        'arrependimento': 'Arrependimento',
        'arrepender': 'Arrependimento',
        'conversão': 'Arrependimento',
        'conversao': 'Arrependimento',
        'mudança': 'Arrependimento',
        'mudanca': 'Arrependimento',

        # Graça
        'graça': 'Graça',
        'graca': 'Graça',
        'misericórdia': 'Graça',
        'misericordia': 'Graça',
        'compaixão': 'Graça',
        'compaixao': 'Graça',

        # Missões
        'missões': 'Missões',
        'missoes': 'Missões',
        'missão': 'Missões',
        'missao': 'Missões',
        'missionário': 'Missões',
        'missionario': 'Missões',
        'missionária': 'Missões',
        'missionaria': 'Missões',
        'envio': 'Missões',

        # Discipulado
        'discipulado': 'Discipulado',
        'discípulo': 'Discipulado',
        'discipulo': 'Discipulado',
        'discípulos': 'Discipulado',
        'discipulos': 'Discipulado',
        'formação': 'Discipulado',
        'formacao': 'Discipulado',
        'ensino': 'Discipulado',

        # Esperança
        'esperança': 'Esperança',
        'esperanca': 'Esperança',
        'esperar': 'Esperança',
        'expectativa': 'Esperança',

        # Justificação
        'justificação': 'Justificação',
        'justificacao': 'Justificação',
        'justificar': 'Justificação',
        'justiça': 'Justificação',
        'justica': 'Justificação',

        # Perdão
        'perdão': 'Perdão',
        'perdao': 'Perdão',
        'perdoar': 'Perdão',
        'reconciliação': 'Perdão',
        'reconciliacao': 'Perdão',

        # Oração
        'oração': 'Oração',
        'oracao': 'Oração',
        'orar': 'Oração',
        'intercessão': 'Oração',
        'intercessao': 'Oração',
        'súplica': 'Oração',
        'suplica': 'Oração',

        # Adoração
        'adoração': 'Adoração',
        'adoracao': 'Adoração',
        'adorar': 'Adoração',
        'louvor': 'Adoração',
        'louvar': 'Adoração',
        'culto': 'Adoração',

        # Sagradas Escrituras
        'escrituras': 'Sagradas Escrituras',
        'escritura': 'Sagradas Escrituras',
        'bíblia': 'Sagradas Escrituras',
        'biblia': 'Sagradas Escrituras',
        'palavra': 'Sagradas Escrituras',
        'palavra de deus': 'Sagradas Escrituras',
    }

    # Query patterns that indicate theme-specific searches
    PATTERNS = [
        # "sermões sobre [theme]", "pregações sobre [theme]"
        r'(?:serm[õô]es?|prega[çc][õô]es?|mensagens?|cultos?)\s+sobre\s+(.+?)(?:\s+(?:do|da|de|dos|das|e|,|;|\.|$))',

        # "sobre [theme]" at start of query
        r'^sobre\s+(.+?)(?:\s+(?:do|da|de|dos|das|e|,|;|\.|$))',

        # "tema [theme]", "assunto [theme]"
        r'(?:tema|assunto|tópico|topico)\s+(?:de|sobre|da|do)?\s*(.+?)(?:\s+(?:do|da|de|dos|das|e|,|;|\.|$))',

        # "falou sobre [theme]", "pregou sobre [theme]"
        r'(?:falou|pregou|ministrou|ensinou|abordou)\s+sobre\s+(.+?)(?:\s+(?:do|da|de|dos|das|e|,|;|\.|$))',

        # Just theme keywords (more lenient)
        r'\b(.+?)\b',
    ]

    def __init__(self):
        """Initialize theme parser"""
        logger.info(f"ThemeParser initialized with {len(self.CANONICAL_THEMES)} canonical themes and {len(self.THEME_SYNONYMS)} synonyms")

    def extract_themes(self, query: str) -> ThemeExtractionResult:
        """
        Extract theme keywords from query

        Args:
            query: User query text

        Returns:
            ThemeExtractionResult with detected themes

        Examples:
            >>> parser = ThemeParser()
            >>> result = parser.extract_themes("sermões sobre graça e fé")
            >>> result.themes
            ['Graça', 'Fé']
            >>> result.found
            True
        """
        if not query or not isinstance(query, str):
            return ThemeExtractionResult(
                themes=[],
                found=False,
                original_query=query or ""
            )

        # Normalize query
        query_lower = query.lower()

        # Try to extract theme keywords
        detected_themes: Set[str] = set()

        # Check for direct theme mentions
        for keyword, canonical_theme in self.THEME_SYNONYMS.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, query_lower):
                detected_themes.add(canonical_theme)
                logger.debug(f"Theme keyword '{keyword}' → canonical theme '{canonical_theme}'")

        # If themes found, return result
        if detected_themes:
            themes_list = sorted(list(detected_themes))
            logger.info(f"🎨 Themes detected: {themes_list}")

            return ThemeExtractionResult(
                themes=themes_list,
                found=True,
                original_query=query,
                pattern_matched="keyword_match",
                confidence=1.0
            )

        # No themes found
        logger.debug(f"No themes detected in query: {query[:100]}")
        return ThemeExtractionResult(
            themes=[],
            found=False,
            original_query=query
        )

    def normalize_theme_name(self, theme: str) -> str:
        """
        Normalize theme name to canonical form

        Args:
            theme: Theme name

        Returns:
            Canonical theme name or empty string if not found
        """
        if not theme:
            return ""

        # Check if already canonical
        if theme in self.CANONICAL_THEMES:
            return theme

        # Check synonyms
        theme_lower = theme.lower()
        if theme_lower in self.THEME_SYNONYMS:
            return self.THEME_SYNONYMS[theme_lower]

        return ""


# Module-level singleton
_theme_parser = None


def get_theme_parser() -> ThemeParser:
    """Get or create singleton ThemeParser instance"""
    global _theme_parser
    if _theme_parser is None:
        _theme_parser = ThemeParser()
    return _theme_parser
