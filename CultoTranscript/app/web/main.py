"""
CultoTranscript - FastAPI Web Application
Main entry point for the web service
"""
import os
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.web.auth import AuthMiddleware, verify_password, get_current_user, require_auth
from app.web.routes import api, channels, videos, reports
from app.common.database import engine, Base

# Create FastAPI app
app = FastAPI(
    title="CultoTranscript",
    description="Sistema de Transcrição e Análise de Sermões",
    version="1.0.0"
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

# Include routers
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(channels.router, prefix="/channels", tags=["Channels"])
app.include_router(videos.router, prefix="/videos", tags=["Videos"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    # Tables are created via SQL migration, not here
    pass


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


@app.get("/admin/import", response_class=HTMLResponse)
async def admin_import(request: Request, user: str = Depends(require_auth)):
    """Admin import page - requires authentication"""
    from app.common.database import get_db_session
    from app.common.models import Channel, Video

    # Get the first active channel (single-channel mode for now)
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

    return templates.TemplateResponse("admin_import.html", {
        "request": request,
        "user": user,
        "channel": channel,
        "total_videos": total_videos,
        "completed_videos": completed_videos
    })


@app.get("/admin/schedule", response_class=HTMLResponse)
async def admin_schedule(request: Request, user: str = Depends(require_auth)):
    """Admin schedule configuration page - requires authentication"""
    return templates.TemplateResponse("admin_schedule.html", {
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.web.main:app", host="0.0.0.0", port=8000, reload=True)
