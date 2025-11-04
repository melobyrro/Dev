"""
Biblical Passage Analyzer
Converts references to OSIS standard and extracts timestamps
"""
import re
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# OSIS book abbreviations mapping (Portuguese to OSIS)
OSIS_BOOK_MAP = {
    # Old Testament
    'Gênesis': 'Gen', 'Êxodo': 'Exod', 'Levítico': 'Lev', 'Números': 'Num',
    'Deuteronômio': 'Deut', 'Josué': 'Josh', 'Juízes': 'Judg', 'Rute': 'Ruth',
    '1 Samuel': '1Sam', '2 Samuel': '2Sam', '1 Reis': '1Kgs', '2 Reis': '2Kgs',
    '1 Crônicas': '1Chr', '2 Crônicas': '2Chr', 'Esdras': 'Ezra', 'Neemias': 'Neh',
    'Ester': 'Esth', 'Jó': 'Job', 'Salmos': 'Ps', 'Provérbios': 'Prov',
    'Eclesiastes': 'Eccl', 'Cânticos': 'Song', 'Isaías': 'Isa', 'Jeremias': 'Jer',
    'Lamentações': 'Lam', 'Ezequiel': 'Ezek', 'Daniel': 'Dan', 'Oséias': 'Hos',
    'Joel': 'Joel', 'Amós': 'Amos', 'Obadias': 'Obad', 'Jonas': 'Jonah',
    'Miquéias': 'Mic', 'Naum': 'Nah', 'Habacuque': 'Hab', 'Sofonias': 'Zeph',
    'Ageu': 'Hag', 'Zacarias': 'Zech', 'Malaquias': 'Mal',

    # New Testament
    'Mateus': 'Matt', 'Marcos': 'Mark', 'Lucas': 'Luke', 'João': 'John',
    'Atos': 'Acts', 'Romanos': 'Rom', '1 Coríntios': '1Cor', '2 Coríntios': '2Cor',
    'Gálatas': 'Gal', 'Efésios': 'Eph', 'Filipenses': 'Phil', 'Colossenses': 'Col',
    '1 Tessalonicenses': '1Thess', '2 Tessalonicenses': '2Thess',
    '1 Timóteo': '1Tim', '2 Timóteo': '2Tim', 'Tito': 'Titus', 'Filemom': 'Phlm',
    'Hebreus': 'Heb', 'Tiago': 'Jas', '1 Pedro': '1Pet', '2 Pedro': '2Pet',
    '1 João': '1John', '2 João': '2John', '3 João': '3John', 'Judas': 'Jude',
    'Apocalipse': 'Rev'
}


@dataclass
class ParsedPassage:
    """Represents a parsed biblical passage with OSIS reference"""
    book: str  # Canonical Portuguese name
    osis_book: str  # OSIS abbreviation
    chapter: Optional[int]
    verse_start: Optional[int]
    verse_end: Optional[int]
    osis_ref: str  # Full OSIS reference (e.g., "Ps.23.1-6")
    start_timestamp: Optional[int] = None  # Seconds
    end_timestamp: Optional[int] = None  # Seconds
    application_note: Optional[str] = None


class PassageAnalyzer:
    """
    Analyzes biblical passages and converts to OSIS standard

    Features:
    - Converts Portuguese book names to OSIS abbreviations
    - Generates OSIS references (e.g., "Ps.23.1-6")
    - Extracts timestamps from transcripts (future enhancement)
    - Validates chapter/verse numbers
    """

    # Maximum chapters per book (for validation)
    MAX_CHAPTERS = {
        'Gen': 50, 'Exod': 40, 'Lev': 27, 'Num': 36, 'Deut': 34,
        'Josh': 24, 'Judg': 21, 'Ruth': 4, '1Sam': 31, '2Sam': 24,
        '1Kgs': 22, '2Kgs': 25, '1Chr': 29, '2Chr': 36, 'Ezra': 10,
        'Neh': 13, 'Esth': 10, 'Job': 42, 'Ps': 150, 'Prov': 31,
        'Eccl': 12, 'Song': 8, 'Isa': 66, 'Jer': 52, 'Lam': 5,
        'Ezek': 48, 'Dan': 12, 'Hos': 14, 'Joel': 3, 'Amos': 9,
        'Obad': 1, 'Jonah': 4, 'Mic': 7, 'Nah': 3, 'Hab': 3,
        'Zeph': 3, 'Hag': 2, 'Zech': 14, 'Mal': 4,
        'Matt': 28, 'Mark': 16, 'Luke': 24, 'John': 21, 'Acts': 28,
        'Rom': 16, '1Cor': 16, '2Cor': 13, 'Gal': 6, 'Eph': 6,
        'Phil': 4, 'Col': 4, '1Thess': 5, '2Thess': 3, '1Tim': 6,
        '2Tim': 4, 'Titus': 3, 'Phlm': 1, 'Heb': 13, 'Jas': 5,
        '1Pet': 5, '2Pet': 3, '1John': 5, '2John': 1, '3John': 1,
        'Jude': 1, 'Rev': 22
    }

    def __init__(self):
        """Initialize passage analyzer"""
        logger.info("Passage analyzer initialized")

    def to_osis(
        self,
        book: str,
        chapter: Optional[int],
        verse_start: Optional[int] = None,
        verse_end: Optional[int] = None
    ) -> ParsedPassage:
        """
        Convert biblical reference to OSIS format

        Args:
            book: Portuguese book name
            chapter: Chapter number
            verse_start: Starting verse
            verse_end: Ending verse (for ranges)

        Returns:
            ParsedPassage with OSIS reference

        Examples:
            to_osis("Salmos", 23, 1, 6) -> "Ps.23.1-6"
            to_osis("João", 3, 16) -> "John.3.16"
            to_osis("Gênesis", 1) -> "Gen.1"
        """
        # Get OSIS book abbreviation
        osis_book = OSIS_BOOK_MAP.get(book)
        if not osis_book:
            logger.warning(f"Unknown book for OSIS conversion: {book}")
            # Fallback: use first 3-4 letters
            osis_book = book[:4] if len(book) >= 4 else book

        # Validate chapter number
        if chapter and osis_book in self.MAX_CHAPTERS:
            if chapter > self.MAX_CHAPTERS[osis_book]:
                logger.warning(
                    f"Invalid chapter {chapter} for {book} "
                    f"(max: {self.MAX_CHAPTERS[osis_book]})"
                )

        # Build OSIS reference
        if chapter is None:
            # Book only
            osis_ref = osis_book
        elif verse_start is None:
            # Book and chapter only
            osis_ref = f"{osis_book}.{chapter}"
        elif verse_end and verse_end != verse_start:
            # Verse range
            osis_ref = f"{osis_book}.{chapter}.{verse_start}-{verse_end}"
        else:
            # Single verse
            osis_ref = f"{osis_book}.{chapter}.{verse_start}"

        return ParsedPassage(
            book=book,
            osis_book=osis_book,
            chapter=chapter,
            verse_start=verse_start,
            verse_end=verse_end,
            osis_ref=osis_ref
        )

    def extract_timestamps(
        self,
        transcript_text: str,
        passage_text: str,
        position: int
    ) -> tuple[Optional[int], Optional[int]]:
        """
        Extract approximate timestamps for a passage

        This is a simplified implementation. In a real system, you would:
        1. Use timed transcripts (SRT/VTT format)
        2. Match passage text to transcript segments
        3. Return actual start/end times

        Args:
            transcript_text: Full transcript
            passage_text: The passage reference text
            position: Character position in transcript

        Returns:
            (start_seconds, end_seconds) tuple or (None, None)
        """
        # Simplified: Estimate timestamp based on position
        # Assume average speaking rate of 150 words per minute
        words_before = transcript_text[:position].split()
        words_count = len(words_before)

        # Calculate approximate timestamp
        start_seconds = int((words_count / 150) * 60)

        # Estimate end (add ~5 seconds for reference mention)
        end_seconds = start_seconds + 5

        return start_seconds, end_seconds

    def generate_application_note(
        self,
        passage: ParsedPassage,
        context: str,
        gemini_client=None
    ) -> str:
        """
        Generate a brief application note for how the passage was used

        Args:
            passage: The parsed passage
            context: Surrounding context text
            gemini_client: Optional Gemini client for AI-generated notes

        Returns:
            Brief application note
        """
        if gemini_client:
            # Use AI to generate application note
            try:
                prompt = f"""
Analise brevemente como a seguinte passagem bíblica foi aplicada no sermão:

Passagem: {passage.osis_ref} ({passage.book} {passage.chapter}:{passage.verse_start})
Contexto: {context[:500]}

Gere uma nota de aplicação muito breve (máximo 100 caracteres) explicando como esta passagem foi usada.
Responda APENAS com a nota, sem explicações adicionais.
"""
                note = gemini_client.generate_content(prompt)
                return note.strip()[:100]
            except Exception as e:
                logger.error(f"Error generating application note: {e}")

        # Fallback: Extract key phrases from context
        context_lower = context.lower()

        if any(word in context_lower for word in ['exemplo', 'ilustra', 'mostra']):
            return "Usado como exemplo/ilustração"
        elif any(word in context_lower for word in ['fundamento', 'base', 'ensina']):
            return "Base doutrinária/ensinamento"
        elif any(word in context_lower for word in ['promessa', 'esperança']):
            return "Promessa/esperança"
        elif any(word in context_lower for word in ['advertência', 'alerta', 'cuidado']):
            return "Advertência/alerta"
        else:
            return "Aplicação geral"

    def from_osis(self, osis_ref: str) -> ParsedPassage:
        """
        Parse an OSIS reference back to components

        Args:
            osis_ref: OSIS reference (e.g., "Ps.23.1-6")

        Returns:
            ParsedPassage object
        """
        # Parse OSIS reference
        parts = osis_ref.split('.')

        osis_book = parts[0]
        chapter = int(parts[1]) if len(parts) > 1 else None

        verse_start = None
        verse_end = None
        if len(parts) > 2:
            verse_part = parts[2]
            if '-' in verse_part:
                verse_start, verse_end = map(int, verse_part.split('-'))
            else:
                verse_start = int(verse_part)
                verse_end = verse_start

        # Reverse lookup Portuguese name
        book = next(
            (pt_name for pt_name, osis in OSIS_BOOK_MAP.items() if osis == osis_book),
            osis_book
        )

        return ParsedPassage(
            book=book,
            osis_book=osis_book,
            chapter=chapter,
            verse_start=verse_start,
            verse_end=verse_end,
            osis_ref=osis_ref
        )
