"""
Sermon formatter utilities.
Stub file - functions needed by report_generators.py
"""
from typing import Optional


def extract_structured_summary(text: str) -> dict:
    """Extract structured summary from text. Stub implementation."""
    return {"summary": text[:500] if text else ""}


def normalize_passage_reference(reference: str) -> str:
    """Normalize biblical passage reference. Stub implementation."""
    return reference.strip() if reference else ""


def format_transcript_text(text: str) -> str:
    """Format transcript text for display. Stub implementation."""
    return text.strip() if text else ""
