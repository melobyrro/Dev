-- Migration 010: Create speakers table for autocomplete
-- This table stores unique speaker names extracted from videos

CREATE TABLE IF NOT EXISTS speakers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    video_count INTEGER DEFAULT 0,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast autocomplete queries
CREATE INDEX IF NOT EXISTS idx_speakers_name ON speakers(name);
CREATE INDEX IF NOT EXISTS idx_speakers_video_count ON speakers(video_count DESC);

-- Comments for documentation
COMMENT ON TABLE speakers IS 'Stores unique speaker/preacher names for autocomplete functionality';
COMMENT ON COLUMN speakers.name IS 'Speaker full name (unique)';
COMMENT ON COLUMN speakers.video_count IS 'Number of videos by this speaker';
COMMENT ON COLUMN speakers.first_seen_at IS 'First time this speaker appeared';
COMMENT ON COLUMN speakers.last_seen_at IS 'Most recent video by this speaker';

-- Trigger to update updated_at timestamp
CREATE TRIGGER update_speakers_updated_at
    BEFORE UPDATE ON speakers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Populate speakers table from existing videos
INSERT INTO speakers (name, video_count, first_seen_at, last_seen_at)
SELECT
    speaker as name,
    COUNT(*) as video_count,
    MIN(published_at) as first_seen_at,
    MAX(published_at) as last_seen_at
FROM videos
WHERE speaker IS NOT NULL AND speaker != ''
GROUP BY speaker
ON CONFLICT (name) DO NOTHING;

DO $$
BEGIN
    RAISE NOTICE 'Migration 010 completed: Created speakers table and populated from existing videos';
END $$;
