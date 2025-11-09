"""
Biblical Reference Parser
Detects and parses biblical references from Portuguese queries
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class BiblicalReferenceResult:
    """Result of biblical reference parsing"""
    found: bool
    book: Optional[str] = None
    chapter: Optional[int] = None
    verse_start: Optional[int] = None
    verse_end: Optional[int] = None
    osis_ref: Optional[str] = None
    raw_text: Optional[str] = None
    is_whole_book: bool = False
    is_whole_chapter: bool = False


# OSIS book codes mapping (all 66 biblical books)
BOOK_TO_OSIS = {
    # Old Testament
    "gênesis": "Gen",
    "genesis": "Gen",
    "êxodo": "Exod",
    "exodo": "Exod",
    "levítico": "Lev",
    "levitico": "Lev",
    "números": "Num",
    "numeros": "Num",
    "deuteronômio": "Deut",
    "deuteronomio": "Deut",
    "josué": "Josh",
    "josue": "Josh",
    "juízes": "Judg",
    "juizes": "Judg",
    "rute": "Ruth",
    "1 samuel": "1Sam",
    "2 samuel": "2Sam",
    "1 reis": "1Kgs",
    "2 reis": "2Kgs",
    "1 crônicas": "1Chr",
    "1 cronicas": "1Chr",
    "2 crônicas": "2Chr",
    "2 cronicas": "2Chr",
    "esdras": "Ezra",
    "neemias": "Neh",
    "ester": "Esth",
    "jó": "Job",
    "jo": "Job",  # Short form
    "salmos": "Ps",
    "salmo": "Ps",
    "provérbios": "Prov",
    "proverbios": "Prov",
    "eclesiastes": "Eccl",
    "cânticos": "Song",
    "canticos": "Song",
    "cantares": "Song",
    "isaías": "Isa",
    "isaias": "Isa",
    "jeremias": "Jer",
    "lamentações": "Lam",
    "lamentacoes": "Lam",
    "ezequiel": "Ezek",
    "daniel": "Dan",
    "oséias": "Hos",
    "oseias": "Hos",
    "joel": "Joel",
    "amós": "Amos",
    "amos": "Amos",
    "obadias": "Obad",
    "jonas": "Jonah",
    "miquéias": "Mic",
    "miqueias": "Mic",
    "naum": "Nah",
    "habacuque": "Hab",
    "sofonias": "Zeph",
    "ageu": "Hag",
    "zacarias": "Zech",
    "malaquias": "Mal",

    # New Testament
    "mateus": "Matt",
    "marcos": "Mark",
    "lucas": "Luke",
    "joão": "John",
    "joao": "John",
    "atos": "Acts",
    "romanos": "Rom",
    "1 coríntios": "1Cor",
    "1 corintios": "1Cor",
    "2 coríntios": "2Cor",
    "2 corintios": "2Cor",
    "gálatas": "Gal",
    "galatas": "Gal",
    "efésios": "Eph",
    "efesios": "Eph",
    "filipenses": "Phil",
    "colossenses": "Col",
    "1 tessalonicenses": "1Thess",
    "2 tessalonicenses": "2Thess",
    "1 timóteo": "1Tim",
    "1 timoteo": "1Tim",
    "2 timóteo": "2Tim",
    "2 timoteo": "2Tim",
    "tito": "Titus",
    "filemom": "Phlm",
    "hebreus": "Heb",
    "tiago": "Jas",
    "1 pedro": "1Pet",
    "2 pedro": "2Pet",
    "1 joão": "1John",
    "1 joao": "1John",
    "2 joão": "2John",
    "2 joao": "2John",
    "3 joão": "3John",
    "3 joao": "3John",
    "judas": "Jude",
    "apocalipse": "Rev",
}

# Common abbreviations
ABBREVIATIONS = {
    "gn": "gênesis",
    "ex": "êxodo",
    "lv": "levítico",
    "nm": "números",
    "dt": "deuteronômio",
    "js": "josué",
    "jz": "juízes",
    "rt": "rute",
    "1sm": "1 samuel",
    "2sm": "2 samuel",
    "1rs": "1 reis",
    "2rs": "2 reis",
    "1cr": "1 crônicas",
    "2cr": "2 crônicas",
    "ed": "esdras",
    "ne": "neemias",
    "et": "ester",
    "sl": "salmos",
    "pv": "provérbios",
    "ec": "eclesiastes",
    "ct": "cânticos",
    "is": "isaías",
    "jr": "jeremias",
    "lm": "lamentações",
    "ez": "ezequiel",
    "dn": "daniel",
    "os": "oséias",
    "jl": "joel",
    "am": "amós",
    "ob": "obadias",
    "jn": "jonas",
    "mq": "miquéias",
    "na": "naum",
    "hc": "habacuque",
    "sf": "sofonias",
    "ag": "ageu",
    "zc": "zacarias",
    "ml": "malaquias",
    "mt": "mateus",
    "mc": "marcos",
    "lc": "lucas",
    "jo": "joão",
    "at": "atos",
    "rm": "romanos",
    "1co": "1 coríntios",
    "2co": "2 coríntios",
    "gl": "gálatas",
    "ef": "efésios",
    "fp": "filipenses",
    "cl": "colossenses",
    "1ts": "1 tessalonicenses",
    "2ts": "2 tessalonicenses",
    "1tm": "1 timóteo",
    "2tm": "2 timóteo",
    "tt": "tito",
    "fm": "filemom",
    "hb": "hebreus",
    "tg": "tiago",
    "1pe": "1 pedro",
    "2pe": "2 pedro",
    "1jo": "1 joão",
    "2jo": "2 joão",
    "3jo": "3 joão",
    "jd": "judas",
    "ap": "apocalipse",
}


class BiblicalReferenceParser:
    """
    Parses biblical references from Portuguese text

    Supports:
    - Full book names: "João 3:16"
    - Abbreviations: "Jo. 3:16", "Rm. 8"
    - Chapter only: "Romanos 8"
    - Verse ranges: "Gênesis 1:1-3"
    - Whole books: "Salmos"
    - Numbered books: "1 Coríntios 13"
    """

    def __init__(self):
        """Initialize parser"""
        logger.info("Biblical reference parser initialized with 66 books")

    def extract_reference(self, query: str) -> BiblicalReferenceResult:
        """
        Extract biblical reference from query

        Args:
            query: Search query text

        Returns:
            BiblicalReferenceResult with parsed details
        """
        # Normalize query
        normalized = self._normalize_text(query)

        # Pattern 1: Book Chapter:Verse-Verse (e.g., "João 3:16-18")
        pattern1 = r'\b([123]?\s*[a-záàâãéêíóôõúç]+)\s+(\d+):(\d+)(?:-(\d+))?\b'
        match = re.search(pattern1, normalized, re.IGNORECASE)

        if match:
            book_name = match.group(1).strip()
            chapter = int(match.group(2))
            verse_start = int(match.group(3))
            verse_end = int(match.group(4)) if match.group(4) else verse_start

            book = self._resolve_book(book_name)
            if book:
                osis_ref = self._build_osis_ref(book, chapter, verse_start, verse_end)
                logger.info(f"📖 Biblical reference detected: {book} {chapter}:{verse_start}-{verse_end} (OSIS: {osis_ref})")
                return BiblicalReferenceResult(
                    found=True,
                    book=book,
                    chapter=chapter,
                    verse_start=verse_start,
                    verse_end=verse_end,
                    osis_ref=osis_ref,
                    raw_text=match.group(0),
                    is_whole_book=False,
                    is_whole_chapter=False
                )

        # Pattern 2: Book Chapter (e.g., "Romanos 8")
        pattern2 = r'\b([123]?\s*[a-záàâãéêíóôõúç]+)\s+(\d+)\b'
        match = re.search(pattern2, normalized, re.IGNORECASE)

        if match:
            book_name = match.group(1).strip()
            chapter = int(match.group(2))

            book = self._resolve_book(book_name)
            if book:
                osis_ref = self._build_osis_ref(book, chapter)
                logger.info(f"📖 Biblical reference detected: {book} {chapter} (whole chapter, OSIS: {osis_ref})")
                return BiblicalReferenceResult(
                    found=True,
                    book=book,
                    chapter=chapter,
                    osis_ref=osis_ref,
                    raw_text=match.group(0),
                    is_whole_book=False,
                    is_whole_chapter=True
                )

        # Pattern 3: Book only (e.g., "Salmos")
        pattern3 = r'\b([123]?\s*[a-záàâãéêíóôõúç]+)\b'
        match = re.search(pattern3, normalized, re.IGNORECASE)

        if match:
            book_name = match.group(1).strip()
            book = self._resolve_book(book_name)

            if book:
                osis_ref = self._build_osis_ref(book)
                logger.info(f"📖 Biblical reference detected: {book} (whole book, OSIS: {osis_ref})")
                return BiblicalReferenceResult(
                    found=True,
                    book=book,
                    osis_ref=osis_ref,
                    raw_text=match.group(0),
                    is_whole_book=True,
                    is_whole_chapter=False
                )

        return BiblicalReferenceResult(found=False)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for parsing"""
        # Remove common noise words
        text = re.sub(r'\b(sobre|citaram|mencionaram|falado|pregações|sermões|leituras)\b', '', text, flags=re.IGNORECASE)
        # Remove punctuation except colons and hyphens
        text = re.sub(r'[^\w\s:áàâãéêíóôõúç-]', ' ', text)
        # Normalize spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _resolve_book(self, book_name: str) -> Optional[str]:
        """
        Resolve book name to OSIS code

        Args:
            book_name: Portuguese book name or abbreviation

        Returns:
            OSIS book code or None
        """
        # Normalize
        normalized = book_name.lower().strip()

        # Handle abbreviations with period (e.g., "Jo.")
        normalized = normalized.rstrip('.')

        # Try abbreviations first
        if normalized in ABBREVIATIONS:
            full_name = ABBREVIATIONS[normalized]
            osis = BOOK_TO_OSIS.get(full_name)
            if osis:
                return osis

        # Try direct lookup
        if normalized in BOOK_TO_OSIS:
            return BOOK_TO_OSIS[normalized]

        # Try fuzzy matching for common variants
        # Handle "1 João" vs "1João" vs "1jo"
        normalized_no_space = re.sub(r'\s+', '', normalized)
        for book, osis in BOOK_TO_OSIS.items():
            if re.sub(r'\s+', '', book) == normalized_no_space:
                return osis

        return None

    def _build_osis_ref(
        self,
        book: str,
        chapter: Optional[int] = None,
        verse_start: Optional[int] = None,
        verse_end: Optional[int] = None
    ) -> str:
        """
        Build OSIS reference string

        Args:
            book: OSIS book code
            chapter: Chapter number
            verse_start: Start verse
            verse_end: End verse

        Returns:
            OSIS reference string
        """
        if not chapter:
            return book

        if not verse_start:
            return f"{book}.{chapter}"

        if verse_end and verse_end != verse_start:
            return f"{book}.{chapter}.{verse_start}-{book}.{chapter}.{verse_end}"

        return f"{book}.{chapter}.{verse_start}"


def get_biblical_reference_parser() -> BiblicalReferenceParser:
    """Get singleton biblical reference parser instance"""
    if not hasattr(get_biblical_reference_parser, '_instance'):
        get_biblical_reference_parser._instance = BiblicalReferenceParser()
    return get_biblical_reference_parser._instance
