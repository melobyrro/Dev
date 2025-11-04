-- Migration 003: Advanced Analytics & AI Features
-- Purpose: Add comprehensive sermon analytics and AI-powered insights

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

-- Vector similarity search for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- MODIFY EXISTING TABLES
-- ============================================================================

-- Add transcription quality metrics to transcripts table
ALTER TABLE transcripts
    ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.0 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    ADD COLUMN IF NOT EXISTS audio_quality VARCHAR(10) DEFAULT 'medium' CHECK (audio_quality IN ('low', 'medium', 'high'));

COMMENT ON COLUMN transcripts.confidence_score IS 'Estimated transcription accuracy (0-1 scale)';
COMMENT ON COLUMN transcripts.audio_quality IS 'Detected audio quality level';

-- Add analytics metadata to videos table
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS wpm INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS analysis_version INTEGER DEFAULT 2;

COMMENT ON COLUMN videos.wpm IS 'Words per minute (speaking pace)';
COMMENT ON COLUMN videos.analysis_version IS 'Analytics system version used for this video';

-- ============================================================================
-- NEW ANALYTICS TABLES
-- ============================================================================

-- Sermon Classifications: Citation vs Reading vs Mention counts
CREATE TABLE IF NOT EXISTS sermon_classifications (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE UNIQUE,
    citacao_count INTEGER DEFAULT 0,
    leitura_count INTEGER DEFAULT 0,
    mencao_count INTEGER DEFAULT 0,
    total_biblical_references INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sermon_classifications_video ON sermon_classifications(video_id);

COMMENT ON TABLE sermon_classifications IS 'Classifies biblical content by type: citation, reading, or mention';
COMMENT ON COLUMN sermon_classifications.citacao_count IS 'Count of explicit biblical citations (book + chapter/verse mentioned)';
COMMENT ON COLUMN sermon_classifications.leitura_count IS 'Count of scripture readings (text read aloud or paraphrased)';
COMMENT ON COLUMN sermon_classifications.mencao_count IS 'Count of nominal mentions (biblical characters/books named without citation)';

-- Biblical Passages: Enhanced verse tracking with OSIS, timestamps, and context
CREATE TABLE IF NOT EXISTS biblical_passages (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    osis_ref VARCHAR(100) NOT NULL,
    book VARCHAR(100) NOT NULL,
    chapter INTEGER,
    verse_start INTEGER,
    verse_end INTEGER,
    passage_type VARCHAR(20) CHECK (passage_type IN ('citation', 'reading', 'mention')),
    start_timestamp INTEGER,
    end_timestamp INTEGER,
    application_note TEXT,
    count INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_biblical_passages_video ON biblical_passages(video_id);
CREATE INDEX idx_biblical_passages_book ON biblical_passages(book);
CREATE INDEX idx_biblical_passages_osis ON biblical_passages(osis_ref);
CREATE INDEX idx_biblical_passages_type ON biblical_passages(passage_type);

COMMENT ON TABLE biblical_passages IS 'Detailed tracking of biblical passages with OSIS references and timestamps';
COMMENT ON COLUMN biblical_passages.osis_ref IS 'OSIS standard reference (e.g., Ps.23.1-6)';
COMMENT ON COLUMN biblical_passages.passage_type IS 'How the passage was used: citation, reading, or mention';
COMMENT ON COLUMN biblical_passages.start_timestamp IS 'Start time in seconds';
COMMENT ON COLUMN biblical_passages.end_timestamp IS 'End time in seconds';
COMMENT ON COLUMN biblical_passages.application_note IS 'Brief note on how this passage was applied in the sermon';

-- Sermon Themes V2: Expanded 17 themes with 0-1 scores and timestamps
CREATE TABLE IF NOT EXISTS sermon_themes_v2 (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    theme_tag VARCHAR(100) NOT NULL,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    segment_start INTEGER,
    segment_end INTEGER,
    key_evidence TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sermon_themes_v2_video ON sermon_themes_v2(video_id);
CREATE INDEX idx_sermon_themes_v2_tag ON sermon_themes_v2(theme_tag);
CREATE INDEX idx_sermon_themes_v2_score ON sermon_themes_v2(confidence_score DESC);

COMMENT ON TABLE sermon_themes_v2 IS 'ML-based thematic analysis with 17 expanded themes';
COMMENT ON COLUMN sermon_themes_v2.confidence_score IS 'Theme relevance score (0-1 scale)';
COMMENT ON COLUMN sermon_themes_v2.segment_start IS 'Timestamp where theme appears (seconds)';
COMMENT ON COLUMN sermon_themes_v2.key_evidence IS 'Key phrases/quotes supporting this theme';

-- Sermon Inconsistencies: Logical, biblical, factual, and language errors
CREATE TABLE IF NOT EXISTS sermon_inconsistencies (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    inconsistency_type VARCHAR(20) CHECK (inconsistency_type IN ('logical', 'biblical', 'factual', 'language')),
    timestamp INTEGER,
    evidence TEXT NOT NULL,
    explanation TEXT NOT NULL,
    severity VARCHAR(10) DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sermon_inconsistencies_video ON sermon_inconsistencies(video_id);
CREATE INDEX idx_sermon_inconsistencies_type ON sermon_inconsistencies(inconsistency_type);

COMMENT ON TABLE sermon_inconsistencies IS 'Detected inconsistencies and potential errors in sermons';
COMMENT ON COLUMN sermon_inconsistencies.inconsistency_type IS 'Category: logical, biblical, factual, or language';
COMMENT ON COLUMN sermon_inconsistencies.evidence IS 'The problematic text or quote';
COMMENT ON COLUMN sermon_inconsistencies.explanation IS 'Why this is considered inconsistent';

-- Sermon Suggestions: Actionable improvement recommendations
CREATE TABLE IF NOT EXISTS sermon_suggestions (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    category VARCHAR(20) CHECK (category IN ('exegesis', 'structure', 'communication')),
    impact VARCHAR(10) CHECK (impact IN ('high', 'medium', 'low')),
    suggestion TEXT NOT NULL,
    concrete_action TEXT NOT NULL,
    rewritten_example TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sermon_suggestions_video ON sermon_suggestions(video_id);
CREATE INDEX idx_sermon_suggestions_category ON sermon_suggestions(category);
CREATE INDEX idx_sermon_suggestions_impact ON sermon_suggestions(impact);

COMMENT ON TABLE sermon_suggestions IS 'AI-generated actionable suggestions to improve future sermons';
COMMENT ON COLUMN sermon_suggestions.category IS 'Type of improvement: exegesis, structure, or communication';
COMMENT ON COLUMN sermon_suggestions.concrete_action IS 'Specific action the pastor can take';
COMMENT ON COLUMN sermon_suggestions.rewritten_example IS 'Example of how to improve a specific segment';

-- Sermon Highlights: Key moments with timestamps
CREATE TABLE IF NOT EXISTS sermon_highlights (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    start_timestamp INTEGER NOT NULL,
    end_timestamp INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    summary TEXT NOT NULL,
    highlight_reason VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sermon_highlights_video ON sermon_highlights(video_id);

COMMENT ON TABLE sermon_highlights IS 'Key moments in sermons (powerful quotes, calls to action, etc.)';
COMMENT ON COLUMN sermon_highlights.highlight_reason IS 'Why this was highlighted (e.g., "clear call to action")';

-- Discussion Questions: Generated questions for small groups
CREATE TABLE IF NOT EXISTS discussion_questions (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    linked_passage_osis VARCHAR(100),
    question_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_discussion_questions_video ON discussion_questions(video_id);

COMMENT ON TABLE discussion_questions IS 'AI-generated discussion questions based on sermon content';
COMMENT ON COLUMN discussion_questions.linked_passage_osis IS 'Optional OSIS reference for context';

-- Sensitivity Flags: Potentially sensitive content tracking
CREATE TABLE IF NOT EXISTS sensitivity_flags (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    term VARCHAR(200) NOT NULL,
    context_before TEXT,
    context_after TEXT,
    flag_reason TEXT NOT NULL,
    reviewed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sensitivity_flags_video ON sensitivity_flags(video_id);
CREATE INDEX idx_sensitivity_flags_reviewed ON sensitivity_flags(reviewed);

COMMENT ON TABLE sensitivity_flags IS 'Potentially sensitive terms flagged for pastor review';
COMMENT ON COLUMN sensitivity_flags.context_before IS 'Text before the term (25 words)';
COMMENT ON COLUMN sensitivity_flags.context_after IS 'Text after the term (25 words)';
COMMENT ON COLUMN sensitivity_flags.reviewed IS 'Whether pastor has reviewed this flag';

-- Transcription Errors: Suspected errors with suggested corrections
CREATE TABLE IF NOT EXISTS transcription_errors (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    timestamp INTEGER,
    original_text VARCHAR(500) NOT NULL,
    suggested_correction VARCHAR(500),
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    corrected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_transcription_errors_video ON transcription_errors(video_id);
CREATE INDEX idx_transcription_errors_corrected ON transcription_errors(corrected);

COMMENT ON TABLE transcription_errors IS 'AI-detected likely transcription errors with suggestions';

-- Sermon Reports: JSON storage for DailySermonReport (hybrid approach)
CREATE TABLE IF NOT EXISTS sermon_reports (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE UNIQUE,
    report_json JSONB NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    cache_expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX idx_sermon_reports_video ON sermon_reports(video_id);
CREATE INDEX idx_sermon_reports_cache ON sermon_reports(cache_expires_at);

COMMENT ON TABLE sermon_reports IS 'Cached DailySermonReport JSON for quick retrieval';
COMMENT ON COLUMN sermon_reports.cache_expires_at IS 'Reports regenerate after 24 hours';

-- Channel Rollups: Monthly aggregated analytics per channel
CREATE TABLE IF NOT EXISTS channel_rollups (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
    month_year VARCHAR(7) NOT NULL,
    rollup_json JSONB NOT NULL,
    video_count INTEGER DEFAULT 0,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(channel_id, month_year)
);

CREATE INDEX idx_channel_rollups_channel ON channel_rollups(channel_id);
CREATE INDEX idx_channel_rollups_month ON channel_rollups(month_year);

COMMENT ON TABLE channel_rollups IS 'Monthly aggregated analytics for channels with 10+ sermons';
COMMENT ON COLUMN channel_rollups.month_year IS 'Format: YYYY-MM';

-- ============================================================================
-- GEMINI CHATBOT TABLES
-- ============================================================================

-- Transcript Embeddings: Vector storage for semantic search
CREATE TABLE IF NOT EXISTS transcript_embeddings (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    segment_start INTEGER NOT NULL,
    segment_end INTEGER NOT NULL,
    segment_text TEXT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_embeddings_video ON transcript_embeddings(video_id);
CREATE INDEX idx_embeddings_vector ON transcript_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

COMMENT ON TABLE transcript_embeddings IS 'Vector embeddings for semantic search in chatbot';
COMMENT ON COLUMN transcript_embeddings.embedding IS 'Gemini embedding (768 dimensions)';

-- Chat History: Conversation tracking per channel
CREATE TABLE IF NOT EXISTS gemini_chat_history (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
    session_id VARCHAR(100) NOT NULL,
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    cited_videos JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_chat_history_channel ON gemini_chat_history(channel_id);
CREATE INDEX idx_chat_history_session ON gemini_chat_history(session_id);

COMMENT ON TABLE gemini_chat_history IS 'Chatbot conversation history per channel';
COMMENT ON COLUMN gemini_chat_history.cited_videos IS 'JSON array of video IDs and timestamps cited in response';

-- ============================================================================
-- DATA MIGRATION NOTES
-- ============================================================================

-- After this migration:
-- 1. Existing 'verses' and 'themes' tables remain (for backward compatibility during migration)
-- 2. All videos will be re-analyzed with the new analytics system
-- 3. Once migration is complete, old tables can be dropped
-- 4. Set analysis_version=2 for all newly analyzed videos

COMMENT ON DATABASE culto IS 'CultoTranscript v2 - Advanced Sermon Analytics & AI Platform';
