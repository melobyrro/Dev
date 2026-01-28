-- Migration 027: Add user login tracking columns
-- Adds last_login timestamp and login_count for user authentication tracking
-- Date: 2026-01-27

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0;

COMMENT ON COLUMN users.last_login IS 'Timestamp of last successful login';
COMMENT ON COLUMN users.login_count IS 'Total number of successful logins';

-- Add index for querying recently active users
CREATE INDEX IF NOT EXISTS idx_users_last_login
    ON users(last_login)
    WHERE last_login IS NOT NULL;
