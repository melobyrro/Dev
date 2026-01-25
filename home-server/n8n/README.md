# n8n Claude Config Auditor

This directory contains the n8n stack for the Claude Config Auditor system.

## Overview

The n8n stack scans GitHub repositories for Claude Code configuration files, stores them in PostgreSQL, runs audit checks against defined rules, and provides a REST API for Home Assistant to poll.

**Key Design:** GitHub is the source of truth. n8n pulls configs directly from your GitHub repos on a schedule - no local scripts needed.

## Components

### Docker Stack
- **PostgreSQL 16** - Stores projects, config snapshots, rules, and audit results
- **n8n** - Workflow automation for webhooks, auditing, and API

### Workflows

| Workflow | Purpose |
|----------|---------|
| **GitHub Repo Scanner** | Scans all GitHub repos for `.claude/` directories (every 6 hours) |
| Config Sync Webhook | Legacy: Receives config data from Mac agent at `/webhook/config-sync` |
| Audit Engine | Compares configs against rules, runs hourly and after scans |
| Status API | Provides audit status at `/webhook/status-api` for HA REST sensor |
| Force Scan | Triggers GitHub scan immediately from HA at `/webhook/force-scan` |
| Source Collector | Fetches Claude docs/releases every 6 hours for rule candidates |

## Deployment

### 1. SSH to Docker VM

```bash
ssh byrro@192.168.1.11
```

### 2. Create directory and copy files

```bash
mkdir -p /home/byrro/docker/n8n
```

Copy these files from your Mac:
- `docker-compose.yml`
- `init.sql`
- `.env` (create from `.env.example`)

### 3. Create .env file

```bash
cd /home/byrro/docker/n8n
cat > .env << 'EOF'
POSTGRES_PASSWORD=<generate_secure_password>
N8N_USER=admin
N8N_PASSWORD=<generate_secure_password>
EOF
chmod 600 .env
```

### 4. Start the stack

```bash
docker compose up -d
```

### 5. Verify containers

```bash
docker ps | grep -E 'n8n|postgres'
```

Expected output:
- `n8n_postgres` - healthy
- `n8n` - running

### 6. Import workflows

1. Access n8n at `http://192.168.1.11:5678`
2. Login with credentials from `.env`
3. Go to Settings > Import
4. Import each workflow JSON from `workflows/` directory

### 7. Configure PostgreSQL credential in n8n

1. Go to Credentials > Add Credential
2. Type: PostgreSQL
3. Name: `PostgreSQL Auditor DB`
4. Settings:
   - Host: `postgres`
   - Port: `5432`
   - Database: `n8n_auditor`
   - User: `n8n_admin`
   - Password: (from `.env`)

### 8. Configure GitHub credentials (NEW)

You need TWO credentials for GitHub access:

#### A. Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name: `n8n-claude-config-auditor`
4. Scopes: Select `repo` (full access to private repos)
   - Or just `public_repo` if you only have public repos
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again)

#### B. Add GitHub API credential in n8n

1. Go to Credentials > Add Credential
2. Type: **GitHub API**
3. Name: `GitHub PAT`
4. Settings:
   - Access Token: (paste your PAT)
5. Save

#### C. Add HTTP Header Auth credential in n8n

This is needed for the HTTP Request nodes that fetch file contents:

1. Go to Credentials > Add Credential
2. Type: **Header Auth**
3. Name: `GitHub Header Auth`
4. Settings:
   - Name: `Authorization`
   - Value: `Bearer <your-github-pat>` (replace with your actual PAT)
5. Save

### 9. Update workflow credentials

After importing the GitHub Repo Scanner workflow:

1. Open the workflow
2. For each node that shows a credential error:
   - Click the node
   - Select the appropriate credential you created
3. Save the workflow

### 10. Activate workflows

Enable all imported workflows, especially:
- GitHub Repo Scanner
- Audit Engine
- Status API
- Force Scan

### 11. Test the setup

```bash
# Trigger a manual scan
curl -X POST http://192.168.1.11:5678/webhook/force-scan

# Check the status API
curl http://192.168.1.11:5678/webhook/status-api | jq
```

## Database Schema

| Table | Purpose |
|-------|---------|
| `projects` | Tracked Claude Code projects |
| `config_snapshots` | Historical config snapshots with settings, CLAUDE.md, etc. |
| `rules` | Audit rules with severity and check logic |
| `candidates` | Pending rule discoveries from external sources |
| `audit_results` | Results of rule checks per project/snapshot |
| `source_sync` | External source tracking for docs/releases |

### Views

| View | Purpose |
|------|---------|
| `audit_summary` | Per-project audit status summary |
| `overall_health` | System-wide health score and status |

## Seed Rules

The `init.sql` includes 10 seed rules:

| ID | Name | Severity |
|----|------|----------|
| SEC-001 | Default Permission Mode | critical |
| SEC-002 | Sensitive Command Deny List | error |
| SEC-003 | No Wildcard Allow All | warning |
| BP-001 | CLAUDE.md Exists | warning |
| BP-002 | CLAUDE.md Has Overview | info |
| BP-003 | Skills Directory Exists | info |
| BP-004 | Commands Directory Exists | info |
| PERF-001 | MCP Servers Configured | info |
| MISS-001 | Settings JSON Exists | warning |
| MISS-002 | Settings Local JSON Exists | info |

## Testing

### Test GitHub scanner (force scan)

```bash
curl -X POST http://192.168.1.11:5678/webhook/force-scan
```

### Test status API

```bash
curl http://192.168.1.11:5678/webhook/status-api | jq
```

### Query database directly

```bash
docker exec -it n8n_postgres psql -U n8n_admin -d n8n_auditor

# Check projects
SELECT name, path, last_seen_at FROM projects;

# Check audit results
SELECT * FROM audit_summary;

# Check overall health
SELECT * FROM overall_health;
```

### Verify HA sensors

1. Go to Home Assistant Developer Tools > States
2. Search for `claude_config`
3. Verify sensors show real data (not "unavailable")

## Cleanup Old Local Agent (Optional)

After GitHub integration is working, you can remove the old local Mac agent:

```bash
# Unload and remove launchd agent
launchctl unload ~/Library/LaunchAgents/com.byrro.claude-config-auditor.plist
rm ~/Library/LaunchAgents/com.byrro.claude-config-auditor.plist

# Remove agent directory
rm -rf ~/Dev/claude-config-auditor
```

You can also disable the Config Sync Webhook workflow in n8n if no longer needed.

## Troubleshooting

### n8n not starting

Check logs:
```bash
docker logs n8n
```

Common issues:
- PostgreSQL not ready (wait for health check)
- Port 5678 already in use
- Invalid credentials in `.env`

### PostgreSQL connection issues

Check PostgreSQL is healthy:
```bash
docker exec n8n_postgres pg_isready -U n8n_admin -d n8n_auditor
```

### GitHub API rate limiting

If you see 403 errors with "rate limit exceeded":
- Wait for the rate limit to reset (usually 1 hour)
- Reduce scan frequency
- Use a PAT with higher rate limits

### Workflow execution errors

1. Check n8n Executions tab for error details
2. Verify PostgreSQL credential is configured
3. Verify GitHub credentials are configured
4. Check workflow is activated

### No repos discovered

1. Verify GitHub PAT has correct scopes
2. Check that your repos have `.claude/` directories
3. Look at the GitHub Repo Scanner execution logs

## Rollback

To completely remove:

```bash
cd /home/byrro/docker/n8n
docker compose down -v  # Warning: deletes all data
```

To restart without losing data:

```bash
docker compose restart
```
