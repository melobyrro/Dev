"""
Advanced Analytics Service (V2)
Orchestrates all analytics components and generates comprehensive sermon reports
"""
import logging
import hashlib
import os
from typing import Dict, List, Optional
from datetime import datetime

from app.common.database import get_db
from app.common.models import (
    Video, Transcript, SermonClassification, BiblicalPassage,
    SermonThemeV2, SermonInconsistency, SermonSuggestion,
    SermonHighlight, DiscussionQuestion, SensitivityFlag,
    TranscriptionError, SermonReport
)
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
from app.worker.ai_summarizer import generate_ai_summary, extract_speaker_name

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
        # Initialize LLM client (Gemini with Ollama fallback)
        self.llm = get_llm_client()

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

            # Save classification counts
            classification = SermonClassification(
                video_id=video_id,
                citacao_count=classification_result['citacao_count'],
                leitura_count=classification_result['leitura_count'],
                mencao_count=classification_result['mencao_count'],
                total_biblical_references=classification_result['total_count']
            )
            db.merge(classification)

            # Step 3: Convert passages to OSIS and save
            logger.info("Step 3/9: Processing biblical passages")
            all_refs = (
                classification_result['citations'] +
                classification_result['readings'] +
                classification_result['mentions']
            )

            # Delete old passages
            db.query(BiblicalPassage).filter(
                BiblicalPassage.video_id == video_id
            ).delete()

            for ref in all_refs[:50]:  # Limit to top 50
                if ref.chapter:  # Only passages with chapters
                    parsed = self.passage_analyzer.to_osis(
                        ref.book, ref.chapter, ref.verse_start, ref.verse_end
                    )

                    # Extract timestamps
                    start_ts, end_ts = self.passage_analyzer.extract_timestamps(
                        text, ref.text, ref.position
                    )

                    passage = BiblicalPassage(
                        video_id=video_id,
                        osis_ref=parsed.osis_ref,
                        book=ref.book,
                        chapter=ref.chapter,
                        verse_start=ref.verse_start,
                        verse_end=ref.verse_end,
                        passage_type=ref.reference_type,
                        start_timestamp=start_ts,
                        end_timestamp=end_ts,
                        count=1
                    )
                    db.add(passage)

            # Step 4: Analyze themes
            logger.info("Step 4/9: Analyzing themes with AI")
            themes = self.theme_analyzer.analyze_themes(text, word_count)

            # Delete old themes
            db.query(SermonThemeV2).filter(SermonThemeV2.video_id == video_id).delete()

            for theme in themes:
                theme_obj = SermonThemeV2(
                    video_id=video_id,
                    theme_tag=theme.theme_tag,
                    confidence_score=theme.confidence_score,
                    segment_start=theme.segment_start,
                    segment_end=theme.segment_end,
                    key_evidence=theme.key_evidence
                )
                db.add(theme_obj)

            # Step 5: Detect inconsistencies
            logger.info("Step 5/9: Detecting inconsistencies")
            biblical_refs_dict = [{'osis_ref': ref.osis_ref} for ref in all_refs if hasattr(ref, 'osis_ref')]
            inconsistencies = self.inconsistency_detector.detect_inconsistencies(
                text, biblical_refs_dict
            )

            # Delete old inconsistencies
            db.query(SermonInconsistency).filter(
                SermonInconsistency.video_id == video_id
            ).delete()

            for inc in inconsistencies:
                inc_obj = SermonInconsistency(
                    video_id=video_id,
                    inconsistency_type=inc.inconsistency_type,
                    timestamp=inc.timestamp,
                    evidence=inc.evidence,
                    explanation=inc.explanation,
                    severity=inc.severity
                )
                db.add(inc_obj)

            # Step 6: Generate improvement suggestions
            logger.info("Step 6/9: Generating improvement suggestions")
            theme_tags = [t.theme_tag for t in themes]
            suggestions = self.sermon_coach.generate_suggestions(
                text, word_count, theme_tags
            )

            # Delete old suggestions
            db.query(SermonSuggestion).filter(
                SermonSuggestion.video_id == video_id
            ).delete()

            for sug in suggestions:
                sug_obj = SermonSuggestion(
                    video_id=video_id,
                    category=sug.category,
                    impact=sug.impact,
                    suggestion=sug.suggestion,
                    concrete_action=sug.concrete_action,
                    rewritten_example=sug.rewritten_example
                )
                db.add(sug_obj)

            # Step 7: Extract highlights
            logger.info("Step 7/9: Extracting key highlights")
            highlights = self.highlight_extractor.extract_highlights(text)

            # Delete old highlights
            db.query(SermonHighlight).filter(
                SermonHighlight.video_id == video_id
            ).delete()

            for hl in highlights:
                hl_obj = SermonHighlight(
                    video_id=video_id,
                    start_timestamp=hl.start_timestamp,
                    end_timestamp=hl.end_timestamp,
                    title=hl.title,
                    summary=hl.summary,
                    highlight_reason=hl.highlight_reason
                )
                db.add(hl_obj)

            # Step 8: Generate discussion questions
            logger.info("Step 8/9: Generating discussion questions")
            passages_for_questions = [
                {'osis_ref': p.osis_ref} for p in
                db.query(BiblicalPassage).filter(
                    BiblicalPassage.video_id == video_id
                ).limit(5).all()
            ]
            questions = self.question_generator.generate_questions(
                text, theme_tags, passages_for_questions
            )

            # Delete old questions
            db.query(DiscussionQuestion).filter(
                DiscussionQuestion.video_id == video_id
            ).delete()

            for q in questions:
                q_obj = DiscussionQuestion(
                    video_id=video_id,
                    question=q.question,
                    linked_passage_osis=q.linked_passage_osis,
                    question_order=q.question_order
                )
                db.add(q_obj)

            # Step 9: Analyze sensitivity
            logger.info("Step 9/10: Analyzing sensitive content")
            flags = self.sensitivity_analyzer.analyze(text)

            # Delete old flags
            db.query(SensitivityFlag).filter(
                SensitivityFlag.video_id == video_id
            ).delete()

            for flag in flags:
                flag_obj = SensitivityFlag(
                    video_id=video_id,
                    term=flag.term,
                    context_before=flag.context_before,
                    context_after=flag.context_after,
                    flag_reason=flag.flag_reason,
                    reviewed=False
                )
                db.add(flag_obj)

            # Identify transcription errors
            errors = quality_result.get('error_patterns_found', 0)
            if errors > 0:
                error_list = self.transcription_scorer.identify_likely_errors(text)

                # Delete old errors
                db.query(TranscriptionError).filter(
                    TranscriptionError.video_id == video_id
                ).delete()

                for err in error_list:
                    err_obj = TranscriptionError(
                        video_id=video_id,
                        timestamp=int(err['position'] / 2.5 / len(text.split()[:err['position']]) * duration_sec) if duration_sec > 0 else 0,
                        original_text=err['error_text'],
                        suggested_correction=err['suggested_correction'],
                        confidence=0.7,
                        corrected=False
                    )
                    db.add(err_obj)

            # Step 10: Generate AI Summary
            logger.info("Step 10/11: Generating AI summary")
            try:
                ai_summary = generate_ai_summary(text, video.sermon_start_time)
                # Store AI summary in video's metadata (we'll use SermonReport for this)
                # The report generator will include this in the report JSON
                video.ai_summary = ai_summary  # Store temporarily for report generation
                logger.info(f"AI summary generated ({len(ai_summary)} chars)")
            except Exception as e:
                logger.error(f"Failed to generate AI summary: {e}", exc_info=True)
                video.ai_summary = "Erro ao gerar resumo"

            # Step 11: Extract Speaker Name (with channel default support)
            logger.info("Step 11/11: Extracting speaker name")
            try:
                # Check if channel has a default speaker configured
                if video.channel and video.channel.default_speaker:
                    # Use channel's default speaker (skip AI extraction)
                    video.speaker = video.channel.default_speaker
                    logger.info(f"Using channel default speaker: {video.channel.default_speaker}")
                else:
                    # Fall back to AI extraction
                    speaker_name = extract_speaker_name(text)
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

            # Commit all changes
            db.commit()

            logger.info(f"Advanced analysis completed for video {video_id}")
            logger.info(f"LLM API usage: {self.llm.get_stats()}")
            logger.info(f"Cache statistics - Hits: {self.cache_hits}, Misses: {self.cache_misses}")

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
                'llm_usage': self.llm.get_stats()
            }
