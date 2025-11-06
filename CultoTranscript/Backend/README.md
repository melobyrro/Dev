# CultoTranscript Backend Worker

## Overview

The **Backend/** directory contains the new API v2 implementation for CultoTranscript, focused on real-time event streaming and modern API patterns.

**Status:** Phase 1 Complete - SSE Endpoint Implementation

---

## Directory Structure

```
Backend/
├── api/v2/
│   ├── __init__.py
│   ├── events.py           # SSE endpoint for real-time updates
│   └── videos.py           # Video API endpoints (stub)
├── services/
│   ├── __init__.py
│   └── sse_manager.py      # SSE connection manager
├── middleware/
│   ├── __init__.py
│   ├── cors.py             # CORS configuration
│   └── csrf.py             # CSRF protection
├── dtos.py                 # Pydantic DTOs (mirrors shared/dtos.ts)
├── requirements.txt        # Python dependencies
├── INTEGRATION.md          # Integration guide
└── README.md               # This file
```

---

## Features

### Phase 1 - Complete

✅ **Server-Sent Events (SSE) Endpoint**
- Real-time event streaming to clients
- Automatic heartbeat every 30 seconds
- Support for multiple concurrent connections
- Event types: video.status, summary.ready, error, heartbeat

✅ **Python DTOs**
- Pydantic models matching TypeScript DTOs
- Type-safe data validation
- JSON serialization support

✅ **CORS Middleware**
- React dev server support (localhost:5173)
- Production domain configuration
- Credentials and headers support

✅ **CSRF Protection**
- Token generation and validation
- Session-based storage
- Exempt paths configuration

✅ **SSE Manager Service**
- Client connection management
- Event broadcasting
- Heartbeat scheduling
- Graceful shutdown

---

## Installation

1. Install dependencies:
```bash
pip install -r Backend/requirements.txt
```

2. Follow integration steps in `INTEGRATION.md`

---

## API Endpoints

### SSE Events

**GET /api/v2/events/stream**

Server-Sent Events stream for real-time updates.

**Response:** `text/event-stream`

**Event Types:**
- `video.status` - Video processing status updates
- `summary.ready` - Video summary completed
- `error` - Error notifications
- `heartbeat` - Connection keep-alive

**Example Client:**
```javascript
const eventSource = new EventSource('http://localhost:8000/api/v2/events/stream');

eventSource.addEventListener('video.status', (event) => {
  const data = JSON.parse(event.data);
  console.log('Status:', data.status, 'Progress:', data.progress);
});

eventSource.addEventListener('heartbeat', () => {
  console.log('Connection alive');
});
```

**GET /api/v2/events/health**

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "sse_events",
  "connected_clients": 2
}
```

### Video API (Stub)

**GET /api/v2/videos/**
- List all videos

**GET /api/v2/videos/{video_id}**
- Get video details

**POST /api/v2/videos/**
- Create/submit new video

**DELETE /api/v2/videos/{video_id}**
- Delete video

*Note: Full implementation pending in Phase 2*

---

## DTOs (Data Transfer Objects)

All DTOs are defined in `Backend/dtos.py` using Pydantic.

### Core DTOs

**VideoStatus** (Enum)
- PROCESSING
- PROCESSED
- FAILED
- PENDING
- QUEUED

**VideoDTO**
```python
{
  "id": "uuid",
  "title": "Sermon Title",
  "youtube_id": "dQw4w9WgXcQ",
  "status": "PROCESSING",
  "duration": 3600,
  "created_at": "2025-11-05T12:00:00Z",
  "channel_id": "uuid"
}
```

**SummaryDTO**
```python
{
  "themes": ["Faith", "Prayer"],
  "passages": [...],
  "citations": [...],
  "speaker": "Pastor Name",
  "word_count": 5000,
  "key_points": ["Point 1", "Point 2"]
}
```

### Event DTOs

**VideoStatusEventDTO**
```python
{
  "type": "video.status",
  "timestamp": "2025-11-05T12:00:00Z",
  "video_id": "uuid",
  "status": "PROCESSING",
  "progress": 45,
  "message": "Transcribing audio..."
}
```

**HeartbeatEventDTO**
```python
{
  "type": "heartbeat",
  "timestamp": "2025-11-05T12:00:00Z"
}
```

See `dtos.py` for complete documentation.

---

## Usage Examples

### Broadcasting Events

```python
from Backend.services.sse_manager import sse_manager
from Backend.dtos import VideoStatusEventDTO, EventType, VideoStatus
from datetime import datetime

# Create event
event = VideoStatusEventDTO(
    type=EventType.VIDEO_STATUS,
    timestamp=datetime.utcnow().isoformat() + "Z",
    video_id="abc-123",
    status=VideoStatus.PROCESSING,
    progress=75,
    message="Analyzing content..."
)

# Broadcast to all connected clients
await sse_manager.broadcast_event(event)
```

### Setting up CORS

```python
from fastapi import FastAPI
from Backend.middleware import setup_cors

app = FastAPI()
setup_cors(app)  # Development mode

# Or for production:
# from Backend.middleware import setup_production_cors
# setup_production_cors(app, "https://church.byrroserver.com")
```

### Adding CSRF Protection

```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from Backend.middleware import CSRFMiddleware

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="secret")
app.add_middleware(CSRFMiddleware)
```

---

## Testing

### Manual Testing

1. Start the server:
```bash
docker-compose up -d culto_web
```

2. Test SSE stream:
```bash
curl -N http://localhost:8000/api/v2/events/stream
```

3. Test health check:
```bash
curl http://localhost:8000/api/v2/events/health
```

4. Browser test:
```javascript
// Open browser console and run:
const es = new EventSource('http://localhost:8000/api/v2/events/stream');
es.onmessage = (e) => console.log(e.data);
```

### Integration Tests (TODO)

```bash
pytest tests/backend/test_sse.py
pytest tests/backend/test_cors.py
pytest tests/backend/test_csrf.py
```

---

## Configuration

### Environment Variables

```bash
# CORS Configuration
FRONTEND_URL=http://localhost:5173

# CSRF Configuration
CSRF_EXEMPT_PATHS=/api/v2/events/stream,/health,/docs

# SSE Configuration
SSE_HEARTBEAT_INTERVAL=30
```

### Middleware Order

**Important:** Middleware runs in reverse order of registration.

```python
# Last to run (outermost)
setup_cors(app)

# Third
app.add_middleware(AuthMiddleware)

# Second
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# First to run (innermost)
app.add_middleware(CSRFMiddleware)
```

---

## Architecture Notes

### SSE Manager Design

- **Singleton Pattern:** Single `sse_manager` instance per web service
- **Async Queues:** Each client gets dedicated asyncio.Queue
- **Heartbeat Task:** Background task sends periodic heartbeats
- **Graceful Shutdown:** Cleans up connections on service stop

### Cross-Process Communication

The SSE manager lives in the web service process. Workers need to send events via:

1. **HTTP POST** to internal broadcast endpoint (recommended)
2. **Redis Pub/Sub** for event distribution
3. **Message Queue** (RabbitMQ, Kafka) for high-volume scenarios

**Phase 2 will implement:** Internal HTTP endpoint for workers to POST events.

### Security Considerations

- **CSRF Protection:** Required for state-changing requests
- **CORS:** Restricted to specific origins
- **Session Management:** Tokens stored in server-side sessions
- **Rate Limiting:** TODO in Phase 3

---

## Roadmap

### Phase 2 (Next)
- [ ] Implement full Video API endpoints
- [ ] Add internal broadcast endpoint for workers
- [ ] Worker integration with SSE events
- [ ] Event filtering (subscribe to specific videos)

### Phase 3 (Future)
- [ ] WebSocket support (bidirectional)
- [ ] Event replay/history
- [ ] Rate limiting
- [ ] Metrics and monitoring
- [ ] Event acknowledgments

---

## Troubleshooting

See `INTEGRATION.md` for detailed troubleshooting guide.

**Common Issues:**

1. **SSE connection closes immediately**
   - Check nginx/Caddy buffering (`X-Accel-Buffering: no`)
   - Verify CORS configuration

2. **CSRF validation fails**
   - Ensure SessionMiddleware is configured
   - Check X-CSRF-Token header is sent

3. **No heartbeats**
   - Verify heartbeat task started (check logs)
   - Test `/api/v2/events/health` endpoint

---

## Contributing

When adding new features to Backend/:

1. Update DTOs in `dtos.py` if data structures change
2. Add endpoint documentation in docstrings
3. Update `INTEGRATION.md` with integration steps
4. Add tests for new functionality
5. Update this README

---

## Resources

- **FastAPI SSE:** https://github.com/sysid/sse-starlette
- **Pydantic Docs:** https://docs.pydantic.dev/
- **CORS Guide:** https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
- **CSRF Protection:** https://owasp.org/www-community/attacks/csrf

---

**Backend Worker - Phase 1 Complete**
