"""
Theme tagger for Portuguese sermon transcripts
Tags sermons with themes based on keyword matching
"""
import json
import os
import re
import logging
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to themes dictionary
THEMES_DICT_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'analytics', 'dictionaries', 'themes_pt.json'
)


class ThemeTagger:
    """Tagger for identifying sermon themes based on keywords"""

    def __init__(self, dict_path: str = THEMES_DICT_PATH):
        """
        Initialize theme tagger

        Args:
            dict_path: Path to themes dictionary JSON file
        """
        self.themes = self._load_themes(dict_path)
        logger.info(f"Loaded {len(self.themes)} themes from dictionary")

    def _load_themes(self, dict_path: str) -> Dict:
        """Load themes dictionary from JSON file"""
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Themes dictionary not found: {dict_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in themes dictionary: {e}")
            return {}

    def tag_text(self, text: str, min_score: float = 1.0) -> List[Tuple[str, float]]:
        """
        Tag text with themes based on keyword matching

        Args:
            text: Transcript or sermon text
            min_score: Minimum score threshold to include a theme

        Returns:
            List of tuples (theme_name, score) sorted by score descending
        """
        if not text or not self.themes:
            return []

        # Normalize text for matching (lowercase, preserve accents)
        text_lower = text.lower()

        theme_scores = {}

        for theme_name, theme_data in self.themes.items():
            keywords = theme_data.get("keywords", [])
            weight = theme_data.get("weight", 1.0)

            # Count keyword occurrences
            matches = 0
            for keyword in keywords:
                keyword_lower = keyword.lower()

                # Use word boundaries to avoid partial matches
                # Example: "Cristo" should match "Cristo" but not "Cristo" in "cristão"
                pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                count = len(re.findall(pattern, text_lower))

                matches += count

            if matches > 0:
                # Calculate score: (matches * weight)
                # Can normalize by text length if needed
                score = matches * weight
                theme_scores[theme_name] = score

        # Filter by min_score and sort by score descending
        filtered = [(theme, score) for theme, score in theme_scores.items() if score >= min_score]
        filtered.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"Tagged text with {len(filtered)} themes")
        return filtered

    def tag_with_details(self, text: str, min_score: float = 1.0) -> Dict:
        """
        Tag text and return detailed information

        Args:
            text: Transcript or sermon text
            min_score: Minimum score threshold

        Returns:
            dict with theme tags and metadata
        """
        tags = self.tag_text(text, min_score)

        return {
            "themes": [{"tag": tag, "score": score} for tag, score in tags],
            "theme_count": len(tags),
            "primary_theme": tags[0][0] if tags else None,
            "is_multi_theme": len(tags) > 1
        }

    def get_theme_description(self, theme_name: str) -> str:
        """Get description for a theme"""
        theme_data = self.themes.get(theme_name, {})
        return theme_data.get("description", "")


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    tagger = ThemeTagger()

    # Sample sermon text in Portuguese
    text = """
    Hoje vamos falar sobre Jesus Cristo, nosso Salvador.
    Ele morreu na cruz por nossos pecados e ressuscitou ao terceiro dia.
    A graça de Deus é suficiente para nos salvar.
    Em Cristo Jesus temos a redenção pelo seu sangue.
    A santidade é importante, devemos viver em pureza e consagração.
    Precisamos nos arrepender de nossos pecados e buscar a Deus em oração.
    """

    result = tagger.tag_with_details(text)

    print(f"\nTheme tagging results:")
    print(f"  Primary theme: {result['primary_theme']}")
    print(f"  Total themes: {result['theme_count']}")
    print(f"  All themes:")
    for theme_data in result['themes']:
        tag = theme_data['tag']
        score = theme_data['score']
        desc = tagger.get_theme_description(tag)
        print(f"    - {tag}: {score:.1f} - {desc}")
