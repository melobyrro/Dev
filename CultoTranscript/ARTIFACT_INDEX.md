# ARTIFACT_INDEX.md

Categorized index of repository artifacts with brief purpose notes. Items marked **[suspect]** are likely deprecated, duplicated, or build/local artifacts.

## Root
- `.DS_Store` — macOS Finder metadata file. [suspect]
- `.env` — Local environment secrets (should not be committed). [suspect]
- `.env.example` — Sample environment configuration template.
- `.gitignore` — Git ignore rules (env files, build outputs, caches, OS files).
- `ARCHITECTURE.md` — CultoTranscript - System Architecture
- `BEFORE_AFTER_EXAMPLES.md` — Before & After: Sermon Date Prefix Implementation
- `CHANGELOG.md` — Changelog
- `Caddyfile.example` — Example reverse proxy configuration for Caddy.
- `DATABASE_FIX_README.md` — Database Schema Fix - Instructions
- `DATABASE_VIEWER_IMPLEMENTATION.md` — Database Viewer Implementation Summary
- `DEPLOYMENT.md` — CultoTranscript - Deployment Guide
- `DEVELOPMENT.md` — CultoTranscript - Development Guide
- `GETTING_STARTED.md` — CultoTranscript - Quick Start Guide
- `INTEGRATION_COMPLETE.md` — Backend Integration Complete ✅
- `LICENSE` — Project license (MIT).
- `MIGRATION_QUICK_START.md` — Quick Start: Sermon Date Prefix Migration
- `README.md` — CultoTranscript
- `RELIABILITY_AUDIT.md` — RELIABILITY_AUDIT.md
- `REMEDIATION_ROADMAP.md` — REMEDIATION_ROADMAP.md
- `RUN_THIS_MIGRATION.sh` — Runs a migration inside the DB container.
- `SERMON_DATE_PREFIX_IMPLEMENTATION_REPORT.md` — Sermon Date Prefix Implementation Report
- `deploy.sh` — Server deployment helper (scp + restart).
- `deploy_delete_feature.sh` — Server deployment helper for delete feature.
- `fix_database_schema.py` — One-off schema fix (adds transcript quality columns).
- `fix_db_simple.py` — Standalone psycopg2 schema fix for transcripts.
- `requirements-web.txt` — Python dependency list for the web container/service.
- `requirements-worker.txt` — Python dependency list for worker/scheduler containers.
- `start-dev.sh` — Dev startup script (Docker + Vite).
- `start.sh` — Quick-start script to run Docker services.
- `stop-dev.sh` — Dev shutdown script for Docker + Vite.
- `test_date_helpers_standalone.py` — Standalone test script for date-prefix helpers.
- `update_server.sh` — Server-side update script (patch + restart).

## Infrastructure / Docker
- `docker/.env` — Local Docker environment overrides (ignored). [suspect]
- `docker/Caddyfile` — Caddy reverse proxy config for Docker setup.
- `docker/docker-compose.yml` — Compose stack for db/redis/web/worker/scheduler/ollama.
- `docker/web.Dockerfile` — Web service container build (FastAPI + Backend modules).
- `docker/worker.Dockerfile` — Worker/scheduler container build (yt-dlp, Whisper, OpenVINO).

## Database / Migrations
- `migrations/001_initial_schema.sql` — CultoTranscript Database Schema
- `migrations/002_add_exclusions.sql` — Migration: Add excluded videos tracking
- `migrations/003_advanced_analytics.sql` — Migration 003: Advanced Analytics & AI Features
- `migrations/004_fix_missing_transcript_columns.sql` — Migration 004: Fix Missing Transcript Columns
- `migrations/005_add_sermon_start_time.sql` — Migration 005: Add Sermon Start Time Column
- `migrations/006_add_ai_summary.sql` — Migration 006: Add AI Summary Column
- `migrations/007_add_speaker_column.sql` — Migration 007: Add speaker column to videos table
- `migrations/008_add_schedule_config.sql` — Migration 008: Add schedule_config table for dynamic scheduler configuration
- `migrations/009_create_transcript_embeddings.sql` — Migration 009: Create transcript_embeddings table for RAG chatbot
- `migrations/010_create_speakers_table.sql` — Migration 010: Create speakers table for autocomplete
- `migrations/012_verify_and_fix_caching.sql` — Migration 012: Verify and Fix Caching Infrastructure
- `migrations/013_add_video_created_at.sql` — Migration 013: Add video_created_at column to videos table
- `migrations/017_add_system_settings.sql` — System settings table for runtime-configurable application settings
- `migrations/026_add_suggested_title.sql` — Migration 026: Add suggested_title column for AI-generated sermon titles

## Analytics / Data
- `analytics/dictionaries/themes_pt.json` — JSON data/config.

## Shared Types
- `shared/dtos.ts` — Shared DTO definitions for UI/backend contracts (TypeScript).

## App / Web
- `app/web/__init__.py` — Python module.
- `app/web/auth.py` — Simple instance password authentication for CultoTranscript
- `app/web/main.py` — CultoTranscript - FastAPI Web Application

## App / Web Routes
- `app/web/routes/__init__.py` — Python module.
- `app/web/routes/api.py` — API routes for AJAX calls and programmatic access
- `app/web/routes/channels.py` — Channel management routes
- `app/web/routes/reports.py` — Reports and analytics routes
- `app/web/routes/videos.py` — Video management and transcription routes
- `app/web/routes/websub.py` — YouTube WebSub (PubSubHubbub) webhook endpoints.

## App / Web Templates
- `app/web/templates/admin.html` — Jinja2 HTML template for web UI.
- `app/web/templates/admin_chatbot_metrics.html` — Jinja2 HTML template for web UI.
- `app/web/templates/admin_import.html` — Jinja2 HTML template for web UI.
- `app/web/templates/admin_schedule.html` — Jinja2 HTML template for web UI.
- `app/web/templates/admin_websub.html` — Jinja2 HTML template for web UI.
- `app/web/templates/base.html` — Jinja2 HTML template for web UI.
- `app/web/templates/channels/chatbot.html` — Jinja2 HTML template for web UI.
- `app/web/templates/channels/import.html` — Jinja2 HTML template for web UI.
- `app/web/templates/channels/list.html` — Jinja2 HTML template for web UI.
- `app/web/templates/channels/new.html` — Jinja2 HTML template for web UI.
- `app/web/templates/database.html` — Jinja2 HTML template for web UI.
- `app/web/templates/index.html` — Jinja2 HTML template for web UI.
- `app/web/templates/login.html` — Jinja2 HTML template for web UI.
- `app/web/templates/reports/index.html` — Jinja2 HTML template for web UI.
- `app/web/templates/videos/detail.html` — Jinja2 HTML template for web UI.
- `app/web/templates/videos/list.html` — Jinja2 HTML template for web UI.

## App / Worker
- `app/worker/__init__.py` — Python module.
- `app/worker/advanced_analytics_service.py` — Advanced Analytics Service (V2)
- `app/worker/ai_summarizer.py` — AI Sermon Summarizer
- `app/worker/analytics_service.py` — Analytics service for sermon transcript analysis
- `app/worker/biblical_classifier.py` — Biblical Content Classifier
- `app/worker/highlight_extractor.py` — Sermon Highlight Extractor
- `app/worker/inconsistency_detector.py` — Sermon Inconsistency Detector
- `app/worker/main.py` — Worker service - processes transcription jobs from Redis queue
- `app/worker/passage_analyzer.py` — Biblical Passage Analyzer
- `app/worker/question_generator.py` — Discussion Question Generator
- `app/worker/report_generators.py` — Report Generators
- `app/worker/sensitivity_analyzer.py` — Sensitivity Analyzer
- `app/worker/sermon_coach.py` — Sermon Coach
- `app/worker/sse_broadcaster.py` — SSE Broadcaster Module
- `app/worker/theme_analyzer_v2.py` — Theme Analyzer V2
- `app/worker/transcript_api_service.py` — YouTube transcript extraction using youtube-transcript-api (fallback method)
- `app/worker/transcription_scorer.py` — Transcription Quality Scorer
- `app/worker/transcription_service.py` — Transcription orchestrator - 3-tier waterfall strategy
- `app/worker/whisper_service.py` — Whisper transcription service with Intel GPU (UHD 770) support via OpenVINO
- `app/worker/youtube_subscription_service.py` — YouTube WebSub (PubSubHubbub) Subscription Service
- `app/worker/yt_dlp_service.py` — YouTube download and auto-caption extraction service using yt-dlp

## App / Scheduler
- `app/scheduler/__init__.py` — Python module.
- `app/scheduler/email_notifier.py` — Email notification service for scheduler alerts
- `app/scheduler/main.py` — Scheduler service - checks channels for new videos on a schedule

## App / AI
- `app/ai/__init__.py` — Python module.
- `app/ai/biblical_passage_service.py` — Biblical Passage Service
- `app/ai/biblical_reference_parser.py` — Biblical Reference Parser
- `app/ai/cache_manager.py` — Chatbot Cache Manager
- `app/ai/chatbot_service.py` — Channel Chatbot Service
- `app/ai/context_linker.py` — Context Linker Service
- `app/ai/embedding_service.py` — Embedding Service
- `app/ai/gemini_client.py` — Google Gemini API Client
- `app/ai/hierarchical_search.py` — Hierarchical Search Service
- `app/ai/hybrid_search.py` — Hybrid Search Service
- `app/ai/json_parser.py` — Robust JSON parser for LLM responses
- `app/ai/llm_client.py` — Unified LLM client with automatic Gemini -> Ollama fallback.
- `app/ai/metadata_extractor.py` — Segment Metadata Extraction Service (Phase 2)
- `app/ai/ollama_health.py` — Ollama health check and model management utilities.
- `app/ai/query_classifier.py` — Query Type Classifier for Chatbot
- `app/ai/query_parser.py` — Query parser for extracting dates from Brazilian Portuguese natural language queries.
- `app/ai/segmentation.py` — Intelligent Text Segmentation
- `app/ai/sermon_detector.py` — Sermon Detection Module
- `app/ai/speaker_parser.py` — Speaker Parser Module
- `app/ai/theme_parser.py` — Theme Parser Module
- `app/ai/theme_service.py` — Theme Service

## App / Common
- `app/common/__init__.py` — Python module.
- `app/common/__pycache__/__init__.cpython-311.pyc` — Build artifact / cache file. [suspect]
- `app/common/__pycache__/database.cpython-311.pyc` — Build artifact / cache file. [suspect]
- `app/common/__pycache__/models.cpython-311.pyc` — Build artifact / cache file. [suspect]
- `app/common/api_keys.py` — Helpers for managing per-church API keys and scoped usage.
- `app/common/bible_detector.py` — Bible reference detector for Portuguese transcripts
- `app/common/bible_pt.py` — Brazilian Portuguese Bible books dictionary with common variants
- `app/common/database.py` — Database configuration and session management
- `app/common/models.py` — SQLAlchemy ORM models matching the database schema
- `app/common/theme_tagger.py` — Theme tagger for Portuguese sermon transcripts

## App / Routers
- `app/routers/database.py` — Database Viewer Router
- `app/routers/llm_status.py` — LLM Status Router

## Backend v2
- `Backend/FILES_MANIFEST.txt` — Project file.
- `Backend/INTEGRATION.md` — Backend Integration Guide
- `Backend/PHASE1_COMPLETE.md` — Backend Worker - Phase 1 Complete
- `Backend/QUICK_START.md` — Backend Phase 1 - Quick Start
- `Backend/README.md` — CultoTranscript Backend Worker
- `Backend/api/__init__.py` — Backend API endpoints
- `Backend/api/v2/__init__.py` — API v2 endpoints
- `Backend/api/v2/chat.py` — Chat API v2 - Enhanced chat endpoint with better integration
- `Backend/api/v2/events.py` — SSE Events Endpoint
- `Backend/api/v2/videos.py` — Videos API Endpoints
- `Backend/dtos.py` — FROZEN DATA TRANSFER OBJECTS (DTOs)
- `Backend/middleware/__init__.py` — Backend middleware
- `Backend/middleware/cors.py` — CORS Middleware Configuration
- `Backend/middleware/csrf.py` — CSRF Protection Middleware
- `Backend/requirements.txt` — Project file.
- `Backend/services/__init__.py` — Backend services
- `Backend/services/sse_manager.py` — SSE Manager Service
- `Backend/syntax_check.py` — Python module.
- `Backend/validate.py` — Python module.

## UI / Config
- `UI/.gitignore` — Project file.
- `UI/README.md` — React + TypeScript + Vite
- `UI/SETUP_COMPLETE.md` — UI Worker - Phase 1 Setup Complete
- `UI/eslint.config.js` — Project file.
- `UI/index.html` — HTML file.
- `UI/package-lock.json` — JSON data/config.
- `UI/package.json` — JSON data/config.
- `UI/postcss.config.js` — Project file.
- `UI/tsconfig.app.json` — JSON data/config.
- `UI/tsconfig.json` — JSON data/config.
- `UI/tsconfig.node.json` — JSON data/config.
- `UI/vite.config.ts` — TypeScript/React source file.

## UI / Public Assets
- `UI/public/vite.svg` — Project file.

## UI / Source
- `UI/src/App.css` — Stylesheet.
- `UI/src/App.tsx` — TypeScript/React source file.
- `UI/src/assets/react.svg` — Project file.
- `UI/src/components/AIDrawer.tsx` — TypeScript/React source file.
- `UI/src/components/ChatMessage.tsx` — TypeScript/React source file.
- `UI/src/components/FloatingActionButton.tsx` — TypeScript/React source file.
- `UI/src/components/Layout.tsx` — TypeScript/React source file.
- `UI/src/components/MonthlyGroup.tsx` — TypeScript/React source file.
- `UI/src/components/StatusChip.tsx` — TypeScript/React source file.
- `UI/src/components/TopAppBar.tsx` — TypeScript/React source file.
- `UI/src/components/VideoDetailDrawer.tsx` — TypeScript/React source file.
- `UI/src/components/VideoList.tsx` — TypeScript/React source file.
- `UI/src/components/VideoListItem.tsx` — TypeScript/React source file.
- `UI/src/hooks/README.md` — Custom React Hooks
- `UI/src/hooks/useSSE.ts` — TypeScript/React source file.
- `UI/src/hooks/useTheme.ts` — TypeScript/React source file.
- `UI/src/hooks/useVideoDetail.ts` — TypeScript/React source file.
- `UI/src/hooks/useVideos.ts` — TypeScript/React source file.
- `UI/src/index.css` — Stylesheet.
- `UI/src/lib/config.ts` — TypeScript/React source file.
- `UI/src/lib/queryClient.ts` — TypeScript/React source file.
- `UI/src/lib/sseClient.ts` — TypeScript/React source file.
- `UI/src/lib/utils.ts` — TypeScript/React source file.
- `UI/src/main.tsx` — TypeScript/React source file.
- `UI/src/services/README.md` — API Services
- `UI/src/services/chatService.ts` — TypeScript/React source file.
- `UI/src/services/videoService.ts` — TypeScript/React source file.
- `UI/src/stores/README.md` — Zustand Stores
- `UI/src/stores/chatStore.ts` — TypeScript/React source file.
- `UI/src/stores/videoStore.ts` — TypeScript/React source file.
- `UI/src/types/index.ts` — TypeScript/React source file.
- `UI/src/types/test-import.ts` — TypeScript/React source file.

## UI / Build Output
- `UI/dist/assets/index-piYjwQGb.js` — Build artifact / cache file. [suspect]
- `UI/dist/assets/index-qagMEHMo.css` — Build artifact / cache file. [suspect]
- `UI/dist/index.html` — Build artifact / cache file. [suspect]
- `UI/dist/vite.svg` — Build artifact / cache file. [suspect]

## Scripts
- `scripts/backfill_suggested_titles.py` — Python module.
- `scripts/decode_transcripts.py` — Migration script to decode HTML entities in existing transcripts
- `scripts/update_video_titles_with_dates.py` — Python module.

## Tooling / Orchestrator
- `.orchestrator/CONTRACT.md` — Master Orchestrator Contract
- `.orchestrator/backend/MANIFEST.json` — Orchestrator manifest file.
- `.orchestrator/skills/registry.json` — JSON data/config.
- `.orchestrator/tests/MANIFEST.json` — Orchestrator manifest file.
- `.orchestrator/ui/MANIFEST.json` — Orchestrator manifest file.

## Tooling / Claude
- `.claude/.gitignore` — Project file.
- `.claude/CLAUDE.md` — CultoTranscript - Claude Code Context
- `.claude/agents/README.md` — Agents for CultoTranscript
- `.claude/commands/context.md` — Context Command
- `.claude/commands/help.md` — Help Command
- `.claude/commands/project.md` — Project Command
- `.claude/commands/test.md` — Test Command
- `.claude/settings.json` — JSON data/config.
- `.claude/settings.local.json` — JSON data/config.
- `.claude/skills/browser-tester.md` — Browser Tester Skill
- `.claude/skills/database-inspector.md` — Database Inspector Skill
- `.claude/skills/environment-checker.md` — Environment Checker Skill
- `.claude/skills/error-fixer.md` — Error Fixer Skill
- `.claude/skills/log-analyzer.md` — Log Analyzer Skill

## Tooling / VSCode
- `.vscode/settings.json` — JSON data/config.

## Build Artifacts
- `app/__pycache__/__init__.cpython-311.pyc` — Build artifact / cache file. [suspect]
