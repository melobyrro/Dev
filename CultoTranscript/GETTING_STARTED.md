# CultoTranscript - Quick Start Guide

## What You Have

A complete sermon transcription and analytics system for Brazilian churches, featuring:

### Core Features
- **3-tier transcription**: Auto-CC → YouTube API → Whisper (Intel GPU)
- **Bible reference detection**: All 66 books with PT-BR variants
- **Theme tagging**: 6 themes (Cristo-cêntrica, Motivacional, Prosperidade, Família, Evangelismo, Santidade)
- **Automated scheduling**: Daily/weekly channel checks
- **Duration validation**: Rejects videos > 2h

### Tech Stack
- **Web**: FastAPI + Jinja2 (PT-BR UI)
- **Worker**: Python + faster-whisper (OpenVINO for Intel GPU)
- **Database**: PostgreSQL 16
- **Queue**: Redis
- **Scheduler**: APScheduler

## First Steps

### 1. Configure Environment

```bash
cp .env.example .env
nano .env
```

**Key settings:**
- `INSTANCE_PASSWORD`: Your login password (default: admin123)
- `WHISPER_MODEL_SIZE`: medium (recommended for Intel UHD 770)
- `MAX_VIDEO_DURATION`: 7200 (120 minutes)

### 2. Start Services

**Option A - Quick start script:**
```bash
./start.sh
```

**Option B - Manual:**
```bash
cd docker
docker-compose up -d
```

### 3. Access Application

Open http://localhost:8000

Login with password from `.env` (default: `admin123`)

## Usage Workflows

### Transcribe Single Video

1. Dashboard → paste YouTube URL
2. Click "Iniciar Transcrição"
3. Wait 5-15 minutes (depends on video length and GPU)
4. View results in Videos → click video title

**What happens:**
1. Extracts video metadata (title, duration, published date)
2. Validates duration (< 120 min)
3. Tries auto-CC → YouTube API → Whisper (first successful wins)
4. Saves transcript to database
5. Detects Bible references (e.g., "João 3:16")
6. Tags themes based on keywords
7. Generates word count and stats

### Monitor YouTube Channel

1. Channels → + Novo Canal
2. Fill in:
   - Title: Church name
   - URL: `https://www.youtube.com/@YourChurch`
   - Channel ID: Get from YouTube channel about page
3. Save

The scheduler will:
- Check daily at 8 AM
- Check weekly on Sunday at 6 AM
- Queue new videos automatically
- Respect 120-minute limit

### View Reports

**Top Bible Books:**
- Reports → Top Livros Citados
- Shows most cited books in last 30 days

**Top Themes:**
- Reports → Top Temas
- Shows theme distribution

## Architecture Overview

```
User Request → FastAPI → Redis Queue → Worker
                   ↓                      ↓
              PostgreSQL  ←───── Analytics (Bible + Themes)
                   ↑
              Scheduler (checks channels)
```

### Service Responsibilities

**web** (port 8000):
- UI in Portuguese
- Auth via single instance password
- REST API for AJAX calls
- Session management

**worker**:
- Polls Redis queue
- Runs yt-dlp / youtube-transcript-api / Whisper
- Calls analytics_service to extract Bible refs + themes
- Updates job status in DB

**scheduler**:
- Runs APScheduler (daily + weekly)
- Lists new videos from channels via yt-dlp
- Queues jobs in Redis
- Tracks last_checked_at per channel

**db** (PostgreSQL):
- Tables: users, channels, videos, transcripts, verses, themes, jobs, audit_logs
- Stores all persistent data

**redis**:
- Job queue: `transcription_queue`
- Used by web to queue, worker to process

## File Locations

### Application Code
- `app/common/`: Database models, Bible detector, theme tagger
- `app/web/`: FastAPI routes, templates, auth
- `app/worker/`: Transcription services (yt-dlp, Whisper, analytics)
- `app/scheduler/`: APScheduler main loop

### Configuration
- `analytics/dictionaries/themes_pt.json`: Theme keywords (editable!)
- `migrations/001_initial_schema.sql`: Database schema
- `.env`: Environment variables
- `docker/docker-compose.yml`: Service orchestration

## Customization

### Add New Theme

Edit `analytics/dictionaries/themes_pt.json`:

```json
{
  "Avivamento": {
    "keywords": ["avivamento", "renovação", "fogo", "poder"],
    "weight": 1.0,
    "description": "Mensagens sobre avivamento espiritual"
  }
}
```

Restart worker: `docker-compose restart worker`

### Change Max Duration

Edit `.env`:
```env
MAX_VIDEO_DURATION=10800  # 3 hours
```

Restart all: `docker-compose restart`

### Adjust Whisper Model

For faster but less accurate:
```env
WHISPER_MODEL_SIZE=small
```

For better quality but slower:
```env
WHISPER_MODEL_SIZE=large-v3
```

## Troubleshooting

### Check Logs

```bash
cd docker
docker-compose logs -f web      # Web service
docker-compose logs -f worker   # Worker
docker-compose logs -f scheduler # Scheduler
docker-compose logs -f db       # Database
```

### Restart Services

```bash
docker-compose restart web worker scheduler
```

### Reset Database (⚠️ DELETES ALL DATA)

```bash
docker-compose down
docker volume rm docker_postgres_data
docker-compose up -d
```

### Worker Stuck

```bash
# Check Redis queue length
docker-compose exec redis redis-cli llen transcription_queue

# Flush queue
docker-compose exec redis redis-cli del transcription_queue

# Restart worker
docker-compose restart worker
```

## Performance Tips

### Intel UHD 770 Optimization

The worker is configured for Intel UHD 770 via:
- OpenVINO backend
- `WHISPER_DEVICE=auto`
- Device passthrough: `/dev/dri:/dev/dri`

Expected speed: ~2-3 minutes for 1 hour video (medium model)

### CPU-Only Mode

If GPU not available, edit `docker-compose.yml`:

```yaml
worker:
  environment:
    - WHISPER_DEVICE=cpu
  # Remove GPU device passthrough
```

Expected speed: ~10-15 minutes for 1 hour video (small model recommended)

## Next Steps

1. ✅ Test with a short video (< 10 min)
2. ✅ Add your church's YouTube channel
3. ✅ Review themes in `analytics/dictionaries/themes_pt.json`
4. ✅ Configure `.env` for production (change passwords!)
5. ✅ Set up Caddy reverse proxy (see `Caddyfile.example`)
6. ✅ Monitor logs for first 24h

## Support

- **README.md**: Full documentation
- **GitHub Issues**: Report bugs
- **Docker logs**: First place to check errors

---

Happy transcribing! 🎤📖
