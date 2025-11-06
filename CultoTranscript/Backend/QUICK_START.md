# Backend Phase 1 - Quick Start

## TL;DR

Backend Worker Phase 1 is **COMPLETE**. Follow these steps to integrate:

---

## 1. Install Dependencies

```bash
pip install sse-starlette==1.6.5
```

Or update `requirements-web.txt`:
```bash
echo "sse-starlette==1.6.5" >> requirements-web.txt
pip install -r requirements-web.txt
```

---

## 2. Update app/web/main.py

Add these imports at the top:
```python
from Backend.middleware import setup_cors, CSRFMiddleware
from Backend.api.v2 import events_router
from Backend.services.sse_manager import sse_manager
```

Configure middleware (after creating FastAPI app):
```python
app = FastAPI(...)

# Add CORS (for React dev server)
setup_cors(app)

# Existing middleware
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Add CSRF protection
app.add_middleware(CSRFMiddleware)
```

Register SSE router:
```python
# After existing routers
app.include_router(events_router, prefix="/api/v2/events", tags=["Events"])
```

Add lifecycle handlers:
```python
@app.on_event("startup")
async def startup_event():
    # Existing code...
    await sse_manager.start_heartbeat_task(interval=30)

@app.on_event("shutdown")
async def shutdown_event():
    await sse_manager.shutdown()
```

---

## 3. Test Integration

Restart the server:
```bash
docker-compose up -d --build culto_web
```

Test SSE endpoint:
```bash
curl -N http://localhost:8000/api/v2/events/stream
```

Expected output (heartbeat every 30s):
```
event: heartbeat
data: {"type":"heartbeat","timestamp":"2025-11-05T12:00:00.000Z"}
```

Test health check:
```bash
curl http://localhost:8000/api/v2/events/health
```

Expected:
```json
{"status": "healthy", "service": "sse_events", "connected_clients": 0}
```

---

## 4. Test from Browser

Open browser console at http://localhost:8000 and run:

```javascript
const eventSource = new EventSource('/api/v2/events/stream');

eventSource.addEventListener('heartbeat', (event) => {
  console.log('Heartbeat:', event.data);
});

eventSource.addEventListener('video.status', (event) => {
  const data = JSON.parse(event.data);
  console.log('Video status:', data);
});
```

---

## 5. Broadcasting Events (Workers)

**Phase 2 Task:** Create internal broadcast endpoint

For now, workers can use the SSE manager directly (same process only):

```python
from Backend.services.sse_manager import sse_manager
from Backend.dtos import VideoStatusEventDTO, EventType, VideoStatus
from datetime import datetime

# Broadcast video status update
event = VideoStatusEventDTO(
    type=EventType.VIDEO_STATUS,
    timestamp=datetime.utcnow().isoformat() + "Z",
    video_id="abc-123",
    status=VideoStatus.PROCESSING,
    progress=50
)

await sse_manager.broadcast_event(event)
```

---

## Complete Example

Full `app/web/main.py` integration:

```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
import os

# Backend imports
from Backend.middleware import setup_cors, CSRFMiddleware
from Backend.api.v2 import events_router
from Backend.services.sse_manager import sse_manager

# Existing imports
from app.web.auth import AuthMiddleware
from app.web.routes import api, channels, videos, reports

# Create app
app = FastAPI(
    title="CultoTranscript",
    description="Sistema de Transcrição e Análise de Sermões",
    version="2.0.0"
)

# Configure CORS
setup_cors(app)

# Add middleware
app.add_middleware(AuthMiddleware)
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(CSRFMiddleware)

# Include routers
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(channels.router, prefix="/channels", tags=["Channels"])
app.include_router(videos.router, prefix="/videos", tags=["Videos"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(events_router, prefix="/api/v2/events", tags=["Events"])

@app.on_event("startup")
async def startup_event():
    await sse_manager.start_heartbeat_task(interval=30)

@app.on_event("shutdown")
async def shutdown_event():
    await sse_manager.shutdown()
```

---

## Troubleshooting

**SSE connection closes immediately:**
- Check browser console for errors
- Verify CORS is configured: `setup_cors(app)`
- Check Caddy/nginx buffering settings

**CSRF validation fails:**
- Ensure SessionMiddleware is added before CSRFMiddleware
- Check X-CSRF-Token header is sent with POST requests

**No heartbeats:**
- Check logs: `docker-compose logs culto_web | grep SSE`
- Test health endpoint: `curl http://localhost:8000/api/v2/events/health`

---

## Documentation

- **INTEGRATION.md** - Full integration guide with detailed steps
- **README.md** - Complete Backend documentation and API reference
- **PHASE1_COMPLETE.md** - Completion summary and validation results

---

## What's Next?

**Phase 2 Tasks:**
1. Implement full Video API endpoints
2. Create internal broadcast endpoint for workers
3. Integrate SSE events into worker pipeline
4. Add event filtering (per-video subscriptions)

---

**Questions? See INTEGRATION.md for detailed troubleshooting.**
