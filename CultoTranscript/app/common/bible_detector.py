"""
Bible reference detector for Portuguese transcripts
Detects references like "João 3:16", "1 Coríntios 13", "Gênesis 1:1-3"
"""
import re
import logging
from typing import List, Dict, Tuple
from collections import defaultdict

from app.common.bible_pt import BIBLE_BOOKS_PT, get_canonical_book_name, is_valid_book

logger = logging.getLogger(__name__)


class BibleReferenceDetector:
    """Detector for Bible verse references in Portuguese text"""

    def __init__(self):
        # Build regex pattern from all book variants
        all_variants = []
        for variants in BIBLE_BOOKS_PT.values():
            all_variants.extend(variants)

        # Sort by length (longest first) to match "1 Coríntios" before "1"
        all_variants.sort(key=len, reverse=True)

        # Escape special regex characters
        escaped_variants = [re.escape(v) for v in all_variants]

        # Build pattern: "Book Chapter:Verse" or "Book Chapter:Verse-Verse" or just "Book Chapter"
        # Examples: "João 3:16", "1 Coríntios 13:1-13", "Gênesis 1"
        book_pattern = f"({'|'.join(escaped_variants)})"

        self.pattern = re.compile(
            rf'\b{book_pattern}\s+'  # Book name with word boundary
            r'(\d+)'  # Chapter number
            r'(?::(\d+))?'  # Optional :verse
            r'(?:-(\d+))?'  # Optional -endverse
            r'\b',
            re.IGNORECASE
        )

    def detect_references(self, text: str) -> List[Dict]:
        """
        Detect all Bible references in text

        Args:
            text: Transcript or sermon text

        Returns:
            List of dicts with keys: book, chapter, verse, end_verse, raw_match
        """
        matches = []

        for match in self.pattern.finditer(text):
            book_variant = match.group(1)
            chapter = int(match.group(2))
            verse = int(match.group(3)) if match.group(3) else None
            end_verse = int(match.group(4)) if match.group(4) else None

            canonical_book = get_canonical_book_name(book_variant)

            matches.append({
                "book": canonical_book,
                "chapter": chapter,
                "verse": verse,
                "end_verse": end_verse,
                "raw_match": match.group(0)
            })

        logger.info(f"Detected {len(matches)} Bible references in text")
        return matches

    def aggregate_references(self, references: List[Dict]) -> Dict:
        """
        Aggregate references by book and count frequency

        Args:
            references: List of reference dicts from detect_references()

        Returns:
            dict with aggregation stats
        """
        book_counts = defaultdict(int)
        chapter_counts = defaultdict(int)
        verse_counts = defaultdict(int)

        for ref in references:
            book = ref["book"]
            chapter = ref["chapter"]
            verse = ref["verse"]

            book_counts[book] += 1

            if verse:
                chapter_key = f"{book} {chapter}"
                chapter_counts[chapter_key] += 1

                verse_key = f"{book} {chapter}:{verse}"
                verse_counts[verse_key] += 1

        # Sort by frequency
        top_books = sorted(book_counts.items(), key=lambda x: x[1], reverse=True)
        top_chapters = sorted(chapter_counts.items(), key=lambda x: x[1], reverse=True)
        top_verses = sorted(verse_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_references": len(references),
            "unique_books": len(book_counts),
            "top_books": top_books[:10],
            "top_chapters": top_chapters[:10],
            "top_verses": top_verses[:10],
            "book_counts": dict(book_counts),
            "chapter_counts": dict(chapter_counts),
            "verse_counts": dict(verse_counts)
        }

    def extract_verses_for_db(self, references: List[Dict]) -> List[Tuple]:
        """
        Extract verse data ready for database insertion

        Args:
            references: List of reference dicts

        Returns:
            List of tuples: (book, chapter, verse, count)
        """
        verse_freq = defaultdict(int)

        for ref in references:
            book = ref["book"]
            chapter = ref["chapter"]
            verse = ref.get("verse")

            key = (book, chapter, verse)
            verse_freq[key] += 1

        return [(book, chapter, verse, count) for (book, chapter, verse), count in verse_freq.items()]


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    detector = BibleReferenceDetector()

    # Sample sermon text in Portuguese
    text = """
    Hoje vamos falar sobre o amor. Vamos ler em 1 Coríntios 13:4-7.
    Também vemos em João 3:16 que Deus amou o mundo.
    Voltando ao Antigo Testamento, Gênesis 1:1 nos diz "No princípio...".
    E não podemos esquecer de Salmos 23 e Provérbios 3:5-6.
    """

    refs = detector.detect_references(text)
    print(f"\nFound {len(refs)} references:")
    for ref in refs:
        print(f"  - {ref}")

    agg = detector.aggregate_references(refs)
    print(f"\nAggregation:")
    print(f"  Total references: {agg['total_references']}")
    print(f"  Unique books: {agg['unique_books']}")
    print(f"  Top books: {agg['top_books']}")
    print(f"  Top verses: {agg['top_verses']}")
