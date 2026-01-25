"""
Language Extractor

Parse language hints from Reddit post bodies and titles.
"""

import re
from typing import Optional, List

LABEL_PATTERN = re.compile(
    r'(?im)^\s*(?:[-*]\s*)?(?:\*+)?\s*(language|languages|audio|dub|dubs|subtitle|subtitles|subs)\s*(?:\*+)?\s*[:\-]\s*([^\n\r]+)$'
)
TABLE_PATTERN = re.compile(
    r'(?im)^\s*\|\s*(language|languages|audio|dub|dubs|subtitle|subtitles|subs)\s*\|\s*([^|\n]+)'
)

LANGUAGE_ALIASES = {
    'English': ['english', 'eng', 'en'],
    'Spanish': ['spanish', 'espanol', 'es'],
    'Portuguese': ['portuguese', 'portugues', 'pt'],
    'Portuguese (Brazil)': ['pt-br', 'ptbr', 'brazilian', 'brazilian portuguese'],
    'French': ['french', 'francais', 'fr'],
    'German': ['german', 'deutsch', 'de'],
    'Italian': ['italian', 'ita', 'it'],
    'Russian': ['russian', 'ru'],
    'Chinese': ['chinese', 'zh', 'mandarin', 'cantonese'],
    'Japanese': ['japanese', 'jp', 'ja'],
    'Korean': ['korean', 'kr', 'ko'],
    'Polish': ['polish', 'pl'],
    'Turkish': ['turkish', 'tr'],
    'Dutch': ['dutch', 'nl'],
    'Swedish': ['swedish', 'sv'],
    'Norwegian': ['norwegian', 'no', 'nb', 'nn'],
    'Danish': ['danish', 'da'],
    'Finnish': ['finnish', 'fi'],
    'Greek': ['greek', 'el'],
    'Hebrew': ['hebrew', 'he'],
    'Arabic': ['arabic', 'ar'],
    'Hindi': ['hindi', 'hi'],
    'Vietnamese': ['vietnamese', 'vi'],
    'Thai': ['thai', 'th'],
    'Romanian': ['romanian', 'ro'],
    'Hungarian': ['hungarian', 'hu'],
    'Czech': ['czech', 'cs'],
    'Slovak': ['slovak', 'sk'],
    'Ukrainian': ['ukrainian', 'uk'],
}

ALIAS_LOOKUP = {}
for canonical, aliases in LANGUAGE_ALIASES.items():
    ALIAS_LOOKUP[canonical.lower()] = canonical
    for alias in aliases:
        ALIAS_LOOKUP[alias] = canonical



def extract_language(body: str, title: Optional[str] = None) -> Optional[str]:
    if body:
        for line in _lines(body):
            match = LABEL_PATTERN.search(line)
            if match:
                return _normalize_value(match.group(2))

        match = TABLE_PATTERN.search(body)
        if match:
            return _normalize_value(match.group(2))

        from_body = _extract_from_text(body)
        if from_body:
            return from_body

    if title:
        from_title = _extract_from_title(title)
        if from_title:
            return from_title

    return None


def _lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _normalize_value(value: str) -> Optional[str]:
    clean = _clean_value(value)
    if not clean:
        return None

    parts = _split_parts(clean)
    mapped = _map_parts(parts, allow_short=True)
    if mapped:
        return ', '.join(mapped)

    return clean


def _clean_value(value: str) -> Optional[str]:
    if not value:
        return None

    value = value.replace('|', '/').replace('\t', ' ')
    value = re.sub(r'[`*_]+', '', value)
    value = value.strip(' .;')
    value = re.sub(r'\s+', ' ', value).strip()

    lowered = value.lower()
    if lowered in {'none', 'n/a', 'na', 'unknown', '-', 'tbd'}:
        return None

    return value or None


def _split_parts(value: str) -> List[str]:
    value = value.replace(' / ', '/').replace(' - ', '-')
    parts = re.split(r'[,/;]|\band\b|\bor\b', value, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _map_parts(parts: List[str], allow_short: bool = False) -> List[str]:
    mapped = []
    seen = set()
    for part in parts:
        key = part.lower()
        if not allow_short and len(key) < 4 and key not in {'pt-br'}:
            continue
        canonical = ALIAS_LOOKUP.get(key)
        if not canonical:
            canonical = ALIAS_LOOKUP.get(key.replace('(', '').replace(')', ''))
        if canonical and canonical not in seen:
            mapped.append(canonical)
            seen.add(canonical)
    return mapped


def _extract_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    text_lower = text.lower()

    hits = []
    for alias, canonical in ALIAS_LOOKUP.items():
        if len(alias) < 4 and alias not in {'pt-br'}:
            continue
        if alias == 'english' and 'non-english' in text_lower:
            continue
        if re.search(rf'\b{re.escape(alias)}\b', text_lower):
            hits.append(canonical)

    if hits:
        unique = []
        seen = set()
        for item in hits:
            if item not in seen:
                unique.append(item)
                seen.add(item)
        return ', '.join(unique)

    return None


def _extract_from_title(title: str) -> Optional[str]:
    tokens = []

    for match in re.findall(r'[\[\(]([A-Z]{2,3}(?:-[A-Z]{2})?)[\]\)]', title):
        canonical = _map_code(match)
        if canonical:
            tokens.append(canonical)

    title_lower = title.lower()
    for alias, canonical in ALIAS_LOOKUP.items():
        if re.search(rf'\b{re.escape(alias)}\b', title_lower):
            tokens.append(canonical)

    if tokens:
        unique = []
        seen = set()
        for token in tokens:
            if token not in seen:
                unique.append(token)
                seen.add(token)
        return ', '.join(unique)

    return None


def _map_code(code: str) -> Optional[str]:
    key = code.lower()
    if key in ALIAS_LOOKUP:
        return ALIAS_LOOKUP[key]
    if key == 'pt-br':
        return 'Portuguese (Brazil)'
    return None
