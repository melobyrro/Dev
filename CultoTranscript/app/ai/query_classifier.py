"""
Query Type Classifier for Chatbot
Detects query types to optimize response length and format
"""
import logging
import re
from enum import Enum
from typing import Dict

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries the chatbot can receive"""
    TITLE_SUGGESTION = "title_suggestion"
    SUMMARY = "summary"
    DETAILED_ANALYSIS = "detailed_analysis"
    LIST_REQUEST = "list_request"
    SINGLE_FACT = "single_fact"
    GENERAL = "general"
    COMPARISON = "comparison"
    RECOMMENDATION = "recommendation"
    VERSE_LOOKUP = "verse_lookup"


class ResponseConfig:
    """Configuration for LLM response based on query type"""
    def __init__(self, max_tokens: int, instruction: str, temperature: float = 0.7, context_size: int = 10):
        self.max_tokens = max_tokens
        self.instruction = instruction
        self.temperature = temperature
        self.context_size = context_size


# Response configurations for each query type
RESPONSE_CONFIGS: Dict[QueryType, ResponseConfig] = {
    QueryType.TITLE_SUGGESTION: ResponseConfig(
        max_tokens=50,
        instruction='Sugira apenas um título curto e criativo (máximo 10 palavras). Seja direto e conciso.',
        temperature=0.9,  # Higher for creativity
        context_size=3     # Need less context for titles
    ),
    QueryType.SINGLE_FACT: ResponseConfig(
        max_tokens=100,
        instruction='Responda de forma direta e breve, fornecendo apenas a informação específica solicitada.',
        temperature=0.3,  # Lower for precision
        context_size=5     # Moderate context
    ),
    QueryType.SUMMARY: ResponseConfig(
        max_tokens=300,
        instruction='Forneça um resumo conciso e bem estruturado dos principais pontos.',
        temperature=0.5,  # Balanced
        context_size=8     # Good coverage
    ),
    QueryType.LIST_REQUEST: ResponseConfig(
        max_tokens=400,
        instruction='Formate a resposta como lista com bullet points (•). Seja organizado e estruturado.',
        temperature=0.5,  # Balanced
        context_size=10    # Comprehensive
    ),
    QueryType.GENERAL: ResponseConfig(
        max_tokens=500,
        instruction='Forneça uma resposta equilibrada, nem muito breve nem muito extensa.',
        temperature=0.7,  # Default balanced
        context_size=10    # Standard
    ),
    QueryType.DETAILED_ANALYSIS: ResponseConfig(
        max_tokens=800,
        instruction='Forneça uma análise detalhada e aprofundada, explorando múltiplos aspectos.',
        temperature=0.7,  # Balanced for analysis
        context_size=15    # Maximum context
    ),
    QueryType.COMPARISON: ResponseConfig(
        max_tokens=600,
        instruction='Compare os sermões mencionados, destacando semelhanças e diferenças nos temas, abordagens e aplicações práticas.',
        temperature=0.6,  # Balanced analytical
        context_size=20    # Need context from multiple sermons
    ),
    QueryType.RECOMMENDATION: ResponseConfig(
        max_tokens=300,
        instruction='Sugira sermões relacionados de forma concisa, explicando brevemente por que cada recomendação é relevante.',
        temperature=0.7,  # Balanced
        context_size=12    # Need to see variety
    ),
    QueryType.VERSE_LOOKUP: ResponseConfig(
        max_tokens=200,
        instruction='Liste as referências bíblicas encontradas com seus contextos específicos de forma organizada.',
        temperature=0.3,  # Low for accuracy
        context_size=8     # Moderate context
    ),
}


class QueryClassifier:
    """
    Classifies user queries into types to optimize chatbot responses

    Uses regex patterns and keyword matching to detect:
    - Title suggestions
    - Summary requests
    - Detailed analysis requests
    - List requests
    - Single fact queries
    - General questions
    """

    def __init__(self):
        """Initialize classifier with Portuguese language patterns"""

        # Title suggestion patterns (Portuguese)
        self.title_patterns = [
            r'\btítulo\b',
            r'\bsuger[ae]\b.*\btítulo\b',
            r'\bque título\b',
            r'\bcomo\s+intitular\b',
            r'\bcomo\s+chamar\b',
            r'\bnome\s+para\b',
            r'\bme\s+dê\s+um\s+título\b'
        ]

        # Summary patterns (Portuguese)
        self.summary_patterns = [
            r'\bresum[oa]\b',
            r'\bsintetiz[ae]\b',
            r'\bsíntese\b',
            r'\bem\s+poucas\s+palavras\b',
            r'\bprincipal\s+mensagem\b',
            r'\bassunto\s+principal\b',
            r'\bdo\s+que\s+trat[ao]u?\b',
            r'\bfal[ao]u\s+sobre\s+o\s+qu[eê]\b',
            r'\bqual\s+foi\s+o\s+tema\b'
        ]

        # Detailed analysis patterns (Portuguese)
        self.detailed_patterns = [
            r'\banalise\b',
            r'\baprofunde\b',
            r'\bdetalhadamente\b',
            r'\bem\s+detalhes\b',
            r'\bexplique\s+melhor\b',
            r'\bexplique\s+mais\b',
            r'\bdiscorra\b',
            r'\baprofund[ae]\b',
            r'\bexpand[ae]\b',
            r'\belabore\b',
            r'\bdesenvolvimento\b',
            r'\bpor\s+que\b.*\bpor\s+que\b',  # Multiple "why" questions
            r'\bcomo\s+isso\b.*\brelacion[ae]\b'
        ]

        # List request patterns (Portuguese)
        self.list_patterns = [
            r'\bliste\b',
            r'\blistar\b',
            r'\bquais\s+foram\b',
            r'\bquais\s+são\b',
            r'\btodos\s+os?\b',
            r'\btodas\s+as?\b',
            r'\benumere\b',
            r'\bprincipal\s+pontos?\b',
            r'\bpontos?\s+principais?\b',
            r'\bcite\b',
            r'\bexemplos?\b',
            r'\bquantos?\b',
            r'\bquantas?\b'
        ]

        # Single fact patterns (Portuguese)
        self.fact_patterns = [
            r'\bquando\b',
            r'\bquem\b',
            r'\bqual\s+vers[íi]culo\b',
            r'\bqual\s+passagem\b',
            r'\bqual\s+texto\b',
            r'\bqual\s+livro\b',
            r'\bqual\s+cap[íi]tulo\b',
            r'\bonde\b',
            r'\bem\s+que\s+ano\b',
            r'\bem\s+que\s+data\b',
            r'\bquanto\s+tempo\b',
            r'\bduração\b',
            r'\bsim\s+ou\s+não\b',
            r'\bverdadeiro\s+ou\s+falso\b'
        ]

        # Comparison patterns
        self.comparison_patterns = [
            r'\bcompar[ae]\b',
            r'\bdiferença[s]?\b.*\bentre\b',
            r'\bsemelhanç[a]?[s]?\b.*\bentre\b',
            r'\bversus\b',
            r'\bvs\.?\b',
            r'\be(?:m relação a|m comparação com)\b',
        ]

        # Recommendation patterns
        self.recommendation_patterns = [
            r'\brecomend[ae]\b',
            r'\bsugir[ae]\b.*\bsermõ(?:es|ão)\b',
            r'\boutros?\s+sermõ(?:es|ão)\b.*\bsemelhante[s]?\b',
            r'\brelacionad(?:os?|as?)\b',
            r'\bque(?:\s+outros?)?\s+sermõ(?:es|ão)\b',
        ]

        # Verse lookup patterns
        self.verse_lookup_patterns = [
            r'\bvers[íi]culos?\b.*\bmencionad(?:os?|as?)\b',
            r'\bpassagens?\b.*\bcitad[oa]s?\b',
            r'\bquais\s+vers[íi]culos\b',
            r'\breferências?\s+b[íi]blicas?\b',
            r'\btextos?\s+b[íi]blicos?\b.*\busad(?:os?|as?)\b',
        ]

        # Compile all patterns for efficiency
        self.compiled_patterns = {
            QueryType.TITLE_SUGGESTION: [re.compile(p, re.IGNORECASE) for p in self.title_patterns],
            QueryType.SUMMARY: [re.compile(p, re.IGNORECASE) for p in self.summary_patterns],
            QueryType.DETAILED_ANALYSIS: [re.compile(p, re.IGNORECASE) for p in self.detailed_patterns],
            QueryType.LIST_REQUEST: [re.compile(p, re.IGNORECASE) for p in self.list_patterns],
            QueryType.SINGLE_FACT: [re.compile(p, re.IGNORECASE) for p in self.fact_patterns],
            QueryType.COMPARISON: [re.compile(p, re.IGNORECASE) for p in self.comparison_patterns],
            QueryType.RECOMMENDATION: [re.compile(p, re.IGNORECASE) for p in self.recommendation_patterns],
            QueryType.VERSE_LOOKUP: [re.compile(p, re.IGNORECASE) for p in self.verse_lookup_patterns],
        }

        logger.info("QueryClassifier initialized with Portuguese patterns")

    def classify(self, query: str) -> QueryType:
        """
        Classify a user query into a specific type

        Args:
            query: User's question in Portuguese

        Returns:
            QueryType enum value
        """
        if not query or not query.strip():
            return QueryType.GENERAL

        query_lower = query.lower().strip()

        # Check each query type in priority order
        # Priority 1: Title suggestions (most specific)
        if self._matches_patterns(query_lower, QueryType.TITLE_SUGGESTION):
            logger.info(f"Query classified as TITLE_SUGGESTION: {query[:50]}...")
            return QueryType.TITLE_SUGGESTION

        # Priority 2: Single facts
        if self._matches_patterns(query_lower, QueryType.SINGLE_FACT):
            logger.info(f"Query classified as SINGLE_FACT: {query[:50]}...")
            return QueryType.SINGLE_FACT

        # Priority 3: Verse lookups (NEW!)
        if self._matches_patterns(query_lower, QueryType.VERSE_LOOKUP):
            logger.info(f"Query classified as VERSE_LOOKUP: {query[:50]}...")
            return QueryType.VERSE_LOOKUP

        # Priority 4: Comparisons (NEW!)
        if self._matches_patterns(query_lower, QueryType.COMPARISON):
            logger.info(f"Query classified as COMPARISON: {query[:50]}...")
            return QueryType.COMPARISON

        # Priority 5: Recommendations (NEW!)
        if self._matches_patterns(query_lower, QueryType.RECOMMENDATION):
            logger.info(f"Query classified as RECOMMENDATION: {query[:50]}...")
            return QueryType.RECOMMENDATION

        # Priority 6: List requests
        if self._matches_patterns(query_lower, QueryType.LIST_REQUEST):
            logger.info(f"Query classified as LIST_REQUEST: {query[:50]}...")
            return QueryType.LIST_REQUEST

        # Priority 7: Detailed analysis
        if self._matches_patterns(query_lower, QueryType.DETAILED_ANALYSIS):
            logger.info(f"Query classified as DETAILED_ANALYSIS: {query[:50]}...")
            return QueryType.DETAILED_ANALYSIS

        # Priority 8: Summaries
        if self._matches_patterns(query_lower, QueryType.SUMMARY):
            logger.info(f"Query classified as SUMMARY: {query[:50]}...")
            return QueryType.SUMMARY

        # Default: General
        logger.info(f"Query classified as GENERAL: {query[:50]}...")
        return QueryType.GENERAL

    def _matches_patterns(self, query: str, query_type: QueryType) -> bool:
        """
        Check if query matches any pattern for the given query type

        Args:
            query: Normalized query string
            query_type: Type to check patterns for

        Returns:
            True if any pattern matches
        """
        patterns = self.compiled_patterns.get(query_type, [])
        return any(pattern.search(query) for pattern in patterns)

    def get_response_config(self, query_type: QueryType) -> ResponseConfig:
        """
        Get response configuration for a query type

        Args:
            query_type: The classified query type

        Returns:
            ResponseConfig with max_tokens and instruction
        """
        config = RESPONSE_CONFIGS[query_type]
        logger.debug(f"Response config for {query_type.value}: max_tokens={config.max_tokens}")
        return config

    def classify_and_configure(self, query: str) -> tuple[QueryType, ResponseConfig]:
        """
        Classify query and return both type and config

        Convenience method that combines classify() and get_response_config()

        Args:
            query: User's question

        Returns:
            Tuple of (QueryType, ResponseConfig)
        """
        query_type = self.classify(query)
        config = self.get_response_config(query_type)
        return query_type, config


# Singleton instance for efficiency
_classifier_instance: QueryClassifier = None


def get_query_classifier() -> QueryClassifier:
    """
    Get singleton instance of QueryClassifier

    Returns:
        QueryClassifier instance
    """
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = QueryClassifier()
        logger.info("QueryClassifier singleton created")
    return _classifier_instance
