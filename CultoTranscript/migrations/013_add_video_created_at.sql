-- Migration 013: Add video_created_at column to videos table
-- Purpose: Store video creation/recording date from YouTube (for display instead of published_at)
-- Date: 2025-11-06

-- Add the column
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS video_created_at TIMESTAMPTZ DEFAULT NULL;

-- Add comment
COMMENT ON COLUMN videos.video_created_at IS 'Video creation/recording date from YouTube (same as published_at, used for display)';

-- Create index for sorting and filtering
CREATE INDEX IF NOT EXISTS idx_videos_video_created_at ON videos(video_created_at);

-- Backfill existing records (copy published_at to video_created_at)
UPDATE videos
SET video_created_at = published_at
WHERE video_created_at IS NULL;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 013 completed: Added video_created_at column to videos table and backfilled from published_at';
END $$;
