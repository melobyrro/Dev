-- Migration 004: Fix Missing Transcript Columns
-- Purpose: Add confidence_score and audio_quality columns that should have been added in migration 003
-- Issue: Database was created with 001 but 003 was never run, causing runtime errors

-- Add missing columns to transcripts table
ALTER TABLE transcripts
    ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.0
        CHECK (confidence_score >= 0 AND confidence_score <= 1),
    ADD COLUMN IF NOT EXISTS audio_quality VARCHAR(10) DEFAULT 'medium'
        CHECK (audio_quality IN ('low', 'medium', 'high'));

COMMENT ON COLUMN transcripts.confidence_score IS 'Estimated transcription accuracy (0-1 scale)';
COMMENT ON COLUMN transcripts.audio_quality IS 'Detected audio quality level';

-- Verify the fix
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'transcripts'
        AND column_name IN ('confidence_score', 'audio_quality')
    ) THEN
        RAISE NOTICE '✓ Migration 004 completed successfully - columns added to transcripts table';
    ELSE
        RAISE EXCEPTION '✗ Migration 004 failed - columns were not added';
    END IF;
END $$;
