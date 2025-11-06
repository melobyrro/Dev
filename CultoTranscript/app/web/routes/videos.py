"""
Video management and transcription routes
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import joinedload

from app.web.auth import get_current_user
from app.common.database import get_db_session
from app.common.models import Video, Transcript, Verse, Theme, SermonClassification, Speaker

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
async def list_videos(
    request: Request,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    speaker: Optional[str] = None,
    status: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    sort: str = "published_at",
    order: str = "desc",
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """List all videos with filtering, sorting, and pagination"""
    skip = (page - 1) * limit

    # Build base query
    query = db.query(Video)

    # Apply filters
    if search:
        query = query.filter(Video.title.ilike(f"%{search}%"))
    if speaker:
        query = query.filter(Video.speaker == speaker)
    if status:
        query = query.filter(Video.status == status)
    if date_start:
        start_date = datetime.fromisoformat(date_start)
        query = query.filter(Video.published_at >= start_date)
    if date_end:
        end_date = datetime.fromisoformat(date_end)
        query = query.filter(Video.published_at <= end_date)

    # Apply sorting
    valid_sorts = ["title", "published_at", "speaker", "status", "duration_sec", "created_at"]
    if sort in valid_sorts:
        sort_column = getattr(Video, sort)
        if order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(Video.published_at.desc())

    # Get total count (before pagination)
    total = query.count()

    # Apply pagination
    videos = query.offset(skip).limit(limit).all()

    # Get all speakers for filter dropdown
    speakers = db.query(Speaker).order_by(Speaker.video_count.desc()).limit(50).all()

    return templates.TemplateResponse("videos/list.html", {
        "request": request,
        "videos": videos,
        "speakers": speakers,
        "page": page,
        "total": total,
        "pages": (total + limit - 1) // limit,
        "user": user,
        # Current filter values (for form persistence)
        "current_search": search or "",
        "current_speaker": speaker or "",
        "current_status": status or "",
        "current_date_start": date_start or "",
        "current_date_end": date_end or "",
        "current_sort": sort,
        "current_order": order,
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
