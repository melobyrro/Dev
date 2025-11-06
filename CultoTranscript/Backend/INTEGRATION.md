# Backend Integration Guide

## Phase 1 - SSE Endpoint Implementation

This document provides instructions for integrating the new Backend/ components into the existing FastAPI application.

---

## Overview

The Backend/ directory contains:

```
Backend/
├── api/v2/
│   ├── events.py          # SSE endpoint
│   └── videos.py          # Video API (stub)
├── services/
│   └── sse_manager.py     # SSE connection manager
├── middleware/
│   ├── cors.py            # CORS configuration
│   └── csrf.py            # CSRF protection
├── dtos.py                # Pydantic DTOs
└── INTEGRATION.md         # This file
```

---

## Required Dependencies

Add these dependencies to `requirements-web.txt`:

```txt
sse-starlette==1.6.5    # SSE support for FastAPI
```

Install:
```bash
pip install sse-starlette==1.6.5
```

---

## Integration Steps

### Step 1: Import Backend Components

In `app/web/main.py`, add these imports at the top:

```python
# Add after existing imports
from Backend.middleware import setup_cors, CSRFMiddleware
from Backend.api.v2 import events_router
from Backend.services.sse_manager import sse_manager
```

### Step 2: Configure CORS Middleware

Add CORS configuration (before other middleware):

```python
# In app/web/main.py, after creating the FastAPI app

app = FastAPI(
    title="CultoTranscript",
    description="Sistema de Transcrição e Análise de Sermões",
    version="1.0.0"
)

# Add CORS middleware (NEW)
from Backend.middleware import setup_cors
setup_cors(app)  # Enables CORS for React dev server (localhost:5173)

# Existing middleware
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
```

**For Production:**
```python
import os
if os.getenv("ENVIRONMENT") == "production":
    from Backend.middleware import setup_production_cors
    setup_production_cors(app, "https://church.byrroserver.com")
else:
    setup_cors(app)  # Development
```

### Step 3: Add CSRF Middleware

Add CSRF protection (after SessionMiddleware):

```python
# In app/web/main.py, after SessionMiddleware

from Backend.middleware import CSRFMiddleware

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(CSRFMiddleware)  # NEW - Add CSRF protection
```

**Middleware Order (important):**
```python
# CORS (runs last)
setup_cors(app)

# Auth (runs third)
app.add_middleware(AuthMiddleware)

# Session (runs second)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# CSRF (runs first)
app.add_middleware(CSRFMiddleware)
```

### Step 4: Register SSE Router

Add the SSE events router:

```python
# In app/web/main.py, after existing include_router calls

from Backend.api.v2 import events_router

# Existing routers
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(channels.router, prefix="/channels", tags=["Channels"])
app.include_router(videos.router, prefix="/videos", tags=["Videos"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])

# NEW: Add SSE events router
app.include_router(events_router, prefix="/api/v2/events", tags=["Events"])
```

### Step 5: Start SSE Heartbeat Task

Add lifecycle event handlers for SSE manager:

```python
# In app/web/main.py, update startup_event

from Backend.services.sse_manager import sse_manager

@app.on_event("startup")
async def startup_event():
    """Initialize database and SSE manager on startup"""
    # Existing code...

    # NEW: Start SSE heartbeat task
    await sse_manager.start_heartbeat_task(interval=30)
    logger.info("SSE manager started with 30s heartbeat")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    # NEW: Stop SSE manager
    await sse_manager.shutdown()
    logger.info("SSE manager stopped")
```

---

## Testing the Integration

### 1. Test SSE Endpoint

Start the server:
```bash
docker-compose up -d culto_web
```

Test with curl:
```bash
curl -N http://localhost:8000/api/v2/events/stream
```

Expected output (heartbeat every 30s):
```
event: heartbeat
data: {"type":"heartbeat","timestamp":"2025-11-05T12:00:00.000Z"}
```

### 2. Test Health Check

```bash
curl http://localhost:8000/api/v2/events/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "sse_events",
  "connected_clients": 0
}
```

### 3. Test CSRF Protection

Get CSRF token:
```bash
curl -c cookies.txt http://localhost:8000/api/videos
```

Check response headers for `X-CSRF-Token`.

Make POST request:
```bash
curl -b cookies.txt -H "X-CSRF-Token: <token>" \
     -H "Content-Type: application/json" \
     -d '{"title":"test"}' \
     http://localhost:8000/api/videos
```

### 4. Test CORS

From React dev server (localhost:5173):
```javascript
fetch('http://localhost:8000/api/v2/events/stream')
  .then(response => {
    console.log('CORS working:', response.ok);
  });
```

---

## Broadcasting Events from Workers

To send events to connected clients from the worker service:

```python
from Backend.services.sse_manager import sse_manager
from Backend.dtos import VideoStatusEventDTO, EventType, VideoStatus
from datetime import datetime

# Example: Broadcast video status change
async def notify_video_status(video_id: str, status: VideoStatus, progress: int = None):
    """Send video status update to all connected clients"""
    event = VideoStatusEventDTO(
        type=EventType.VIDEO_STATUS,
        timestamp=datetime.utcnow().isoformat() + "Z",
        video_id=video_id,
        status=status,
        progress=progress,
        message=f"Video {status.value.lower()}"
    )

    await sse_manager.broadcast_event(event)
```

**Important:** Workers need access to the same SSE manager instance. Options:
1. Use Redis pub/sub for cross-process communication
2. Use HTTP POST to web service endpoint that broadcasts
3. Share SSE manager via multiprocessing (complex)

**Recommended approach for Phase 2:**
Create a REST endpoint in the web service that workers can POST events to:

```python
# In Backend/api/v2/events.py

@router.post("/broadcast")
async def broadcast_event(event: SSEEventDTO):
    """
    Internal endpoint for workers to broadcast events.

    **Note:** Should be restricted to internal network only.
    """
    await sse_manager.broadcast_event(event)
    return {"status": "broadcasted"}
```

---

## Environment Variables

Add to `.env`:

```bash
# CORS Configuration
FRONTEND_URL=http://localhost:5173

# CSRF Configuration
CSRF_EXEMPT_PATHS=/api/v2/events/stream,/health,/docs

# SSE Configuration
SSE_HEARTBEAT_INTERVAL=30
```

---

## Troubleshooting

### SSE connection immediately closes
- Check nginx/Caddy buffering settings (add `X-Accel-Buffering: no`)
- Verify CORS is properly configured
- Check browser console for errors

### CSRF validation fails
- Ensure SessionMiddleware is configured before CSRFMiddleware
- Verify X-CSRF-Token header is sent with POST/PUT/DELETE
- Check cookies are enabled in browser

### No heartbeats received
- Verify heartbeat task started: check logs for "SSE manager started"
- Check if SSE manager is shared across workers (it shouldn't be)
- Test health endpoint to see connected clients count

### CORS errors
- Verify frontend URL in CORS allowed origins
- Check if credentials are being sent: `credentials: 'include'`
- Test preflight (OPTIONS) requests

---

## Next Steps

**Phase 2 Tasks:**
1. Implement full Video API endpoints (Backend/api/v2/videos.py)
2. Create internal broadcast endpoint for workers
3. Integrate SSE events in worker processing pipeline
4. Add event filtering (subscribe to specific video IDs)
5. Add reconnection logic in UI client

---

## API Documentation

Once integrated, view full API docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

The SSE endpoint will appear under "Events" tag with full documentation.

---

## Complete Example

Full integration in `app/web/main.py`:

```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
import os

# Import Backend components
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

# Add middleware (order matters!)
app.add_middleware(AuthMiddleware)
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
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

**END OF INTEGRATION GUIDE**
