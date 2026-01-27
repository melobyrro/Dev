"""
CultoTranscript - FastAPI Web Application
Main entry point for the web service
"""
import os
import sys
import logging
from pathlib import Path

# Add Backend directory to Python path for imports
backend_path = Path(__file__).parent.parent.parent / "Backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.web.auth import AuthMiddleware, verify_password, get_current_user, require_auth
from app.web.routes import api, channels, videos, reports, websub
from app.routers import llm_status, database
from app.common.database import engine, Base, get_db
from app.common.models import Job

# Import Backend components
try:
    from Backend.middleware.cors import setup_cors
    from Backend.middleware.csrf import CSRFMiddleware
    from Backend.api.v2 import events as sse_router
    from Backend.api.v2 import videos as videos_v2_router
    from Backend.api.v2 import chat as chat_v2_router
    from Backend.api.v2 import channels as channels_v2_router
    from Backend.api.v2 import speakers as speakers_v2_router
    from Backend.services.sse_manager import sse_manager
    BACKEND_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Backend components not available: {e}")
    BACKEND_AVAILABLE = False

# Create FastAPI app
app = FastAPI(
    title="CultoTranscript",
    description="Sistema de Transcrição e Análise de Sermões",
    version="2.0.0"  # Upgraded for React SPA integration
)

# Add CORS middleware (if Backend is available)
if BACKEND_AVAILABLE:
    setup_cors(app)

# Add CSRF middleware (if Backend is available)
if BACKEND_AVAILABLE:
    app.add_middleware(
        CSRFMiddleware,
        exempt_paths=["/health", "/login", "/api/v2/events/stream", "/api/v2/events/broadcast", "/api/channels/", "/api/websub/callback"]
    )

# Add auth middleware (added first so it runs second)
app.add_middleware(AuthMiddleware)

# Add session middleware (added second so it runs first)
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Mount static files
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/web/templates")

# Custom Jinja2 filters
def format_duration(seconds):
    """Format duration from seconds to HH:MM"""
    if not seconds or seconds < 0:
        return '00:00'
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    return f'{hours:02d}:{mins:02d}'

templates.env.filters['format_duration'] = format_duration

# Include routers
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(channels.router, prefix="/channels", tags=["Channels"])
app.include_router(videos.router, prefix="/videos", tags=["Videos"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(websub.router, tags=["WebSub"])
app.include_router(llm_status.router, tags=["LLM Status"])
app.include_router(database.router, prefix="/api/database", tags=["Database"])

# Include Backend v2 API routers (if available)
if BACKEND_AVAILABLE:
    app.include_router(sse_router.router, prefix="/api/v2/events", tags=["SSE Events"])
    app.include_router(videos_v2_router.router, prefix="/api/v2/videos", tags=["Videos v2"])
    app.include_router(chat_v2_router.router, prefix="/api/v2", tags=["Chat v2"])
    app.include_router(channels_v2_router.router, prefix="/api/v2/channels", tags=["Channels v2"])


@app.on_event("startup")
async def startup_event():
    """Initialize database and SSE manager on startup"""
    # Tables are created via SQL migration, not here

    # Load configuration from database on startup
    try:
        from app.common.models import SystemSettings
        from app.common.database import get_db_session

        logger = logging.getLogger(__name__)
        db = next(get_db_session())

        # Load Gemini API key from database
        api_key_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "gemini_api_key"
        ).first()

        if api_key_setting and api_key_setting.setting_value:
            os.environ["GEMINI_API_KEY"] = api_key_setting.setting_value
            print("✅ Loaded Gemini API key from database")
            logger.info("✅ Loaded Gemini API key from database")
        else:
            print("⚠️ No Gemini API key found in database, using .env value")
            logger.warning("⚠️ No Gemini API key found in database, using .env value")

        # Load AI service provider setting
        service_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "ai_service_provider"
        ).first()

        if service_setting and service_setting.setting_value:
            os.environ["PRIMARY_LLM"] = service_setting.setting_value
            print(f"✅ Loaded AI service provider from database: {service_setting.setting_value}")
            logger.info(f"✅ Loaded AI service provider from database: {service_setting.setting_value}")

        db.close()
    except Exception as e:
        print(f"❌ Error loading config from database: {e}")
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading config from database: {e}")

    # Initialize SSE Manager (if Backend is available)
    if BACKEND_AVAILABLE:
        print("🚀 Starting SSE Manager...")
        await sse_manager.start_heartbeat_task()
        print("✅ SSE Manager initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    # Gracefully shutdown SSE Manager (if Backend is available)
    if BACKEND_AVAILABLE:
        print("🛑 Shutting down SSE Manager...")
        await sse_manager.shutdown()
        print("✅ SSE Manager shut down gracefully")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: str = Depends(get_current_user)):
    """Home page / Dashboard - Channel-focused"""
    from app.common.database import get_db_session
    from app.common.models import Channel, Video

    # Get the first active channel (single-channel mode for now)
    # In the future, could add channel selection dropdown
    with next(get_db_session()) as db:
        channel = db.query(Channel).filter(Channel.active == True).first()

        if channel:
            # Get video stats for this channel
            total_videos = db.query(Video).filter(Video.channel_id == channel.id).count()
            completed_videos = db.query(Video).filter(
                Video.channel_id == channel.id,
                Video.status == 'completed'
            ).count()
        else:
            total_videos = 0
            completed_videos = 0

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "channel": channel,
        "total_videos": total_videos,
        "completed_videos": completed_videos
    })


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, user: str = Depends(require_auth)):
    """Unified admin page with tabs - requires authentication"""
    from app.common.database import get_db_session
    from app.common.models import Channel

    # Get channel_id from session (multi-tenant mode)
    session_channel_id = request.session.get("channel_id", 1)

    with next(get_db_session()) as db:
        # Get all active channels for selector dropdown
        channels = db.query(Channel).filter(Channel.active == True).all()
        # Get the current channel from session
        channel = db.query(Channel).filter(Channel.id == session_channel_id).first()
        if not channel and channels:
            channel = channels[0]  # Fallback to first channel

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "channel": channel,
        "channels": channels,
        "current_channel_id": channel.id if channel else 1
    })


@app.get("/admin/import", response_class=HTMLResponse)
async def admin_import_redirect(user: str = Depends(require_auth)):
    """Redirect to unified admin page - import tab (backward compatibility)"""
    return RedirectResponse(url="/admin#importar", status_code=303)


@app.get("/admin/schedule", response_class=HTMLResponse)
async def admin_schedule_redirect(user: str = Depends(require_auth)):
    """Redirect to unified admin page - schedule tab (backward compatibility)"""
    return RedirectResponse(url="/admin#agendamento", status_code=303)


@app.get("/admin/websub", response_class=HTMLResponse)
async def admin_websub(request: Request, user: str = Depends(require_auth)):
    """WebSub subscriptions management page."""
    return templates.TemplateResponse(
        "admin_websub.html",
        {"request": request, "user": user}
    )


@app.get("/admin/chatbot-metrics", response_class=HTMLResponse)
async def admin_chatbot_metrics(request: Request, user: str = Depends(require_auth)):
    """Chatbot metrics and analytics dashboard (Phase 2)"""
    return templates.TemplateResponse("admin_chatbot_metrics.html", {
        "request": request,
        "user": user
    })


@app.get("/database", response_class=HTMLResponse)
async def database_page(request: Request, user: str = Depends(require_auth)):
    """Database viewer page - requires authentication"""
    return templates.TemplateResponse("database.html", {
        "request": request,
        "user": user
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None
    })


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Handle login form submission"""
    if verify_password(password):
        # Set session
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=303)
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Senha incorreta"
        })


@app.get("/logout")
async def logout(request: Request):
    """Logout and clear session"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/health")
async def health_check():
    """Health check endpoint (public, no auth)"""
    return {"status": "ok", "service": "culto-web"}


@app.get("/api/health/worker")
def worker_health():
    """Check for stuck jobs and worker health"""
    from datetime import datetime, timedelta

    with get_db() as db:
        stuck_jobs = db.query(Job).filter(
            Job.status == 'running',
            Job.started_at < datetime.now() - timedelta(minutes=30)
        ).all()

        stuck_details = [
            {
                "job_id": job.id,
                "video_id": job.video_id,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "duration_minutes": int((datetime.now() - job.started_at).total_seconds() / 60) if job.started_at else 0
            }
            for job in stuck_jobs
        ]

        return {
            "healthy": len(stuck_jobs) == 0,
            "stuck_job_count": len(stuck_jobs),
            "stuck_jobs": stuck_details,
            "message": f"{len(stuck_jobs)} jobs stuck for > 30 minutes" if stuck_jobs else "All jobs running normally"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.web.main:app", host="0.0.0.0", port=8000, reload=True)
