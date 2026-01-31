# CultoTranscript

> **Inherits from:** [/Dev/CLAUDE.md](../CLAUDE.md) — Read root file for universal dev workflow (git sync, Chrome MCP, Tasks, /done)

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

### 1. Session Start Protocol (MANDATORY)

Before ANY code changes, verify browser access:

**Step 1 — Chrome MCP Check:**
```
Call: mcp__claude-in-chrome__tabs_context_mcp
If unavailable: STOP — inform user, cannot proceed
```

**Step 2 — Navigate to App:**
- Go to https://church.byrroserver.com
- Confirm logged-in session (not on login page)
- Take baseline screenshot for reference

**Step 3 — If Browser Unavailable:**
- STOP immediately
- No code changes allowed without validation capability
- Inform user: "Browser automation unavailable — cannot validate changes"

**Law:** A session without verified browser access cannot make UI-affecting changes.

---

### 2. Execution Discipline

#### Task-Driven Workflow

All multi-step work MUST use tasks:

| Work Type | Requirement |
|-----------|-------------|
| Single trivial fix | Optional task tracking |
| 2+ file changes | MUST use `TaskCreate` |
| Feature work | MUST use `TaskCreate` + validation tasks |

#### Agent Delegation Pattern

| Role | Responsibilities |
|------|------------------|
| **Main context** | Planning, user communication, orchestration |
| **Task agents** | Implementation, file edits, searches |
| **Validation agents** | Browser verification after changes |

**Rule:** Keep main context clean. Delegate implementation and validation to agents.

#### Post-Change Validation Protocol (MANDATORY)

After ANY code change, spawn a validation agent:

```
Subagent Task: Validate <change description>
- Navigate to https://church.byrroserver.com
- Go to <affected page/component>
- Verify: <specific checks — what should be visible/functional>
- Check browser console for errors
- Take screenshot evidence
- Report: PASS with evidence, or FAIL with details
```

**Law:** No change is complete until a validation agent confirms it in the live UI.

---

### 3. Verification Checklist

Before claiming ANY work complete:

| Gate | Requirement | Evidence |
|------|-------------|----------|
| Browser validation | Validation agent PASSED | Screenshot + report |
| No console errors | Console clear of new errors | Console check |
| Multi-tenant check | If channel-scoped, tested with 2 channels | Cross-channel verification |
| Tasks complete | All tasks marked done | Task list clean |
| Temp files cleaned | `.scratch/` cleared | No orphan files |

---

### 4. File Discipline

**Active Directory Rule:** No temp files in project root.

| File Type | Location | Cleanup |
|-----------|----------|---------|
| Temp scripts | `.scratch/` | Delete after use |
| Debug output | `.scratch/` | Delete after use |
| Migration scripts | `scripts/` | Delete after successful run |
| Test data | `.scratch/` | Delete after use |
| Test files | `tests/` | Keep if reusable |

The `.scratch/` directory is gitignored. Use it freely for temporary work.

**Law:** If `ls` shows temp files in project root, the session is non-compliant.

---

### 5. Requirements Documentation

When modifying feature behavior, update documentation in the same commit:

| Change Type | Requires Doc Update? | Where |
|-------------|---------------------|-------|
| New API endpoint | **Yes** | `docs/ARCHITECTURE.md` |
| Changed UI behavior | **Yes** | `docs/ARCHITECTURE.md` |
| New feature | **Yes** | `docs/ARCHITECTURE.md` or new doc |
| Bug fix (same behavior) | No | — |
| Refactor (same behavior) | No | — |

**Law:** A commit that changes behavior without updating documentation is non-compliant.

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
