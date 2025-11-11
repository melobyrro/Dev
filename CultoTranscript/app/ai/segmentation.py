"""
Intelligent Text Segmentation
Non-overlapping segments with natural boundary detection
"""
import re
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class TextSegmenter:
    """
    Segments text into non-overlapping chunks at natural boundaries

    Features:
    - Finds natural breakpoints (paragraphs, sentences, clauses)
    - Maintains target segment size with flexible boundaries
    - Adds minimal context markers for continuity
    - No overlap between segments (eliminates redundancy)
    """

    def __init__(
        self,
        target_words: int = 250,
        min_words: int = 150,
        max_words: int = 350
    ):
        """
        Initialize segmenter

        Args:
            target_words: Target segment size in words
            min_words: Minimum acceptable segment size
            max_words: Maximum acceptable segment size
        """
        self.target_words = target_words
        self.min_words = min_words
        self.max_words = max_words

        # Boundary patterns (in priority order)
        self.paragraph_pattern = re.compile(r'\n\n+')
        self.sentence_pattern = re.compile(r'[.!?]\s+')
        self.clause_pattern = re.compile(r'[,;:]\s+')

    def segment_text(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Segment text into non-overlapping chunks

        Args:
            text: Input text to segment

        Returns:
            List of (segment_text, start_word_pos, end_word_pos) tuples
        """
        if not text or not text.strip():
            return []

        words = text.split()
        total_words = len(words)

        if total_words <= self.target_words:
            # Text is small enough for single segment
            return [(text, 0, total_words)]

        # Find natural boundaries
        boundaries = self._find_boundaries(text, words)

        # Create segments at boundaries
        segments = self._create_segments_at_boundaries(text, words, boundaries)

        logger.info(
            f"Segmented {total_words} words into {len(segments)} non-overlapping segments "
            f"(avg size: {total_words / len(segments):.0f} words)"
        )

        return segments

    def _find_boundaries(self, text: str, words: List[str]) -> List[int]:
        """
        Find natural text boundaries with word positions

        Args:
            text: Original text
            words: List of words

        Returns:
            List of word positions representing boundaries
        """
        boundaries = []

        # Build word position map (character position -> word index)
        word_positions = {}
        char_pos = 0
        for word_idx, word in enumerate(words):
            # Find word in text starting from char_pos
            word_start = text.find(word, char_pos)
            if word_start >= 0:
                word_positions[word_start] = word_idx
                char_pos = word_start + len(word)

        # Find paragraph boundaries (highest priority)
        for match in self.paragraph_pattern.finditer(text):
            char_pos = match.end()
            word_idx = self._char_to_word_position(char_pos, word_positions)
            if word_idx is not None:
                boundaries.append(('paragraph', word_idx, char_pos))

        # Find sentence boundaries
        for match in self.sentence_pattern.finditer(text):
            char_pos = match.end()
            word_idx = self._char_to_word_position(char_pos, word_positions)
            if word_idx is not None:
                boundaries.append(('sentence', word_idx, char_pos))

        # Find clause boundaries
        for match in self.clause_pattern.finditer(text):
            char_pos = match.end()
            word_idx = self._char_to_word_position(char_pos, word_positions)
            if word_idx is not None:
                boundaries.append(('clause', word_idx, char_pos))

        # Sort by position
        boundaries.sort(key=lambda x: x[1])

        return boundaries

    def _char_to_word_position(
        self,
        char_pos: int,
        word_positions: dict
    ) -> int:
        """
        Convert character position to word index

        Args:
            char_pos: Character position in text
            word_positions: Map of character positions to word indices

        Returns:
            Word index or None
        """
        # Find closest word position at or before char_pos
        valid_positions = [pos for pos in word_positions.keys() if pos <= char_pos]
        if valid_positions:
            closest_char_pos = max(valid_positions)
            return word_positions[closest_char_pos]
        return None

    def _create_segments_at_boundaries(
        self,
        text: str,
        words: List[str],
        boundaries: List[Tuple[str, int, int]]
    ) -> List[Tuple[str, int, int]]:
        """
        Create segments by selecting best boundaries

        Strategy:
        1. Start at position 0
        2. Look for best boundary near target_words
        3. Prefer: paragraph > sentence > clause
        4. Ensure segments are within min_words and max_words
        5. Add context markers between segments

        Args:
            text: Original text
            words: List of words
            boundaries: List of (type, word_pos, char_pos) tuples

        Returns:
            List of (segment_text, start_pos, end_pos) tuples
        """
        segments = []
        current_start = 0
        total_words = len(words)

        while current_start < total_words:
            # Calculate ideal end position
            ideal_end = current_start + self.target_words

            if ideal_end >= total_words:
                # Last segment - take remaining words
                segment_words = words[current_start:]
                segment_text = ' '.join(segment_words)
                segments.append((segment_text, current_start, total_words))
                break

            # Find best boundary near ideal position
            best_boundary = self._find_best_boundary(
                boundaries,
                current_start,
                ideal_end,
                total_words
            )

            if best_boundary:
                boundary_type, boundary_pos, _ = best_boundary
                segment_words = words[current_start:boundary_pos]
                segment_text = ' '.join(segment_words)

                # Add context marker for non-first segments
                if current_start > 0:
                    segment_text = "[...continuação] " + segment_text

                segments.append((segment_text, current_start, boundary_pos))
                current_start = boundary_pos

                logger.debug(
                    f"Segment at {boundary_type} boundary: "
                    f"words {current_start}-{boundary_pos} "
                    f"(size: {boundary_pos - current_start})"
                )
            else:
                # No good boundary found - split at ideal position
                segment_words = words[current_start:ideal_end]
                segment_text = ' '.join(segment_words)

                if current_start > 0:
                    segment_text = "[...continuação] " + segment_text

                segments.append((segment_text, current_start, ideal_end))
                current_start = ideal_end

                logger.debug(
                    f"Segment at word boundary: "
                    f"words {current_start}-{ideal_end} "
                    f"(size: {ideal_end - current_start})"
                )

        return segments

    def _find_best_boundary(
        self,
        boundaries: List[Tuple[str, int, int]],
        start_pos: int,
        ideal_end: int,
        total_words: int
    ) -> Tuple[str, int, int]:
        """
        Find the best boundary near the ideal end position

        Priority:
        1. Paragraph boundary within acceptable range
        2. Sentence boundary within acceptable range
        3. Clause boundary within acceptable range
        4. None (will split at word boundary)

        Args:
            boundaries: List of all boundaries
            start_pos: Current segment start position
            ideal_end: Ideal end position
            total_words: Total words in text

        Returns:
            Best boundary tuple or None
        """
        # Filter boundaries in acceptable range
        min_end = start_pos + self.min_words
        max_end = min(start_pos + self.max_words, total_words)

        candidates = [
            b for b in boundaries
            if min_end <= b[1] <= max_end
        ]

        if not candidates:
            return None

        # Prioritize by boundary type and distance from ideal
        priority_map = {'paragraph': 3, 'sentence': 2, 'clause': 1}

        def score_boundary(boundary):
            boundary_type, boundary_pos, _ = boundary
            priority = priority_map.get(boundary_type, 0)
            distance = abs(boundary_pos - ideal_end)
            # Higher priority, lower distance = better score
            return (priority, -distance)

        best_boundary = max(candidates, key=score_boundary)
        return best_boundary


def get_text_segmenter(
    target_words: int = 250,
    min_words: int = 150,
    max_words: int = 350
) -> TextSegmenter:
    """
    Get a text segmenter instance

    Args:
        target_words: Target segment size
        min_words: Minimum segment size
        max_words: Maximum segment size

    Returns:
        TextSegmenter instance
    """
    return TextSegmenter(
        target_words=target_words,
        min_words=min_words,
        max_words=max_words
    )
