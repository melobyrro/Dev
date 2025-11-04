-- Migration 008: Add schedule_config table for dynamic scheduler configuration
-- Purpose: Allow admins to configure automatic channel check schedule via UI
-- Date: 2025-11-03

CREATE TABLE IF NOT EXISTS schedule_config (
    id SERIAL PRIMARY KEY,
    schedule_type VARCHAR(50) NOT NULL,  -- e.g., 'weekly_check', 'daily_check'
    day_of_week INTEGER CHECK (day_of_week >= 0 AND day_of_week <= 6),  -- 0=Monday, 6=Sunday
    time_of_day TIME NOT NULL,  -- Time in HH:MM:SS format
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE schedule_config IS 'Stores scheduler configuration for automatic channel checks';
COMMENT ON COLUMN schedule_config.schedule_type IS 'Type of scheduled job (e.g., weekly_check, daily_check)';
COMMENT ON COLUMN schedule_config.day_of_week IS 'Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday). NULL for daily schedules.';
COMMENT ON COLUMN schedule_config.time_of_day IS 'Time of day to run the scheduled job';
COMMENT ON COLUMN schedule_config.enabled IS 'Whether this schedule is active';

-- Create unique constraint to prevent duplicate schedule types
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_config_type ON schedule_config(schedule_type);

-- Insert default schedule: Monday at 2 AM (as requested by user)
INSERT INTO schedule_config (schedule_type, day_of_week, time_of_day, enabled)
VALUES ('weekly_check', 0, '02:00:00', TRUE)
ON CONFLICT (schedule_type) DO NOTHING;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 008 completed: Created schedule_config table with default Monday 2 AM schedule';
END $$;
