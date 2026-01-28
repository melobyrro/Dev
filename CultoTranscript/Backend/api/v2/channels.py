"""
Channels API Endpoints

REST API endpoints for channel (church) management.
"""
import logging
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

# Add app directory to path for imports
app_path = Path(__file__).parent.parent.parent.parent / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from app.common.database import get_db_session
from app.common.models import Channel, ChurchMember
from app.web.auth import get_user_churches

from Backend.dtos import ApiSuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class SwitchChurchRequest(BaseModel):
    """Request body for switching churches"""
    church_id: int


class ChannelDTO(BaseModel):
    """Channel/Church data transfer object"""
    id: int
    title: str
    youtube_url: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    active: bool = True
    default_speaker: Optional[str] = None


class UpdateChannelRequest(BaseModel):
    """Request body for updating channel"""
    youtube_url: Optional[str] = None
    title: Optional[str] = None
    default_speaker: Optional[str] = None


@router.get("/", response_model=ApiSuccessResponse)
async def list_channels(
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    List channels the current user can access.
    Also returns the currently selected channel from the session.

    Returns:
        List of channels and current channel ID
    """
    try:
        user_id = request.session.get("user_id")
        current_channel_id = request.session.get("channel_id")
        channels = []

        # If authenticated, prefer scoped list to user memberships
        if user_id:
            churches = get_user_churches(db, user_id)
            channel_ids = [c["id"] for c in churches]

            if channel_ids:
                channels = db.query(Channel).filter(
                    Channel.id.in_(channel_ids),
                    Channel.active == True
                ).all()

        # If not authenticated or no memberships, return all active channels (public view)
        if not channels:
            channels = db.query(Channel).filter(
                Channel.active == True
            ).order_by(Channel.id.asc()).all()

        # Ensure the session is aligned with available channels
        if not current_channel_id and channels:
            current_channel_id = channels[0].id
            request.session["channel_id"] = current_channel_id
        elif current_channel_id and channels and current_channel_id not in [c.id for c in channels]:
            # Session channel no longer available; reset to first
            current_channel_id = channels[0].id
            request.session["channel_id"] = current_channel_id

        channel_dtos = [
            ChannelDTO(
                id=c.id,
                title=c.title,
                youtube_url=c.youtube_url,
                youtube_channel_id=c.youtube_channel_id,
                active=c.active,
                default_speaker=c.default_speaker
            ).model_dump()
            for c in channels
        ]

        logger.info(f"Returning {len(channel_dtos)} channels for user {user_id}")

        return ApiSuccessResponse(
            success=True,
            data={
                "channels": channel_dtos,
                "current_channel_id": current_channel_id
            },
            message="Channels retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error listing channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch", response_model=ApiSuccessResponse)
async def switch_church(
    request: Request,
    body: SwitchChurchRequest,
    db: Session = Depends(get_db_session)
):
    """
    Switch to a different church.
    Allows switching to any active channel.

    Args:
        body: Contains church_id to switch to
        request: FastAPI request object
        db: Database session

    Returns:
        Success confirmation with church details
    """
    try:
        user_id = request.session.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        church_id = body.church_id

        # Verify channel exists and is active
        channel = db.query(Channel).filter(
            Channel.id == church_id,
            Channel.active == True
        ).first()

        if not channel:
            raise HTTPException(
                status_code=404,
                detail="Church not found"
            )

        # Update session with new channel
        request.session["channel_id"] = church_id
        logger.info(f"User {user_id} switched to channel {church_id}")

        return ApiSuccessResponse(
            success=True,
            data={
                "church_id": church_id,
                "church_name": channel.title
            },
            message="Church switched successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching church: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{channel_id}", response_model=ApiSuccessResponse)
async def update_channel(
    channel_id: int,
    body: UpdateChannelRequest,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Update channel information.
    Requires user to be admin of the channel.

    Args:
        channel_id: ID of the channel to update
        body: Contains fields to update
        request: FastAPI request object
        db: Database session

    Returns:
        Success confirmation with updated channel details
    """
    try:
        user_id = request.session.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Verify user is admin of this channel
        member = db.query(ChurchMember).filter(
            ChurchMember.user_id == user_id,
            ChurchMember.channel_id == channel_id,
            ChurchMember.role == 'admin'
        ).first()

        if not member:
            raise HTTPException(
                status_code=403,
                detail="Admin permission required"
            )

        # Get channel
        channel = db.query(Channel).filter(Channel.id == channel_id).first()

        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        # Update fields
        if body.youtube_url is not None:
            channel.youtube_url = body.youtube_url

        if body.title is not None:
            channel.title = body.title

        if body.default_speaker is not None:
            channel.default_speaker = body.default_speaker

        db.commit()
        db.refresh(channel)

        logger.info(f"User {user_id} updated channel {channel_id}")

        return ApiSuccessResponse(
            success=True,
            data={
                "channel": ChannelDTO(
                    id=channel.id,
                    title=channel.title,
                    youtube_url=channel.youtube_url,
                    youtube_channel_id=channel.youtube_channel_id,
                    active=channel.active,
                    default_speaker=channel.default_speaker
                ).model_dump()
            },
            message="Channel updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating channel: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
