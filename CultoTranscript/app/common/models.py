"""
SQLAlchemy ORM models matching the database schema
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, CheckConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.common.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_superadmin = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    channels = relationship("Channel", back_populates="creator")
    audit_logs = relationship("AuditLog", back_populates="user")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    youtube_url = Column(String(500), nullable=False)
    channel_id = Column(String(100), unique=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    schedule_cron = Column(String(100))
    active = Column(Boolean, default=True)
    last_checked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    creator = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="channel")


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'too_long', 'skipped')",
            name="check_video_status"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    youtube_id = Column(String(20), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_sec = Column(Integer, nullable=False)
    has_auto_cc = Column(Boolean, default=False)
    status = Column(String(50), nullable=False, default='pending', index=True)
    language = Column(String(10), default='pt')
    wpm = Column(Integer, default=0)
    analysis_version = Column(Integer, default=2)
    sermon_start_time = Column(Integer, nullable=True, comment='Sermon start time in seconds (0 if sermon starts immediately)')
    ai_summary = Column(Text, nullable=True, comment='AI-generated narrative summary of the sermon')
    speaker = Column(String(255), nullable=True, comment='Main speaker/preacher name (auto-detected by Gemini or manually edited)')
    ingested_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    channel = relationship("Channel", back_populates="videos")
    transcript = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
    verses = relationship("Verse", back_populates="video", cascade="all, delete-orphan")
    themes = relationship("Theme", back_populates="video", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="video")


class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        CheckConstraint(
            "source IN ('auto_cc', 'transcript_api', 'whisper')",
            name="check_transcript_source"
        ),
        CheckConstraint(
            "audio_quality IN ('low', 'medium', 'high')",
            name="check_audio_quality"
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="check_confidence_score"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True)
    source = Column(String(50), nullable=False)
    text = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False)
    char_count = Column(Integer, nullable=False)
    confidence_score = Column(Float, default=0.0)
    audio_quality = Column(String(10), default='medium')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video", back_populates="transcript")


class Verse(Base):
    __tablename__ = "verses"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    book = Column(String(100), nullable=False, index=True)
    chapter = Column(Integer, nullable=False)
    verse = Column(Integer)
    count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video", back_populates="verses")


class Theme(Base):
    __tablename__ = "themes"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    tag = Column(String(100), nullable=False, index=True)
    score = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video", back_populates="themes")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50))
    target_id = Column(Integer)
    meta = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="check_job_status"
        ),
        CheckConstraint(
            "job_type IN ('transcribe_video', 'analyze_video', 'check_channel', 'weekly_scan')",
            name="check_job_type"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default='queued', index=True)
    priority = Column(Integer, default=5)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"))
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    meta = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    video = relationship("Video", back_populates="jobs")
    channel = relationship("Channel", back_populates="jobs")


class ExcludedVideo(Base):
    __tablename__ = "excluded_videos"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    youtube_id = Column(String(20), nullable=False, index=True)
    reason = Column(String(100), default='user_deleted')
    excluded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    channel = relationship("Channel")


# ============================================================================
# ADVANCED ANALYTICS MODELS (V2)
# ============================================================================

class SermonClassification(Base):
    __tablename__ = "sermon_classifications"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True)
    citacao_count = Column(Integer, default=0)
    leitura_count = Column(Integer, default=0)
    mencao_count = Column(Integer, default=0)
    total_biblical_references = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    video = relationship("Video")


class BiblicalPassage(Base):
    __tablename__ = "biblical_passages"
    __table_args__ = (
        CheckConstraint(
            "passage_type IN ('citation', 'reading', 'mention')",
            name="check_passage_type"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    osis_ref = Column(String(100), nullable=False, index=True)
    book = Column(String(100), nullable=False, index=True)
    chapter = Column(Integer)
    verse_start = Column(Integer)
    verse_end = Column(Integer)
    passage_type = Column(String(20))
    start_timestamp = Column(Integer)
    end_timestamp = Column(Integer)
    application_note = Column(Text)
    count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class SermonThemeV2(Base):
    __tablename__ = "sermon_themes_v2"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="check_theme_confidence"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    theme_tag = Column(String(100), nullable=False, index=True)
    confidence_score = Column(Float)
    segment_start = Column(Integer)
    segment_end = Column(Integer)
    key_evidence = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class SermonInconsistency(Base):
    __tablename__ = "sermon_inconsistencies"
    __table_args__ = (
        CheckConstraint(
            "inconsistency_type IN ('logical', 'biblical', 'factual', 'language')",
            name="check_inconsistency_type"
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="check_severity"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    inconsistency_type = Column(String(20))
    timestamp = Column(Integer)
    evidence = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    severity = Column(String(10), default='medium')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class SermonSuggestion(Base):
    __tablename__ = "sermon_suggestions"
    __table_args__ = (
        CheckConstraint(
            "category IN ('exegesis', 'structure', 'communication')",
            name="check_suggestion_category"
        ),
        CheckConstraint(
            "impact IN ('high', 'medium', 'low')",
            name="check_suggestion_impact"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    category = Column(String(20))
    impact = Column(String(10))
    suggestion = Column(Text, nullable=False)
    concrete_action = Column(Text, nullable=False)
    rewritten_example = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class SermonHighlight(Base):
    __tablename__ = "sermon_highlights"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    start_timestamp = Column(Integer, nullable=False)
    end_timestamp = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    summary = Column(Text, nullable=False)
    highlight_reason = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class DiscussionQuestion(Base):
    __tablename__ = "discussion_questions"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    question = Column(Text, nullable=False)
    linked_passage_osis = Column(String(100))
    question_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class SensitivityFlag(Base):
    __tablename__ = "sensitivity_flags"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    term = Column(String(200), nullable=False)
    context_before = Column(Text)
    context_after = Column(Text)
    flag_reason = Column(Text, nullable=False)
    reviewed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class TranscriptionError(Base):
    __tablename__ = "transcription_errors"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="check_error_confidence"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    timestamp = Column(Integer)
    original_text = Column(String(500), nullable=False)
    suggested_correction = Column(String(500))
    confidence = Column(Float)
    corrected = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class SermonReport(Base):
    __tablename__ = "sermon_reports"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True)
    report_json = Column(JSONB, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    cache_expires_at = Column(DateTime(timezone=True), index=True)

    # Relationships
    video = relationship("Video")


class ChannelRollup(Base):
    __tablename__ = "channel_rollups"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    month_year = Column(String(7), nullable=False, index=True)
    rollup_json = Column(JSONB, nullable=False)
    video_count = Column(Integer, default=0)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    channel = relationship("Channel")


# ============================================================================
# GEMINI CHATBOT MODELS
# ============================================================================

class TranscriptEmbedding(Base):
    __tablename__ = "transcript_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    segment_start = Column(Integer, nullable=False)
    segment_end = Column(Integer, nullable=False)
    segment_text = Column(Text, nullable=False)
    embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class GeminiChatHistory(Base):
    __tablename__ = "gemini_chat_history"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    cited_videos = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    channel = relationship("Channel")


class ScheduleConfig(Base):
    __tablename__ = "schedule_config"

    id = Column(Integer, primary_key=True, index=True)
    schedule_type = Column(String(50), nullable=False, unique=True, comment='Type of scheduled job (e.g., weekly_check, daily_check)')
    day_of_week = Column(Integer, nullable=True, comment='Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday). NULL for daily schedules.')
    time_of_day = Column(String(8), nullable=False, comment='Time of day to run in HH:MM:SS format')
    enabled = Column(Boolean, default=True, nullable=False, comment='Whether this schedule is active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    video_count = Column(Integer, default=0)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
