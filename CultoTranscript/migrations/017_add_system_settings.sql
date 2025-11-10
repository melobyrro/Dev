-- System settings table for runtime-configurable application settings
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    encrypted BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    description TEXT
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_system_settings_key ON system_settings(setting_key);

-- Insert default values
INSERT INTO system_settings (setting_key, setting_value, encrypted, description)
VALUES
    ('ai_service_provider', 'gemini', FALSE, 'Primary AI service (gemini or ollama)'),
    ('gemini_api_key', '', TRUE, 'Google Gemini API key (encrypted)')
ON CONFLICT (setting_key) DO NOTHING;
