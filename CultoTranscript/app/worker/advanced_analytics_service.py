"""
Advanced Analytics Service (V2)
Orchestrates all analytics components and generates comprehensive sermon reports
"""
import logging
import hashlib
import os
import time
from typing import Dict, List, Optional
from datetime import datetime

from app.common.database import get_db
from app.common.models import (
    Video, Transcript, SermonClassification, BiblicalPassage,
    SermonThemeV2, SermonInconsistency, SermonSuggestion,
    SermonHighlight, DiscussionQuestion, SensitivityFlag,
    TranscriptionError, SermonReport
)
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from app.ai.llm_client import get_llm_client
from app.worker.biblical_classifier import BiblicalClassifier
from app.worker.passage_analyzer import PassageAnalyzer
from app.worker.transcription_scorer import TranscriptionScorer
from app.worker.theme_analyzer_v2 import ThemeAnalyzerV2
from app.worker.inconsistency_detector import InconsistencyDetector
from app.worker.sermon_coach import SermonCoach
from app.worker.highlight_extractor import HighlightExtractor
from app.worker.question_generator import QuestionGenerator
from app.worker.sensitivity_analyzer import SensitivityAnalyzer
from app.worker.ai_summarizer import generate_ai_summary, extract_speaker_name, generate_suggested_title

logger = logging.getLogger(__name__)

# Feature flags from environment
ENABLE_ANALYTICS_CACHE = os.getenv("ENABLE_ANALYTICS_CACHE", "true").lower() == "true"


class AdvancedAnalyticsService:
    """
    Advanced Sermon Analytics Orchestrator

    Coordinates all analytics services and generates:
    - Biblical classifications (citation/reading/mention)
    - OSIS biblical passages with timestamps
    - 17 theological themes with AI confidence scores
    - Inconsistencies and errors
    - Improvement suggestions
    - Key highlights
    - Discussion questions
    - Sensitivity flags
    - Transcription quality scores
    - Comprehensive DailySermonReport JSON
    """

    def __init__(self):
        """Initialize all analytics services"""
        # Initialize all analytics services
        self.biblical_classifier = BiblicalClassifier()
        self.passage_analyzer = PassageAnalyzer()
        self.transcription_scorer = TranscriptionScorer()
        self.theme_analyzer = ThemeAnalyzerV2()
        self.inconsistency_detector = InconsistencyDetector()
        self.sermon_coach = SermonCoach()
        self.highlight_extractor = HighlightExtractor()
        self.question_generator = QuestionGenerator()
        self.sensitivity_analyzer = SensitivityAnalyzer()

        # Cache statistics
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info("Advanced analytics service initialized with all components")

    @staticmethod
    def _hash_transcript(text: str) -> str:
        """
        Generate SHA-256 hash of transcript text for cache validation

        Args:
            text: Transcript text

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _check_analytics_cache(self, video_id: int, transcript_hash: str) -> bool:
        """
        Check if analytics already exist and are valid for this transcript

        Args:
            video_id: Video ID
            transcript_hash: SHA-256 hash of transcript text

        Returns:
            True if valid cached analytics exist, False otherwise
        """
        if not ENABLE_ANALYTICS_CACHE:
            return False

        with get_db() as db:
            # Check if report exists
            report = db.query(SermonReport).filter(
                SermonReport.video_id == video_id
            ).first()

            if not report:
                logger.info(f"No cached analytics for video {video_id}")
                return False

            # Check if transcript has changed
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video or not hasattr(video, 'transcript_hash') or video.transcript_hash != transcript_hash:
                logger.info(f"Transcript changed for video {video_id}, invalidating cache")
                return False

            # Validate critical fields exist - if missing, force regeneration
            # Check analysis version - ensure it's the latest version (v2)
            if not hasattr(video, 'analysis_version') or video.analysis_version != 2:
                logger.info(f"Outdated analysis version for video {video_id} (v{getattr(video, 'analysis_version', 'unknown')}), invalidating cache to regenerate with v2")
                return False

            # Check if ai_summary is missing, empty, or contains an error message
            if not video.ai_summary or not video.ai_summary.strip():
                logger.info(f"Missing ai_summary for video {video_id}, invalidating cache to regenerate")
                return False

            # Invalidate cache if ai_summary is an error message (to allow retry)
            if video.ai_summary.startswith("Erro ao gerar resumo"):
                logger.info(f"Error ai_summary for video {video_id}, invalidating cache to retry generation")
                return False

            if not video.speaker or video.speaker.strip() == "Desconhecido":
                logger.info(f"Missing or unknown speaker for video {video_id}, invalidating cache to regenerate")
                return False

            # Check if suggested_title is missing
            if not video.suggested_title or not video.suggested_title.strip():
                logger.info(f"Missing suggested_title for video {video_id}, invalidating cache to regenerate")
                return False

            # Update last_accessed timestamp
            report.last_accessed = datetime.utcnow()
            db.commit()

            logger.info(f"Valid cached analytics found for video {video_id}")
            return True

    def analyze_video(self, video_id: int, force: bool = False) -> Dict:
        """
        Perform comprehensive analysis on a video

        Args:
            video_id: Video ID to analyze
            force: Force re-analysis even if cached results exist

        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Starting advanced analysis for video {video_id} (force={force})")

        with get_db() as db:
            # Get video and transcript
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError(f"Video {video_id} not found")

            transcript = db.query(Transcript).filter(
                Transcript.video_id == video_id
            ).first()
            if not transcript:
                raise ValueError(f"No transcript found for video {video_id}")

            text = transcript.text
            word_count = transcript.word_count
            duration_sec = video.duration_sec

            # Calculate transcript hash
            transcript_hash = self._hash_transcript(text)

            # Store hash in video record for future comparisons
            video.transcript_hash = transcript_hash

            # Check cache if not forcing re-analysis
            if not force and self._check_analytics_cache(video_id, transcript_hash):
                self.cache_hits += 1
                logger.info(f"CACHE HIT: Using cached analytics for video {video_id}")
                logger.info(f"Cache statistics - Hits: {self.cache_hits}, Misses: {self.cache_misses}")

                # Return existing results from database
                classification = db.query(SermonClassification).filter(
                    SermonClassification.video_id == video_id
                ).first()

                return {
                    'success': True,
                    'video_id': video_id,
                    'cached': True,
                    'citacoes': classification.citacao_count if classification else 0,
                    'leituras': classification.leitura_count if classification else 0,
                    'mencoes': classification.mencao_count if classification else 0,
                    'themes_count': db.query(SermonThemeV2).filter(
                        SermonThemeV2.video_id == video_id
                    ).count(),
                    'inconsistencies_count': db.query(SermonInconsistency).filter(
                        SermonInconsistency.video_id == video_id
                    ).count(),
                    'suggestions_count': db.query(SermonSuggestion).filter(
                        SermonSuggestion.video_id == video_id
                    ).count(),
                    'highlights_count': db.query(SermonHighlight).filter(
                        SermonHighlight.video_id == video_id
                    ).count(),
                    'questions_count': db.query(DiscussionQuestion).filter(
                        DiscussionQuestion.video_id == video_id
                    ).count(),
                    'sensitivity_flags_count': db.query(SensitivityFlag).filter(
                        SensitivityFlag.video_id == video_id
                    ).count(),
                    'wpm': video.wpm,
                    'confidence_score': transcript.confidence_score,
                    'audio_quality': transcript.audio_quality,
                    'llm_usage': {'cached': True, 'tokens_used': 0}
                }

            # Cache miss - perform full analysis
            self.cache_misses += 1
            logger.info(f"CACHE MISS: Running full analysis for video {video_id}")
            logger.info(f"Cache statistics - Hits: {self.cache_hits}, Misses: {self.cache_misses}")

            # Calculate WPM
            wpm = int((word_count / duration_sec) * 60) if duration_sec > 0 else 0
            video.wpm = wpm
            video.analysis_version = 2

            logger.info(f"Analyzing {word_count} words ({wpm} WPM)")

            # Step 1: Score transcription quality
            logger.info("Step 1/9: Scoring transcription quality")
            quality_result = self.transcription_scorer.score_transcript(
                text, transcript.source, word_count
            )
            transcript.confidence_score = quality_result['confidence_score']
            transcript.audio_quality = quality_result['audio_quality']

            # Step 2: Classify biblical content
            logger.info("Step 2/9: Classifying biblical content")
            classification_result = self.biblical_classifier.classify_text(text)

            # Save classification counts.
            #
            # IMPORTANT: use UPSERT to avoid rare race conditions where duplicate jobs
            # process the same video concurrently (can cause unique violations on video_id).
            insert_stmt = insert(SermonClassification).values(
                video_id=video_id,
                citacao_count=classification_result['citacao_count'],
                leitura_count=classification_result['leitura_count'],
                mencao_count=classification_result['mencao_count'],
                total_biblical_references=classification_result['total_count'],
            )
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[SermonClassification.video_id],
                set_={
                    "citacao_count": insert_stmt.excluded.citacao_count,
                    "leitura_count": insert_stmt.excluded.leitura_count,
                    "mencao_count": insert_stmt.excluded.mencao_count,
                    "total_biblical_references": insert_stmt.excluded.total_biblical_references,
                    "updated_at": func.now(),
                },
            )
            db.execute(upsert_stmt)

            # Step 3: Convert passages to OSIS and PREPARE (don't save yet - safe reprocessing)
            logger.info("Step 3/9: Processing biblical passages")
            all_refs = (
                classification_result['citations'] +
                classification_result['readings'] +
                classification_result['mentions']
            )

            # Debug logging for reference detection
            logger.info(f"Biblical references detected: {len(all_refs)} total "
                       f"(citations: {len(classification_result['citations'])}, "
                       f"readings: {len(classification_result['readings'])}, "
                       f"mentions: {len(classification_result['mentions'])})")

            # SAFE REPROCESSING: Collect new passages in memory first (don't delete old yet)
            # Aggregate references by unique key (video_id, osis_ref) to get counts
            ref_aggregation = {}
            for ref in all_refs:  # No limit - process all references
                # Store all references, allowing chapter/verse to be nullable (UI hides missing parts).
                chapter_num = ref.chapter if ref.chapter else None
                chapter_for_osis = chapter_num if (chapter_num and chapter_num > 0) else 1

                parsed = self.passage_analyzer.to_osis(
                    ref.book, chapter_for_osis, ref.verse_start, ref.verse_end
                )

                # Extract timestamps
                start_ts, end_ts = self.passage_analyzer.extract_timestamps(
                    text, ref.text, ref.position
                )

                osis_key = parsed.osis_ref if (chapter_num and chapter_num > 0) else ref.book

                # Create unique key for aggregation
                agg_key = (video_id, osis_key)

                if agg_key in ref_aggregation:
                    # Increment count for existing reference
                    ref_aggregation[agg_key]['count'] += 1
                else:
                    # Add new reference
                    ref_aggregation[agg_key] = {
                        'video_id': video_id,
                        'osis_ref': osis_key,
                        'book': ref.book,
                        'chapter': chapter_num,
                        'verse_start': ref.verse_start,
                        'verse_end': ref.verse_end,
                        'passage_type': ref.reference_type,
                        'start_timestamp': start_ts,
                        'end_timestamp': end_ts,
                        'count': 1
                    }

            # Store new passages data for later insertion (after all generation succeeds)
            new_passages_data = list(ref_aggregation.values())
            logger.info(f"Biblical references prepared: {len(new_passages_data)} unique references from {len(all_refs)} total occurrences")

            # Step 4: Analyze themes (collect in memory - safe reprocessing)
            logger.info("Step 4/9: Analyzing themes with AI")
            themes = self.theme_analyzer.analyze_themes(text, word_count)
            time.sleep(6)  # Respect 10 RPM limit (1 call every 6 seconds)
            logger.debug("✓ Rate limit delay applied after theme analysis")

            # SAFE REPROCESSING: Collect themes data in memory (don't delete old yet)
            new_themes_data = [
                {
                    'video_id': video_id,
                    'theme_tag': theme.theme_tag,
                    'confidence_score': theme.confidence_score,
                    'segment_start': theme.segment_start,
                    'segment_end': theme.segment_end,
                    'key_evidence': theme.key_evidence
                }
                for theme in themes
            ]

            # Step 5: Detect inconsistencies (collect in memory - safe reprocessing)
            logger.info("Step 5/9: Detecting inconsistencies")
            biblical_refs_dict = [{'osis_ref': ref.osis_ref} for ref in all_refs if hasattr(ref, 'osis_ref')]
            inconsistencies = self.inconsistency_detector.detect_inconsistencies(
                text, biblical_refs_dict
            )

            # SAFE REPROCESSING: Collect inconsistencies data in memory
            new_inconsistencies_data = [
                {
                    'video_id': video_id,
                    'inconsistency_type': inc.inconsistency_type,
                    'timestamp': inc.timestamp,
                    'evidence': inc.evidence,
                    'explanation': inc.explanation,
                    'severity': inc.severity
                }
                for inc in inconsistencies
            ]

            # Step 6: Generate improvement suggestions (collect in memory - safe reprocessing)
            logger.info("Step 6/9: Generating improvement suggestions")
            theme_tags = [t.theme_tag for t in themes]
            suggestions = self.sermon_coach.generate_suggestions(
                text, word_count, theme_tags
            )

            # SAFE REPROCESSING: Collect suggestions data in memory
            new_suggestions_data = [
                {
                    'video_id': video_id,
                    'category': sug.category,
                    'impact': sug.impact,
                    'suggestion': sug.suggestion,
                    'concrete_action': sug.concrete_action,
                    'rewritten_example': sug.rewritten_example
                }
                for sug in suggestions
            ]

            # Step 7: Extract highlights (collect in memory - safe reprocessing)
            logger.info("Step 7/9: Extracting key highlights")
            highlights = self.highlight_extractor.extract_highlights(text)

            # SAFE REPROCESSING: Collect highlights data in memory
            new_highlights_data = [
                {
                    'video_id': video_id,
                    'start_timestamp': hl.start_timestamp,
                    'end_timestamp': hl.end_timestamp,
                    'title': hl.title,
                    'summary': hl.summary,
                    'highlight_reason': hl.highlight_reason
                }
                for hl in highlights
            ]

            # Step 8: Generate discussion questions (collect in memory - safe reprocessing)
            logger.info("Step 8/9: Generating discussion questions")
            # Use already generated passages data for questions (safe - not from DB yet)
            passages_for_questions = [
                {'osis_ref': p['osis_ref']} for p in new_passages_data[:5]
            ]
            questions = self.question_generator.generate_questions(
                text, theme_tags, passages_for_questions
            )

            # SAFE REPROCESSING: Collect questions data in memory
            new_questions_data = [
                {
                    'video_id': video_id,
                    'question': q.question,
                    'linked_passage_osis': q.linked_passage_osis,
                    'question_order': q.question_order
                }
                for q in questions
            ]

            # Step 9: Analyze sensitivity (collect in memory - safe reprocessing)
            logger.info("Step 9/12: Analyzing sensitive content")
            flags = self.sensitivity_analyzer.analyze(text)

            # SAFE REPROCESSING: Collect flags data in memory
            new_flags_data = [
                {
                    'video_id': video_id,
                    'term': flag.term,
                    'context_before': flag.context_before,
                    'context_after': flag.context_after,
                    'flag_reason': flag.flag_reason,
                    'reviewed': False
                }
                for flag in flags
            ]

            # Identify transcription errors (collect in memory - safe reprocessing)
            new_errors_data = []
            try:
                errors = quality_result.get('error_patterns_found', 0)
                if errors > 0:
                    error_list = self.transcription_scorer.identify_likely_errors(text)

                    for err in error_list:
                        # Calculate timestamp safely
                        timestamp = 0
                        try:
                            # Estimate timestamp based on character position ratio
                            if len(text) > 0 and duration_sec > 0:
                                timestamp = int((err['position'] / len(text)) * duration_sec)
                        except Exception:
                            timestamp = 0

                        new_errors_data.append({
                            'video_id': video_id,
                            'timestamp': timestamp,
                            'original_text': err['error_text'],
                            'suggested_correction': err['suggested_correction'],
                            'confidence': 0.7,
                            'corrected': False
                        })
            except Exception as e:
                logger.error(f"Error processing transcription errors: {e}")

            # Step 10: Generate AI Summary (SAFE: preserve existing if new generation fails)
            logger.info("Step 10/12: Generating AI summary")
            existing_summary = video.ai_summary  # Preserve existing summary
            try:
                ai_summary = generate_ai_summary(text, video.sermon_start_time)
                time.sleep(6)  # Respect 10 RPM limit (1 call every 6 seconds)
                logger.debug("✓ Rate limit delay applied after AI summary generation")

                # SAFE SUMMARY PRESERVATION: Only replace if new summary is valid
                is_valid_summary = (
                    ai_summary and
                    len(ai_summary) >= 100 and
                    'Erro' not in ai_summary and
                    'erro' not in ai_summary.lower()[:50]
                )

                if is_valid_summary:
                    video.ai_summary = ai_summary
                    logger.info(f"✅ AI summary generated successfully ({len(ai_summary)} chars)")
                else:
                    # Keep existing summary if it was valid, otherwise use error message
                    if existing_summary and len(existing_summary) >= 100 and 'Erro' not in existing_summary:
                        logger.warning(f"⚠️ New summary invalid, keeping existing summary ({len(existing_summary)} chars)")
                        video.ai_summary = existing_summary
                    else:
                        video.ai_summary = ai_summary  # Use new (possibly error) summary
                        logger.warning(f"⚠️ New summary may be invalid ({len(ai_summary) if ai_summary else 0} chars)")
            except Exception as e:
                logger.error(f"Failed to generate AI summary: {e}", exc_info=True)
                # SAFE: Keep existing summary if it was valid
                if existing_summary and len(existing_summary) >= 100 and 'Erro' not in existing_summary:
                    logger.info(f"Keeping existing valid summary after error ({len(existing_summary)} chars)")
                    video.ai_summary = existing_summary
                else:
                    video.ai_summary = "Erro ao gerar resumo (tente novamente mais tarde)"

            # Step 11: Extract Speaker Name (with channel default support)
            logger.info("Step 11/12: Extracting speaker name")
            try:
                # Check if channel has a default speaker configured
                if video.channel and video.channel.default_speaker:
                    # Use channel's default speaker (skip AI extraction)
                    video.speaker = video.channel.default_speaker
                    logger.info(f"Using channel default speaker: {video.channel.default_speaker}")
                else:
                    # Fall back to AI extraction
                    speaker_name = extract_speaker_name(text)
                    time.sleep(6)  # Respect 10 RPM limit (1 call every 6 seconds)
                    logger.debug("✓ Rate limit delay applied after speaker name extraction")
                    video.speaker = speaker_name
                    logger.info(f"AI-extracted speaker name: {speaker_name}")
            except Exception as e:
                logger.error(f"Failed to extract speaker name: {e}", exc_info=True)
                # Try channel default as last resort
                if video.channel and video.channel.default_speaker:
                    video.speaker = video.channel.default_speaker
                    logger.info(f"Using channel default speaker after error: {video.channel.default_speaker}")
                else:
                    video.speaker = "Desconhecido"

            # Step 12: Generate Suggested Title
            logger.info("Step 12/12: Generating suggested title")
            try:
                # Get themes and passages for title generation (use in-memory data - safe reprocessing)
                theme_tags = [t.theme_tag for t in themes]
                passages_for_title = [p['osis_ref'] for p in new_passages_data[:5]]

                suggested_title = generate_suggested_title(
                    summary=video.ai_summary,
                    themes=theme_tags,
                    passages=passages_for_title
                )
                time.sleep(6)  # Respect 10 RPM limit (1 call every 6 seconds)
                logger.debug("Rate limit delay applied after suggested title generation")

                if suggested_title:
                    video.suggested_title = suggested_title
                    logger.info(f"Suggested title generated: {suggested_title}")
                else:
                    # If generation failed (None), keep existing title if present
                    if not video.suggested_title:
                        video.suggested_title = None
                        logger.warning("Failed to generate suggested title - will be None")
                    else:
                        logger.warning("Failed to generate new suggested title - keeping existing one")

            except Exception as e:
                logger.error(f"Failed to generate suggested title: {e}", exc_info=True)
                # Keep existing title on error
                if not video.suggested_title:
                    video.suggested_title = None

            # ============================================================================
            # SAFE REPROCESSING: Atomic delete+insert block
            # All new data has been generated in memory. Now delete old and insert new.
            # This ensures old data is preserved if generation failed earlier.
            # ============================================================================
            logger.info("SAFE REPROCESSING: Performing atomic delete+insert for all analytics data")

            # Delete old data (all in one block) - except BiblicalPassage which uses UPSERT
            # BiblicalPassage uses UPSERT to avoid race condition unique constraint violations
            new_osis_refs = {p['osis_ref'] for p in new_passages_data}
            if new_osis_refs:
                # Delete only passages that won't be upserted
                db.query(BiblicalPassage).filter(
                    BiblicalPassage.video_id == video_id,
                    ~BiblicalPassage.osis_ref.in_(new_osis_refs)
                ).delete(synchronize_session=False)
            else:
                # No new passages, delete all existing
                db.query(BiblicalPassage).filter(BiblicalPassage.video_id == video_id).delete()
            db.query(SermonThemeV2).filter(SermonThemeV2.video_id == video_id).delete()
            db.query(SermonInconsistency).filter(SermonInconsistency.video_id == video_id).delete()
            db.query(SermonSuggestion).filter(SermonSuggestion.video_id == video_id).delete()
            db.query(SermonHighlight).filter(SermonHighlight.video_id == video_id).delete()
            db.query(DiscussionQuestion).filter(DiscussionQuestion.video_id == video_id).delete()
            db.query(SensitivityFlag).filter(SensitivityFlag.video_id == video_id).delete()
            db.query(TranscriptionError).filter(TranscriptionError.video_id == video_id).delete()

            # Insert new data (all in one block)
            # Use UPSERT for BiblicalPassage to handle race conditions
            for passage_data in new_passages_data:
                insert_stmt = insert(BiblicalPassage).values(**passage_data)
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    constraint='biblical_passages_video_osis_unique',
                    set_={
                        'book': insert_stmt.excluded.book,
                        'chapter': insert_stmt.excluded.chapter,
                        'verse_start': insert_stmt.excluded.verse_start,
                        'verse_end': insert_stmt.excluded.verse_end,
                        'passage_type': insert_stmt.excluded.passage_type,
                        'start_timestamp': insert_stmt.excluded.start_timestamp,
                        'end_timestamp': insert_stmt.excluded.end_timestamp,
                        'count': insert_stmt.excluded.count,
                    }
                )
                db.execute(upsert_stmt)
            logger.info(f"Upserted {len(new_passages_data)} biblical passages")

            for theme_data in new_themes_data:
                db.add(SermonThemeV2(**theme_data))
            logger.info(f"Inserted {len(new_themes_data)} themes")

            for inc_data in new_inconsistencies_data:
                db.add(SermonInconsistency(**inc_data))
            logger.info(f"Inserted {len(new_inconsistencies_data)} inconsistencies")

            for sug_data in new_suggestions_data:
                db.add(SermonSuggestion(**sug_data))
            logger.info(f"Inserted {len(new_suggestions_data)} suggestions")

            for hl_data in new_highlights_data:
                db.add(SermonHighlight(**hl_data))
            logger.info(f"Inserted {len(new_highlights_data)} highlights")

            for q_data in new_questions_data:
                db.add(DiscussionQuestion(**q_data))
            logger.info(f"Inserted {len(new_questions_data)} discussion questions")

            for flag_data in new_flags_data:
                db.add(SensitivityFlag(**flag_data))
            logger.info(f"Inserted {len(new_flags_data)} sensitivity flags")

            for err_data in new_errors_data:
                db.add(TranscriptionError(**err_data))
            logger.info(f"Inserted {len(new_errors_data)} transcription errors")

            logger.info("SAFE REPROCESSING: All data inserted successfully")

            # Commit all changes atomically
            db.commit()

            logger.info(f"Advanced analysis completed for video {video_id}")
            try:
                logger.info(f"LLM API usage: {get_llm_client().get_stats()}")
            except Exception:
                logger.info("LLM API usage unavailable")
            logger.info(f"Cache statistics - Hits: {self.cache_hits}, Misses: {self.cache_misses}")

            try:
                llm_usage_stats = get_llm_client().get_stats()
            except Exception:
                llm_usage_stats = {}

            return {
                'success': True,
                'video_id': video_id,
                'cached': False,
                'citacoes': classification_result['citacao_count'],
                'leituras': classification_result['leitura_count'],
                'mencoes': classification_result['mencao_count'],
                'themes_count': len(themes),
                'inconsistencies_count': len(inconsistencies),
                'suggestions_count': len(suggestions),
                'highlights_count': len(highlights),
                'questions_count': len(questions),
                'sensitivity_flags_count': len(flags),
                'wpm': wpm,
                'confidence_score': transcript.confidence_score,
                'audio_quality': transcript.audio_quality,
                'llm_usage': llm_usage_stats
            }
