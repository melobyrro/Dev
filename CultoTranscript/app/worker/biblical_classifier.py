"""
Biblical Content Classifier
Distinguishes between biblical citations, readings, and mentions using context analysis
"""
import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from app.common.bible_pt import BIBLE_BOOKS_PT

logger = logging.getLogger(__name__)


@dataclass
class BiblicalReference:
    """Represents a detected biblical reference with classification"""
    text: str  # The matched text
    book: str  # Canonical book name
    chapter: Optional[int]
    verse_start: Optional[int]
    verse_end: Optional[int]
    reference_type: str  # 'citation', 'reading', or 'mention'
    position: int  # Character position in text
    context_before: str  # 30 words before
    context_after: str  # 30 words after
    confidence: float  # 0-1 confidence score


class BiblicalClassifier:
    """
    Classifies biblical content into three categories:

    1. Citation (citacao): Explicit book + chapter/verse mentioned
       Example: "Salmo 23", "João 3:16"

    2. Reading (leitura): Biblical text read aloud or paraphrased
       Detected by: quotation marks, "diz", "está escrito", etc.

    3. Mention (mencao): Biblical character/book named without citation
       Example: "Jó sofreu muito", "como Davi"
    """

    # Context window size (number of words)
    CONTEXT_WINDOW = 30

    # Indicators of scripture reading
    READING_INDICATORS = [
        r'\b(diz|disse|dizia|falou|escreveu|está escrito|a palavra diz)\b',
        r'\b(versículo|verso|texto|passagem|escritura)\b',
        r'["""„]',  # Quotation marks
        r'\b(lemos|leiamos|vamos ler)\b',
    ]

    # Indicators of mentions (without reading)
    MENTION_INDICATORS = [
        r'\b(como|igual|semelhante a|tipo)\b',
        r'\b(história de|vida de|exemplo de)\b',
        r'\b(personagem|pessoa|profeta|apóstolo|rei)\b',
    ]

    # Biblical character names (for mention detection)
    BIBLICAL_CHARACTERS = [
        'Adão', 'Eva', 'Noé', 'Abraão', 'Sara', 'Isaque', 'Jacó', 'José',
        'Moisés', 'Arão', 'Josué', 'Davi', 'Salomão', 'Elias', 'Eliseu',
        'Isaías', 'Jeremias', 'Ezequiel', 'Daniel', 'Jonas', 'Jó',
        'Pedro', 'Paulo', 'João', 'Tiago', 'Mateus', 'Marcos', 'Lucas',
        'Maria', 'Marta', 'Lázaro', 'Zaqueu', 'Nicodemos', 'Tomé',
        'Barnabé', 'Timóteo', 'Tito', 'Filemon'
    ]

    # Words that might be confused with biblical terms
    DISAMBIGUATION_COMMON_WORDS = {
        'jó': ['trabalho', 'emprego', 'função'],  # Jó (person) vs job
        'marcos': ['março'],  # Marcos (disciple) vs March
        'lucas': ['lugar'],  # Lucas vs place
        'pedro': ['pedra', 'pedreiro'],  # Pedro vs stone/mason
        'joão': ['banho'],  # João vs bath (unlikely but possible)
    }

    def __init__(self):
        """Initialize the biblical classifier"""
        # Build book name patterns
        self.book_patterns = self._build_book_patterns()

        # Compile regex patterns
        self.reading_pattern = re.compile(
            '|'.join(self.READING_INDICATORS),
            re.IGNORECASE
        )
        self.mention_pattern = re.compile(
            '|'.join(self.MENTION_INDICATORS),
            re.IGNORECASE
        )

        logger.info("Biblical classifier initialized")

    def _build_book_patterns(self) -> Dict[str, re.Pattern]:
        """Build regex patterns for each biblical book"""
        patterns = {}

        for canonical_name, variants in BIBLE_BOOKS_PT.items():
            # Create pattern matching any variant
            variant_patterns = []
            for variant in variants:
                # Escape special regex characters
                escaped = re.escape(variant)
                # Allow optional spaces in numbered books (1 João or 1João)
                escaped = escaped.replace(r'\ ', r'\s*')
                variant_patterns.append(escaped)

            # Combined pattern for this book
            pattern = r'\b(' + '|'.join(variant_patterns) + r')\b'
            patterns[canonical_name] = re.compile(pattern, re.IGNORECASE)

        return patterns

    def classify_text(self, text: str) -> Dict[str, any]:
        """
        Classify all biblical content in text

        Args:
            text: Full transcript text

        Returns:
            Dictionary with classification results:
            {
                'citations': List[BiblicalReference],
                'readings': List[BiblicalReference],
                'mentions': List[BiblicalReference],
                'total_count': int,
                'citacao_count': int,
                'leitura_count': int,
                'mencao_count': int
            }
        """
        citations = []
        readings = []
        mentions = []

        # First pass: Find explicit citations (book + chapter/verse)
        for canonical_name, pattern in self.book_patterns.items():
            for match in pattern.finditer(text):
                ref = self._extract_full_reference(text, match, canonical_name)
                if ref and ref.chapter is not None:
                    # This is a citation (has chapter/verse)
                    ref.reference_type = self._classify_reference(text, ref)

                    if ref.reference_type == 'citation':
                        citations.append(ref)
                    elif ref.reference_type == 'reading':
                        readings.append(ref)

        # Second pass: Find character mentions without citations
        for character in self.BIBLICAL_CHARACTERS:
            pattern = re.compile(rf'\b{character}\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                # Check if this is part of a citation we already found
                if self._is_part_of_citation(match.start(), citations + readings):
                    continue

                # Get context
                context_before, context_after = self._get_context(text, match.start())

                # Disambiguate (check if it's really a biblical reference)
                if not self._is_biblical_context(character, context_before, context_after):
                    continue

                # This is a mention
                ref = BiblicalReference(
                    text=match.group(),
                    book=character,  # Character name as "book"
                    chapter=None,
                    verse_start=None,
                    verse_end=None,
                    reference_type='mention',
                    position=match.start(),
                    context_before=context_before,
                    context_after=context_after,
                    confidence=0.7
                )
                mentions.append(ref)

        # Deduplicate overlapping references
        citations = self._deduplicate_references(citations)
        readings = self._deduplicate_references(readings)
        mentions = self._deduplicate_references(mentions)

        return {
            'citations': citations,
            'readings': readings,
            'mentions': mentions,
            'total_count': len(citations) + len(readings) + len(mentions),
            'citacao_count': len(citations),
            'leitura_count': len(readings),
            'mencao_count': len(mentions)
        }

    def _extract_full_reference(
        self,
        text: str,
        match: re.Match,
        canonical_name: str
    ) -> Optional[BiblicalReference]:
        """Extract full reference including chapter and verse numbers"""
        position = match.start()

        # Look ahead for chapter:verse pattern
        lookahead = text[match.end():match.end() + 20]

        # Pattern: Book Chapter:Verse or Book Chapter:Verse-EndVerse
        verse_pattern = r'\s*(\d+)(?::(\d+))?(?:-(\d+))?'
        verse_match = re.match(verse_pattern, lookahead)

        if not verse_match:
            # No chapter/verse found, this might be just a mention
            return None

        chapter = int(verse_match.group(1))
        verse_start = int(verse_match.group(2)) if verse_match.group(2) else None
        verse_end = int(verse_match.group(3)) if verse_match.group(3) else verse_start

        # Get context
        context_before, context_after = self._get_context(text, position)

        # Full matched text
        full_text = text[position:match.end() + verse_match.end()]

        return BiblicalReference(
            text=full_text,
            book=canonical_name,
            chapter=chapter,
            verse_start=verse_start,
            verse_end=verse_end,
            reference_type='citation',  # Will be reclassified
            position=position,
            context_before=context_before,
            context_after=context_after,
            confidence=0.95
        )

    def _classify_reference(self, text: str, ref: BiblicalReference) -> str:
        """
        Classify a reference as citation or reading based on context

        Args:
            text: Full text
            ref: Biblical reference to classify

        Returns:
            'citation' or 'reading'
        """
        context = ref.context_before + ' ' + ref.context_after

        # Check for reading indicators
        if self.reading_pattern.search(context):
            return 'reading'

        # Check for quotation marks nearby
        nearby_text = text[max(0, ref.position - 50):ref.position + len(ref.text) + 50]
        if '"' in nearby_text or '"' in nearby_text or '"' in nearby_text:
            return 'reading'

        # Default to citation
        return 'citation'

    def _get_context(self, text: str, position: int) -> Tuple[str, str]:
        """
        Get context window around a position

        Args:
            text: Full text
            position: Character position

        Returns:
            (context_before, context_after) tuple of 30 words each
        """
        # Get words before
        before_text = text[:position]
        words_before = before_text.split()[-self.CONTEXT_WINDOW:]
        context_before = ' '.join(words_before)

        # Get words after
        after_text = text[position:]
        words_after = after_text.split()[:self.CONTEXT_WINDOW]
        context_after = ' '.join(words_after)

        return context_before, context_after

    def _is_biblical_context(
        self,
        term: str,
        context_before: str,
        context_after: str
    ) -> bool:
        """
        Determine if a term is used in biblical context (disambiguation)

        Args:
            term: The term to check (e.g., "Jó")
            context_before: Words before the term
            context_after: Words after the term

        Returns:
            True if biblical context, False if likely a common word
        """
        term_lower = term.lower()

        # Check if term has disambiguation rules
        if term_lower in self.DISAMBIGUATION_COMMON_WORDS:
            common_words = self.DISAMBIGUATION_COMMON_WORDS[term_lower]
            context = (context_before + ' ' + context_after).lower()

            # If any common word indicator is present, it's not biblical
            for common in common_words:
                if common in context:
                    return False

        # Check for biblical context indicators
        context = context_before + ' ' + context_after
        biblical_indicators = [
            'bíblia', 'escritura', 'livro', 'capítulo', 'versículo',
            'profeta', 'apóstolo', 'discípulo', 'rei', 'patriarca',
            'testamento', 'evangelho', 'carta', 'epístola'
        ]

        for indicator in biblical_indicators:
            if indicator in context.lower():
                return True

        # Default to biblical if we're uncertain
        return True

    def _is_part_of_citation(
        self,
        position: int,
        citations: List[BiblicalReference]
    ) -> bool:
        """Check if a position is part of an existing citation"""
        for citation in citations:
            if (position >= citation.position and
                position <= citation.position + len(citation.text)):
                return True
        return False

    def _deduplicate_references(
        self,
        references: List[BiblicalReference]
    ) -> List[BiblicalReference]:
        """Remove duplicate or overlapping references"""
        if not references:
            return []

        # Sort by position
        sorted_refs = sorted(references, key=lambda r: r.position)

        # Remove overlaps
        deduplicated = [sorted_refs[0]]
        for ref in sorted_refs[1:]:
            last_ref = deduplicated[-1]

            # Check if overlapping
            if ref.position > last_ref.position + len(last_ref.text):
                deduplicated.append(ref)
            else:
                # Keep the one with higher confidence
                if ref.confidence > last_ref.confidence:
                    deduplicated[-1] = ref

        return deduplicated
