-- Migration 012: Verify and Fix Caching Infrastructure
-- Purpose: Ensures all caching-related columns/tables exist
-- Safe to run multiple times (idempotent)
-- Created: 2025-11-06

BEGIN;

-- ============================================
-- Part 1: Migration Tracking System
-- ============================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    description TEXT
);

-- Record all historical migrations
INSERT INTO schema_migrations (version, description)
VALUES
    ('003_sermon_analytics_v2', 'Initial analytics schema')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version, description)
VALUES
    ('011_add_caching_infrastructure', 'Add caching columns and tables')
ON CONFLICT (version) DO NOTHING;

-- ============================================
-- Part 2: Fix sermon_reports.last_accessed
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sermon_reports'
        AND column_name = 'last_accessed'
    ) THEN
        ALTER TABLE sermon_reports
        ADD COLUMN last_accessed TIMESTAMPTZ;

        RAISE NOTICE '✓ Added last_accessed column to sermon_reports';
    ELSE
        RAISE NOTICE '✓ Column sermon_reports.last_accessed already exists';
    END IF;
END $$;

-- Add index if not exists
CREATE INDEX IF NOT EXISTS idx_sermon_reports_last_accessed
ON sermon_reports(last_accessed);

-- ============================================
-- Part 3: Fix videos.transcript_hash
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'videos'
        AND column_name = 'transcript_hash'
    ) THEN
        ALTER TABLE videos
        ADD COLUMN transcript_hash VARCHAR(64);

        RAISE NOTICE '✓ Added transcript_hash column to videos';
    ELSE
        RAISE NOTICE '✓ Column videos.transcript_hash already exists';
    END IF;
END $$;

-- Add index if not exists
CREATE INDEX IF NOT EXISTS idx_videos_transcript_hash
ON videos(transcript_hash);

-- ============================================
-- Part 4: Create chatbot_cache table
-- ============================================
CREATE TABLE IF NOT EXISTS chatbot_cache (
    id SERIAL PRIMARY KEY,
    question_hash VARCHAR(64) UNIQUE NOT NULL,
    question_text TEXT NOT NULL,
    response TEXT NOT NULL,
    video_ids JSONB,
    cited_videos JSONB,
    relevance_scores JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ
);

-- Indexes for chatbot_cache
CREATE INDEX IF NOT EXISTS idx_chatbot_cache_question_hash
ON chatbot_cache(question_hash);

CREATE INDEX IF NOT EXISTS idx_chatbot_cache_created_at
ON chatbot_cache(created_at);

CREATE INDEX IF NOT EXISTS idx_chatbot_cache_expires_at
ON chatbot_cache(expires_at);

-- ============================================
-- Part 5: Verify Critical Tables Exist
-- ============================================
DO $$
DECLARE
    missing_tables TEXT[] := ARRAY[]::TEXT[];
BEGIN
    -- Check for critical tables
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'videos') THEN
        missing_tables := array_append(missing_tables, 'videos');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sermon_reports') THEN
        missing_tables := array_append(missing_tables, 'sermon_reports');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sermon_classifications') THEN
        missing_tables := array_append(missing_tables, 'sermon_classifications');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'biblical_passages') THEN
        missing_tables := array_append(missing_tables, 'biblical_passages');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sermon_themes_v2') THEN
        missing_tables := array_append(missing_tables, 'sermon_themes_v2');
    END IF;

    IF array_length(missing_tables, 1) > 0 THEN
        RAISE EXCEPTION 'CRITICAL: Missing tables: %. Run migration 003 first.', array_to_string(missing_tables, ', ');
    END IF;

    RAISE NOTICE '✓ All critical tables verified';
END $$;

-- ============================================
-- Part 6: Record this migration
-- ============================================
INSERT INTO schema_migrations (version, description)
VALUES
    ('012_verify_and_fix_caching', 'Verify and fix all caching infrastructure')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Final verification query
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('sermon_reports', 'videos', 'chatbot_cache')
    AND column_name IN ('last_accessed', 'transcript_hash', 'question_hash')
ORDER BY table_name, column_name;
