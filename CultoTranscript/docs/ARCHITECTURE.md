# CultoTranscript - System Architecture

## Overview

CultoTranscript is a distributed video processing and AI analysis system. It processes YouTube sermon videos through a pipeline that extracts transcripts, analyzes content with AI, generates embeddings for semantic search, and provides a chatbot interface for exploration.

## System Design

### Container Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Internet / Cloudflare DNS                                       │
│ church.byrroserver.com → 192.168.1.11 (host IP)                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
        ┌───────────────┐           ┌─────────────────┐
        │ Host-level    │           │ (Other Docker   │
        │ Caddy         │           │  projects on    │
        │ (byrro-net)   │           │  byrro-net)     │
        └───────┬───────┘           └─────────────────┘
                │
                │ Routes traffic to culto_caddy
                │
        ┌───────┴──────────────────────────────────────┐
        │                                              │
┌───────▼──────────────────────────────────────────────┴──┐
│ culto_caddy (reverse proxy)                             │
│ - Routes /api/v2/* → culto_web:8000                     │
│ - Routes / → culto_web:8000 (React SPA)                │
│ - HTTPS termination                                     │
│ - Rate limiting                                         │
└───────┬────────────────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────────────────┐
│ culto_culto_network (Docker bridge)                      │
├────────────────────────────────────────────────────────┤
│                                                        │
│ ┌────────────────────────────────────────────────┐   │
│ │ culto_web (FastAPI)                            │   │
│ │ ├─ Receives HTTP requests                      │   │
│ │ ├─ Returns React SPA (index.html)              │   │
│ │ ├─ REST API endpoints (/api/v2/*)              │   │
│ │ ├─ SSE real-time status updates                │   │
│ │ ├─ Session & authentication                    │   │
│ │ └─ Pushes jobs to Redis                        │   │
│ └────────────────────────────────────────────────┘   │
│          ↓ SQL              ↓ Redis                     │
│ ┌─────────────────┐  ┌──────────────────────────┐    │
│ │ culto_db        │  │ culto_redis (Queue)      │    │
│ │ PostgreSQL 16   │  │ └─ transcription_queue   │    │
│ │ + pgvector      │  │    (JSON objects)        │    │
│ │                 │  │                          │    │
│ │ Tables:         │  │ Blocking BLPOP pattern:  │    │
│ │ • videos        │  │ Worker waits 5s for job  │    │
│ │ • jobs          │  │ (no busy polling)        │    │
│ │ • transcripts   │  │                          │    │
│ │ • embeddings    │  │ Also used for caching:   │    │
│ │ • biblical_refs │  │ • config_reload_flag    │    │
│ │ • themes        │  │ • query results         │    │
│ │ • users         │  │ • session data          │    │
│ │ • ... 40+ more  │  │                          │    │
│ └─────────────────┘  └──────────────────────────┘    │
│          ↑ SQL                                         │
│ ┌────────────────────────────────────────────────┐   │
│ │ culto_worker (Background Job Processor)        │   │
│ │ ├─ Pulls jobs from Redis queue                 │   │
│ │ ├─ 6-step video processing pipeline            │   │
│ │ ├─ Calls Gemini API for AI analysis            │   │
│ │ ├─ Generates vector embeddings                 │   │
│ │ ├─ Posts SSE events to web                     │   │
│ │ └─ Updates job status in database              │   │
│ └────────────────────────────────────────────────┘   │
│                                                        │
│ ┌────────────────────────────────────────────────┐   │
│ │ culto_scheduler (Periodic Jobs)                │   │
│ │ ├─ Runs every 60 seconds                       │   │
│ │ ├─ Checks schedule_config table                │   │
│ │ ├─ Queries YouTube for new videos              │   │
│ │ ├─ Creates Video + Job records                 │   │
│ │ └─ Pushes jobs to Redis                        │   │
│ └────────────────────────────────────────────────┘   │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Why This Design?

| Component | Purpose | Why Separate? |
|-----------|---------|---------------|
| **culto_web** | FastAPI application | Must remain responsive for UI. Long jobs would block requests. SSE needs to work while jobs run. |
| **culto_worker** | Video processing | Jobs can take minutes. Must not block web. Can crash without losing data (jobs stay in Redis). Can be restarted independently for upgrades. |
| **culto_scheduler** | YouTube polling | Runs on fixed schedule. Can be restarted without stopping other services. If it crashes, next check happens at scheduled time. |
| **culto_redis** | Job queue | Memory-based BLPOP is microseconds vs DB queries (milliseconds). Survives web/worker crashes. Acts as communication buffer. |
| **culto_db** | Persistent storage | Single source of truth. Shared by all services. PostgreSQL + pgvector handles both relational and vector data. |
| **culto_caddy** | Internal reverse proxy | Isolates CultoTranscript from host network issues. Can restart without affecting other containers. Sets per-app security headers. |

## Video Processing Pipeline

### High-Level Flow

```
User Action (Web UI)
  ↓
1. User clicks "Import" or scheduler finds new video
  ↓
2. Web/Scheduler creates Video record (status='processing')
  ↓
3. Web/Scheduler creates Job record (status='queued')
  ↓
4. Web/Scheduler pushes JSON to Redis queue
  ↓
5. Worker polls Redis (BLPOP with 5s timeout)
  ↓
6. Worker executes 6-step pipeline (30+ minutes total)
  ↓
7. Worker posts SSE events every step
  ↓
8. Browser receives updates via EventSource listener
  ↓
9. Video status updates to 'completed' or 'failed'
  ↓
10. User sees final metadata, transcript, analysis
```

### 6-Step Processing Pipeline

#### Step 1: Extract Video Metadata (10%)
**Purpose**: Get basic info from YouTube

**Code**: `app/worker/main.py` lines ~300-350

**Process**:
```python
# Extract using yt-dlp
info = extract_info_from_youtube(youtube_url)

# Store in DB
video.title = info['title']  # e.g. "10/05/2025 - Culto Pr. Carlos"
video.duration_sec = info['duration']  # 5715
video.published_at = info['upload_date']  # 2025-10-05
video.language = detect_language(info['description'])
```

**Outputs to DB**:
- `videos.title` - Channel's title format
- `videos.duration_sec` - Total duration
- `videos.published_at` - YouTube publish date
- `videos.language` - Detected language

---

#### Step 2: Validate Duration (20%)
**Purpose**: Ensure video is within channel's configured limits

**Code**: `app/worker/main.py` lines ~350-380

**Process**:
```python
# Get channel config
channel = db.query(Channel).filter(Channel.id == job.channel_id).first()
min_duration = channel.min_video_duration_sec  # e.g. 300 (5 min)
max_duration = channel.max_video_duration_sec  # e.g. 7200 (2 hours)

# Validate
if video.duration_sec < min_duration:
    raise ValueError(f"Video too short: {video.duration_sec}s")
if video.duration_sec > max_duration:
    raise ValueError(f"Video too long: {video.duration_sec}s")
```

**Reason**: Filter out ads, intros, or accidentally uploaded very long videos

---

#### Step 3: Transcribe Video (30-50%)
**Purpose**: Extract text from audio using 3-tier strategy

**Code**: `app/worker/transcription_service.py` lines ~100-250

**3-Tier Waterfall Strategy**:

```
┌─────────────────────────────────────┐
│ Tier 1: yt-dlp auto-captions (1-2s) │
│ YouTube automatic captions          │
│ Success rate: ~70% for popular      │
└──────┬──────────────────────────────┘
       ├─ YES: Use it ✓
       │
       └─ NO (or empty)
          ↓
    ┌─────────────────────────────────────┐
    │ Tier 2: youtube-transcript-api (1s) │
    │ Official channel transcripts        │
    │ Success rate: ~30% (if enabled)     │
    └──────┬──────────────────────────────┘
           ├─ YES: Use it ✓
           │
           └─ NO
              ↓
        ┌──────────────────────────────────┐
        │ Tier 3: faster-whisper (3-5 min) │
        │ Local AI transcription           │
        │ Success rate: ~99% (always works)│
        └──────┬───────────────────────────┘
               └─ Use it ✓ (Fallback)
```

**Example Transcription**:
```python
# Tier 1: Try auto-captions
captions = yt_dlp_service.extract_captions(youtube_id)
if captions:
    transcript = captions  # 150,000 chars
    source = "auto_cc"
else:
    # Tier 2: Try official transcript
    try:
        transcript = youtube_transcript_api.get(youtube_id)
        source = "official"
    except:
        # Tier 3: Fallback to Whisper
        audio_path = download_audio(youtube_url)  # ~200-500MB
        transcript = whisper_model.transcribe(audio_path)
        source = "whisper"

        # Cache for future use
        os.remove(audio_path)  # ~500MB

# Store in DB
video.transcript = transcript  # Full text
video.transcript_source = source
video.transcript_hash = hash(transcript)  # For change detection
```

**Output**: `videos.transcript` - Full text (100KB - 500KB typically)

---

#### Step 4: Detect Sermon Start (60%)
**Purpose**: Skip intro/ads, find where actual sermon starts

**Code**: `app/ai/sermon_detector.py` lines ~40-120

**Process**:
```python
# Send first 2000 chars to Gemini
intro_text = video.transcript[:2000]

gemini_response = llm_client.call(
    prompt=f"""
    This is the start of a Portuguese sermon transcript.
    Find the approximate character position where the actual sermon begins
    (skip: intro, announcements, prayer requests, songs).

    Return only: JSON with "start_position": <number>

    Transcript start:
    {intro_text}
    """
)

# Parse response
start_position = json.loads(gemini_response)['start_position']

# Store
video.sermon_start_time = (start_position / avg_chars_per_second)  # Convert to seconds
video.sermon_text = video.transcript[start_position:]  # Trimmed
```

**Example Output**:
```
Full transcript: 150,000 chars over 95 minutes
Start position: ~12,000 chars (8 min into video)
Result: Sermon text starts at 8:00, saved as "sermon_start_time"
```

---

#### Step 5: Advanced AI Analysis (70%)
**Purpose**: Extract meaning, themes, biblical refs, suggestions

**Code**: `app/worker/advanced_analytics_service.py` lines ~50-300

**Sub-components**:

##### 5a. Theme Analysis
```python
# Extract main theological themes
themes = theme_analyzer.analyze(video.sermon_text)

# Store
for theme in themes:  # e.g. ["faith", "redemption", "prayer"]
    db.add(Theme(
        video_id=video.id,
        theme_name=theme,
        confidence=0.92
    ))
```

**Output**: `themes` table with 5-15 rows per video

##### 5b. Biblical Passage Detection
```python
# Find scripture references in transcript
biblical_refs = biblical_classifier.extract(video.sermon_text)

# Normalize and store
for ref in biblical_refs:  # e.g. "Romans 3:23", "Genesis 1:1-3"
    passage = normalize_passage(ref)  # "Romans 3:23" → "Rom 3:23"

    db.add(BiblicalPassage(
        video_id=video.id,
        book=passage.book,  # "Romans"
        chapter=3,
        verse_start=23,
        verse_end=23,
        context=context  # Surrounding text
    ))
```

**Output**: `biblical_passages` table with 5-30 rows per video

##### 5c. Suggested Title Generation
```python
# Generate AI title if missing
suggested_title = ai_summarizer.generate_title(
    transcript=video.sermon_text,
    original_title=video.title
)

# Store
video.suggested_title = suggested_title
# e.g. "Obedecer a Deus traz prosperidade" instead of "10/05/2025 - Culto Pr. Carlos"
```

**Output**: `videos.suggested_title` - Replaces YouTube auto-title

##### 5d. Main Points Extraction
```python
# Extract 3-5 key points from sermon
main_points = sermon_coach.extract_points(video.sermon_text)

# Store in ai_summary as JSON
video.ai_summary = {
    "main_points": main_points,  # List[str]
    "themes": themes,            # List[str]
    "key_scripture": key_refs,   # List[str]
    ...
}
```

**Output**: `videos.ai_summary` - JSON structure

##### 5e. Inconsistency Detection
```python
# Find contradictions, unclear explanations
inconsistencies = inconsistency_detector.analyze(video.sermon_text)

# Store
for issue in inconsistencies:
    db.add(Inconsistency(
        video_id=video.id,
        issue_type=issue.type,  # "contradiction" | "unclear_definition"
        description=issue.desc,
        position=issue.char_pos
    ))
```

**Output**: `inconsistencies` table

##### 5f. Sensitivity Flags
```python
# Detect potentially sensitive topics
flags = sensitivity_analyzer.analyze(video.sermon_text)

# Store (for content filtering)
for flag in flags:
    db.add(SensitivityFlag(
        video_id=video.id,
        flag_type=flag.type,  # "violence", "explicit", "politics"
        confidence=flag.confidence
    ))
```

**Output**: `sensitivity_flags` table

---

#### Step 6: Generate Embeddings (90%)
**Purpose**: Create vector representation for semantic search

**Code**: `app/ai/embedding_service.py` lines ~80-200

**Process**:
```python
# Split sermon into non-overlapping segments
# ~250 words each = ~2000 chars per segment
segments = split_into_segments(
    text=video.sermon_text,
    target_words=250,
    overlap=0  # Non-overlapping
)

# For each segment, generate vector
for i, segment in enumerate(segments):
    # Call embedding model (e.g., Google's text-embedding-3-large)
    vector = embedding_model.embed(segment)
    # Returns: [0.123, -0.456, 0.789, ...] (768 dimensions)

    # Store in pgvector
    db.add(TranscriptEmbedding(
        video_id=video.id,
        segment_number=i,
        segment_text=segment,
        embedding=vector,  # pgvector stores this as native vector type
        start_position=segments[i].char_position,
        end_position=segments[i].end_char_position
    ))
```

**Example**:
```
Video: 95 minutes (150,000 chars)
Segments: 150,000 / 2000 = 75 segments
Vectors: 75 x 768 dimensions each
Storage: ~1.8 MB per video in pgvector

Later, user asks chatbot: "What does the pastor say about faith?"
1. User question embedded: [0.234, -0.567, 0.123, ...] (768 dims)
2. Search similar vectors: SELECT * FROM transcript_embeddings
   WHERE video_id = ?
   ORDER BY embedding <-> user_vector  -- pgvector dot product
   LIMIT 5
3. Return top 5 most similar segments
```

**Output**: `transcript_embeddings` table - 75-200 rows per video

---

### Complete Example: End-to-End Processing

**User Action**: Clicks "Import Videos" for YouTube channel "Igreja Vida Abundante"

**Step 1: Web Container**
```
POST /api/v2/admin/import-videos
  ├─ Body: { channel_id: 1, youtube_urls: ["...fnv-0U2hqhc..."] }
  ├─ Creates Video record:
  │  └─ id=26, channel_id=1, youtube_id="fnv-0U2hqhc",
  │     status='processing', created_at=now()
  ├─ Creates Job record:
  │  └─ id=1423, video_id=26, status='queued',
  │     job_type='transcribe_video'
  └─ Pushes to Redis:
     └─ RPUSH "transcription_queue"
        '{"job_id":1423, "video_id":26, "youtube_id":"fnv-0U2hqhc", ...}'
```

**UI Update (Real-time via SSE)**:
```
Browser EventSource listener opens to /api/v2/events/stream
  ├─ Connected: "Connection established"
  ├─ Status Update: {"type":"video.status", "video_id":26, "status":"processing"}
  └─ Video in list now shows "PROCESSANDO" badge
```

**Step 2: Worker Container (BLPOP)**
```
Worker.main() loop:
  ├─ Calls: redis_client.blpop("transcription_queue", timeout=5)
  ├─ BLOCKED for up to 5 seconds waiting
  ├─ Receives: (b"transcription_queue", b'{"job_id":1423, ...}')
  ├─ Decodes JSON
  └─ process_video(job_id=1423, video_id=26, youtube_id="fnv-0U2hqhc")
```

**Step 3-6: Worker Processing (with SSE broadcasts)**

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: Extract Metadata (1 sec)                        │
├─────────────────────────────────────────────────────────┤
│ yt_dlp downloads: title, duration, upload_date          │
│ Duration: 5397 seconds (89 minutes)                     │
│ Title: "10/05/2025 - Culto Pr. Carlos Patente AO VIVO" │
│ → POST /api/v2/events/broadcast                         │
│   {"type":"step_progress", "step":1, "progress":10}     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Step 2: Validate Duration (1 sec)                       │
├─────────────────────────────────────────────────────────┤
│ Min: 300s (5 min), Max: 7200s (2 hours) ✓               │
│ 5397s is between min-max ✓                              │
│ → POST /api/v2/events/broadcast                         │
│   {"type":"step_progress", "step":2, "progress":20}     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Step 3: Transcription (1-5 mins)                        │
├─────────────────────────────────────────────────────────┤
│ Tier 1: Check auto-captions → NOT FOUND                 │
│ Tier 2: Check official transcript → NOT FOUND           │
│ Tier 3: Download audio (500 MB)                         │
│         Load Whisper model (4.7 GB GPU)                 │
│         Process audio → 165,000 characters              │
│ → POST /api/v2/events/broadcast                         │
│   {"type":"step_progress", "step":3, "progress":50}     │
│   {"type":"transcript_ready", "char_count":165000}      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Step 4: Detect Sermon Start (10 secs + API time)        │
├─────────────────────────────────────────────────────────┤
│ Call Gemini: "Where does sermon start?"                 │
│ Response: position 14500 chars = ~9 minutes in         │
│ Store: sermon_start_time = 540 seconds                  │
│ → POST /api/v2/events/broadcast                         │
│   {"type":"step_progress", "step":4, "progress":60}     │
└─────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ Step 5: AI Analysis (15-20 mins)                         │
├──────────────────────────────────────────────────────────┤
│ Call Gemini 40 times:                                    │
│   - Extract themes: ["faith", "redemption", ...]        │
│   - Find scripture: ["Romans 3:23", "John 3:16", ...]  │
│   - Generate title: "Obedecer a Deus traz prosperidade" │
│   - Extract points, check consistency, flags            │
│                                                          │
│ Store: themes (10 rows), biblical_passages (20 rows),   │
│        inconsistencies (5 rows), etc.                   │
│                                                          │
│ → POST /api/v2/events/broadcast (multiple times)        │
│   {"type":"step_progress", "step":5, "progress":70}     │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ Step 6: Generate Embeddings (2-3 mins)                  │
├──────────────────────────────────────────────────────────┤
│ Split into 75 segments (~2000 chars each)               │
│ For each segment:                                        │
│   - Call embedding API: "embed this text"               │
│   - Receive: [0.123, -0.456, ...] (768 dims)            │
│   - Store in pgvector table                             │
│                                                          │
│ Total: 75 rows in transcript_embeddings table           │
│ Size: ~1.8 MB                                            │
│                                                          │
│ → POST /api/v2/events/broadcast                         │
│   {"type":"step_progress", "step":6, "progress":90}     │
│   {"type":"video.status", "status":"completed"}         │
└──────────────────────────────────────────────────────────┘
```

**Total Time**: 20-25 minutes (mostly API calls + Whisper)

**Final Database State**:
```
videos.id=26:
  ├─ status: 'completed' ✓
  ├─ transcript: 165,000 chars (full text)
  ├─ suggested_title: "Obedecer a Deus traz prosperidade"
  └─ sermon_start_time: 540 (seconds)

Jobs.id=1423:
  ├─ status: 'completed' ✓
  ├─ started_at: 2026-01-20 08:15:00
  └─ completed_at: 2026-01-20 08:40:00

themes (10 rows): faith, redemption, obedience, ...

biblical_passages (20 rows):
  ├─ Romans 3:23
  ├─ John 3:16
  └─ ...

transcript_embeddings (75 rows):
  ├─ Segment 1: [vector 768 dims]
  ├─ Segment 2: [vector 768 dims]
  └─ ...
```

---

## AI Chatbot: Knowledge Modes

The chatbot provides two ways to interact with sermon content:

### Mode 1: Database-Only (Somente Sermões)

**Purpose**: Retrieve information from actual sermons

**Flow**:
```
User: "What did the pastor say about faith?"
   ↓
UI chatService.sendMessage(message, mode='database_only')
   ↓
Backend receives: knowledge_mode='database_only'
   ↓
llm_client.call(prompt=SERMON_SPECIALIST_PROMPT)
   ↓
chatbot_service._build_system_prompt():
   └─ "Você é um assistente especializado em sermões desta igreja"
      "Responda baseado APENAS nos sermões disponíveis"
      "Se não encontrar informação, diga claramente"
   ↓
hybrid_search.search(query, channel_id=1):
   ├─ BM25 keyword search: "faith" → Find segments with word
   ├─ Vector search: embed("faith") → Find semantically similar
   ├─ Combine results (top 5 segments from both)
   └─ Return with citation info (video_id, timestamp, speaker)
   ↓
Gemini combines:
   ├─ System prompt (database-only mode)
   ├─ Search results (actual sermon excerpts)
   └─ User question
   ↓
Response: "Em [Video X] (02/01/2026), o pastor Carlos citou...
           [Excerpt from segment]. Veja em 45:32 do vídeo."
```

**Example Search Result**:
```python
# User asks about "faith"
segments = hybrid_search(
    query="What about faith?",
    channel_id=1  # Only this church's sermons
)

# Returns:
[
    {
        "video_id": 9,
        "video_title": "Somente a Fé (12/01/2026)",
        "segment": "Faith is not just belief, it is action taken in trust...",
        "start_position": 2400,  # chars into transcript
        "speaker": "Pr. João Silva",
        "bm25_score": 0.92,  # Keyword match
        "vector_score": 0.87  # Semantic match
    },
    # ... 4 more results
]
```

### Mode 2: Global (Global / Internet)

**Purpose**: General Bible/theology knowledge from Gemini

**Flow**:
```
User: "What does Genesis 1:1 mean?"
   ↓
UI chatService.sendMessage(message, mode='global')
   ↓
Backend receives: knowledge_mode='global'
   ↓
chatbot_service._build_system_prompt():
   └─ "Você é um assistente bíblico e teológico"
      "Responda com conhecimento geral da Bíblia"
      "NÃO use os sermões locais"
   ↓
Skip all sermon retrieval (no database queries)
   ↓
Gemini combines:
   ├─ System prompt (general knowledge mode)
   ├─ User question
   └─ Chat history
   ↓
Response: "Gênesis 1:1 'No princípio, Deus criou os céus e a terra'
           é o começo de toda a narrativa bíblica. Estabelece que..."
```

**Key Difference**:
```
Database-Only:  Sermon segments → Gemini → Answer WITH citations
Global:         Just question  → Gemini → Answer from training
```

---

## Vector Embeddings: Deep Dive

### What Are Embeddings?

Embeddings are numerical vectors that represent meaning:

```
Text: "Jesus died for our sins and rose again"
      ↓ (embedding model)
Vector: [0.234, -0.567, 0.123, 0.890, ..., -0.341]
        └─ 768 dimensions
        └─ Can represent any amount of text in fixed space
        └─ Similar meanings → similar vectors (dot product distance)
```

### pgvector Integration

PostgreSQL pgvector extension stores vectors as native columns:

```sql
-- Table definition
CREATE TABLE transcript_embeddings (
    id BIGSERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id),
    segment_number INTEGER,
    segment_text TEXT,
    embedding vector(768),  -- ← pgvector type!
    start_position INTEGER,
    end_position INTEGER,
    created_at TIMESTAMP
);

-- Create index for fast similarity search
CREATE INDEX ON transcript_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Semantic Search Example

**User asks**: "How should we treat our enemies?"

**Process**:
```python
# 1. Embed the question
user_vector = embedding_model.embed("How should we treat enemies?")
# Result: [0.123, -0.456, 0.234, ...] (768 dims)

# 2. Search database using pgvector
results = db.query(TranscriptEmbedding).filter(
    TranscriptEmbedding.video_id.in_(allowed_videos)
).order_by(
    TranscriptEmbedding.embedding.cosine_distance(user_vector)
).limit(5).all()

# 3. Get top results with similarity scores
for result in results:
    similarity = 1 - cosine_distance(user_vector, result.embedding)
    print(f"{similarity:.2%}: {result.segment_text[:100]}")

# Output:
# 92%: "Love your enemies. Do good to those who hate you..."
# 89%: "The Lord teaches us to forgive even those who hurt us..."
# 87%: "In Matthew 5, Jesus commands us to turn the other cheek..."
# 85%: "Enemies become friends when we show them the love of Christ..."
# 83%: "Patience and forgiveness are marks of a mature Christian..."
```

---

## Data Storage: Database Schema (Key Tables)

```sql
-- Videos being processed
videos (id, channel_id, youtube_id, status, transcript, ...)

-- Processing jobs queue (also in Redis)
jobs (id, video_id, status, job_type, started_at, error_message)

-- Full sermon text split into segments
transcript_embeddings (id, video_id, segment_number, embedding)
  └─ 75-200 rows per video

-- Extracted themes from AI analysis
themes (id, video_id, theme_name, confidence)
  └─ 5-15 rows per video

-- Bible verses mentioned in sermon
biblical_passages (id, video_id, book, chapter, verse_start, context)
  └─ 5-30 rows per video

-- User chat history
gemini_chat_history (
    id, channel_id, session_id, user_message, ai_response, knowledge_mode
)
  └─ Grows with each chat interaction

-- Redis queue (separate from DB)
transcription_queue (FIFO list in Redis)
  └─ Job objects: {"job_id": 1423, "video_id": 26, ...}
```

---

## Real-Time Updates: SSE (Server-Sent Events)

### Event Flow

```
Worker:                          SSE Manager:              Browser:
1. finishes step 2
   ↓
2. POST /api/v2/events/broadcast
   {
     "type": "step_progress",
     "video_id": 26,
     "step": 2,
     "progress": 20
   }
                                 ↓
                        Receives broadcast
                                 ↓
                        Queue for all SSE clients
                        (in-memory dict)
                                 ↓
                                              GET /api/v2/events/stream
                                              (client opens connection)
                                              ↓
                                              Sends: data: {...json...}\n\n
                                              ↓
                                              Browser receives event
                                              ↓
                                              JavaScript triggers update
                                              ↓
                                              React re-renders UI
                                              ↓
                                              Video shows "20% complete"
```

### Why SSE Instead of Polling?

```
Polling:                         SSE:
├─ Browser polls every 1s        ├─ One persistent connection
├─ 60 requests/min per video     ├─ ~0.1 requests/min
├─ Wasteful (mostly empty)       ├─ Updates only when data available
└─ Uses more bandwidth           └─ Uses less bandwidth
```

---

## Redis Queue: Job Persistence

### Why Redis Instead of Database Queue?

```
Database Queue:                  Redis Queue:
├─ Slower (disk I/O)             ├─ Faster (memory)
├─ Race conditions if not atomic ├─ BLPOP is atomic
├─ Need polling loop             ├─ BLPOP blocks (no polling)
└─ More complex code             └─ Simpler pattern
```

### Example Job in Queue

```json
{
  "job_id": 1423,
  "video_id": 26,
  "youtube_id": "fnv-0U2hqhc",
  "reprocess": false,
  "channel_id": 1
}
```

### Worker's BLPOP Loop

```python
while True:
    # Block for 5 seconds waiting for job
    result = redis_client.blpop("transcription_queue", timeout=5)

    if result:
        # result = (b"transcription_queue", b'{"job_id": 1423, ...}')
        key, job_json = result
        job = json.loads(job_json)

        # Process the job (takes 20-30 minutes)
        try:
            process_video(job['video_id'])
            # Job successfully completed (removed from queue)
        except Exception as e:
            # Job failed - stays in DB, NOT re-queued
            db_session.query(Job).filter(
                Job.id == job['job_id']
            ).update({'status': 'failed', 'error_message': str(e)})
            db_session.commit()
    else:
        # Timeout - no job, sleep and try again
        time.sleep(1)
```

---

## Gemini API Integration

### Multi-Model Strategy

```
Task                    Model                   Reason
──────────────────────────────────────────────────────────
General chat           gemini-2.5-flash        Fast, good quality
Bible questions        gemini-2.5-flash        Good knowledge
Theme extraction       gemini-2.5-flash        Adequate
Title generation       gemini-2.5-flash        Creative
Long analysis          gemini-2.5-flash        Up to 2M tokens
Fallback (slow)        gemma-3-4b-it          Cheaper, local
```

### Rate Limiting

```python
# Configured limits per minute
GEMINI_REQUEST_BUDGET_PER_MINUTE = 8      # Max 8 calls/min
GEMINI_INPUT_TOKEN_BUDGET = 12000         # Max 12k input tokens

# When limit reached:
# 1. Queue request
# 2. Sleep to next minute boundary
# 3. Retry

# Example:
for i in range(40):  # 40 API calls for a sermon
    # Each iteration waits if needed
    llm_response = llm_client.call(...)
    # If rate limit hit: sleep 30s, then retry
```

---

## Deployment Architecture

See `docker-compose.yml` for container configuration and `.claude/CLAUDE.md` for networking details.

Key points:
- External volumes for data persistence
- culto_web must be on both networks (culto_network + byrro-net)
- Use explicit hostname `culto_redis` not `redis` (avoids conflicts)
- Restart scheduler after schedule config changes
