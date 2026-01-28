"""
Speakers API Endpoints

REST API endpoints for speaker management.
"""
import logging
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from pydantic import BaseModel

# Add app directory to path for imports
app_path = Path(__file__).parent.parent.parent.parent / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from app.common.database import get_db_session
from app.common.models import Video

from Backend.dtos import ApiSuccessResponse
from app.web.auth import get_user_churches

logger = logging.getLogger(__name__)

router = APIRouter()


class SpeakerSuggestionDTO(BaseModel):
    """Speaker suggestion data transfer object"""
    id: int
    name: str
    video_count: int


@router.get("/autocomplete", response_model=ApiSuccessResponse)
async def autocomplete_speakers(
    request: Request,
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    channel_id: Optional[int] = Query(None, description="Channel ID to scope search"),
    db: Session = Depends(get_db_session)
):
    """
    Autocomplete speakers by name prefix.

    If no query provided, returns most popular speakers (by video count).
    If query provided, searches by name prefix (case-insensitive).

    Args:
        q: Search query (optional)
        limit: Maximum number of results
        channel_id: Channel ID to scope search (optional, uses session if not provided)
        db: Database session

    Returns:
        List of speaker suggestions with video counts
    """
    try:
        effective_channel_id = channel_id or request.session.get("channel_id")
        user_id = request.session.get("user_id")
        user_churches = get_user_churches(db, user_id) if user_id else []

        if user_churches:
            allowed_ids = {c["id"] for c in user_churches}
            if effective_channel_id and effective_channel_id not in allowed_ids:
                effective_channel_id = next(iter(allowed_ids), None)
            if not effective_channel_id:
                effective_channel_id = next(iter(allowed_ids), None)

        speakers = []

        if effective_channel_id:
            # Get distinct speakers from videos scoped to channel
            video_query = db.query(
                Video.speaker,
                func.count(Video.id).label("cnt")
            ).filter(
                Video.channel_id == effective_channel_id,
                Video.speaker.isnot(None),
                Video.speaker != ""
            )

            if q:
                video_query = video_query.filter(Video.speaker.ilike(f"{q}%"))

            video_speakers = (
                video_query.group_by(Video.speaker)
                .order_by(func.count(Video.id).desc())
                .limit(limit)
                .all()
            )

            speakers = [
                SpeakerSuggestionDTO(
                    id=idx + 1,
                    name=name,
                    video_count=cnt
                ).model_dump()
                for idx, (name, cnt) in enumerate(video_speakers)
            ]

        # Fallback to global search if channel empty
        if not speakers:
            global_query = db.query(
                Video.speaker,
                func.count(Video.id).label("cnt")
            ).filter(
                Video.speaker.isnot(None),
                Video.speaker != ""
            )

            if q:
                global_query = global_query.filter(Video.speaker.ilike(f"{q}%"))

            global_speakers = (
                global_query.group_by(Video.speaker)
                .order_by(func.count(Video.id).desc())
                .limit(limit)
                .all()
            )

            speakers = [
                SpeakerSuggestionDTO(
                    id=idx + 1,
                    name=name,
                    video_count=cnt
                ).model_dump()
                for idx, (name, cnt) in enumerate(global_speakers)
            ]

        logger.info(f"Returning {len(speakers)} speaker suggestions for query '{q}'")

        return ApiSuccessResponse(
            success=True,
            data={"suggestions": speakers},
            message="Speaker suggestions retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting speaker suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
