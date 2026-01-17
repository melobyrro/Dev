"""
Report Generators
Creates DailySermonReport and ChannelRollup JSON reports
"""
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from collections import Counter
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.common.database import get_db
from app.common.models import (
    Video, Transcript, SermonClassification, BiblicalPassage,
    SermonThemeV2, SermonInconsistency, SermonSuggestion,
    SermonHighlight, DiscussionQuestion, SensitivityFlag,
    TranscriptionError, SermonReport, ChannelRollup
)
from app.common.sermon_formatter import (
    extract_structured_summary,
    normalize_passage_reference,
    format_transcript_text,
)

logger = logging.getLogger(__name__)


def generate_daily_sermon_report(video_id: int) -> Dict:
    """
    Generate comprehensive DailySermonReport for a single sermon

    Args:
        video_id: Video ID

    Returns:
        Dictionary with complete sermon analysis
    """
    with get_db() as db:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
        if transcript and transcript.text:
            formatted = format_transcript_text(transcript.text)
            if formatted != transcript.text:
                transcript.text = formatted
                transcript.word_count = len(formatted.split())
                transcript.char_count = len(formatted)
                db.flush()

        classification = db.query(SermonClassification).filter(
            SermonClassification.video_id == video_id
        ).first()

        # Normalize structured summary and canonical biblical passages
        structured_summary = extract_structured_summary(video.ai_summary)
        canonical_passages = []
        seen = set()
        import re as _re
        for ref in structured_summary.get("biblical_texts", []):
            for chunk in [c.strip() for c in _re.split(r"[;,]", ref) if c.strip()]:
                parsed = normalize_passage_reference(chunk)
                if parsed and parsed["osis_ref"] not in seen:
                    seen.add(parsed["osis_ref"])
                    canonical_passages.append(parsed)

        if canonical_passages:
            # Delete passages that won't be in the new set
            new_osis_refs = {p["osis_ref"] for p in canonical_passages}
            db.query(BiblicalPassage).filter(
                BiblicalPassage.video_id == video_id,
                ~BiblicalPassage.osis_ref.in_(new_osis_refs)
            ).delete(synchronize_session=False)
            # UPSERT new passages to avoid unique constraint violations
            for p in canonical_passages:
                insert_stmt = insert(BiblicalPassage).values(
                    video_id=video_id,
                    osis_ref=p["osis_ref"],
                    book=p["book"],
                    chapter=p["chapter"],
                    verse_start=p["verse_start"],
                    verse_end=p["verse_end"],
                    passage_type="reading",
                    count=1
                )
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    constraint='biblical_passages_video_osis_unique',
                    set_={
                        'book': insert_stmt.excluded.book,
                        'chapter': insert_stmt.excluded.chapter,
                        'verse_start': insert_stmt.excluded.verse_start,
                        'verse_end': insert_stmt.excluded.verse_end,
                        'passage_type': insert_stmt.excluded.passage_type,
                        'count': insert_stmt.excluded.count,
                    }
                )
                db.execute(upsert_stmt)
            db.flush()

        # Clean invalid placeholders
        db.query(BiblicalPassage).filter(
            BiblicalPassage.video_id == video_id,
            (BiblicalPassage.chapter == None) | (BiblicalPassage.chapter == 0) | (BiblicalPassage.verse_start == None) | (BiblicalPassage.verse_start == 0)
        ).delete(synchronize_session=False)
        db.flush()

        # Build report
        report = {
            'video_id': video_id,
            'title': video.title,
            'suggested_title': video.suggested_title if video.suggested_title else None,
            'published_at': video.published_at.isoformat(),
            'youtube_id': video.youtube_id,
            'generated_at': datetime.now().isoformat(),

            # AI Summary (replaces statistics)
            'ai_summary': video.ai_summary if video.ai_summary else 'Resumo não disponível',

            # Sermon detection
            'sermon_start_time': video.sermon_start_time,

            # Core statistics (minimal, for reference)
            'statistics': {
                'word_count': transcript.word_count if transcript else 0,
                'wpm': video.wpm,
                'duration_minutes': video.duration_sec // 60,
                'confidence_score': transcript.confidence_score if transcript else 0,
                'audio_quality': transcript.audio_quality if transcript else 'unknown'
            },

            # Biblical content
            'biblical_content': {
                'total_references': classification.total_biblical_references if classification else 0,
                'citations_count': classification.citacao_count if classification else 0,
                'readings_count': classification.leitura_count if classification else 0,
                'mentions_count': classification.mencao_count if classification else 0,

                'top_books': _get_top_books(db, video_id),
                'key_passages': _get_key_passages(db, video_id)
            },

            # Themes
            'themes': _get_themes(db, video_id),

            # Structured summary (canonical sections for UI)
            'structured_summary': structured_summary,

            # Quality analysis
            'inconsistencies': _get_inconsistencies(db, video_id),
            'suggestions': _get_suggestions(db, video_id),

            # Content highlights
            'highlights': _get_highlights(db, video_id),
            'discussion_questions': _get_questions(db, video_id),

            # Metadata
            'sensitivity_flags': _get_sensitivity_flags(db, video_id),
            'transcription_errors': _get_transcription_errors(db, video_id)
        }

        # Cache report
        cached_report = db.query(SermonReport).filter(
            SermonReport.video_id == video_id
        ).first()

        if cached_report:
            cached_report.report_json = report
            cached_report.generated_at = datetime.now()
            cached_report.cache_expires_at = datetime.now() + timedelta(hours=24)
        else:
            cached_report = SermonReport(
                video_id=video_id,
                report_json=report,
                cache_expires_at=datetime.now() + timedelta(hours=24)
            )
            db.add(cached_report)

        db.commit()

        return report


def generate_channel_rollup(channel_id: int, month_year: str = None) -> Dict:
    """
    Generate ChannelRollup report for a channel

    Args:
        channel_id: Channel ID
        month_year: Month in YYYY-MM format (defaults to current month)

    Returns:
        Dictionary with channel-wide analytics
    """
    if not month_year:
        month_year = datetime.now().strftime('%Y-%m')

    with get_db() as db:
        # Get all videos for this channel in this month
        year, month = map(int, month_year.split('-'))
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month + 1, 1)

        videos = db.query(Video).filter(
            Video.channel_id == channel_id,
            Video.published_at >= month_start,
            Video.published_at < month_end,
            Video.status == 'completed'
        ).all()

        if len(videos) < 1:
            logger.warning(f"No videos found for channel {channel_id} in {month_year}")
            return None

        video_ids = [v.id for v in videos]

        # Aggregate statistics
        rollup = {
            'channel_id': channel_id,
            'month_year': month_year,
            'video_count': len(videos),
            'generated_at': datetime.now().isoformat(),

            # Temporal trends
            'top_books_monthly': _get_monthly_top_books(db, video_ids),
            'top_themes_monthly': _get_monthly_top_themes(db, video_ids),

            # Book frequency
            'book_frequency': _get_book_frequency(db, video_ids),

            # Recurring passages
            'recurring_passages': _get_recurring_passages(db, video_ids),

            # Style metrics
            'style_metrics': {
                'avg_wpm': sum(v.wpm for v in videos) / len(videos) if videos else 0,
                'avg_duration_minutes': sum(v.duration_sec for v in videos) / len(videos) / 60 if videos else 0,
                'avg_word_count': _get_avg_word_count(db, video_ids)
            },

            # Alerts
            'alerts': _generate_alerts(db, video_ids)
        }

        # Save rollup
        existing = db.query(ChannelRollup).filter(
            ChannelRollup.channel_id == channel_id,
            ChannelRollup.month_year == month_year
        ).first()

        if existing:
            existing.rollup_json = rollup
            existing.video_count = len(videos)
            existing.generated_at = datetime.now()
        else:
            rollup_obj = ChannelRollup(
                channel_id=channel_id,
                month_year=month_year,
                rollup_json=rollup,
                video_count=len(videos)
            )
            db.add(rollup_obj)

        db.commit()

        return rollup


# Helper functions
def _get_top_books(db, video_id) -> List[Dict]:
    """Get top 5 cited books"""
    books = db.query(
        BiblicalPassage.book,
        func.count(BiblicalPassage.id).label('count')
    ).filter(
        BiblicalPassage.video_id == video_id
    ).group_by(
        BiblicalPassage.book
    ).order_by(
        func.count(BiblicalPassage.id).desc()
    ).limit(5).all()

    return [{'book': b[0], 'count': b[1]} for b in books]


def _get_key_passages(db, video_id) -> List[Dict]:
    """Get key passages with timestamps - include all passage types, ordered by importance"""
    from app.worker.passage_analyzer import OSIS_BOOK_MAP
    
    passages = db.query(BiblicalPassage).filter(
        BiblicalPassage.video_id == video_id
    ).order_by(
        BiblicalPassage.count.desc(),  # Order by count to get most important references first
        BiblicalPassage.book,
        BiblicalPassage.chapter
    ).all()  # No limit - return all references

    logger.info(f"Biblical references retrieved for report (video {video_id}): {len(passages)}")

    # Filter out invalid passages
    valid_passages = []
    for p in passages:
        # Skip if chapter or verse is 0 (invalid)
        if p.chapter == 0 or p.verse_start == 0:
            logger.debug(f"Skipping invalid passage with 0:0 reference: {p.book} {p.chapter}:{p.verse_start}")
            continue
        
        # Skip if book doesn't exist in OSIS map (non-existent book)
        if p.book not in OSIS_BOOK_MAP:
            logger.debug(f"Skipping passage with non-existent book: {p.book}")
            continue
        
        valid_passages.append({
            'osis_ref': p.osis_ref,
            'book': p.book,  # Full book name (e.g., "Gênesis")
            'chapter': p.chapter,
            'verse_start': p.verse_start,
            'verse_end': p.verse_end,
            'type': p.passage_type,
            'timestamp_start': p.start_timestamp,
            'timestamp_end': p.end_timestamp,
            'count': p.count  # Number of times this reference appears
        })
    
    logger.info(f"Valid passages after filtering: {len(valid_passages)}/{len(passages)}")
    return valid_passages


def _get_themes(db, video_id) -> List[Dict]:
    """Get detected themes"""
    themes = db.query(SermonThemeV2).filter(
        SermonThemeV2.video_id == video_id
    ).order_by(
        SermonThemeV2.confidence_score.desc()
    ).all()

    return [
        {
            'theme': t.theme_tag,
            'score': t.confidence_score,
            'evidence': t.key_evidence[:200] if t.key_evidence else ''
        }
        for t in themes
    ]


def _get_inconsistencies(db, video_id) -> List[Dict]:
    """Get detected inconsistencies"""
    incs = db.query(SermonInconsistency).filter(
        SermonInconsistency.video_id == video_id
    ).all()

    return [
        {
            'type': i.inconsistency_type,
            'evidence': i.evidence,
            'explanation': i.explanation,
            'severity': i.severity
        }
        for i in incs
    ]


def _get_suggestions(db, video_id) -> List[Dict]:
    """Get improvement suggestions"""
    sugs = db.query(SermonSuggestion).filter(
        SermonSuggestion.video_id == video_id
    ).all()

    return [
        {
            'category': s.category,
            'impact': s.impact,
            'suggestion': s.suggestion,
            'action': s.concrete_action
        }
        for s in sugs
    ]


def _get_highlights(db, video_id) -> List[Dict]:
    """Get key highlights"""
    hls = db.query(SermonHighlight).filter(
        SermonHighlight.video_id == video_id
    ).all()

    return [
        {
            'title': h.title,
            'summary': h.summary,
            'timestamp': h.start_timestamp,
            'reason': h.highlight_reason
        }
        for h in hls
    ]


def _get_questions(db, video_id) -> List[Dict]:
    """Get discussion questions"""
    qs = db.query(DiscussionQuestion).filter(
        DiscussionQuestion.video_id == video_id
    ).order_by(
        DiscussionQuestion.question_order
    ).all()

    return [
        {
            'question': q.question,
            'passage': q.linked_passage_osis
        }
        for q in qs
    ]


def _get_sensitivity_flags(db, video_id) -> List[Dict]:
    """Get sensitivity flags"""
    flags = db.query(SensitivityFlag).filter(
        SensitivityFlag.video_id == video_id
    ).all()

    return [
        {
            'term': f.term,
            'reason': f.flag_reason,
            'reviewed': f.reviewed
        }
        for f in flags[:5]  # Limit to 5
    ]


def _get_transcription_errors(db, video_id) -> List[Dict]:
    """Get transcription errors"""
    errors = db.query(TranscriptionError).filter(
        TranscriptionError.video_id == video_id
    ).limit(5).all()

    return [
        {
            'original': e.original_text,
            'suggestion': e.suggested_correction,
            'corrected': e.corrected
        }
        for e in errors
    ]


def _get_monthly_top_books(db, video_ids) -> List[str]:
    """Get top 3 books for the month"""
    books = db.query(
        BiblicalPassage.book,
        func.count(BiblicalPassage.id).label('count')
    ).filter(
        BiblicalPassage.video_id.in_(video_ids)
    ).group_by(
        BiblicalPassage.book
    ).order_by(
        func.count(BiblicalPassage.id).desc()
    ).limit(3).all()

    return [b[0] for b in books]


def _get_monthly_top_themes(db, video_ids) -> List[str]:
    """Get top 5 themes for the month"""
    themes = db.query(
        SermonThemeV2.theme_tag,
        func.avg(SermonThemeV2.confidence_score).label('avg_score')
    ).filter(
        SermonThemeV2.video_id.in_(video_ids)
    ).group_by(
        SermonThemeV2.theme_tag
    ).order_by(
        func.avg(SermonThemeV2.confidence_score).desc()
    ).limit(5).all()

    return [t[0] for t in themes]


def _get_book_frequency(db, video_ids) -> Dict:
    """Get frequency of all books"""
    passages = db.query(BiblicalPassage).filter(
        BiblicalPassage.video_id.in_(video_ids)
    ).all()

    freq = {}
    for p in passages:
        if p.book not in freq:
            freq[p.book] = {
                'citations': 0,
                'readings': 0,
                'mentions': 0,
                'total': 0
            }

        freq[p.book]['total'] += 1
        if p.passage_type == 'citation':
            freq[p.book]['citations'] += 1
        elif p.passage_type == 'reading':
            freq[p.book]['readings'] += 1
        elif p.passage_type == 'mention':
            freq[p.book]['mentions'] += 1

    return freq


def _get_recurring_passages(db, video_ids) -> List[Dict]:
    """Get passages used multiple times"""
    passages = db.query(
        BiblicalPassage.osis_ref,
        func.count(BiblicalPassage.id).label('count')
    ).filter(
        BiblicalPassage.video_id.in_(video_ids)
    ).group_by(
        BiblicalPassage.osis_ref
    ).having(
        func.count(BiblicalPassage.id) > 1
    ).order_by(
        func.count(BiblicalPassage.id).desc()
    ).limit(10).all()

    return [{'passage': p[0], 'usage_count': p[1]} for p in passages]


def _get_avg_word_count(db, video_ids) -> int:
    """Get average word count"""
    result = db.query(
        func.avg(Transcript.word_count)
    ).filter(
        Transcript.video_id.in_(video_ids)
    ).scalar()

    return int(result) if result else 0


def _generate_alerts(db, video_ids) -> List[str]:
    """Generate automated alerts"""
    alerts = []

    # Check for lack of diversity
    passages = db.query(BiblicalPassage).filter(
        BiblicalPassage.video_id.in_(video_ids)
    ).all()

    if passages:
        book_counter = Counter(p.book for p in passages)
        total = len(passages)

        for book, count in book_counter.most_common(1):
            if count / total > 0.6:
                alerts.append(
                    f"Alta concentração em {book} ({int(count/total*100)}% das citações)"
                )

    return alerts
