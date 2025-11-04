# CultoTranscript - System Architecture

## Overview

CultoTranscript is a multi-tier Brazilian church sermon transcription and analytics platform that automatically processes YouTube videos through a 3-tier fallback transcription pipeline and performs advanced AI-powered content analysis using Google Gemini.

## System Components

### 1. Web Service (`culto_web`)
- **Framework**: FastAPI with Jinja2 templates
- **Port**: 8000
- **Responsibilities**:
  - User authentication (instance password)
  - Channel management UI
  - Video listing and detail pages
  - Transcript editing interface
  - AI-powered chatbot interface
  - Job status polling and progress display
  - RESTful API endpoints

### 2. Worker Service (`culto_worker`)
- **Framework**: Python with Redis queue consumer
- **Responsibilities**:
  - Process transcription jobs from queue
  - Execute 3-tier transcription fallback
  - Run V2 analytics with Gemini AI
  - Generate embeddings for chatbot
  - Handle channel bulk imports
  - Track detailed progress metadata

### 3. Scheduler Service (`culto_scheduler`)
- **Framework**: Python with APScheduler
- **Responsibilities**:
  - Weekly channel scans for new videos
  - Automatic video discovery
  - Scheduled maintenance tasks

### 4. Database (`culto_db`)
- **Engine**: PostgreSQL 16 with pgvector extension
- **Responsibilities**:
  - Store videos, channels, transcripts
  - Store SermonReport analytics data (JSONB)
  - Store transcript embeddings (768-dim vectors)
  - Track job statuses and metadata
  - Manage excluded videos

### 5. Message Queue (`culto_redis`)
- **Engine**: Redis 7
- **Queues**:
  - `transcription_queue` - Transcription jobs
  - `job_queue` - Analytics and re-analysis jobs
- **Responsibilities**:
  - Decouple job submission from processing
  - Enable asynchronous task execution
  - Track active jobs

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         User Browser                         │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTPS
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    Caddy Reverse Proxy                       │
│              (church.byrroserver.com → :8000)                │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    Web Service (FastAPI)                     │
│  • Jinja2 Templates  • Authentication  • REST API           │
│  • Job Submission    • Progress Display • Chatbot UI        │
└────┬────────────────────┬────────────────────┬──────────────┘
     │                    │                    │
     │ SQL Queries        │ Queue Jobs         │ Chatbot Queries
     │                    │                    │
┌────▼────────┐   ┌──────▼────────┐   ┌──────▼──────────────┐
│  PostgreSQL │   │  Redis Queue  │   │  Gemini AI API      │
│   + pgvector│   │               │   │  (google.generative │
│             │   │ • transcription│   │   ai)               │
│  • Videos   │   │   _queue       │   │                     │
│  • Transcripts   │ • job_queue   │   │  • ChatbotService   │
│  • Reports  │   │               │   │  • Embeddings       │
│  • Embeddings│   │               │   │                     │
└─────────────┘   └───────┬───────┘   └─────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
  ┌───────▼────────┐            ┌────────▼─────────┐
  │ Worker Service │            │ Scheduler Service │
  │ • Transcribe   │            │ • Weekly Scans    │
  │ • Analyze      │            │ • Maintenance     │
  │ • Generate     │            │                   │
  │   Embeddings   │            └───────────────────┘
  └────────────────┘
          │
  ┌───────┴────────┐
  │  External APIs │
  │ • YouTube       │
  │ • yt-dlp        │
  │ • youtube-      │
  │   transcript-api│
  │ • faster-whisper│
  │ • Gemini AI     │
  └─────────────────┘
```

## Data Flow

### 1. Video Transcription Flow

```
User submits video → Web creates Job → Job queued in Redis
                                              ↓
                           Worker picks job from queue
                                              ↓
                    ┌──────────────────────────────────┐
                    │  Tier 1: yt-dlp Auto-Captions   │
                    │  (Fastest, best quality)         │
                    └──────┬───────────────────────────┘
                           │ If fails
                           ↓
                    ┌──────────────────────────────────┐
                    │  Tier 2: youtube-transcript-api  │
                    │  (API-based, reliable)           │
                    └──────┬───────────────────────────┘
                           │ If fails
                           ↓
                    ┌──────────────────────────────────┐
                    │  Tier 3: faster-whisper          │
                    │  (Local AI, always works)        │
                    └──────┬───────────────────────────┘
                           │
                           ↓
              Transcript saved to database
                           ↓
         V2 Analytics automatically triggered
                           ↓
          Embeddings generated for chatbot
                           ↓
                Job marked as completed
```

### 2. Analytics V2 Flow

```
Transcript ready → Queue analyze_video_v2 job → Worker picks job
                                                       ↓
                              Gemini AI analyzes transcript
                          (rate-limited: 60 req/min, 1M tokens/min)
                                                       ↓
                                      Extract structured data:
                                      • Biblical citations
                                      • Readings
                                      • Mentions
                                      • Themes & topics
                                      • Suggestions
                                                       ↓
                          Save as SermonReport (JSONB in PostgreSQL)
```

### 3. Chatbot Flow

```
User asks question → Web service → ChatbotService
                                           ↓
                      Embed question using Gemini
                                           ↓
           Vector similarity search in transcript_embeddings
                      (pgvector cosine similarity)
                                           ↓
                     Retrieve top 5 relevant segments
                                           ↓
          Build context prompt with segments + question
                                           ↓
                    Send to Gemini for answer generation
                                           ↓
                   Return answer to user interface
```

### 4. Channel Bulk Import Flow

```
User submits date range → Web creates import_channel job
                                           ↓
                         Job queued with metadata
                                           ↓
                      Worker picks import job
                                           ↓
              yt-dlp lists all videos in date range
         (with --flat-playlist and date filtering)
                                           ↓
              Filter out existing and excluded videos
                                           ↓
        For each new video (with progress tracking):
        • Create transcribe_video job in database
        • Queue job in Redis transcription_queue
        • Update import job metadata with:
          - current_video: X
          - new_videos: Y
          - current_video_title: "Title"
          - progress: 80-100%
                                           ↓
               Import job marked completed
```

## Technology Stack

### Backend
- **Python 3.11+**
- **FastAPI** - Web framework
- **SQLAlchemy** - ORM
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **yt-dlp** - YouTube video downloading
- **youtube-transcript-api** - API-based transcript fetching
- **faster-whisper** - Local AI transcription (OpenVINO/CUDA)
- **google-generativeai** - Gemini AI integration

### Frontend
- **Jinja2** - Server-side templating
- **Vanilla JavaScript** - Dynamic UI updates
- **CSS3** - Styling with transitions
- **Fetch API** - AJAX requests for progress polling

### Infrastructure
- **PostgreSQL 16** - Primary database
  - `pgvector` extension for embeddings
- **Redis 7** - Message queue
- **Docker** - Containerization
- **Caddy 2** - Reverse proxy with automatic HTTPS
- **Cloudflare DNS** - DNS challenge for SSL certificates

### External APIs
- **YouTube Data API v3** - Optional channel discovery
- **Google Gemini API** - AI analytics and chatbot
  - Model: `gemini-1.5-flash`
  - Rate limits: 60 req/min, 1M tokens/min

## Directory Structure

```
CultoTranscript/
├── app/
│   ├── web/                    # FastAPI web service
│   │   ├── main.py            # Application entry point
│   │   ├── auth.py            # Authentication
│   │   ├── routes/
│   │   │   ├── web.py         # HTML page routes
│   │   │   └── api.py         # REST API endpoints
│   │   └── templates/         # Jinja2 templates
│   │       ├── base.html
│   │       ├── index.html     # Channel homepage
│   │       └── videos/
│   │           └── detail.html
│   ├── worker/                # Background worker service
│   │   ├── main.py           # Worker entry point
│   │   ├── transcription_service.py  # 3-tier transcription
│   │   ├── yt_dlp_service.py         # Tier 1: Auto-captions
│   │   ├── transcript_api_service.py # Tier 2: API
│   │   ├── whisper_service.py        # Tier 3: Local AI
│   │   ├── analytics_service.py      # Legacy V1 (deprecated)
│   │   ├── advanced_analytics_service.py  # V2 with Gemini
│   │   └── report_generators.py      # Report generation
│   ├── scheduler/             # Scheduler service
│   │   └── main.py           # Weekly channel scans
│   ├── ai/                    # AI services
│   │   ├── gemini_client.py  # Gemini API wrapper
│   │   ├── chatbot_service.py # Chatbot logic
│   │   └── embedding_service.py # Vector embedding generation
│   └── common/               # Shared code
│       ├── database.py       # Database connection
│       └── models.py         # SQLAlchemy models
├── migrations/               # Alembic migrations
├── docker/                   # Docker configurations
│   ├── web/
│   │   └── Dockerfile
│   ├── worker/
│   │   └── Dockerfile
│   └── docker-compose.yml
├── tests/                    # Test suite
├── .env                      # Environment variables
├── Caddyfile                 # Caddy reverse proxy config
├── requirements-web.txt      # Web service dependencies
├── requirements-worker.txt   # Worker service dependencies
├── ARCHITECTURE.md           # This file
├── DEPLOYMENT.md             # Deployment guide
├── CHANGELOG.md              # Version history
└── README.md                 # Project overview
```

## Key Design Decisions

### 1. 3-Tier Transcription Fallback
**Decision**: Implement three fallback tiers instead of relying on a single method.

**Rationale**:
- Tier 1 (auto-captions) is fastest and highest quality but not always available
- Tier 2 (API) is reliable but requires community contributions
- Tier 3 (Whisper AI) is slowest but works for any video with audio

**Trade-offs**: Increased complexity vs. 99%+ success rate

### 2. Gemini Flash for Analytics
**Decision**: Use Gemini 1.5 Flash instead of GPT-4 or other models.

**Rationale**:
- Cost-effective for high-volume processing
- Fast response times (suitable for real-time generation)
- Large context window (1M tokens) handles long transcripts
- Good Portuguese language support
- Rate limits (60 req/min) are acceptable

**Trade-offs**: Slightly lower quality than GPT-4 but 10x cheaper

### 3. JSONB for Analytics Storage
**Decision**: Store SermonReport as JSONB instead of normalized tables.

**Rationale**:
- Flexible schema allows V2 analytics to evolve
- Efficient querying with PostgreSQL JSONB operators
- Simplified migrations when adding new analysis fields
- Fast reads for report generation

**Trade-offs**: Less referential integrity vs. flexibility

### 4. pgvector for Embeddings
**Decision**: Use pgvector extension instead of dedicated vector database (Pinecone, Weaviate).

**Rationale**:
- Keep all data in PostgreSQL (simpler architecture)
- Avoid additional service dependencies
- Good enough performance for chatbot use case (<10k videos)
- Transactional guarantees with rest of data

**Trade-offs**: Lower performance at massive scale vs. simplicity

### 5. Redis for Job Queue
**Decision**: Use Redis instead of RabbitMQ or Celery.

**Rationale**:
- Simple RPUSH/BLPOP queue pattern
- No additional broker needed
- Fast and reliable
- Already needed for caching

**Trade-offs**: Less advanced features vs. simplicity

### 6. Direct Worker Polling vs. Message Passing
**Decision**: Worker updates job metadata in database; frontend polls for status.

**Rationale**:
- Stateless web service (no WebSockets needed)
- Survives web service restarts
- Simple to implement
- Good enough latency (1-second polls)

**Trade-offs**: Higher database load vs. simplicity

### 7. Automatic Re-analysis on Transcript Edit
**Decision**: Delete SermonReport and queue analyze_video_v2 job when transcript is edited.

**Rationale**:
- Ensures analytics always match current transcript
- Transparent to user (notification shown)
- Gemini costs are low enough to regenerate

**Trade-offs**: Additional API costs vs. data consistency

## Security Considerations

### Authentication
- Single instance password (INSTANCE_PASSWORD env var)
- Session-based auth with secure cookies
- No user registration (single-tenant system)

### API Keys
- Gemini API key stored in environment variables
- Never exposed to frontend
- Rate limiting enforced

### Input Validation
- All user inputs validated with Pydantic models
- SQL injection prevented by SQLAlchemy ORM
- XSS prevention in Jinja2 templates (auto-escaping)

### HTTPS
- Caddy provides automatic HTTPS with Let's Encrypt
- Cloudflare DNS challenge for certificate validation
- HTTP redirected to HTTPS

## Scalability Notes

### Current Limitations
- Single worker instance (can scale horizontally)
- PostgreSQL single node (can add read replicas)
- Gemini rate limits: 60 req/min (can request quota increase)

### Scaling Strategies
1. **Horizontal Worker Scaling**: Add more worker containers
2. **Database Replication**: Read replicas for report queries
3. **Redis Clustering**: If queue becomes bottleneck
4. **CDN**: For static assets and video thumbnails
5. **Batch Analytics**: Process multiple videos per Gemini request

## Monitoring & Observability

### Logging
- Structured logging with timestamps
- Log levels: DEBUG, INFO, WARNING, ERROR
- Container logs accessible via `docker logs`

### Metrics (Future)
- Job success/failure rates
- Transcription tier distribution
- Average processing times
- Gemini API usage and costs

### Health Checks
- Database connection health
- Redis connectivity
- Worker queue depth
- Gemini API availability

## Future Enhancements

1. **Multi-tenant Support**: Multiple churches with isolated data
2. **Video Segmentation**: Split long videos into chapters
3. **Speaker Diarization**: Identify different speakers
4. **Audio Quality Detection**: Warn about poor audio quality
5. **Playlist Support**: Batch import entire playlists
6. **Backup & Restore**: Automated database backups
7. **Admin Dashboard**: System health and usage statistics
8. **API Rate Limiting**: Protect against abuse
9. **WebSocket Updates**: Real-time progress without polling
10. **Mobile App**: Native iOS/Android apps

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Additional Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment and configuration guide
- [GETTING_STARTED.md](GETTING_STARTED.md) - Quick start guide
- [README.md](README.md) - Project overview and features
