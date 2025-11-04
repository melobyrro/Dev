# Changelog

All notable changes to CultoTranscript will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-11-03

### 🚀 Major Release - UI Enhancements & Production Deployment

#### Added

**User Interface Improvements**:
- **In-page Transcript Expansion**: Click video rows to view transcripts inline without navigating away
  - Smooth CSS transitions for expand/collapse
  - Loading indicators while fetching
  - Displays transcript source, word count, and character count
  - Caches fetched transcripts to avoid redundant API calls
  - `app/web/routes/api.py:723-756` - New `/api/videos/{video_id}/transcript` endpoint
  - `app/web/templates/index.html:135-188` - Transcript expansion CSS
  - `app/web/templates/index.html:555-586` - Expandable table rows
  - `app/web/templates/index.html:694-779` - JavaScript functions for transcript loading

- **Expand/Collapse All Buttons**: Control all monthly groups at once
  - Appears above video list when videos are loaded
  - "Expandir Todos" and "Recolher Todos" buttons
  - `app/web/templates/index.html:271-280` - Button UI
  - `app/web/templates/index.html:686-702` - Expand/collapse functions

- **Hierarchical Date Grouping**: Reorganized video list from daily to monthly grouping
  - Changed from Year → Day to Year → Month hierarchy
  - Date format changed from dd/mm/yyyy to mm/dd/yyyy (US format)
  - Current month highlighted with "(Mês Atual)" label
  - Videos sorted newest first within each month
  - `app/web/templates/index.html:602-653` - Updated grouping logic

**Automatic Re-analysis System**:
- **Transcript Edit Triggers Re-analysis**: Editing and saving a transcript automatically:
  - Deletes existing SermonReport analytics
  - Queues new `analyze_video_v2` job
  - Displays notification: "Análise será regerada automaticamente"
  - `app/web/routes/api.py:266-325` - Enhanced `/api/videos/{video_id}/transcript` PUT endpoint
  - `app/web/templates/videos/detail.html:398-415` - Frontend notification display

**Detailed Progress Tracking**:
- **Channel Bulk Import Progress**: Real-time "Processing video X of Y" updates
  - Counts total videos before processing
  - Updates progress for each video being queued
  - Displays current video title and number
  - Progress bar shows 80-100% during video queuing
  - Polls every 1 second for status updates
  - `app/worker/main.py:311-406` - Enhanced bulk import with per-video progress
  - `app/web/templates/index.html:420-492` - Frontend progress polling and display

**Production Infrastructure**:
- **Caddy Reverse Proxy Integration**: HTTPS deployment with automatic certificates
  - Added `church.byrroserver.com` to production Caddyfile
  - Connected `culto_web` to `byrro-net` network
  - Automatic HTTPS via Let's Encrypt + Cloudflare DNS challenge
  - `/mnt/ByrroServer/docker-data/caddy/Caddyfile` - Added church services section

- **Comprehensive Documentation**:
  - `ARCHITECTURE.md` - Complete system architecture, data flows, and design decisions
  - `DEPLOYMENT.md` - Production deployment guide with troubleshooting
  - `.env.example` - Added CLOUDFLARE_API_TOKEN documentation

#### Changed

- **Date Format Standardization**: All dates now display as mm/dd/yyyy (was dd/mm/yyyy)
- **Video List Organization**: Monthly grouping instead of daily (less clutter)
- **Transcript Save Response**: Now includes `reanalysis_queued: true` flag
- **Progress Metadata Structure**: Added `total_videos`, `new_videos`, `current_video`, `current_video_title` fields

#### Fixed

- **Gemini API Key Configuration**: Updated production .env with correct API key `gen-lang-client-0496274851`
- **Job Metadata Tracking**: Worker now properly tracks and updates job progress during bulk imports
- **Network Connectivity**: Ensured culto_web can communicate with Caddy on byrro-net

#### Verified

- **V2 Analytics System**: Confirmed all new transcriptions use `AdvancedAnalyticsService`
- **Gemini Integration**: Chatbot and analytics using Gemini 1.5 Flash
- **3-Tier Transcription**: yt-dlp → youtube-transcript-api → faster-whisper pipeline working
- **Database Migrations**: All migrations up to date
- **Production Services**: All 5 containers running and healthy

### Technical Details

**API Endpoints**:
- `GET /api/videos/{video_id}/transcript` - Fetch transcript for inline display
- `PUT /api/videos/{video_id}/transcript` - Save transcript with auto re-analysis

**Database Changes**:
- No schema migrations required
- SermonReport deletion/recreation on transcript edit

**Configuration**:
- `CLOUDFLARE_API_TOKEN` environment variable documented
- Gemini API key updated in production

**Performance**:
- Transcript caching reduces redundant API calls
- Optimized progress updates (1-second polling interval)
- Per-video progress tracking with minimal database writes

### Deployment

**Production URL**: https://church.byrroserver.com
**Server**: 192.168.1.11 (byrro@192.168.1.11)
**Status**: ✅ Live

**Deployment Steps**:
1. ✅ Code deployed to ~/CultoTranscript
2. ✅ Services restarted (web, worker, scheduler)
3. ✅ Caddy configuration updated
4. ✅ DNS record created (church.byrroserver.com)
5. ✅ HTTPS certificate provisioning (auto)

---

## [1.0.0] - 2025-11-02

### 🎉 Initial Production Release

#### Added

**Core Transcription System**:
- 3-tier fallback transcription pipeline
  - Tier 1: yt-dlp auto-generated captions (fastest)
  - Tier 2: youtube-transcript-api (API-based)
  - Tier 3: faster-whisper AI (local processing)
- Support for videos up to 120 minutes (7200 seconds)
- Whisper model configuration (tiny, base, small, medium, large-v3)

**Analytics V2 with Gemini AI**:
- Advanced sermon analysis using Google Gemini 1.5 Flash
- Extract biblical citations, readings, mentions
- Identify themes and topics
- Generate improvement suggestions
- Store results in JSONB (SermonReport model)
- Rate limiting: 60 req/min, 1M tokens/min

**AI-Powered Chatbot**:
- Context-aware Q&A about sermon content
- pgvector embeddings for semantic search
- Retrieves top 5 relevant transcript segments
- Generates answers using Gemini AI
- Chat history stored in database

**Channel Management**:
- Monitor Brazilian church YouTube channels
- Weekly automatic scans for new videos
- Bulk import with date range filtering
- Exclude list for unwanted videos
- Channel statistics and rollups

**Web Interface**:
- FastAPI with Jinja2 templates
- Instance password authentication
- Dashboard with channel overview
- Video detail pages with analytics
- Transcript editor
- Job status tracking with progress indicators
- Chatbot interface

**Background Processing**:
- Redis-based job queue
- Worker service for transcriptions
- Scheduler service for channel monitoring
- Job metadata with step-by-step progress

**Database**:
- PostgreSQL 16 with pgvector extension
- SQLAlchemy ORM
- Alembic migrations
- Models: Channel, Video, Transcript, Job, SermonReport, TranscriptEmbedding

#### Technical Stack

- Python 3.11+
- FastAPI web framework
- PostgreSQL 16 + pgvector
- Redis 7
- Docker & Docker Compose
- yt-dlp for YouTube downloading
- youtube-transcript-api for API transcripts
- faster-whisper for AI transcription
- Google Gemini AI (gemini-1.5-flash)

#### Configuration

- Environment-based configuration (.env file)
- Configurable Whisper model size
- Configurable video duration limits
- Gemini API rate limiting
- Optional YouTube Data API integration

---

## Version History

- **[2.0.0]** - 2025-11-03: UI enhancements, auto re-analysis, detailed progress tracking, production deployment
- **[1.0.0]** - 2025-11-02: Initial release with core transcription, analytics V2, and chatbot features

---

## Upgrade Notes

### Upgrading to 2.0.0 from 1.0.0

1. **Pull latest code**:
   ```bash
   git pull origin main
   ```

2. **Restart services** (no database migrations required):
   ```bash
   docker restart culto_web culto_worker
   ```

3. **Update Gemini API key** (if not already set):
   ```bash
   nano ~/.env
   # Set GEMINI_API_KEY=gen-lang-client-0496274851
   docker restart culto_web culto_worker
   ```

4. **Configure Caddy** (for HTTPS access):
   - Add church.byrroserver.com to Caddyfile
   - Create DNS A record in Cloudflare
   - Reload Caddy: `docker exec caddy caddy reload`

5. **Test new features**:
   - Click video rows to expand transcripts
   - Try "Expandir Todos" / "Recolher Todos" buttons
   - Edit a transcript and verify re-analysis notification
   - Start a bulk import and watch detailed progress

---

## Future Roadmap

### Planned Features

- **Multi-tenant Support**: Multiple churches with isolated data
- **Video Segmentation**: Split long videos into chapters
- **Speaker Diarization**: Identify different speakers
- **Audio Quality Detection**: Warn about poor audio
- **Playlist Support**: Batch import entire playlists
- **Mobile App**: Native iOS/Android apps
- **API Rate Limiting**: Protect against abuse
- **WebSocket Updates**: Real-time progress without polling
- **Admin Dashboard**: System health and usage statistics

### Performance Improvements

- Read replicas for PostgreSQL
- Redis clustering
- CDN for static assets
- Batch analytics processing
- Horizontal worker scaling

---

**Maintained By**: CultoTranscript Team
**License**: See [LICENSE](LICENSE)
**Documentation**: See [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DEPLOYMENT.md](DEPLOYMENT.md)
