"""
Video management and transcription routes
"""
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import joinedload

from app.web.auth import get_current_user
from app.common.database import get_db_session
from app.common.models import Video, Transcript, Verse, Theme, SermonClassification

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
async def list_videos(
    request: Request,
    page: int = 1,
    limit: int = 20,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """List all videos with pagination"""
    skip = (page - 1) * limit

    videos = db.query(Video).order_by(Video.created_at.desc()).offset(skip).limit(limit).all()
    total = db.query(Video).count()

    return templates.TemplateResponse("videos/list.html", {
        "request": request,
        "videos": videos,
        "page": page,
        "total": total,
        "pages": (total + limit - 1) // limit,
        "user": user
    })


# ROUTE DISABLED: Individual video detail pages removed per user request
# All video functionality should be on the dashboard (/) only
# The "Ver" button now expands videos inline on the dashboard instead of navigating to /videos/{video_id}

# @router.get("/{video_id}", response_class=HTMLResponse)
# async def video_detail(
#     video_id: int,
#     request: Request,
#     db=Depends(get_db_session),
#     user: str = Depends(get_current_user)
# ):
#     """Show video details with transcript and analytics"""
#     # This route is disabled - use dashboard expansion instead
#     pass
