"""
Keyword Matcher Module v2

Matches Reddit posts against signup keywords for ANY tracker.
Supports language filtering for English and Portuguese.
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple

logger = logging.getLogger(__name__)

# Common Portuguese words to detect language
PORTUGUESE_INDICATORS = [
    'convite', 'convites', 'aberto', 'abertos', 'abertas', 'cadastro',
    'registro', 'inscrição', 'inscrições', 'vagas', 'limitado', 'limitadas',
    'apenas', 'somente', 'brasileiro', 'brasil', 'português', 'pt-br',
    'usuários', 'membros', 'acesso', 'liberado', 'disponível'
]

# Common non-English/Portuguese languages to filter out
OTHER_LANGUAGE_INDICATORS = {
    'russian': ['приглашение', 'открыт', 'регистрация', 'раздача'],
    'chinese': ['开放', '注册', '邀请', '限时'],
    'french': ['inscription', 'ouvert', 'limité', 'compte'],
    'german': ['anmeldung', 'offen', 'registrierung', 'einladung'],
    'spanish': ['registro', 'abierto', 'invitación', 'limitado'],
}


class KeywordMatcher:
    """Matches posts against signup keywords with language filtering."""

    def __init__(self, config: Dict):
        """Initialize keyword matcher from config.

        Args:
            config: Full configuration dictionary
        """
        self.detection_mode = config.get('detection_mode', 'all')
        self.signup_keywords = config.get('signup_keywords', [])
        self.close_keywords = [w.lower() for w in config.get('close_keywords', [])]
        self.close_flairs = [f.lower() for f in config.get('close_flairs', ['closed'])]
        self.ignored_trackers = [t.lower() for t in config.get('ignored_trackers', [])]

        # Language config
        lang_config = config.get('language', {})
        self.language_filter_enabled = lang_config.get('enabled', True)
        self.allowed_languages = lang_config.get('allowed', ['english', 'portuguese'])
        self.portuguese_trackers = [t.lower() for t in lang_config.get('portuguese_trackers', [])]

        # Filter config
        filters = config.get('filters', {})
        self.ignore_words = [w.lower() for w in filters.get('ignore_words', [])]
        self.min_score = filters.get('minimum_post_score', 0)

        # Legacy: specific trackers (for backwards compatibility)
        self.specific_trackers = config.get('trackers', [])

        # Compile patterns
        self._compile_patterns()

        logger.info(f"Matcher initialized: mode={self.detection_mode}, "
                   f"{len(self.signup_keywords)} signup keywords, "
                   f"{len(self.close_keywords)} close keywords, "
                   f"{len(self.close_flairs)} close flairs, "
                   f"language_filter={self.language_filter_enabled}")

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        # Signup keyword patterns
        self.signup_patterns = []
        for keyword in self.signup_keywords:
            escaped = re.escape(keyword)
            pattern = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
            self.signup_patterns.append((keyword, pattern))

        # Close keyword patterns
        self.close_patterns = []
        for keyword in self.close_keywords:
            escaped = re.escape(keyword)
            pattern = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
            self.close_patterns.append((keyword, pattern))

        # Ignored tracker patterns
        self.ignored_patterns = []
        for tracker in self.ignored_trackers:
            escaped = re.escape(tracker)
            pattern = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
            self.ignored_patterns.append(pattern)

        # Specific tracker patterns (legacy mode)
        self.tracker_patterns = {}
        for tracker in self.specific_trackers:
            tracker_name = tracker['name']
            patterns = []
            for keyword in tracker.get('keywords', []):
                escaped = re.escape(keyword)
                pattern = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
                patterns.append(pattern)
            self.tracker_patterns[tracker_name] = patterns

    def match_post(self, post: Dict) -> Optional[Tuple[str, str, str]]:
        """Check if a post matches signup or closing criteria.

        Args:
            post: Post dictionary with 'title', 'body', 'score', etc.

        Returns:
            Tuple of (tracker_name, matched_keyword, event_type) if match found, None otherwise
        """
        # Apply score filter first
        if not self._passes_filters(post, check_ignore_words=False):
            return None

        text = f"{post['title']} {post.get('body', '')}".lower()
        title = post['title']

        # Check for ignored trackers
        for pattern in self.ignored_patterns:
            if pattern.search(text):
                logger.debug(f"Post ignored (tracker in ignore list): {title[:50]}")
                return None

        # Language check
        if self.language_filter_enabled:
            language = self._detect_language(text, title)
            if language not in self.allowed_languages:
                logger.debug(f"Post filtered by language ({language}): {title[:50]}")
                return None

        # Closing detection (takes precedence)
        flair = (post.get('flair') or post.get('flair_text') or '').lower()
        if flair and flair in self.close_flairs:
            tracker_name = self._extract_tracker_name(title)
            logger.info(f"CLOSE: '{tracker_name}' - flair '{flair}' in: {title[:60]}")
            return (tracker_name, flair, 'closed')

        close_keyword = self._match_close_keyword(text)
        if close_keyword:
            tracker_name = self._extract_tracker_name(title)
            logger.info(f"CLOSE: '{tracker_name}' - keyword '{close_keyword}' in: {title[:60]}")
            return (tracker_name, close_keyword, 'closed')

        # Ignore words filter (open detection only)
        if not self._passes_filters(post, text=text, check_ignore_words=True):
            return None

        # Detection based on mode
        if self.detection_mode == 'all':
            match = self._match_any_signup(post, text, title)
        else:
            match = self._match_specific_trackers(post, text, title)

        if match:
            tracker_name, matched_keyword = match
            return (tracker_name, matched_keyword, 'open')
        return None

    def _match_any_signup(self, post: Dict, text: str, title: str) -> Optional[Tuple[str, str]]:
        """Match any open signup post.

        Returns:
            Tuple of (tracker_name_from_title, matched_keyword) or None
        """
        # Check for signup keywords
        matched_keyword = None
        for keyword, pattern in self.signup_patterns:
            if pattern.search(text):
                matched_keyword = keyword
                break

        if not matched_keyword:
            return None

        # Try to extract tracker name from title
        tracker_name = self._extract_tracker_name(title)

        logger.info(f"MATCH: '{tracker_name}' - keyword '{matched_keyword}' in: {title[:60]}")
        return (tracker_name, matched_keyword)

    def _match_specific_trackers(self, post: Dict, text: str, title: str) -> Optional[Tuple[str, str]]:
        """Match only specific configured trackers (legacy mode)."""
        for tracker_name, patterns in self.tracker_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    logger.info(f"MATCH: '{tracker_name}' in: {title[:60]}")
                    return (tracker_name, pattern.pattern)
        return None

    def _passes_filters(self, post: Dict, text: Optional[str] = None,
                       check_ignore_words: bool = True) -> bool:
        """Check if post passes score and ignore word filters."""
        # Check minimum score
        score = post.get('score', 0)
        if score < self.min_score:
            logger.debug(f"Post filtered by score ({score}): {post.get('title', '')[:50]}")
            return False

        # Check for ignore words
        if check_ignore_words:
            if text is None:
                text = f"{post['title']} {post.get('body', '')}".lower()
            for ignore_word in self.ignore_words:
                if ignore_word in text:
                    logger.debug(f"Post filtered by ignore word '{ignore_word}'")
                    return False

        return True

    def _match_close_keyword(self, text: str) -> Optional[str]:
        """Return the close keyword that matched, if any."""
        for keyword, pattern in self.close_patterns:
            if pattern.search(text):
                return keyword
        return None

    def _detect_language(self, text: str, title: str) -> str:
        """Detect language of post content.

        Returns:
            'english', 'portuguese', or detected language name
        """
        text_lower = text.lower()
        title_lower = title.lower()

        # Check for known Portuguese trackers first
        for pt_tracker in self.portuguese_trackers:
            if pt_tracker in text_lower:
                return 'portuguese'

        # Check for Portuguese indicators
        pt_count = sum(1 for word in PORTUGUESE_INDICATORS if word in text_lower)
        if pt_count >= 2:
            return 'portuguese'

        # Check for other languages
        for lang, indicators in OTHER_LANGUAGE_INDICATORS.items():
            if any(ind in text_lower for ind in indicators):
                return lang

        # Default to English (most posts are English)
        return 'english'

    def _extract_tracker_name(self, title: str) -> str:
        """Extract tracker name from post title.

        Tries common patterns like:
        - "TrackerName - Open Signups"
        - "TrackerName open for registration"
        - "[TrackerName] Now accepting applications"
        """
        # Pattern 1: Name at start before separator
        match = re.match(r'^[\[\(]?([A-Za-z0-9\-\.]+)[\]\)]?\s*[-:|]', title)
        if match:
            return match.group(1).strip()

        # Pattern 2: Name at start followed by "open/signup/etc"
        match = re.match(r'^([A-Za-z0-9\-\.]+)\s+(?:is\s+)?(?:now\s+)?(?:open|signup|registration|application)', title, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Pattern 3: Look for capitalized words that might be tracker names
        words = title.split()
        for word in words[:3]:  # Check first 3 words
            # Clean brackets
            clean = re.sub(r'[\[\]\(\)\-\|:]', '', word)
            if clean and clean[0].isupper() and len(clean) >= 2:
                return clean

        # Fallback: first significant word
        for word in words:
            clean = re.sub(r'[^\w]', '', word)
            if len(clean) >= 3:
                return clean

        return "Unknown Tracker"


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    test_config = {
        'detection_mode': 'all',
        'signup_keywords': [
            'open signup', 'open signups', 'open registration',
            'applications open', 'signups open', 'now open'
        ],
        'ignored_trackers': ['IPTorrents'],
        'language': {
            'enabled': True,
            'allowed': ['english', 'portuguese'],
            'portuguese_trackers': ['BrasilTracker', 'BRT']
        },
        'filters': {
            'ignore_words': ['closed', 'ended'],
            'minimum_post_score': 0
        }
    }

    matcher = KeywordMatcher(test_config)

    test_posts = [
        {'title': 'PassThePopcorn - Open Signups for 48 hours!', 'body': '', 'score': 10},
        {'title': 'BTN now accepting applications', 'body': '', 'score': 5},
        {'title': 'IPTorrents open signup', 'body': '', 'score': 20},  # Should be ignored
        {'title': 'Some Russian Tracker открыт', 'body': 'регистрация', 'score': 5},  # Russian
        {'title': 'BrasilTracker - Cadastro aberto', 'body': 'convites limitados', 'score': 3},
        {'title': 'Random discussion about trackers', 'body': '', 'score': 50},  # No signup keywords
        {'title': 'PTP signup has closed', 'body': '', 'score': 10},  # Ignore word
    ]

    print("Testing keyword matcher:\n")
    for post in test_posts:
        result = matcher.match_post(post)
        status = f"MATCH: {result}" if result else "NO MATCH"
        print(f"  {status}: '{post['title'][:50]}'")
