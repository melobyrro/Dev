-- Migration 007: Add speaker column to videos table
-- Purpose: Store the main speaker/preacher name (auto-detected by Gemini or manually edited)
-- Date: 2025-11-03

ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS speaker VARCHAR(255) DEFAULT NULL;

COMMENT ON COLUMN videos.speaker IS 'Main speaker/preacher name (auto-detected by Gemini or manually edited)';

-- Create index for speaker lookups
CREATE INDEX IF NOT EXISTS idx_videos_speaker ON videos(speaker);

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 007 completed: Added speaker column to videos table';
END $$;
