"""
SQLAlchemy ORM models matching the database schema
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, Float, ForeignKey, CheckConstraint, JSON
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
    youtube_url = Column(String(500))
    channel_id = Column(String(100), unique=True)
    youtube_channel_id = Column(String(100), comment='YouTube channel ID extracted from channel URL')
    created_by = Column(Integer, ForeignKey("users.id"))
    active = Column(Boolean, default=True)
    default_speaker = Column(String(255), nullable=True, comment='Default speaker name for videos from this channel')
    last_checked_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    subdomain = Column(String(50), unique=True)
    min_video_duration_sec = Column(Integer, default=300)
    max_video_duration_sec = Column(Integer, default=9000)

    # Relationships
    creator = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="channel")
    youtube_subscription = relationship("YouTubeSubscription", back_populates="channel", uselist=False, cascade="all, delete-orphan")
    schedule_configs = relationship("ScheduleConfig", back_populates="channel", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'transcribed', 'completed', 'failed', 'too_long', 'too_short', 'skipped')",
            name="check_video_status"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    youtube_id = Column(String(20), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    video_created_at = Column(DateTime(timezone=True), nullable=True, index=True, comment='Video creation/recording date from YouTube (same as published_at, used for display)')
    sermon_actual_date = Column(Date, nullable=True, comment='Actual sermon date (previous Sunday) used for filtering')
    duration_sec = Column(Integer, nullable=False)
    has_auto_cc = Column(Boolean, default=False)
    status = Column(String(50), nullable=False, default='pending', index=True)
    language = Column(String(10), default='pt')
    wpm = Column(Integer, default=0)
    analysis_version = Column(Integer, default=2)
    sermon_start_time = Column(Integer, nullable=True, comment='Sermon start time in seconds (0 if sermon starts immediately)')
    ai_summary = Column(Text, nullable=True, comment='AI-generated narrative summary of the sermon')
    speaker = Column(String(255), nullable=True, comment='Main speaker/preacher name (auto-detected by Gemini or manually edited)')
    suggested_title = Column(String(500), nullable=True, comment='AI-generated descriptive title based on sermon content')
    transcript_hash = Column(String(64), nullable=True, comment='SHA-256 hash of transcript text for cache validation')
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
    term = Column(Text, nullable=False)
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
    last_accessed = Column(DateTime(timezone=True), index=True, comment='Last time this cached report was accessed')

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
    segment_start = Column(Integer, nullable=False, comment="Segment start position in words")
    segment_end = Column(Integer, nullable=False, comment="Segment end position in words")
    segment_start_sec = Column(Integer, nullable=True, comment="Segment start time in seconds (for YouTube timestamp links)")
    segment_end_sec = Column(Integer, nullable=True, comment="Segment end time in seconds (for YouTube timestamp links)")
    segment_text = Column(Text, nullable=False)
    embedding = Column(Vector(768))

    # Phase 2: Segment metadata
    keywords = Column(JSONB, comment='Extracted keywords (array)')
    topics = Column(JSONB, comment='Identified theological topics (array)')
    sentiment = Column(String(20), comment='Emotional tone: positive, neutral, negative')
    question_type = Column(String(50), comment='Type of question answered: what, why, how, etc.')
    has_scripture = Column(Boolean, default=False)
    has_practical_application = Column(Boolean, default=False)
    metadata_generated_at = Column(DateTime(timezone=True))

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


class ChatbotCache(Base):
    __tablename__ = "chatbot_cache"

    id = Column(Integer, primary_key=True, index=True)
    question_hash = Column(String(64), unique=True, nullable=False, index=True, comment='SHA-256 hash of question + video context')
    question_text = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    video_ids = Column(JSONB, comment='Array of video IDs included in context')
    cited_videos = Column(JSONB, comment='Videos cited in the response')
    relevance_scores = Column(JSONB, comment='Relevance scores from embedding search')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), index=True, comment='TTL expiration timestamp')
    hit_count = Column(Integer, default=0, comment='Number of times this cache entry was used')
    last_accessed = Column(DateTime(timezone=True), comment='Last time this cache entry was accessed')


class ChurchApiKey(Base):
    """Per-church API keys for AI services"""
    __tablename__ = 'church_api_keys'

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), unique=True, index=True)
    api_key = Column(Text, nullable=False)
    key_suffix = Column(String(10), nullable=True, comment='Last 5 characters for verification display')
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    channel = relationship("Channel")
    updated_by_user = relationship("User")

    def __repr__(self):
        suffix = self.key_suffix or (self.api_key[-5:] if self.api_key else "***")
        return f"<ChurchApiKey(channel_id={self.channel_id}, key_suffix='{suffix}')>"


class ChurchMember(Base):
    """Many-to-many relationship between users and churches with roles"""
    __tablename__ = "church_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'owner', 'admin', 'user'
    invited_by = Column(Integer, ForeignKey("users.id"))
    invited_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    channel = relationship("Channel", foreign_keys=[channel_id])
    inviter = relationship("User", foreign_keys=[invited_by])

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'user')", name='check_role'),
    )


class ScheduleConfig(Base):
    __tablename__ = "schedule_config"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_type = Column(String(50), nullable=False, comment='Type of scheduled job (e.g., weekly_check, daily_check)')
    day_of_week = Column(Integer, nullable=True, comment='Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday). NULL for daily schedules.')
    time_of_day = Column(String(8), nullable=False, comment='Time of day to run in HH:MM:SS format')
    enabled = Column(Boolean, default=True, nullable=False, comment='Whether this schedule is active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    channel = relationship("Channel", back_populates="schedule_configs")


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    video_count = Column(Integer, default=0)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============================================================================
# YOUTUBE WEBSUB (PUBSUBHUBBUB) MODELS
# ============================================================================

class YouTubeSubscription(Base):
    """
    Tracks YouTube PubSubHubbub subscriptions for real-time video notifications.
    Each channel can have one active subscription.
    """
    __tablename__ = "youtube_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "subscription_status IN ('pending', 'active', 'expired', 'failed', 'unsubscribed')",
            name="check_youtube_subscription_status"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    youtube_channel_id = Column(String(100), nullable=False, unique=True, comment='YouTube channel ID (e.g., UCxxxxx)')
    callback_url = Column(String(500), nullable=False, comment='Webhook callback URL for notifications')
    hub_url = Column(String(500), default="https://pubsubhubbub.appspot.com/subscribe", comment='PubSubHubbub hub URL')
    topic_url = Column(String(500), nullable=False, comment='YouTube channel feed URL')
    subscription_status = Column(String(50), default="pending", index=True, comment='Current status: pending, active, expired, failed, unsubscribed')
    last_subscribed_at = Column(DateTime(timezone=True), comment='When subscription was last confirmed')
    expires_at = Column(DateTime(timezone=True), index=True, comment='Subscription expiration (typically 10 days)')
    last_notification_at = Column(DateTime(timezone=True), comment='Last time a notification was received')
    notification_count = Column(Integer, default=0, comment='Total notifications received')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    channel = relationship("Channel", back_populates="youtube_subscription")


class SystemSettings(Base):
    """System-wide configuration settings"""
    __tablename__ = 'system_settings'

    id = Column(Integer, primary_key=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text)
    encrypted = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String(100))
    description = Column(Text)

    def __repr__(self):
        return f"<SystemSettings(key='{self.setting_key}', value='{'***' if self.encrypted else self.setting_value}')>"


# ============================================================================
# PHASE 2: CHATBOT ENHANCEMENTS MODELS
# ============================================================================

class ChatbotFeedback(Base):
    """User feedback on chatbot responses"""
    __tablename__ = "chatbot_feedback"
    __table_args__ = (
        CheckConstraint(
            "rating IN ('helpful', 'not_helpful')",
            name="check_feedback_rating"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    query = Column(Text, nullable=False)
    response_summary = Column(Text)
    rating = Column(String(20), nullable=False)
    feedback_text = Column(Text)
    segments_shown = Column(JSONB, comment='Array of segment IDs that were shown')
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_ip = Column(String(45))
    extra_metadata = Column(JSONB, server_default='{}')

    # Relationships
    channel = relationship("Channel")


class ChatbotQueryMetrics(Base):
    """Tracks all chatbot queries for analytics"""
    __tablename__ = "chatbot_query_metrics"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)
    query_normalized = Column(Text, index=True, comment='Normalized query for grouping')
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    session_id = Column(String(100))
    segments_returned = Column(Integer)
    response_time_ms = Column(Integer)
    cache_hit = Column(Boolean, default=False, index=True)
    date_filters_used = Column(Boolean, default=False)
    speaker_filter_used = Column(Boolean, default=False)
    biblical_filter_used = Column(Boolean, default=False)
    theme_filter_used = Column(Boolean, default=False)
    query_type = Column(String(50), index=True, comment='Query type from classifier')
    backend_used = Column(String(20), index=True, comment='LLM backend: gemini or ollama')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    extra_metadata = Column(JSONB, server_default='{}')

    # Relationships
    channel = relationship("Channel")


# ============================================================================
# PHASE 3: CHATBOT ENHANCEMENTS MODELS (Hybrid Search, Hierarchical, Context)
# ============================================================================

class VideoEmbedding(Base):
    """Video-level embeddings from sermon summaries for broader topical searches"""
    __tablename__ = "video_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True)
    embedding = Column(Vector(768))
    summary = Column(Text, comment='200-300 word AI-generated summary of entire sermon')
    main_topics = Column(JSONB, comment='Top 3-5 main topics covered in sermon')
    key_scripture_refs = Column(JSONB, comment='Key scripture passages referenced (OSIS format)')
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    video = relationship("Video")


class ChannelEmbedding(Base):
    """Channel-level embeddings capturing overall teaching style and themes"""
    __tablename__ = "channel_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), unique=True, index=True)
    embedding = Column(Vector(768))
    teaching_summary = Column(Text, comment='Overview of channel teaching style and emphasis')
    common_themes = Column(JSONB, comment='Most frequently taught themes across all sermons')
    style_notes = Column(Text, comment='Notes on preaching style and approach')
    sermon_count = Column(Integer, default=0, comment='Number of sermons used to generate this embedding')
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    channel = relationship("Channel")


class SermonContextLink(Base):
    """Links related sermon segments across different videos for cross-referencing"""
    __tablename__ = "sermon_context_links"
    __table_args__ = (
        CheckConstraint(
            "link_type IN ('same_topic', 'contrasting_view', 'elaboration', 'example', 'related')",
            name="check_link_type"
        ),
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="check_similarity_score"
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="check_confidence_score"
        ),
        CheckConstraint(
            "source_embedding_id != related_embedding_id",
            name="check_different_segments"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_embedding_id = Column(Integer, ForeignKey("transcript_embeddings.id", ondelete="CASCADE"), index=True)
    related_embedding_id = Column(Integer, ForeignKey("transcript_embeddings.id", ondelete="CASCADE"), index=True)
    similarity_score = Column(Float, nullable=False, comment='Cosine similarity score (0-1, higher = more similar)')
    link_type = Column(String(50), comment='Type of relationship: same_topic, contrasting_view, elaboration, example, related')
    confidence_score = Column(Float, default=0.8, comment='AI confidence in the link type classification')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source_embedding = relationship("TranscriptEmbedding", foreign_keys=[source_embedding_id])
    related_embedding = relationship("TranscriptEmbedding", foreign_keys=[related_embedding_id])
