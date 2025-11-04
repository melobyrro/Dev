# Project Command

Display CultoTranscript project overview and key information.

## Instructions

Provide a concise project overview:

1. **Project Identity**:
   - **Name**: CultoTranscript
   - **Type**: Web Application (Sermon Transcription & Analysis Platform)
   - **Stack**: Python, FastAPI, PostgreSQL, Redis, Docker
   - **Production URL**: https://church.byrroserver.com

2. **Purpose**:
   - Automatically transcribe Brazilian church sermons from YouTube
   - Perform AI-powered content analysis using Google Gemini
   - Detect biblical references and identify themes
   - Provide chatbot interface for sermon content queries

3. **Architecture** (Multi-Service):
   ```
   Web Service (FastAPI) → PostgreSQL + pgvector
                        → Redis Queue
                        → Gemini AI API
                        ↓
   Worker Service (Transcription & Analysis)
   Scheduler Service (Weekly Scans)
   ```

4. **Key Features**:
   - 3-tier transcription: yt-dlp → youtube-transcript-api → faster-whisper (GPU)
   - AI analysis: Biblical references, themes, citations (Portuguese)
   - Chatbot: Semantic search using pgvector embeddings
   - Batch processing: Scheduled channel monitoring

5. **Development Quick Start**:
   ```bash
   # Start all services
   docker-compose up -d

   # Access web UI
   open http://localhost:8000

   # Monitor logs
   docker-compose logs -f culto_web culto_worker

   # Run tests
   docker-compose exec culto_web pytest
   ```

6. **Available Claude Code Skills**:
   - environment-checker, browser-tester, database-inspector
   - log-analyzer, error-fixer

7. **Documentation**:
   - .claude/CLAUDE.md - Complete Claude Code context
   - README.md - Quick start guide
   - ARCHITECTURE.md - System architecture details
   - DEPLOYMENT.md - Production deployment guide

Format clearly using markdown with sections and code blocks.
