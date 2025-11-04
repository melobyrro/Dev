-- Migration 005: Add Sermon Start Time Column
-- Purpose: Add sermon_start_time column to videos table for sermon detection feature
-- Feature: Gemini AI detects when the sermon actually begins (skipping announcements/music)

-- Add sermon_start_time column to videos table
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS sermon_start_time INTEGER DEFAULT NULL;

COMMENT ON COLUMN videos.sermon_start_time IS 'Sermon start time in seconds (NULL if not detected, 0 if sermon starts immediately)';

-- Verify the migration
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'videos'
        AND column_name = 'sermon_start_time'
    ) THEN
        RAISE NOTICE '✓ Migration 005 completed successfully - sermon_start_time column added to videos table';
    ELSE
        RAISE EXCEPTION '✗ Migration 005 failed - column was not added';
    END IF;
END $$;
