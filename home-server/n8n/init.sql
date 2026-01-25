-- Claude Config Auditor Database Schema
-- This schema supports config auditing, rule management, and external source tracking

-- Projects table: Tracked Claude Code projects
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    path TEXT NOT NULL UNIQUE,
    config_hash VARCHAR(64),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Config snapshots: Historical config snapshots
CREATE TABLE config_snapshots (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    config_hash VARCHAR(64) NOT NULL,
    settings_json JSONB,
    settings_local_json JSONB,
    claude_md TEXT,
    skills_list TEXT[],
    commands_list TEXT[],
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rules table: Audit rules
CREATE TABLE rules (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'error', 'warning', 'info')),
    category VARCHAR(50) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    check_config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Candidates table: Pending rule discoveries
CREATE TABLE candidates (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    source_url TEXT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    suggested_rule JSONB,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'implemented')),
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE
);

-- Audit results: Rule check results
CREATE TABLE audit_results (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_id INTEGER REFERENCES config_snapshots(id) ON DELETE CASCADE,
    rule_id VARCHAR(50) REFERENCES rules(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pass', 'fail', 'skip', 'error')),
    details JSONB,
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Source sync: External source tracking
CREATE TABLE source_sync (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL UNIQUE,
    source_type VARCHAR(50) NOT NULL,
    source_url TEXT NOT NULL,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    last_etag VARCHAR(255),
    last_content_hash VARCHAR(64),
    sync_status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_projects_path ON projects(path);
CREATE INDEX idx_projects_last_seen ON projects(last_seen_at);
CREATE INDEX idx_snapshots_project ON config_snapshots(project_id);
CREATE INDEX idx_snapshots_captured ON config_snapshots(captured_at);
CREATE INDEX idx_audit_results_project ON audit_results(project_id);
CREATE INDEX idx_audit_results_rule ON audit_results(rule_id);
CREATE INDEX idx_audit_results_status ON audit_results(status);
CREATE INDEX idx_candidates_status ON candidates(status);

-- Seed data: Initial audit rules
INSERT INTO rules (id, name, description, severity, category, check_type, check_config) VALUES
('SEC-001', 'Default Permission Mode', 'Ensure defaultMode is not set to bypassPermissions for security', 'critical', 'security', 'json_path_not_equals', '{"file": "settings.json", "path": "$.defaultMode", "forbidden_value": "bypassPermissions"}'),
('SEC-002', 'Sensitive Command Deny List', 'Verify deny list contains dangerous commands like rm -rf', 'error', 'security', 'json_path_contains', '{"file": "settings.json", "path": "$.deny", "should_contain": ["rm -rf", "sudo rm"]}'),
('SEC-003', 'No Wildcard Allow All', 'Ensure allow list does not have unrestricted Bash(*)', 'warning', 'security', 'json_path_not_contains', '{"file": "settings.json", "path": "$.allow", "forbidden_value": "Bash(*)"}'),
('BP-001', 'CLAUDE.md Exists', 'Project should have a CLAUDE.md file for context', 'warning', 'best-practice', 'file_exists', '{"file": "CLAUDE.md"}'),
('BP-002', 'CLAUDE.md Has Overview', 'CLAUDE.md should contain an Overview section', 'info', 'best-practice', 'file_regex_match', '{"file": "CLAUDE.md", "pattern": "(?i)##\\s*overview"}'),
('BP-003', 'Skills Directory Exists', 'Project should have a skills directory', 'info', 'best-practice', 'directory_exists', '{"directory": "skills"}'),
('BP-004', 'Commands Directory Exists', 'Project should have a commands directory', 'info', 'best-practice', 'directory_exists', '{"directory": "commands"}'),
('PERF-001', 'MCP Servers Configured', 'Check if MCP servers are configured', 'info', 'performance', 'json_path_exists', '{"file": "settings.json", "path": "$.enabledMcpjsonServers"}'),
('MISS-001', 'Settings JSON Exists', 'settings.json should exist in .claude directory', 'warning', 'missing', 'file_exists', '{"file": "settings.json"}'),
('MISS-002', 'Settings Local JSON Exists', 'settings.local.json for local overrides', 'info', 'missing', 'file_exists', '{"file": "settings.local.json"}');

-- Seed data: External sources to track
INSERT INTO source_sync (source_name, source_type, source_url) VALUES
('claude-code-releases', 'github_releases', 'https://api.github.com/repos/anthropics/claude-code/releases'),
('claude-docs', 'web_scrape', 'https://docs.anthropic.com/en/docs/claude-code'),
('claude-code-changelog', 'github_file', 'https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md');

-- Create view for audit summary
CREATE VIEW audit_summary AS
SELECT
    p.id as project_id,
    p.name as project_name,
    p.path as project_path,
    p.last_seen_at,
    COUNT(CASE WHEN ar.status = 'fail' AND r.severity = 'critical' THEN 1 END) as critical_failures,
    COUNT(CASE WHEN ar.status = 'fail' AND r.severity = 'error' THEN 1 END) as error_failures,
    COUNT(CASE WHEN ar.status = 'fail' AND r.severity = 'warning' THEN 1 END) as warning_failures,
    COUNT(CASE WHEN ar.status = 'fail' AND r.severity = 'info' THEN 1 END) as info_failures,
    COUNT(CASE WHEN ar.status = 'pass' THEN 1 END) as passes,
    MAX(ar.checked_at) as last_audit
FROM projects p
LEFT JOIN audit_results ar ON p.id = ar.project_id
LEFT JOIN rules r ON ar.rule_id = r.id
GROUP BY p.id, p.name, p.path, p.last_seen_at;

-- Create view for overall health
CREATE VIEW overall_health AS
SELECT
    CASE
        WHEN SUM(critical_failures) > 0 THEN 'critical'
        WHEN SUM(error_failures) > 0 THEN 'error'
        WHEN SUM(warning_failures) > 0 THEN 'warning'
        ELSE 'healthy'
    END as status,
    COUNT(DISTINCT project_id) as total_projects,
    SUM(critical_failures) as total_critical,
    SUM(error_failures) as total_errors,
    SUM(warning_failures) as total_warnings,
    SUM(info_failures) as total_info,
    SUM(passes) as total_passes,
    CASE
        WHEN SUM(passes) + SUM(critical_failures) + SUM(error_failures) + SUM(warning_failures) + SUM(info_failures) = 0 THEN 0
        ELSE ROUND(
            100.0 * SUM(passes) /
            (SUM(passes) + SUM(critical_failures) + SUM(error_failures) + SUM(warning_failures) + SUM(info_failures))
        )
    END as health_score
FROM audit_summary;
