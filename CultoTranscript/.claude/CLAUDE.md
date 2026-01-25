# CultoTranscript - Claude Code Context

## Overview

CultoTranscript is a multi-tenant sermon transcription and analytics platform. Each church (channel) operates in complete isolation with its own configuration, data, and API keys.

### Documentation Structure

- **CLAUDE.md** (this file): Quick reference for common tasks, configurations, APIs, and debugging
- **ARCHITECTURE.md**: Deep technical documentation covering:
  - System design and container interactions
  - 6-step video processing pipeline with examples
  - AI chatbot knowledge modes and embeddings
  - Vector search implementation
  - Database schema and Redis queue patterns
  - SSE real-time updates

**When to use each:**
- Working on a feature? → Check CLAUDE.md first for patterns and common issues
- Understanding how video processing works? → See ARCHITECTURE.md
- Designing new feature that affects multiple containers? → Read ARCHITECTURE.md system design section
- Need quick reference? → CLAUDE.md has it all indexed

## Multi-Tenancy Architecture

### Core Principle
**Every configuration and data item is scoped to a channel.** The system is multi-tenant but config and data are completely separate per church.

### Per-Channel Configuration Tables

| Configuration | Storage Location | Key Fields |
|---------------|------------------|------------|
| Schedule (polling) | `schedule_config` table | `channel_id`, `day_of_week`, `time_of_day` |
| API Keys | `church_api_keys` table | `channel_id`, `provider`, `api_key` |
| Video Duration | `channels` table | `min_video_duration_sec`, `max_video_duration_sec` |
| Default Speaker | `channels` table | `default_speaker_id` |

### API Call Pattern (CRITICAL)

When making API calls from the frontend, **always pass `channel_id` explicitly** as a query parameter. This avoids race conditions between React state updates and backend session changes.

```typescript
// CORRECT: Explicit channel_id
const response = await axios.get('/api/admin/settings/schedule-config', {
    params: { channel_id: selectedChannelId }
});

// WRONG: Relying on session state
const response = await axios.get('/api/admin/settings/schedule-config');
```

**Why?** When switching churches in the UI, `setSelectedChannelId()` triggers a React re-render that calls `loadAdminData()` before the `switchChurch` API completes. Without explicit `channel_id`, you may get data from the wrong church.

### Backend Resolution Pattern

Backend endpoints should use a `resolve_channel_id` helper:

```python
def resolve_channel_id(request: Request, explicit_id: Optional[int] = None) -> int:
    """Get channel_id from explicit param, falling back to session."""
    if explicit_id:
        return explicit_id
    return request.session.get("channel_id", 1)
```

## Key Files

### Models
- `app/common/models.py` - SQLAlchemy models including `Channel`, `ScheduleConfig`, `ChurchApiKey`

### API Routes
- `app/web/routes/api.py` - Admin API endpoints with per-channel configuration
- `Backend/api/v2/` - v2 API routes for videos, chat, events

### Frontend
- `UI/src/pages/Admin.tsx` - Consolidated admin panel (schedule, AI config, duration settings)
- `UI/src/stores/` - Zustand stores for state management

### Migrations
- `migrations/036_per_channel_schedule.sql` - Schedule config per church
- `migrations/037_per_channel_duration_settings.sql` - Duration settings per church

## CSRF Configuration

The CSRF middleware exempts certain API paths. Configuration is in `app/web/main.py` (not in the middleware file itself):

```python
app.add_middleware(
    CSRFMiddleware,
    exempt_paths=[
        "/api/login", "/api/register",
        "/api/admin/settings/",  # Admin settings APIs
        "/api/v2/",              # v2 API
        # ... other paths
    ]
)
```

**Note:** If you add new admin API paths, ensure they're covered by the exempt list or include CSRF tokens.

## Testing

### Browser Testing (Required)
Before claiming any UI change is complete, **test it via browser**. Use Chrome DevTools MCP:

```
mcp__chrome-devtools__navigate_page - Navigate to URL
mcp__chrome-devtools__take_snapshot - Get page state
mcp__chrome-devtools__click - Click elements
mcp__chrome-devtools__fill - Fill inputs
```

### Multi-Tenant Test Checklist
When modifying configuration features:
1. Switch to Church A, make a change, verify it saves
2. Switch to Church B, verify Church A's value is NOT shown
3. Make a different change in Church B, verify it saves
4. Switch back to Church A, verify original value is still there

## Common Patterns

### Adding a New Per-Channel Setting

1. **Migration**: Add column to `channels` table or create a new table with `channel_id` foreign key
2. **Model**: Update SQLAlchemy model in `models.py`
3. **API GET**: Accept `channel_id` query param, use `resolve_channel_id()`, query by channel
4. **API PUT/POST**: Accept `channel_id` query param, update the specific channel's record
5. **Frontend**: Pass `channel_id` explicitly in all API calls
6. **Test**: Verify changes don't leak between churches

### API Key Display Pattern

For sensitive data like API keys, return only the last few characters:

```python
# Backend
"key_info": {
    "last_five": api_key[-5:] if api_key else None,
    "provider": "gemini"
}

# Frontend
setCurrentApiKeyMasked(lastFive ? `****${lastFive}` : '');
```

## AI Chatbot

The chatbot is a sliding drawer panel that helps users explore sermon content or ask general Bible/theology questions.

### Knowledge Mode Toggle

The chatbot has a toggle button at the bottom with two modes:

| Mode | Button Label | Behavior |
|------|--------------|----------|
| `database_only` | "Somente sermões" | Searches local sermon transcripts, cites specific sermons, refuses to answer if no relevant content found |
| `global` | "Global / Internet" | Uses Gemini's general knowledge of the Bible and theology, ignores local sermons entirely |

### Data Flow

```
UI (AIDrawer.tsx)
    ↓ mode stored in chatStore (Zustand)
    ↓
chatService.sendMessage(channelId, message, sessionId, mode)
    ↓
POST /api/v2/channels/{id}/chat  (knowledge_mode in body)
    ↓
chatbot_service._build_prompt(... knowledge_mode=mode)
    ↓
Different prompt templates based on mode
```

### Key Files

- `UI/src/components/AIDrawer.tsx` - Drawer UI with mode toggle buttons
- `UI/src/stores/chatStore.ts` - Zustand store holding `mode` state
- `UI/src/services/chatService.ts` - API client passing mode to backend
- `Backend/api/v2/chat.py` - v2 API endpoint receiving `knowledge_mode`
- `app/ai/chatbot_service.py` - `_build_prompt()` method with mode-specific prompts

### Prompt Behavior by Mode

**database_only (Somente sermões)**:
- Identity: "assistente teológico especializado em sermões desta igreja"
- Searches `transcript_embeddings` table using hybrid BM25 + vector search
- Must cite sermon title, date, and speaker
- If no relevant sermons found: "Nos sermões disponíveis, não encontrei referência direta a..."

**global (Global / Internet)**:
- Identity: "assistente bíblico e teológico conhecedor da Bíblia"
- Skips all sermon retrieval
- Uses Gemini's training knowledge about the Bible
- Can quote scripture, explain theology, answer "What is Genesis 1?" type questions

### Channel Scoping

The chatbot is channel-aware:
- `channelId` comes from `videoStore.selectedChannelId`
- Sermon searches are filtered by channel
- Chat history (`gemini_chat_history` table) is keyed by `channel_id` + `session_id`
- Each church's chatbot only sees its own sermons

## Video Detail Drawer

The video detail drawer is a sliding panel that displays comprehensive sermon information when a user clicks on a video in the list.

### Features

| Feature | Description |
|---------|-------------|
| Sermon Title | Displays suggested title or original YouTube title |
| Metadata | Date, duration, word count, speaker |
| YouTube Link | Direct link to watch on YouTube |
| Biblical Texts | Passages referenced in the sermon |
| Central Theme | AI-extracted main theme |
| Main Points | Key points from the sermon |
| Practical Application | Actionable takeaways |
| Full Transcript | Collapsible section with formatted text |

### YouTube Link

The drawer includes a "Ver no YouTube" link positioned between the metadata (speaker) and the biblical texts section. This link:
- Uses the `youtube_id` field stored in the `videos` table
- Opens in a new tab (`target="_blank"`)
- Displays with a YouTube icon in red (`text-red-600`)
- Works for all videos (existing and new) since `youtube_id` is a required field

### Key Files

- `UI/src/components/VideoDetailDrawer.tsx` - Main drawer component
- `Backend/api/v2/videos.py` - `/videos/{id}/detailed-report` endpoint
- `shared/dtos.ts` - `VideoDetailedReportDTO` type definition

### Data Flow

```
User clicks video in list
    ↓
VideoDetailDrawer opens (selectedVideoId set)
    ↓
GET /api/v2/videos/{id}/detailed-report
    ↓
Backend returns VideoDetailedReportDTO (includes youtube_id)
    ↓
Drawer renders all sections including YouTube link
```

## Environment

- **Python**: 3.11+ with FastAPI, SQLAlchemy
- **Frontend**: React 18 + Vite + TypeScript + Zustand
- **Database**: PostgreSQL 16 with pgvector
- **Queue**: Redis 7
- **Deployment**: Docker Compose with Caddy reverse proxy

## Transcription Pipeline

The worker uses a **3-tier waterfall strategy** for transcription:

| Tier | Method | Speed | When Used |
|------|--------|-------|-----------|
| 1 | yt-dlp auto-captions | Seconds | YouTube has auto-CC available |
| 2 | youtube-transcript-api | Seconds | Official transcripts exist |
| 3 | faster-whisper (local AI) | Minutes | Fallback, runs on Intel GPU |

**Key file**: `app/worker/transcription_service.py`

## Video Processing Pipeline

6-step pipeline executed by the worker:

| Step | Action | Progress |
|------|--------|----------|
| 1 | Extract YouTube metadata | 10% |
| 2 | Validate duration (min/max) | 20% |
| 3 | Transcribe (3-tier waterfall) | 30-50% |
| 4 | Detect sermon start (skip intro) | 60% |
| 5 | Advanced analytics (Gemini) | 70% |
| 6 | Generate embeddings (pgvector) | 90% |

**Status flow**: `processing` → steps 1-6 → `completed` (or `failed`)

**Critical**: Only step 6 completion marks video as `completed`. Never set this status elsewhere.

**Key files**:
- `app/worker/main.py` - Job loop and pipeline orchestration
- `app/common/models.py` - Job and Video models

## SSE Real-time Updates

Real-time status updates flow from worker to browser:

```
Worker (broadcast_processing)
    ↓ POST /api/v2/events/broadcast
SSE Manager (queues to clients)
    ↓ GET /api/v2/events/stream
Browser (EventSource listener)
```

**Event types**: `video.status`, `summary.ready`, `error`, `heartbeat`

**Key files**:
- `Backend/api/v2/events.py` - SSE endpoints
- `app/worker/sse_broadcaster.py` - Worker broadcast helpers
- `UI/src/hooks/useSSE.ts` - React hook for SSE connection

### SSE Integration in React

The `useSSE` hook is called in `App.tsx` to establish the SSE connection:

```typescript
// UI/src/App.tsx
import { useSSE } from './hooks/useSSE';

function AppContent() {
    useSSE(); // Establishes SSE connection
    // ...
}
```

**CRITICAL**: The SSE endpoints must be in `public_paths` in `auth.py`:
```python
public_paths = [
    # ... other paths
    "/api/v2/events/broadcast",  # Worker broadcasts (has internal IP check)
    "/api/v2/events/stream",     # SSE stream for clients
]
```

Without this, the auth middleware blocks SSE connections and worker broadcasts.

## Authentication

**Type**: Session-based with instance password

```python
request.session["authenticated"] = True/False
request.session["channel_id"] = int  # Current church
```

**Multi-church roles**: `owner` > `admin` > `user`

**Key file**: `app/web/auth.py`

## Configuration Hot-Reload

Workers can reload config without restart:

1. Admin saves new API key in UI
2. Backend sets Redis flag: `config_reload_requested=true`
3. Worker detects flag, reloads from DB
4. Resets LLM/Gemini/Embedding singletons

## Scheduler

The scheduler (`culto_scheduler`) checks YouTube channels for new videos on a per-channel schedule.

### Schedule Configuration

Schedules are stored in `schedule_config` table (singular, not plural):

| Column | Type | Description |
|--------|------|-------------|
| `channel_id` | int | FK to channels |
| `day_of_week` | int | 0=Monday, 1=Tuesday, ... 6=Sunday |
| `time_of_day` | time | HH:MM:SS in UTC |
| `enabled` | bool | Whether schedule is active |

### Day of Week Mapping

```
0 = Monday (mon)
1 = Tuesday (tue)
2 = Wednesday (wed)
3 = Thursday (thu)
4 = Friday (fri)
5 = Saturday (sat)
6 = Sunday (sun)
```

### CRITICAL: Restart Required After Config Changes

**The scheduler reads config only at startup.** If you change a channel's schedule in the admin UI, you must restart the scheduler container for changes to take effect:

```bash
# On the Docker host (192.168.1.11)
cd /home/byrro/CultoTranscript/docker
docker compose restart scheduler
```

The scheduler runs an initial check on startup, so restarting will also trigger an immediate scan of all channels.

### Verifying Schedule

Check current scheduled jobs:
```bash
docker logs culto_scheduler --tail=50 | grep "Scheduled:"
```

Example output:
```
Scheduled: Check 'Igreja Vida Abundante' (sun at 19:57)
Scheduled: Check 'Igreja Presbiteriana da Ilha' (sun at 19:56)
```

### Key File

- `app/scheduler/main.py` - Scheduler entry point, reads `schedule_config` table

## Docker Networking (CRITICAL)

### Network Architecture

The CultoTranscript stack runs on `culto_culto_network`, but the `culto_web` container must ALSO be on `byrro-net` for the host-level Caddy reverse proxy to reach it.

```
Internet → Cloudflare → Host Caddy (byrro-net) → culto_web → culto_network services
```

### Redis Hostname Resolution Issue

**Problem**: The host has multiple Redis instances on `byrro-net`:
- `authelia-redis`
- `paperless-redis`
- `immich-redis`
- `dawarich-redis`

If `culto_web` is on `byrro-net`, the hostname `redis` may resolve to the WRONG Redis instance (e.g., `authelia-redis` instead of `culto_redis`).

**Solution**: Always use explicit container name `culto_redis` in REDIS_URL:

```yaml
# docker-compose.yml - CORRECT
environment:
  - REDIS_URL=redis://culto_redis:6379/0

# WRONG - may resolve to wrong Redis on byrro-net
environment:
  - REDIS_URL=redis://redis:6379/0
```

### External Volumes

The database and Redis data are stored in named volumes that persist across container recreations:

```yaml
volumes:
  postgres_data:
    name: docker_postgres_data
    external: true
  redis_data:
    name: docker_redis_data
    external: true
```

**CRITICAL**: If you change the compose project name or recreate containers without `external: true`, Docker will create NEW empty volumes and you'll lose all data!

### After Container Recreation

When containers are recreated with `docker compose up -d`, the web container loses its `byrro-net` connection. You MUST reconnect it:

```bash
# Reconnect web to byrro-net for external access
docker network connect byrro-net culto_web

# Verify both networks are connected
docker inspect culto_web --format '{{json .NetworkSettings.Networks}}' | python3 -c 'import json,sys; d=json.load(sys.stdin); print("\n".join(d.keys()))'
# Should show: byrro-net AND culto_culto_network
```

### Docker Compose Commands

Always use project name `-p culto` to ensure consistency:

```bash
cd /home/byrro/CultoTranscript/docker

# Start/restart services
docker compose -p culto up -d

# Recreate a specific service
docker compose -p culto up -d --force-recreate web

# View logs
docker compose -p culto logs -f worker

# Stop everything
docker compose -p culto down
```

### Debugging Network Issues

```bash
# Check which IP redis resolves to from web container
docker exec culto_web python3 -c "import socket; print(socket.gethostbyname('redis'))"

# Check which IP culto_redis resolves to (should be same network)
docker exec culto_web python3 -c "import socket; print(socket.gethostbyname('culto_redis'))"

# Test Redis connection
docker exec culto_web python3 -c "from app.common.redis_client import redis_client; print(redis_client.ping())"

# Check Redis queue
docker exec culto_web python3 -c "from app.common.redis_client import redis_client; print(redis_client.lrange('transcription_queue', 0, -1))"
```

## Docker Development

**Start stack**:
```bash
cd docker && docker-compose up -d
```

**View logs**:
```bash
docker-compose logs -f worker   # Worker processing
docker-compose logs -f web      # API requests
```

**Shell into service**:
```bash
docker-compose exec worker bash
docker-compose exec db psql -U culto_admin -d culto
```

**Restart after code changes**:
```bash
docker-compose restart worker  # For worker code
docker-compose restart web     # For API code
```

## Frontend Deployment

The React frontend is built with Vite and served as static files by FastAPI.

### Build and Deploy Process

```bash
# 1. Build the frontend (from UI directory)
cd /Users/andrebyrro/Dev/CultoTranscript/UI && npm run build

# 2. Copy built assets to server
scp -r /Users/andrebyrro/Dev/CultoTranscript/UI/dist/assets/* byrro@192.168.1.11:/home/byrro/CultoTranscript/app/web/static/assets/

# 3. Copy updated index.html (contains new bundle filenames)
scp /Users/andrebyrro/Dev/CultoTranscript/app/web/templates/index.html byrro@192.168.1.11:/home/byrro/CultoTranscript/app/web/templates/

# 4. If you changed main.py (routing), copy that too
scp /Users/andrebyrro/Dev/CultoTranscript/app/web/main.py byrro@192.168.1.11:/home/byrro/CultoTranscript/app/web/

# 5. Restart web container
ssh byrro@192.168.1.11 "cd /home/byrro/CultoTranscript/docker && docker compose restart web"
```

### Updating index.html Bundle References

After each build, Vite generates new hashed filenames. Update `app/web/templates/index.html`:

```html
<!-- Check UI/dist/index.html for the new filenames -->
<script type="module" crossorigin src="/static/assets/index-NEWHASH.js"></script>
<link rel="stylesheet" crossorigin href="/static/assets/index-NEWHASH.css">
```

### Important Notes

- **Bundle filenames include hashes** (e.g., `index-Cl9KggVv.js`). After each build, the filenames change.
- **Always update `index.html`** in `app/web/templates/` to reference the new bundle filenames.
- **Stale builds cause bugs**: If the deployed JS doesn't match source code, features may appear broken (e.g., missing `channel_id` in API calls).
- **Verify deployment**: Check browser DevTools Network tab to confirm the correct bundle is loaded.

### Quick Verification

After deploying, verify the build is current:
1. Open browser DevTools → Network tab
2. Look for API calls (e.g., `/api/schedule-config`)
3. Confirm query parameters match source code (e.g., `?channel_id=X`)

**Services**:
| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| db | culto_db | 5432 | PostgreSQL + pgvector |
| redis | culto_redis | 6379 | Job queue + cache |
| web | culto_web | 8000 | FastAPI app |
| worker | culto_worker | - | Background jobs |
| scheduler | culto_scheduler | 8001 | Periodic tasks |
| caddy | culto_caddy | 18080/18443 | Reverse proxy |

## TypeScript Patterns

### ID Types

Channel and Video IDs are **strings** in the frontend (from DTOs), not numbers:

```typescript
// shared/dtos.ts
export interface ChannelDTO {
    id: string;  // NOT number
    // ...
}

// When using as Record keys:
const statsMap: Record<string, ChannelStats> = {};  // string keys
statsMap[channel.id] = stats;  // Works because channel.id is string
```

### Promise.all Type Annotations

When using `Promise.all` with `forEach`, explicitly type the callback parameter:

```typescript
// Without type annotation: TypeScript can't infer result.id type
statsResults.forEach((result) => {
    statsMap[result.id] = result.stats;  // Error: result.id is 'any'
});

// With type annotation: Works correctly
statsResults.forEach((result: { id: string; stats: Stats | null }) => {
    if (result.stats) {
        statsMap[result.id] = result.stats;  // OK
    }
});
```

## Common Debugging

| Issue | Check |
|-------|-------|
| SSE not updating | Check: 1) useSSE hook called in App.tsx, 2) SSE endpoints in auth.py public_paths, 3) `docker logs culto_web` |
| Worker broadcasts failing (500) | SSE broadcast endpoint not in auth.py public_paths |
| Job stuck "running" | Worker alive? `docker ps`, check `jobs` table |
| Job stuck "queued" | Redis connection issue - check if web/worker use same Redis (see Docker Networking section) |
| 502 Bad Gateway | Web container not on `byrro-net`? Run `docker network connect byrro-net culto_web` |
| Reprocess not working | Jobs in DB but not Redis? Check REDIS_URL uses `culto_redis` not `redis` |
| Whisper slow | GPU available? Check `WHISPER_DEVICE` env var |
| Config not reloading | `redis-cli GET config_reload_requested` |
| Frontend feature broken | Stale build? Check Network tab for missing query params, rebuild & redeploy |
| Settings not per-channel | Missing `channel_id` param? Check API calls include `?channel_id=X` |
| Schedule not running at expected time | Scheduler needs restart after config change: `docker compose restart scheduler` |
| Wrong day of week in schedule | Check `day_of_week` mapping: 0=Mon, 5=Sat, 6=Sun (not 0=Sun!) |
| Data missing after container recreate | Wrong volume? Check `external: true` in docker-compose.yml volumes section |

## Frontend Architecture

### Single React SPA (Post-Migration)

The frontend is a **single React SPA** that handles all routing. Previously, some routes served Jinja templates while others served React, causing feature fragmentation (e.g., SSE only worked on React pages). This was consolidated in January 2026.

**All routes now serve `index.html` (React SPA)**:
- FastAPI returns `templates.TemplateResponse("index.html", {"request": request})`
- React Router handles client-side routing
- No more Jinja templates for user-facing pages

### Navigation Structure

| Tab | Route | Purpose |
|-----|-------|---------|
| Inicio | `/` | Video list with search/filter |
| Relatorios | `/reports` | Analytics dashboard (stats, biblical books, themes) |
| Admin | `/admin` | All admin functions (import, config, schedule, AI, members, channels) |
| Sermões | `/database` | Video management (select, delete, reprocess) |

### Key React Pages

| File | Route | Features |
|------|-------|----------|
| `UI/src/components/VideoList.tsx` | `/` | Main video list, search, filters |
| `UI/src/pages/Reports.tsx` | `/reports` | Stats cards, progress bar, monthly analytics |
| `UI/src/pages/Admin.tsx` | `/admin` | Import, config, schedule, AI settings, members, channels |
| `UI/src/pages/Database.tsx` | `/database` | Video table with checkboxes, delete, reprocess |
| `UI/src/pages/Login.tsx` | `/login` | Authentication |
| `UI/src/pages/Register.tsx` | `/register` | New user registration |
| `UI/src/pages/ForgotPassword.tsx` | `/forgot-password` | Password reset request |
| `UI/src/pages/ResetPassword.tsx` | `/reset-password` | New password form (with token) |
| `UI/src/pages/AcceptInvite.tsx` | `/accept-invite` | Church invitation acceptance |

### Sermões Page (Video Management)

The Sermões page (`/database`) provides video management with:

**Features:**
- Checkboxes for selecting multiple videos
- "Reprocessar" button - replaces all AI-generated metadata
- "Excluir" button - permanently deletes video and all dependencies
- Bulk actions when multiple videos selected
- Confirmation dialogs for destructive actions

**API Endpoints Used:**
- `DELETE /api/v2/videos/{id}` - Delete video and dependencies
- `POST /api/v2/videos/{id}/reprocess` - Queue video for reprocessing

**Key Implementation:**
```typescript
// Selection state
const [selectedVideos, setSelectedVideos] = useState<Set<string>>(new Set());

// Delete handler
const handleDelete = async (videoId: string) => {
    await videoService.deleteVideo(videoId);
    // Refresh list
};

// Reprocess handler
const handleReprocess = async (videoId: string) => {
    await videoService.reprocessVideo(videoId);
    // Show success message
};
```

### Adding New React Pages

When adding a new page to the React SPA:

1. **Create the page component** in `UI/src/pages/YourPage.tsx`

2. **Add the route** in `UI/src/App.tsx`:
   ```typescript
   import YourPage from './pages/YourPage';

   // In Routes:
   <Route path="/your-page" element={<YourPage />} />

   // Or protected:
   <Route path="/your-page" element={
       <ProtectedRoute>
           <YourPage />
       </ProtectedRoute>
   } />
   ```

3. **Add navigation link** in `UI/src/components/TopAppBar.tsx`:
   ```typescript
   const navLinks = [
       { label: 'Inicio', path: '/' },
       { label: 'YourPage', path: '/your-page' },
       // ...
   ];
   ```

4. **Add FastAPI route** in `app/web/main.py`:
   ```python
   @app.get("/your-page")
   async def your_page(request: Request):
       return templates.TemplateResponse("index.html", {"request": request})
   ```

5. **Update auth middleware** if needed (in `app/web/auth.py`):
   - Add to `public_paths` if no auth required
   - Otherwise, auth middleware will require login

6. **Build and deploy**:
   ```bash
   cd UI && npm run build
   scp -r dist/assets/* byrro@192.168.1.11:/home/byrro/CultoTranscript/app/web/static/assets/
   scp app/web/templates/index.html byrro@192.168.1.11:/home/byrro/CultoTranscript/app/web/templates/
   ssh byrro@192.168.1.11 "cd /home/byrro/CultoTranscript/docker && docker compose restart web"
   ```

### Public vs Protected Routes

**Public routes** (no login required):
- `/login`, `/register`
- `/forgot-password`, `/reset-password`, `/accept-invite`

**Protected routes** (require login):
- `/` (videos), `/reports`, `/admin`, `/database`

**Role-based routes:**
- `/admin` - requires `admin` or `owner` role
- `/database` - requires `admin` or higher (superadmin for some features)

Protection is handled by `<ProtectedRoute>` wrapper in App.tsx and `AuthMiddleware` in backend.

## Documentation Maintenance

### When to Update ARCHITECTURE.md

Update `ARCHITECTURE.md` if you:

1. **Change container structure**
   - Add/remove containers (e.g., new worker type)
   - Change container roles or responsibilities
   - Add new inter-container communication patterns
   - → Update "System Design" section

2. **Change video processing pipeline**
   - Add/remove/reorder processing steps
   - Change how embeddings are generated
   - Update transcription strategy
   - → Update "Video Processing Pipeline" section

3. **Change AI/chatbot functionality**
   - Add new knowledge modes
   - Change embedding model
   - Update RAG (retrieval-augmented generation)
   - → Update "AI Chatbot" and "Vector Embeddings" sections

4. **Change database schema significantly**
   - Add new tables affecting core flow
   - Change how data is stored/queried
   - → Update "Data Storage" section

5. **Change job queue or async patterns**
   - Modify Redis queue structure
   - Change job retry logic
   - Update worker loop
   - → Update "Redis Queue" section

### When to Update CLAUDE.md

Update `CLAUDE.md` (this file) if you:

1. **Add/change configuration**
   - New environment variables
   - New API keys or settings
   - → Update "Multi-Tenancy Architecture" section

2. **Add/change common API patterns**
   - New endpoints
   - New parameter patterns
   - → Update "Common Patterns" section

3. **Discover new debugging tips**
   - New common issues found
   - New debugging commands
   - → Update "Common Debugging" table

4. **Change Docker networking**
   - Update compose file structure
   - Change how containers connect
   - → Update "Docker Networking" section

5. **Change deployment process**
   - New frontend build steps
   - New deployment checklist
   - → Update "Frontend Deployment" section

### Quick Update Checklist

When implementing a significant feature:
- [ ] Update ARCHITECTURE.md (if affects system design)
- [ ] Update CLAUDE.md (if affects configurations/patterns)
- [ ] Update docker-compose.yml comments (if changes containers)
- [ ] Run `docker compose -p culto up -d` to verify
- [ ] Test in browser to verify no regressions

## Related Documentation

- `ARCHITECTURE.md` - Full system architecture with technical deep-dives
- `/docker/docker-compose.yml` - Container configuration (source of truth for services)

## Sync Protocol

This project syncs via the Dev monorepo. See `/CLAUDE.md` for system-wide context.
Check `/PLANS/` for pending tasks from ChatGPT before starting new work.
