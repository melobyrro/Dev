# n8n Claude Config Auditor

This directory contains the n8n stack for the Claude Config Auditor system.

## Overview

The n8n stack receives configuration data from the Mac local agent, stores it in PostgreSQL, runs audit checks against defined rules, and provides a REST API for Home Assistant to poll.

## Components

### Docker Stack
- **PostgreSQL 16** - Stores projects, config snapshots, rules, and audit results
- **n8n** - Workflow automation for webhooks, auditing, and API

### Workflows

| Workflow | Purpose |
|----------|---------|
| Config Sync Webhook | Receives config data from Mac agent at `/webhook/config-sync` |
| Audit Engine | Compares configs against rules, runs hourly and on config sync |
| Status API | Provides audit status at `/webhook/status-api` for HA REST sensor |
| Force Scan | Allows triggering immediate scan from HA at `/webhook/force-scan` |
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
3. Name: `PostgreSQL n8n_auditor`
4. Settings:
   - Host: `postgres`
   - Port: `5432`
   - Database: `n8n_auditor`
   - User: `n8n_admin`
   - Password: (from `.env`)

### 8. Activate workflows

Enable all imported workflows.

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

### Test webhook endpoint

```bash
curl -X POST http://192.168.1.11:5678/webhook/config-sync \
  -H "Content-Type: application/json" \
  -d '{"agent_version":"1.0.0","hostname":"test","projects":[]}'
```

### Test status API

```bash
curl http://192.168.1.11:5678/webhook/status-api
```

### Query database directly

```bash
docker exec -it n8n_postgres psql -U n8n_admin -d n8n_auditor

# Check projects
SELECT * FROM projects;

# Check audit results
SELECT * FROM audit_summary;

# Check overall health
SELECT * FROM overall_health;
```

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

### Workflow execution errors

1. Check n8n Executions tab for error details
2. Verify PostgreSQL credential is configured
3. Check workflow is activated

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
