# RELIABILITY_AUDIT.md

## Executive Summary
CultoTranscript has a solid architectural vision (web + worker + scheduler + Redis + Postgres + SSE + optional React UI), but the current repo has multiple **P0/P1 reliability blockers**: missing Python modules, missing dependencies in the worker image, schema drift between models and migrations, and queue/constraint mismatches that prevent key workflows (re-analysis, scheduling, and SSE) from running reliably. Several components appear partially migrated (Backend v2, React UI), creating duplicated paths and stale references. Before any refactor, the system needs stabilization: fix import-time failures, align schema with code, restore queue consistency, and add minimal test/observability gates.

## System Map
### Components & Entrypoints
- **Web (FastAPI)**: `app/web/main.py` (uvicorn entrypoint). Routes in `app/web/routes/*`, template rendering in `app/web/templates/*`. Optional v2 routers from `Backend/api/v2/*` are conditionally imported in `app/web/main.py`.
- **Worker**: `app/worker/main.py` (Redis BLPOP consumer) + services in `app/worker/*` (transcription, analytics, embeddings, SSE broadcast).
- **Scheduler**: `app/scheduler/main.py` (APScheduler + health endpoint on port 8001).
- **SSE**: `Backend/api/v2/events.py` + `Backend/services/sse_manager.py`, consumed by worker via `app/worker/sse_broadcaster.py`.
- **Data Stores**: PostgreSQL (pgvector) + Redis (queue/cache) via `docker/docker-compose.yml`.
- **Optional LLM backend**: Ollama container `culto_ollama`.
- **UI**:
  - Server-rendered Jinja templates in `app/web/templates/*` (active).
  - React UI in `UI/` (incomplete/placeholder, not wired in Docker build).

### Execution Paths (Dev/Build/Run/Jobs/Webhooks)
- **Local dev (Docker)**: `start.sh` → `docker/docker-compose.yml` (web/worker/scheduler/db/redis/ollama). `start-dev.sh` additionally starts Vite (`UI/`).
- **Local dev (no Docker)**: README instructs `python -m app.web.main`, `python -m app.worker.main`, `python -m app.scheduler.main`.
- **Build**: `docker/web.Dockerfile` and `docker/worker.Dockerfile`; UI uses `npm run build` (Vite).
- **Runtime**: web receives requests, creates DB `jobs` entries, pushes to Redis `transcription_queue`; worker consumes, updates DB, broadcasts SSE; scheduler polls YouTube and enqueues jobs; websub callback enqueues jobs for uploads.
- **Queues**: Redis list `transcription_queue` (worker BLPOP) and various cache keys (chatbot).
- **Webhooks**: YouTube WebSub endpoints in `app/web/routes/websub.py`.

### Environments & Config Layering
- **Environment files**: `.env` (local, ignored), `.env.example` (documented defaults), `docker/.env` (mounted into web container).
- **Docker Compose** injects env vars (db/redis/LLM/keys) (`docker/docker-compose.yml:45-59`).
- **DB-backed config**: `SystemSettings` table overrides key settings (Gemini API key, AI provider) in `app/web/main.py:104-133` and `app/worker/main.py:704-729`.
- **Per-church keys**: `church_api_keys` table (but missing migration).
- **Feature flags**: `ENABLE_ANALYTICS_CACHE`, `ENABLE_LAZY_ANALYTICS`, chatbot/embedding flags in `.env.example`.

## Consistency & Drift Summary
- **Dual backends/UI**: `Backend/` (v2 API/SSE) and `app/` (v1/v2 hybrid), plus a React UI that is not integrated into Docker build. This creates stale code paths and mismatched DTO/model assumptions.
- **Schema drift**: Models include columns/tables not present in migrations (e.g., `youtube_subscriptions`, `church_api_keys`, `chatbot_feedback`, `video_embeddings`, `schedule_config.channel_id`, `channels.default_speaker`, `videos.sermon_actual_date`).
- **Queue drift**: Some code pushes to Redis key `job_queue` while worker consumes `transcription_queue`.

---

## Issue List (Prioritized)

### P0-1: Web service import-time failure due to missing modules
- **Evidence**:
  - `app/ai/chatbot_service.py:37-38` imports `app.ai.search_router` and `app.ai.multi_layer_cache` (missing files).
  - `app/ai/chatbot_service.py:981-982` imports `app.ai.gemini_usage_tracker` (missing file).
  - `app/worker/report_generators.py:19-23` imports `app.common.sermon_formatter` (missing file).
  - `app/web/routes/api.py:17-18` imports `report_generators` and `ChatbotService` at module import time.
- **Root cause**: Partially migrated feature set; referenced modules were never added or removed, so web app crashes during import.
- **Fix proposal**:
  1) Add missing modules (even as minimal stubs) or remove/guard imports behind feature flags.
  2) Defer optional imports inside handlers to avoid startup crashes.
- **Validation**: `python -m app.web.main` or `uvicorn app.web.main:app` should start; hit `/health` and `/api/v2/events/health`.
- **Rollback**: Revert import changes; disable affected routes via router removal.

### P0-2: Scheduler fails to start due to missing rollup service
- **Evidence**: `app/scheduler/main.py:20` imports `app.worker.rollup_service.MonthlyRollupService` (module missing).
- **Root cause**: Rollup feature referenced but implementation removed or never committed.
- **Fix proposal**: Implement `app/worker/rollup_service.py` or replace with `app/worker/report_generators.generate_channel_rollup` and remove the import.
- **Validation**: `python -m app.scheduler.main` starts; `/health` on port 8001 returns 200.
- **Rollback**: Remove rollup job scheduling if feature deferred.

### P0-3: Worker image missing required dependencies (import crashes)
- **Evidence**:
  - `app/worker/sse_broadcaster.py:8` imports `httpx`.
  - `app/worker/youtube_subscription_service.py:13` imports `requests`.
  - `app/ai/llm_client.py:15` and `app/ai/ollama_health.py:11` import `requests` (worker imports `llm_client` via advanced analytics).
  - `requirements-worker.txt` does **not** include `requests` or `httpx`.
- **Root cause**: Dependency lists diverged between web and worker images.
- **Fix proposal**: Add `requests` and `httpx` to `requirements-worker.txt` (or refactor to avoid those imports in worker runtime).
- **Validation**: `docker compose -f docker/docker-compose.yml build worker` + `docker logs culto_worker` shows no ImportError.
- **Rollback**: Revert requirements change; disable SSE/WebSub features in worker.

### P0-4: Static files mount points to a non-existent directory
- **Evidence**: `app/web/main.py:65-66` mounts `StaticFiles(directory="app/web/static")`, but the repo has no `app/web/static/` directory.
- **Root cause**: Static directory removed or never added; Starlette raises RuntimeError on startup.
- **Fix proposal**: Create `app/web/static/` (even empty) or remove the static mount and update templates accordingly.
- **Validation**: `uvicorn app.web.main:app` starts without RuntimeError; static URLs resolve.
- **Rollback**: Revert static mount if not needed.

### P0-5: Schema drift between models and migrations (channels/schedules/videos)
- **Evidence**:
  - Model expects per-channel schedules: `app/common/models.py:513-518` includes `schedule_config.channel_id` (NOT in DB).
  - Migration defines `schedule_config` without `channel_id` and with `TIME` type: `migrations/008_add_schedule_config.sql:5-12`.
  - Scheduler assumes `time_of_day` is a `time` object: `app/scheduler/main.py:400-407`.
  - Channel model includes `default_speaker`, `subdomain`, `min_video_duration_sec`, `max_video_duration_sec`: `app/common/models.py:38-44`, but channels table in initial schema lacks these fields: `migrations/001_initial_schema.sql:18-31`.
  - Video model uses `sermon_actual_date` and `transcript_hash` (`app/common/models.py:69-81`), but `sermon_actual_date` has **no migration**.
- **Root cause**: Database evolved outside migrations; models updated without corresponding SQL migrations.
- **Fix proposal**: Add migrations to align DB with models (or downscope models to match DB). Update `schedule_config` to include `channel_id` + fix type mapping (use `Time` in models).
- **Validation**: Run migrations against a clean DB; verify schema via `psql \d schedule_config` and `alembic`/SQL checks; run scheduler and channel admin flows.
- **Rollback**: Restore DB snapshot, revert migrations.

### P1-1: Constraint mismatch for `Job.job_type` and `Video.status`
- **Evidence**:
  - Model constraint: `app/common/models.py:176-177` does NOT include `analyze_video_v2`.
  - DB constraint: `migrations/001_initial_schema.sql:123-124` only allows `transcribe_video`, `analyze_video`, `check_channel`, `weekly_scan`.
  - Code enqueues `analyze_video_v2`: `app/web/routes/api.py:831-848`; worker handles it: `app/worker/main.py:783-785`.
  - Worker sets video status `transcribed`: `app/worker/main.py:225-230`, but DB constraint excludes it (`migrations/001_initial_schema.sql:48`).
- **Root cause**: Schema constraints not updated when job/status taxonomy changed.
- **Fix proposal**: Add migration to extend check constraints (or replace with enum types). Update model constraint to match.
- **Validation**: Create jobs with `analyze_video_v2` and set status `transcribed` without IntegrityError.
- **Rollback**: Restore previous constraints and revert new job types.

### P1-2: Transcript update re-analysis is queued to the wrong Redis list and lacks Job record
- **Evidence**:
  - `app/web/routes/api.py:656-665` pushes `job_type: analyze_video_v2` to `job_queue` without creating a `Job` row.
  - Worker consumes `transcription_queue` only: `app/worker/main.py:769-771`.
- **Root cause**: Queue name drift + missing job creation for reanalysis workflow.
- **Fix proposal**: Use `transcription_queue` consistently and create a `Job` row with `job_id` before enqueueing.
- **Validation**: Update transcript → worker picks up job → analytics re-run → job status updates.
- **Rollback**: Disable auto-reanalysis on transcript updates.

### P1-3: Upsert expects missing unique constraint on biblical passages
- **Evidence**: `app/worker/advanced_analytics_service.py:595-599` uses `constraint='biblical_passages_video_osis_unique'`, but `migrations/003_advanced_analytics.sql:55-74` defines no such constraint.
- **Root cause**: Upsert assumes unique constraint that was never created.
- **Fix proposal**: Add a unique constraint on `(video_id, osis_ref)` or switch to `index_elements=[...]`.
- **Validation**: Run analytics twice; no unique-constraint errors.
- **Rollback**: Disable upsert path; revert to delete + insert.

### P1-4: Backend v2 API uses fields not present in models
- **Evidence**:
  - `Backend/api/v2/videos.py:90-92` uses `theme.theme_name` (model uses `Theme.tag`).
  - `Backend/api/v2/videos.py:266-270` uses `theme.frequency` (model has `Theme.score`).
  - `Backend/api/v2/chat.py:100-101` uses `video.processed_at` (model has no such field).
- **Root cause**: v2 API built against an earlier schema version.
- **Fix proposal**: Update v2 API to current models or gate v2 routes behind a version switch.
- **Validation**: Hit `/api/v2/videos/*` and `/api/v2/channels/*/chat` without attribute errors.
- **Rollback**: Disable v2 routes if not maintained.

### P1-5: LLM status endpoint uses wrong DB dependency and missing table
- **Evidence**:
  - `app/routers/llm_status.py:20` uses `Depends(get_db)` but `get_db` is a context manager (`app/common/database.py:33-46`).
  - `app/routers/llm_status.py:167-174` queries `gemini_cache_responses` table, which has no migration.
- **Root cause**: Dependency misuse + references to an abandoned cache table.
- **Fix proposal**: Use `get_db_session` and either remove the query or add migration for `gemini_cache_responses`.
- **Validation**: `GET /api/llm/status` returns 200 with cache stats.
- **Rollback**: Return cache stats as `enabled=false` if table missing.

### P2-1: Dev scripts run docker compose from repo root (no compose file)
- **Evidence**:
  - `start-dev.sh:66-86` and `stop-dev.sh:60-73` run `$DOCKER_COMPOSE` in repo root; compose file is in `docker/docker-compose.yml`.
- **Root cause**: script path drift after moving compose file.
- **Fix proposal**: `cd docker` or use `-f docker/docker-compose.yml`.
- **Validation**: `./start-dev.sh` starts containers correctly.
- **Rollback**: Document manual `cd docker` workaround.

### P2-2: External Docker volumes required but not created
- **Evidence**: `docker/docker-compose.yml:170-176` declares `docker_postgres_data` and `docker_redis_data` as `external: true`.
- **Root cause**: Compose assumes pre-existing volumes; `start.sh` doesn’t create them.
- **Fix proposal**: Create volumes in `start.sh` or set `external: false` for first-run installs.
- **Validation**: Clean install succeeds with `start.sh`.
- **Rollback**: Restore external volumes and document manual `docker volume create`.

### P2-3: yt-dlp subprocess calls can hang without timeouts
- **Evidence**:
  - `app/worker/yt_dlp_service.py:69-83` / `126-160` / `253-283` call `subprocess.run` without timeouts.
  - `app/scheduler/main.py:71-82` also uses `subprocess.run` without timeout.
- **Root cause**: Long-running yt-dlp calls can block worker/scheduler loops.
- **Fix proposal**: Add timeouts and retry logic; surface failures in job metadata.
- **Validation**: Simulate slow network and ensure worker continues.
- **Rollback**: Remove timeouts if they create false negatives.

### P2-4: Security defaults and hard-coded internal token
- **Evidence**:
  - `app/web/auth.py:9` default `INSTANCE_PASSWORD=admin123`.
  - `app/web/main.py:62-63` default `SECRET_KEY`.
  - `docker/docker-compose.yml:51-53` default secrets.
  - `Backend/api/v2/events.py:163` hard-coded internal token.
- **Root cause**: Defaults left in production paths; internal auth not moved to env.
- **Fix proposal**: Require non-default secrets at startup; move token to env; add warnings/health checks.
- **Validation**: Startup fails fast if defaults used; SSE broadcast requires proper token.
- **Rollback**: Allow defaults in dev only via explicit `ENV=dev` flag.

---

## Security & Secrets Hygiene (Repo-level)
- `.env` and `docker/.env` exist locally (ignored) — ensure they are **never committed**.
- Default secrets in compose and auth middleware need explicit override before production.
- Web service mounts Docker socket (`docker/docker-compose.yml:60-65`), which grants container control. Consider restricting or removing in production.

## Observability & Debuggability (Current State)
- Logging is mostly `logging.basicConfig` + `logger.info` per service. No structured logs, request IDs, or centralized error tracking.
- Health endpoints exist for web (`/health`), worker (`/api/health/worker`), scheduler (`:8001/health`), and SSE (`/api/v2/events/health`).
- No metrics or tracing; error handling is inconsistent (some swallowed exceptions, some logged).

## Testing & Quality Gates (Current State)
- No automated test suite or CI config found.
- Only ad-hoc script: `test_date_helpers_standalone.py`.
- No lint/typecheck steps for Python, and Vite UI lint not wired to CI.

