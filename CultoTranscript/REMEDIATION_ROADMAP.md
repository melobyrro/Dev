# REMEDIATION_ROADMAP.md

## Overview
This roadmap prioritizes stabilization first, then removes drift and dead code, then refactors boundaries, and finally upgrades dependencies/frameworks. Each phase is scoped to small, low-risk PRs with validation gates and rollback strategies.

---

## Phase 0 — Stabilize (P0/P1 blockers)
**Goal:** Make web/worker/scheduler start reliably; fix schema/queue/dependency mismatches; restore critical workflows.

**Tasks**
1) **Fix import-time failures**
   - Add missing modules or gate imports: `app.ai.search_router`, `app.ai.multi_layer_cache`, `app.ai.gemini_usage_tracker`, `app.common.sermon_formatter`, `app.worker.rollup_service`.
   - Alternatively, remove unused features and adjust routers accordingly.

2) **Align worker dependencies**
   - Add `requests` + `httpx` to `requirements-worker.txt`.
   - Rebuild worker image.

3) **Restore re-analysis queue consistency**
   - Change `/videos/{id}/transcript` reanalysis enqueue to use `transcription_queue` and create a `Job` row with `job_id`.

4) **Unblock web startup**
   - Create `app/web/static/` or remove static mount if unused.

5) **Schema hotfixes for blocking mismatches**
   - Add migrations to align `schedule_config` (`channel_id`, `TIME` type) and `channels` columns required by the app (or remove from models).
   - Add missing tables used at runtime (`church_api_keys`, `youtube_subscriptions`, `chatbot_feedback`, `chatbot_query_metrics`, `video_embeddings`, `channel_embeddings`, `sermon_context_links`).

6) **Constraint fixes**
   - Update `jobs.job_type` check constraint to include `analyze_video_v2`.
   - Update `videos.status` constraint to include `transcribed` and `too_short` (or remove if unused).

7) **Biblical passages upsert constraint**
   - Add unique constraint on `(video_id, osis_ref)` or change upsert to `index_elements`.

**Validation gates**
- `docker compose -f docker/docker-compose.yml up -d --build` (web/worker/scheduler running)
- `curl http://localhost:8000/health` (web)
- `curl http://localhost:8000/api/v2/events/health` (SSE)
- `curl http://localhost:8001/health` (scheduler)
- Trigger `/api/transcribe` and verify job dequeues and completes.

**Risk level:** Medium (schema changes)

**Rollback strategy:**
- DB snapshot prior to migrations; rollback via restore.
- Revert import/dependency changes if needed.

---

## Phase 1 — Eliminate Drift & Dead Code
**Goal:** Reduce duplicated/obsolete paths; align backend/UI/API expectations.

**Tasks**
1) **Decide on the canonical API surface**
   - Either update `Backend/api/v2/*` to current models or deprecate v2 routes.
   - Remove stale fields (`theme_name`, `frequency`, `processed_at`) or add compatibility mapping.

2) **UI alignment**
   - Decide between Jinja templates vs React UI in `UI/`.
   - If React is intended: integrate Vite build into web container and serve `UI/dist` via FastAPI or Caddy.
   - If not intended: remove `UI/dist` artifacts and clarify in docs.

3) **Remove schema drift artifacts**
   - Drop `channels.schedule_cron` usage or migrate to `schedule_config` properly.
   - Ensure `system_settings` is the source of truth for AI config; document precedence.

4) **Centralize config & feature flags**
   - Document env vars and DB overrides; add a single “config report” endpoint.

**Validation gates**
- All API endpoints used by UI pass smoke tests (GET list videos, details, chat).
- Scheduler job reload works after schedule updates.

**Risk level:** Medium

**Rollback strategy:**
- Keep v2 routes behind a feature flag or versioned prefix until verified.

---

## Phase 2 — Refactor Architecture Boundaries
**Goal:** Make background processing and web flows more deterministic and observable.

**Tasks**
1) **Job model + queue contract**
   - Formalize `Job` schema and states; enforce schema in worker + scheduler.
   - Use a single queue name and a structured job payload schema.

2) **SSE event flow**
   - Replace hard-coded token with env-based auth; add retries with backoff.
   - Consider switching to WebSockets if/when available.

3) **Analytics pipeline isolation**
   - Wrap LLM calls with circuit breakers and explicit timeouts.
   - Move heavy operations behind dedicated task types.

4) **Database migrations**
   - Introduce Alembic or a migration runner for idempotent upgrades.

**Validation gates**
- End-to-end run: enqueue job → worker → analytics → embeddings → SSE update.
- Manual DB schema validation script in CI (diff models vs DB).

**Risk level:** Medium–High

**Rollback strategy:**
- Feature flags for new job types; keep old path available until stable.

---

## Phase 3 — Dependency & Framework Modernization
**Goal:** Upgrade dependencies safely and remove legacy packages.

**Tasks**
1) **Python deps**
   - Upgrade FastAPI, SQLAlchemy, and LLM clients with pinned versions.
   - Consolidate duplicated LLM clients (`llm_client.py` vs `gemini_client.py`).

2) **Frontend**
   - If React is canonical, add test harness and CI for build.
   - If Jinja is canonical, simplify UI assets and remove unused React deps.

3) **Infrastructure**
   - Harden Docker images (non-root user, healthchecks, slimmer layers).
   - Remove `--reload` in production containers.

**Validation gates**
- Full system smoke test; `docker compose up --build` on clean environment.
- Regression tests for API endpoints and worker pipeline.

**Risk level:** Medium

**Rollback strategy:**
- Versioned Docker images; deploy canary containers before full rollout.

---

## Test/CI Gates to Add (All Phases)
- **Lint/format**: `ruff` or `flake8` + `black` for Python; `eslint` for UI.
- **Type checks**: `mypy` for Python; `tsc --noEmit` for UI.
- **Unit tests**: Transcription helpers, query parser, LLM prompt builders.
- **Integration tests**: DB migration + worker queue processing.
- **E2E smoke**: `/health`, `/api/transcribe`, SSE stream connect.

## Observability Upgrades
- Structured JSON logs with request IDs and job IDs.
- Metrics: queue depth, job durations, LLM error rates, SSE client count.
- Health checks: DB + Redis connectivity + LLM availability.
- Alerting thresholds: job failures > N, queue age > N minutes.

