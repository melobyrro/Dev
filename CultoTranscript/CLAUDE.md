# CultoTranscript

Sermon transcription and analytics platform for Brazilian churches.
Live: https://church.byrroserver.com

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19 + TypeScript + Vite + Zustand |
| Backend | FastAPI + Python 3.11 |
| Database | PostgreSQL 16 + pgvector |
| Queue | Redis |
| AI | Google Gemini 1.5 Flash |
| Transcription | yt-dlp → YouTube API → Whisper (3-tier fallback) |

## Quick Start

```bash
cd docker && docker-compose up -d
# http://localhost:8000 (password: see .env INSTANCE_PASSWORD)
```

## Development Rules

### Session Startup (REQUIRED)

**Before any code changes**, verify browser access:

1. Run `mcp__claude-in-chrome__tabs_context_mcp` to check Chrome connection
2. Navigate to https://church.byrroserver.com
3. Confirm you can interact with the logged-in session
4. If browser unavailable, **STOP** and inform the user

**Why**: Every change must be validated in-browser before claiming completion.

### Task Management

- **Always use tasks** for multi-step work (`TaskCreate`, `TaskUpdate`)
- **Delegate to subagents** for independent work (`Task` tool with appropriate `subagent_type`)
- **Run parallel tasks** when no dependencies exist (single message, multiple `Task` calls)
- **Mark tasks complete** only after browser verification

### Artifact Policy

**Do NOT create one-time files in the project root.**

| Artifact Type | Location | Cleanup |
|---------------|----------|---------|
| Temp scripts | `.scratch/` | Delete after use |
| Debug output | `.scratch/` | Delete after use |
| Migration scripts | `scripts/` | Delete after successful run |
| Test files | `tests/` or `.scratch/` | Keep if reusable |

The `.scratch/` directory is gitignored. Use it freely for temporary work.

### Verification Checklist

Before claiming any work complete:

- [ ] Browser test passed (visual verification at https://church.byrroserver.com)
- [ ] No console errors
- [ ] Multi-tenant check (if channel-scoped feature)
- [ ] Tasks marked complete
- [ ] Temp files in `.scratch/` cleaned up

## Project Structure

```
app/
├── web/           # FastAPI app, routes, Jinja2 templates
├── worker/        # Background transcription + AI analysis
├── scheduler/     # APScheduler (YouTube polling)
├── ai/            # Gemini chatbot, embeddings, theme analysis
└── common/        # Models, database, helpers
Backend/api/v2/    # REST API v2 endpoints (preferred)
UI/src/            # React SPA (pages, components, stores)
migrations/        # SQL schema files
shared/dtos.ts     # TypeScript DTOs (mirrors Backend/dtos.py)
```

## Key Patterns

### Multi-Tenancy (Channel-Scoped)

Every API call must pass `channel_id` explicitly to avoid race conditions:

```typescript
// CORRECT - explicit channel_id
await axios.get('/api/admin/settings', { params: { channel_id } });

// WRONG - relies on session state
await axios.get('/api/admin/settings');
```

Backend uses `resolve_channel_id()` helper to get channel from param or session.

### DTO Synchronization

`Backend/dtos.py` (Python) ↔ `shared/dtos.ts` (TypeScript)

These are manually mirrored. **Update both** when changing API contracts.

### Container Restarts

| Change | Restart Command |
|--------|-----------------|
| Python code | `docker restart culto_web culto_worker` |
| Templates/CSS | `docker restart culto_web` |
| .env changes | `docker restart culto_web culto_worker culto_scheduler` |
| Dockerfile | `docker-compose up -d --build` |

### Production SSH

```bash
ssh byrro@192.168.1.11 "docker restart culto_web culto_worker"
```

## Common Tasks

### Add API Endpoint

1. Add route in `Backend/api/v2/` (preferred) or `app/web/routes/`
2. Add to CSRF exempt list in `app/web/main.py` if needed
3. Update `Backend/dtos.py` + `shared/dtos.ts` if new types

### Run Migration

```bash
docker exec culto_db psql -U culto_admin -d culto < migrations/XXX_file.sql
docker restart culto_web culto_worker
```

### View Logs

```bash
docker logs -f culto_web    # Web server
docker logs -f culto_worker # Background jobs
```

### Clear Redis Queue

```bash
docker exec culto_redis redis-cli FLUSHALL
```

## AI Chatbot

Two knowledge modes controlled by UI toggle:

| Mode | Label | Behavior |
|------|-------|----------|
| `database_only` | "Somente sermões" | Searches local transcripts, cites sermons |
| `global` | "Global / Internet" | Uses Gemini's general Bible knowledge |

Key files: `UI/src/components/AIDrawer.tsx`, `app/ai/chatbot_service.py`

## Testing

### Multi-Tenant Checklist

When modifying channel-scoped features:
1. Switch to Church A, make change, verify saves
2. Switch to Church B, verify A's value NOT shown
3. Make different change in B, verify saves
4. Switch back to A, verify original value intact

## Documentation

- `docs/ARCHITECTURE.md` - Deep technical reference (pipelines, embeddings, SSE)
- `docs/DEPLOYMENT.md` - Production deployment and troubleshooting
