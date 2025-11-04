"""
Reports and analytics routes
"""
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from datetime import datetime, timedelta

from app.web.auth import get_current_user
from app.common.database import get_db_session
from app.common.models import Video, Verse, Theme, Transcript

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
async def reports_home(
    request: Request,
    user: str = Depends(get_current_user)
):
    """Reports homepage"""
    return templates.TemplateResponse("reports/index.html", {
        "request": request,
        "user": user
    })


@router.get("/top-books", response_class=HTMLResponse)
async def top_books_report(
    request: Request,
    days: int = 30,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Report: Top Bible books cited"""
    since = datetime.now() - timedelta(days=days)

    # Query top books
    top_books = db.query(
        Verse.book,
        func.sum(Verse.count).label('total')
    ).join(Video).filter(
        Video.published_at >= since
    ).group_by(Verse.book).order_by(func.sum(Verse.count).desc()).limit(20).all()

    return templates.TemplateResponse("reports/top_books.html", {
        "request": request,
        "top_books": top_books,
        "days": days,
        "user": user
    })


@router.get("/top-themes", response_class=HTMLResponse)
async def top_themes_report(
    request: Request,
    days: int = 30,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Report: Top themes"""
    since = datetime.now() - timedelta(days=days)

    # Query top themes
    top_themes = db.query(
        Theme.tag,
        func.count(Theme.id).label('count'),
        func.avg(Theme.score).label('avg_score')
    ).join(Video).filter(
        Video.published_at >= since
    ).group_by(Theme.tag).order_by(func.count(Theme.id).desc()).all()

    return templates.TemplateResponse("reports/top_themes.html", {
        "request": request,
        "top_themes": top_themes,
        "days": days,
        "user": user
    })
