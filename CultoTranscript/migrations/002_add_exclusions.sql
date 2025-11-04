-- Migration: Add excluded videos tracking
-- Purpose: Track deleted/excluded videos to prevent re-import

CREATE TABLE IF NOT EXISTS excluded_videos (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
    youtube_id VARCHAR(20) NOT NULL,
    reason VARCHAR(100) DEFAULT 'user_deleted',
    excluded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(channel_id, youtube_id)
);

CREATE INDEX idx_excluded_videos_channel ON excluded_videos(channel_id);
CREATE INDEX idx_excluded_videos_youtube_id ON excluded_videos(youtube_id);

COMMENT ON TABLE excluded_videos IS 'Tracks videos that have been deleted/excluded to prevent re-import';
