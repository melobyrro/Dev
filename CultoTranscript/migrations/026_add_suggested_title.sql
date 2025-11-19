-- Migration 026: Add suggested_title column for AI-generated sermon titles
-- This column stores AI-generated descriptive titles based on sermon content

ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS suggested_title VARCHAR(500) DEFAULT NULL;

COMMENT ON COLUMN videos.suggested_title IS 'AI-generated descriptive title based on sermon content';

-- Add index for potential searching/filtering by suggested title
CREATE INDEX IF NOT EXISTS idx_videos_suggested_title
    ON videos(suggested_title)
    WHERE suggested_title IS NOT NULL;
