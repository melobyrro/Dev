-- CultoTranscript Database Schema
-- Version: 1.0
-- Description: Initial schema for sermon transcription and analytics

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (v1: all superadmins)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_superadmin BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Channels table
CREATE TABLE channels (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    youtube_url VARCHAR(500) NOT NULL,
    channel_id VARCHAR(100) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    schedule_cron VARCHAR(100),
    active BOOLEAN DEFAULT TRUE,
    last_checked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id)
);

-- Videos table
CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
    youtube_id VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    published_at TIMESTAMP NOT NULL,
    duration_sec INTEGER NOT NULL,
    has_auto_cc BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    language VARCHAR(10) DEFAULT 'pt',
    ingested_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'too_long', 'skipped'))
);

CREATE INDEX idx_videos_channel_id ON videos(channel_id);
CREATE INDEX idx_videos_status ON videos(status);
CREATE INDEX idx_videos_published_at ON videos(published_at);

-- Transcripts table (using TOAST for large text storage)
CREATE TABLE transcripts (
    id SERIAL PRIMARY KEY,
    video_id INTEGER UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,
    text TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    char_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (source IN ('auto_cc', 'transcript_api', 'whisper'))
);

CREATE INDEX idx_transcripts_video_id ON transcripts(video_id);

-- Bible verses references table
CREATE TABLE verses (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    book VARCHAR(100) NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER,
    count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_verses_video_id ON verses(video_id);
CREATE INDEX idx_verses_book ON verses(book);

-- Themes/tags table
CREATE TABLE themes (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    tag VARCHAR(100) NOT NULL,
    score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_themes_video_id ON themes(video_id);
CREATE INDEX idx_themes_tag ON themes(tag);

-- Audit logs table
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50),
    target_id INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- Jobs tracking table (for scheduler and worker)
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    priority INTEGER DEFAULT 5,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    CHECK (job_type IN ('transcribe_video', 'analyze_video', 'check_channel', 'weekly_scan'))
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_job_type ON jobs(job_type);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_channels_updated_at BEFORE UPDATE ON channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default admin user (password: admin123)
-- Hash generated with: passlib.hash.bcrypt.hash("admin123")
INSERT INTO users (email, password_hash, is_superadmin)
VALUES ('admin@culto.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5yvJy0NyHd.Ny', TRUE);
