"""
Channel management routes
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import subprocess
import json
import logging

from app.web.auth import get_current_user
from app.common.database import get_db_session
from app.common.models import Channel, User

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


def extract_channel_id_from_url(youtube_url: str) -> str:
    """Extract YouTube channel ID from channel URL using yt-dlp"""
    try:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--playlist-end", "1",
            youtube_url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"yt-dlp error: {result.stderr}")
            raise ValueError(f"Failed to extract channel info: {result.stderr}")

        # Parse first line of JSON output
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                data = json.loads(line)
                channel_id = data.get('channel_id') or data.get('uploader_id')
                if channel_id:
                    return channel_id
                break

        raise ValueError("Could not find channel_id in YouTube data")

    except subprocess.TimeoutExpired:
        raise ValueError("Timeout while extracting channel information")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        raise ValueError("Failed to parse YouTube channel data")
    except Exception as e:
        logger.error(f"Error extracting channel ID: {e}")
        raise ValueError(f"Error: {str(e)}")


@router.get("/", response_class=HTMLResponse)
async def list_channels(
    request: Request,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """List all channels"""
    channels = db.query(Channel).order_by(Channel.created_at.desc()).all()

    return templates.TemplateResponse("channels/list.html", {
        "request": request,
        "channels": channels,
        "user": user
    })


@router.get("/new", response_class=HTMLResponse)
async def new_channel_form(
    request: Request,
    user: str = Depends(get_current_user)
):
    """Show form to create new channel"""
    return templates.TemplateResponse("channels/new.html", {
        "request": request,
        "user": user
    })


@router.post("/new")
async def create_channel(
    request: Request,
    title: str = Form(...),
    youtube_url: str = Form(...),
    schedule_cron: str = Form(None),
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Create a new channel - extracts channel_id automatically from URL"""
    try:
        # Extract channel_id from URL
        logger.info(f"Extracting channel ID from URL: {youtube_url}")
        channel_id = extract_channel_id_from_url(youtube_url)
        logger.info(f"Extracted channel ID: {channel_id}")

        # Get first user as creator (v1: single admin)
        creator = db.query(User).first()

        channel = Channel(
            title=title,
            youtube_url=youtube_url,
            channel_id=channel_id,
            created_by=creator.id if creator else None,
            schedule_cron=schedule_cron,
            active=True
        )

        db.add(channel)
        db.commit()
        db.refresh(channel)

        # Redirect to import progress page
        return RedirectResponse(url=f"/channels/{channel.id}/import", status_code=303)

    except ValueError as e:
        # Return to form with error message
        return templates.TemplateResponse("channels/new.html", {
            "request": request,
            "user": user,
            "error": str(e),
            "title": title,
            "youtube_url": youtube_url,
            "schedule_cron": schedule_cron
        }, status_code=400)


@router.get("/{channel_id}/import", response_class=HTMLResponse)
async def channel_import_progress(
    channel_id: int,
    request: Request,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Show channel import progress page"""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Canal não encontrado",
            "user": user
        }, status_code=404)

    return templates.TemplateResponse("channels/import.html", {
        "request": request,
        "channel": channel,
        "user": user
    })


@router.get("/{channel_id}/chatbot", response_class=HTMLResponse)
async def channel_chatbot(
    channel_id: int,
    request: Request,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Show chatbot interface for channel"""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Canal não encontrado",
            "user": user
        }, status_code=404)

    return templates.TemplateResponse("channels/chatbot.html", {
        "request": request,
        "channel": channel,
        "user": user
    })
