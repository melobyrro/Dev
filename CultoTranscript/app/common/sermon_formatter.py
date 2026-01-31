"""
Helpers to normalize sermon data for consistent rendering.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.worker.passage_analyzer import OSIS_BOOK_MAP


def format_transcript_text(raw_text: str) -> str:
    """
    Reformat transcript text into readable paragraphs.

    - Strips HTML entities/tags
    - Collapses excess whitespace
    - Splits into paragraphs on sentence boundaries to avoid run-on blocks
    """
    if not raw_text:
        return ""

    text = (
        raw_text.replace("\r", "\n")
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    # Drop HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Split on sentence boundaries and group into short paragraphs
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÃÕÂÊÔ])", text)
    paragraphs: List[str] = []
    buffer: List[str] = []

    for sentence in sentences:
        if not sentence:
            continue
        buffer.append(sentence.strip())
        # Flush buffer when it gets long enough
        if sum(len(s) for s in buffer) > 400 or len(buffer) >= 3:
            paragraphs.append(" ".join(buffer))
            buffer = []

    if buffer:
        paragraphs.append(" ".join(buffer))

    # Ensure we never return a single giant blob
    if not paragraphs and text:
        paragraphs = [text]

    return "\n\n".join(paragraphs)


def extract_structured_summary(ai_summary: Optional[str]) -> Dict[str, List[str]]:
    """
    Parse a markdown-style AI summary into canonical sections.
    Sections: Texto(s) Bíblico(s), Tema Central, Pontos Principais, Aplicação Prática.
    """
    sections = {
        "biblical_texts": [],
        "tema_central": [],
        "pontos_principais": [],
        "aplicacao_pratica": [],
    }
    if not ai_summary:
        return sections

    lines = [ln.strip() for ln in ai_summary.splitlines() if ln.strip()]
    current: Optional[str] = None

    def match_section(line: str) -> Optional[str]:
        normalized = line.lower()
        if "texto" in normalized and ("bíblico" in normalized or "biblico" in normalized):
            return "biblical_texts"
        if "tema central" in normalized:
            return "tema_central"
        if "pontos principais" in normalized or "ponto principal" in normalized:
            return "pontos_principais"
        if "aplica" in normalized:
            return "aplicacao_pratica"
        return None

    for line in lines:
        heading = match_section(line)

        # Support two formats:
        # 1) Markdown headings: "## Tema Central" followed by bullet lines
        # 2) Labelled bullets: "• **Tema Central:** ..." (the label line contains the content)
        if heading:
            current = heading

            # If this line contains inline content after ":" (labelled bullet style),
            # capture the content for the selected section.
            if ":" in line:
                after = line.split(":", 1)[1].strip()
                after = re.sub(r"^[•\-\d\.\s]+", "", after).strip()
                after = re.sub(r"^\*+\s*", "", after)
                after = re.sub(r"\s*\*+$", "", after).strip()
                if after:
                    sections[current].append(after)
            continue

        if current:
            cleaned = re.sub(r"^[•\-\d\.\s]+", "", line).strip()
            if cleaned and cleaned not in {"*", "**"}:
                sections[current].append(cleaned)

    # Deduplicate while preserving order
    for key in sections:
        seen = set()
        deduped = []
        for item in sections[key]:
            if item not in seen:
                deduped.append(item)
                seen.add(item)
        sections[key] = deduped

    # Fallback: if nothing was parsed, derive a minimal structure from sentences
    if not any(sections.values()) and ai_summary:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", ai_summary) if s.strip()]
        if sentences:
            sections["tema_central"] = [sentences[0]]
            if len(sentences) > 1:
                sections["pontos_principais"] = sentences[1:4]

    return sections


def normalize_passage_reference(raw_line: str) -> Optional[Dict]:
    """
    Convert a human-readable passage line into structured data.
    Returns dict with book, chapter, verse_start, verse_end, osis_ref, display.
    """
    if not raw_line:
        return None

    # Strip parenthetical notes and common prefixes
    core = raw_line.split("(")[0].strip()
    core = re.sub(r"^referênci[ae]s?\s+a\s+", "", core, flags=re.IGNORECASE)
    # Match book + chapter + optional verse range
    match = re.match(
        r"^([\dI]{0,2}\s*[A-Za-zÁÉÍÓÚÂÊÔÃÕà-úçÇ ]+)\s+(\d+)(?::(\d+)(?:[-–](\d+))?)?",
        core,
    )
    if not match:
        return None

    book = match.group(1).strip()
    chapter = int(match.group(2))
    verse_start = int(match.group(3)) if match.group(3) else None
    verse_end = int(match.group(4)) if match.group(4) else None

    # Build OSIS ref (best effort)
    osis_book = (
        OSIS_BOOK_MAP.get(book)
        or OSIS_BOOK_MAP.get(book.title())
        or OSIS_BOOK_MAP.get(book.lower().title())
        or OSIS_BOOK_MAP.get(book.lower())
        or book
    )
    osis_ref = f"{osis_book} {chapter}"
    if verse_start:
        osis_ref += f":{verse_start}"
    if verse_end and verse_end != verse_start:
        osis_ref += f"-{verse_end}"

    display = f"{book} {chapter}"
    if verse_start:
        display += f":{verse_start}"
    if verse_end and verse_end != verse_start:
        display += f"-{verse_end}"

    return {
        "book": book,
        "chapter": chapter,
        "verse_start": verse_start,
        "verse_end": verse_end,
        "osis_ref": osis_ref,
        "display": display,
    }
