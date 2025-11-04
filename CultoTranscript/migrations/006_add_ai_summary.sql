-- Migration 006: Add AI Summary Column
-- Purpose: Add ai_summary column to videos table for storing AI-generated narrative summaries
-- Feature: Replaces statistics with narrative AI summary

-- Add ai_summary column to videos table
ALTER TABLE videos
    ADD COLUMN IF NOT EXISTS ai_summary TEXT DEFAULT NULL;

COMMENT ON COLUMN videos.ai_summary IS 'AI-generated narrative summary of the sermon (3-4 paragraphs)';

-- Verify the migration
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'videos'
        AND column_name = 'ai_summary'
    ) THEN
        RAISE NOTICE '✓ Migration 006 completed successfully - ai_summary column added to videos table';
    ELSE
        RAISE EXCEPTION '✗ Migration 006 failed - column was not added';
    END IF;
END $$;
