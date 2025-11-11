"""
Segment Metadata Extraction Service (Phase 2)
Extracts keywords, topics, sentiment, and other metadata from sermon segments
"""
import logging
import re
from typing import Dict, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """
    Extract metadata from sermon segments for enhanced search and filtering

    Features:
    - Keyword extraction (top 5-10 keywords)
    - Topic identification (theological themes)
    - Sentiment analysis (positive, neutral, negative)
    - Question type detection (what, why, how, who, when, where)
    - Scripture reference detection
    - Practical application detection
    """

    # Portuguese theological topics
    THEOLOGICAL_TOPICS = {
        'salvação': ['salvação', 'redenção', 'resgate', 'salvar', 'salvo'],
        'fé': ['fé', 'crer', 'acreditar', 'confiança', 'confiar'],
        'oração': ['oração', 'orar', 'interceder', 'suplicar', 'pedir'],
        'adoração': ['adoração', 'adorar', 'louvor', 'louvar', 'culto'],
        'amor': ['amor', 'amar', 'caridade', 'compaixão', 'misericórdia'],
        'santidade': ['santidade', 'santo', 'santificação', 'consagração', 'pureza'],
        'pecado': ['pecado', 'transgressão', 'iniquidade', 'mal', 'erro'],
        'graça': ['graça', 'gratuito', 'favor', 'benção'],
        'evangelho': ['evangelho', 'boa nova', 'mensagem', 'proclamar'],
        'reino': ['reino', 'reino de deus', 'reino dos céus', 'reinado'],
        'cruz': ['cruz', 'crucificado', 'sacrifício', 'morte', 'calvário'],
        'ressurreição': ['ressurreição', 'ressuscitar', 'vivo', 'vida eterna'],
        'espírito': ['espírito santo', 'consolador', 'espírito', 'pneuma'],
        'igreja': ['igreja', 'corpo', 'comunidade', 'assembleia'],
        'missão': ['missão', 'evangelizar', 'missões', 'testemunhar'],
        'família': ['família', 'casamento', 'filhos', 'pais', 'lar'],
        'esperança': ['esperança', 'esperar', 'aguardar', 'anseio'],
        'perseverança': ['perseverança', 'perseverar', 'persistir', 'firme'],
        'discipulado': ['discípulo', 'discipulado', 'seguir', 'aprender'],
        'arrependimento': ['arrependimento', 'arrepender', 'converter', 'conversão'],
        'batismo': ['batismo', 'batizar', 'batizado', 'batismal'],
        'jejum': ['jejum', 'jejuar', 'abstinência'],
        'perdão': ['perdão', 'perdoar', 'reconciliação', 'reconciliar'],
        'justiça': ['justiça', 'justo', 'retidão', 'integridade'],
        'humildade': ['humildade', 'humilde', 'humilhar', 'servo'],
        'obediência': ['obediência', 'obedecer', 'submissão', 'sujeição'],
        'tentação': ['tentação', 'tentar', 'prova', 'provação'],
        'prosperidade': ['prosperidade', 'próspero', 'abundância', 'riqueza'],
        'sofrimento': ['sofrimento', 'sofrer', 'aflição', 'tribulação'],
        'alegria': ['alegria', 'alegrar', 'regozijo', 'gozo']
    }

    # Portuguese stopwords (common words to ignore in keyword extraction)
    STOPWORDS = {
        'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas',
        'de', 'da', 'do', 'das', 'dos', 'em', 'na', 'no', 'nas', 'nos',
        'por', 'para', 'com', 'sem', 'sob', 'sobre',
        'e', 'ou', 'mas', 'porém', 'contudo',
        'que', 'qual', 'quais', 'quando', 'onde', 'como',
        'é', 'são', 'foi', 'eram', 'ser', 'estar', 'ter', 'haver',
        'muito', 'mais', 'menos', 'tão', 'também', 'só', 'já', 'ainda',
        'isso', 'isto', 'esse', 'este', 'aquele', 'aquilo',
        'ele', 'ela', 'eles', 'elas', 'você', 'nós', 'vocês',
        'meu', 'minha', 'seu', 'sua', 'nosso', 'nossa',
        'ao', 'aos', 'à', 'às', 'pelo', 'pela', 'pelos', 'pelas',
        'num', 'numa', 'dum', 'duma'
    }

    # Biblical book names (Portuguese)
    BIBLICAL_BOOKS = {
        'gênesis', 'êxodo', 'levítico', 'números', 'deuteronômio',
        'josué', 'juízes', 'rute', 'samuel', 'reis', 'crônicas',
        'esdras', 'neemias', 'ester', 'jó', 'salmos', 'provérbios',
        'eclesiastes', 'cantares', 'isaías', 'jeremias', 'lamentações',
        'ezequiel', 'daniel', 'oséias', 'joel', 'amós', 'obadias',
        'jonas', 'miquéias', 'naum', 'habacuque', 'sofonias', 'ageu',
        'zacarias', 'malaquias', 'mateus', 'marcos', 'lucas', 'joão',
        'atos', 'romanos', 'coríntios', 'gálatas', 'efésios',
        'filipenses', 'colossenses', 'tessalonicenses', 'timóteo',
        'tito', 'filemom', 'hebreus', 'tiago', 'pedro', 'judas',
        'apocalipse'
    }

    # Practical application indicators
    PRACTICAL_INDICATORS = [
        'aplicar', 'praticar', 'fazer', 'agir', 'viver',
        'dia a dia', 'cotidiano', 'prática', 'ação', 'comportamento',
        'exemplo', 'modelo', 'como', 'deve', 'precisa',
        'importante', 'essencial', 'fundamental'
    ]

    # Question type patterns (Portuguese)
    QUESTION_PATTERNS = {
        'what': [r'\bque\b', r'\bo que\b', r'\bqual\b', r'\bquais\b'],
        'why': [r'\bpor que\b', r'\bporque\b', r'\bmotivo\b', r'\brazão\b'],
        'how': [r'\bcomo\b', r'\bde que forma\b', r'\bde que maneira\b'],
        'who': [r'\bquem\b', r'\bque pessoa\b'],
        'when': [r'\bquando\b', r'\bem que momento\b', r'\bque tempo\b'],
        'where': [r'\bonde\b', r'\bem que lugar\b', r'\baonde\b']
    }

    def __init__(self):
        """Initialize metadata extractor"""
        logger.info("Metadata extractor initialized")

    def extract_all_metadata(self, text: str) -> Dict:
        """
        Extract all metadata from a segment

        Args:
            text: Segment text

        Returns:
            Dictionary with all extracted metadata
        """
        return {
            'keywords': self.extract_keywords(text),
            'topics': self.identify_topics(text),
            'sentiment': self.analyze_sentiment(text),
            'question_type': self.detect_question_type(text),
            'has_scripture': self.detect_scripture_reference(text),
            'has_practical_application': self.detect_practical_application(text)
        }

    def extract_keywords(self, text: str, top_n: int = 8) -> List[str]:
        """
        Extract top keywords using simple word frequency (TF)

        Args:
            text: Segment text
            top_n: Number of top keywords to return

        Returns:
            List of top keywords
        """
        # Normalize text
        text_lower = text.lower()

        # Remove punctuation and split
        words = re.findall(r'\b[a-záàâãéèêíïóôõúç]+\b', text_lower)

        # Filter stopwords and short words
        filtered_words = [
            word for word in words
            if word not in self.STOPWORDS and len(word) > 3
        ]

        # Count frequencies
        word_counts = Counter(filtered_words)

        # Get top N
        top_keywords = [word for word, count in word_counts.most_common(top_n)]

        logger.debug(f"Extracted {len(top_keywords)} keywords from segment")
        return top_keywords

    def identify_topics(self, text: str, min_confidence: float = 0.5) -> List[str]:
        """
        Identify theological topics in text

        Args:
            text: Segment text
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            List of identified topics
        """
        text_lower = text.lower()
        identified_topics = []

        for topic, keywords in self.THEOLOGICAL_TOPICS.items():
            # Count how many keywords match
            matches = sum(1 for keyword in keywords if keyword in text_lower)

            # Calculate confidence (simple approach: matches / total keywords)
            confidence = matches / len(keywords)

            if confidence >= min_confidence or matches >= 2:
                identified_topics.append(topic)

        logger.debug(f"Identified {len(identified_topics)} topics: {identified_topics}")
        return identified_topics[:5]  # Limit to top 5 topics

    def analyze_sentiment(self, text: str) -> str:
        """
        Classify sentiment as positive, neutral, or negative

        Uses simple keyword-based approach for Portuguese

        Args:
            text: Segment text

        Returns:
            Sentiment: 'positive', 'neutral', or 'negative'
        """
        text_lower = text.lower()

        # Positive indicators
        positive_words = [
            'alegria', 'amor', 'paz', 'esperança', 'bênção', 'graça',
            'misericórdia', 'salvação', 'vitória', 'glória', 'feliz',
            'maravilhoso', 'excelente', 'bom', 'melhor', 'benção'
        ]

        # Negative indicators
        negative_words = [
            'pecado', 'morte', 'sofrimento', 'dor', 'tristeza', 'mal',
            'iniquidade', 'transgressão', 'aflição', 'angústia', 'medo',
            'erro', 'falha', 'problema', 'dificuldade', 'crise'
        ]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        # Determine sentiment
        if positive_count > negative_count * 1.5:
            return 'positive'
        elif negative_count > positive_count * 1.5:
            return 'negative'
        else:
            return 'neutral'

    def detect_question_type(self, text: str) -> Optional[str]:
        """
        Detect if segment answers a specific type of question

        Args:
            text: Segment text

        Returns:
            Question type or None
        """
        text_lower = text.lower()

        for question_type, patterns in self.QUESTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    logger.debug(f"Detected question type: {question_type}")
                    return question_type

        return None

    def detect_scripture_reference(self, text: str) -> bool:
        """
        Check if segment contains biblical references

        Args:
            text: Segment text

        Returns:
            True if scripture references found
        """
        text_lower = text.lower()

        # Check for biblical book names
        for book in self.BIBLICAL_BOOKS:
            if book in text_lower:
                logger.debug(f"Found biblical reference: {book}")
                return True

        # Check for generic scripture references
        scripture_patterns = [
            r'\bbíblia\b',
            r'\bescritu?ra\b',
            r'\bpalavra\b.*\bdeus\b',
            r'\bversículo\b',
            r'\bcapítulo\b.*\bversículo\b',
            r'\b\d+:\d+\b'  # Chapter:verse pattern
        ]

        for pattern in scripture_patterns:
            if re.search(pattern, text_lower):
                return True

        return False

    def detect_practical_application(self, text: str) -> bool:
        """
        Check if segment has practical life applications

        Args:
            text: Segment text

        Returns:
            True if practical applications found
        """
        text_lower = text.lower()

        # Count practical indicators
        matches = sum(
            1 for indicator in self.PRACTICAL_INDICATORS
            if indicator in text_lower
        )

        # Require at least 2 matches for high confidence
        return matches >= 2


# Singleton instance
_metadata_extractor = None


def get_metadata_extractor() -> MetadataExtractor:
    """Get or create metadata extractor singleton"""
    global _metadata_extractor
    if _metadata_extractor is None:
        _metadata_extractor = MetadataExtractor()
    return _metadata_extractor
