# CultoTranscript - Claude Code Context

## Project Overview

**CultoTranscript** is an automated sermon transcription and analysis platform for Brazilian churches. It processes YouTube videos through a 3-tier transcription pipeline and performs AI-powered content analysis using Google Gemini.

**Live Production**: https://church.byrroserver.com

## Stack & Technologies

### Core Technologies
- **Backend**: Python 3.11+, FastAPI
- **Frontend**: Jinja2 templates, HTML/CSS/JavaScript
- **Database**: PostgreSQL 16 with pgvector extension
- **Queue**: Redis 7
- **Containerization**: Docker & Docker Compose
- **Reverse Proxy**: Caddy (HTTPS)

### AI & ML
- **Transcription**: faster-whisper (OpenVINO acceleration with Intel UHD 770 GPU)
- **Analysis**: Google Gemini 1.5 Flash API
- **Embeddings**: pgvector (768-dimensional vectors)
- **Fallback Services**: yt-dlp, youtube-transcript-api

## Architecture

### Multi-Service Architecture

```
User Browser → Caddy (HTTPS) → FastAPI Web Service
                                      ↓
                    ┌─────────────────┼─────────────────┐
                    ↓                 ↓                 ↓
               PostgreSQL          Redis           Gemini API
               + pgvector          Queue
                    ↑                 ↑
                    └─────┬─────┬─────┘
                          ↓     ↓
                    Worker  Scheduler
```

### Services

1. **culto_web** (port 8000)
   - FastAPI web application
   - User authentication, UI, REST API
   - Job submission and progress display
   - Chatbot interface

2. **culto_worker**
   - Redis queue consumer
   - Transcription processing (3-tier fallback)
   - AI analysis with Gemini
   - Embedding generation

3. **culto_scheduler**
   - APScheduler for periodic tasks
   - Weekly channel scans
   - Automatic video discovery

4. **culto_db**
   - PostgreSQL with pgvector
   - Stores videos, transcripts, analytics, embeddings

5. **culto_redis**
   - Message queues (transcription_queue, job_queue)
   - Job tracking and coordination

### 3-Tier Transcription Pipeline

1. **Tier 1**: yt-dlp auto-captions (fastest)
2. **Tier 2**: youtube-transcript-api (free fallback)
3. **Tier 3**: faster-whisper with GPU (most accurate)

## Key Features

### v2.0.0 Features
- Inline transcript viewing
- Automatic re-analysis on edits
- Detailed progress tracking for batch imports
- AI chatbot (Gemini) for sermon content questions
- HTTPS with automatic certificates (Caddy)
- Monthly video grouping (mm/dd/yyyy format)

### Analytics
- Biblical reference detection (66 books, Portuguese variants)
- Theme identification and frequency analysis
- Citation tracking
- Improvement suggestions
- Structured JSONB storage

### Batch Processing
- Scheduled channel monitoring (weekly/daily)
- Date-range filtered imports
- Progress tracking ("Processing video 3 of 10: Title...")
- Video length limits (rejects > 2h by default)

## Development Workflow

### Running Locally

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f culto_web
docker-compose logs -f culto_worker

# Rebuild after code changes
docker-compose up -d --build

# Run tests
docker-compose exec culto_web pytest
```

### Common Operations

**Add a channel:**
- Use web UI at http://localhost:8000
- Enter YouTube channel URL
- Set up weekly scanning schedule

**Monitor jobs:**
- Check web UI job progress display
- Query Redis: `docker-compose exec culto_redis redis-cli LLEN transcription_queue`
- Check worker logs: `docker-compose logs -f culto_worker`

**Database access:**
```bash
docker-compose exec culto_db psql -U culto -d culto_db
```

## Project Structure

```
CultoTranscript/
├── app/
│   ├── main.py              # FastAPI application
│   ├── worker.py            # Queue worker
│   ├── scheduler.py         # Scheduled tasks
│   ├── models/              # SQLAlchemy models
│   ├── services/            # Business logic
│   │   ├── transcription.py
│   │   ├── analytics_v2.py
│   │   ├── chatbot.py
│   │   └── ...
│   ├── routers/             # API routes
│   └── templates/           # Jinja2 templates
├── tests/                   # Test suite
├── docker-compose.yml       # Service orchestration
├── Dockerfile               # Container image
├── requirements.txt         # Python dependencies
├── .env                     # Environment configuration
└── .claude/
    ├── skills/              # 5 specialized skills
    └── settings.local.json  # Permissions config
```

## Claude Code Integration

### Available Skills

#### 1. environment-checker
**Purpose**: Verify development environment setup
**Use when**: Starting development, debugging environment issues
**Checks**:
- Docker daemon status
- Required ports (8000, 5432, 6379)
- .env file presence and configuration
- GPU availability for Whisper

#### 2. browser-tester
**Purpose**: E2E browser testing with automation
**Use when**: Testing user flows, validating UI changes
**Capabilities**:
- Submit YouTube videos via web UI
- Monitor job processing status
- Capture screenshots
- Validate transcription results

#### 3. database-inspector
**Purpose**: Query and inspect PostgreSQL database
**Use when**: Debugging data issues, analyzing content
**Operations**:
- Inspect videos, jobs, transcripts
- Query analytics reports
- Clean up test data
- Extract error details from job metadata

#### 4. log-analyzer
**Purpose**: Monitor and analyze Docker container logs
**Use when**: Troubleshooting errors, monitoring processing
**Features**:
- Real-time log streaming
- Error pattern detection
- Structured analysis output
- Multi-container log aggregation

#### 5. error-fixer
**Purpose**: Diagnose and fix errors automatically
**Use when**: Encountering errors in development or testing
**Workflow**:
1. Analyzes error messages and stack traces
2. Searches documentation using ref MCP server
3. Implements code fixes
4. Rebuilds and restarts services
5. Verifies fix with tests

### MCP Servers Used

1. **ref** - Used by error-fixer for documentation research
2. **browser-use** - Used by browser-tester for UI automation
3. **sequential-thinking** - Available for complex problem-solving
4. **ide** - Available for workspace operations

### Recommended Workflows

**Debugging a transcription failure:**
1. Use database-inspector to check job status and error details
2. Use log-analyzer to examine worker logs
3. Use error-fixer to diagnose and fix the issue

**Testing a new feature:**
1. Use environment-checker to ensure setup is correct
2. Make code changes
3. Use browser-tester to validate E2E flows
4. Use database-inspector to verify data changes

**Analyzing performance:**
1. Use log-analyzer to monitor processing times
2. Use database-inspector to query job durations
3. Identify bottlenecks and optimize

## Environment Variables

Key environment variables (see `.env`):

```bash
# Database
DATABASE_URL=postgresql://user:pass@culto_db:5432/culto_db

# Redis
REDIS_URL=redis://culto_redis:6379

# Gemini API
GEMINI_API_KEY=your_api_key_here

# Authentication
INSTANCE_PASSWORD=your_password_here

# Feature Flags
MAX_VIDEO_DURATION=7200  # 2 hours in seconds
WEEKLY_SCAN_ENABLED=true
```

## Testing

```bash
# Run all tests
docker-compose exec culto_web pytest

# Run specific test file
docker-compose exec culto_web pytest tests/test_transcription.py

# Run with coverage
docker-compose exec culto_web pytest --cov=app tests/
```

## Deployment

**Production deployment** is on a home server:
- Domain: church.byrroserver.com
- Caddy handles HTTPS with automatic certificates
- See DEPLOYMENT.md for detailed instructions

## Common Issues & Solutions

### Worker not processing jobs
- Check Redis connection: `docker-compose logs culto_redis`
- Verify queue has jobs: `docker-compose exec culto_redis redis-cli LLEN transcription_queue`
- Check worker logs: `docker-compose logs -f culto_worker`

### Whisper transcription fails
- Verify GPU is available (Intel UHD 770)
- Check disk space (models require ~2GB)
- Review worker logs for OpenVINO errors
- Fallback to CPU-only if needed (set ENABLE_GPU=false)

### Database connection errors
- Ensure culto_db container is running
- Check DATABASE_URL in .env
- Verify PostgreSQL logs: `docker-compose logs culto_db`

### Gemini API errors
- Verify GEMINI_API_KEY is set correctly
- Check API quota limits
- Review rate limiting in analytics_v2.py

## Documentation

- **README.md** - Quick start guide
- **ARCHITECTURE.md** - Detailed system architecture and design decisions
  - Located at: `/Users/andrebyrro/Dev/CultoTranscript/ARCHITECTURE.md`
  - Contains: Component diagrams, data flow, API design, deployment architecture
  - Reference this for understanding the system's technical design and structure
- **DEPLOYMENT.md** - Production deployment guide
- **GETTING_STARTED.md** - Development setup
- **DATABASE_FIX_README.md** - Database migration notes
- **CHANGELOG.md** - Version history

## Best Practices

### Code Style
- Follow PEP 8 for Python code
- Use type hints for all functions
- Document complex logic with inline comments
- Keep functions focused and single-purpose

### Error Handling
- Always use try-except for external API calls
- Log errors with context (job_id, video_id, etc.)
- Store error details in job metadata
- Provide user-friendly error messages in UI

### Database Operations
- Use SQLAlchemy ORM for queries
- Always use connection pooling
- Index frequently queried columns
- Use JSONB for flexible analytics storage

### Docker Best Practices
- Keep images small (multi-stage builds)
- Use volume mounts for development
- Always use health checks
- Tag images with version numbers

## Resources

- **Python FastAPI**: https://fastapi.tiangolo.com/
- **PostgreSQL pgvector**: https://github.com/pgvector/pgvector
- **Google Gemini**: https://ai.google.dev/
- **faster-whisper**: https://github.com/guillaumekln/faster-whisper
- **Docker Compose**: https://docs.docker.com/compose/

---

**Remember**: This project processes Brazilian Portuguese content. Biblical references use Portuguese book names (e.g., "João" for "John", "Apocalipse" for "Revelation").
