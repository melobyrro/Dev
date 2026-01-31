"""
Chat API v2 - Enhanced chat endpoint with better integration

Provides conversational AI interface for channel-specific sermon Q&A
using RAG (Retrieval-Augmented Generation) with Gemini.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from Backend.dtos import (
    ChatRequestDTO,
    ChatResponseDTO,
    ApiSuccessResponse,
    ApiErrorResponse,
    VideoDTO,
    VideoStatus
)
from app.common.database import get_db_session
from app.common.models import Channel, Video
from app.ai.chatbot_service import ChatbotService

logger = logging.getLogger(__name__)

router = APIRouter()
chatbot_service = ChatbotService()


@router.post(
    "/channels/{channel_id}/chat",
    response_model=ApiSuccessResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Channel not found"},
        500: {"model": ApiErrorResponse, "description": "Internal server error"}
    }
)
async def chat(
    channel_id: str,
    request: ChatRequestDTO,
    db: Session = Depends(get_db_session)
):
    """
    Send a chat message to the channel-specific AI assistant

    The assistant uses RAG to find relevant sermon segments and generates
    contextual responses using Gemini. It maintains conversation history
    per session.

    Args:
        channel_id: Channel ID to query
        request: Chat request containing message and session_id

    Returns:
        ChatResponseDTO with response, cited videos, and relevance scores

    Example:
        POST /api/v2/channels/1/chat
        {
            "message": "O que o pastor falou sobre fé?",
            "session_id": "uuid-here",
            "channel_id": "1"
        }
    """
    logger.info(f"Chat request for channel {channel_id}: {request.message[:100]}")

    try:
        # Validate channel exists
        channel = db.query(Channel).filter(Channel.id == int(channel_id)).first()
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel {channel_id} not found"
            )

        if not channel.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Channel is not active"
            )

        # Generate chat response using ChatbotService
        response_data = chatbot_service.chat(
            channel_id=int(channel_id),
            user_message=request.message,
            session_id=request.session_id,
            knowledge_mode=request.knowledge_mode
        )

        # Transform cited videos to VideoDTO format
        cited_videos = []
        for cited in response_data.get('cited_videos', []):
            video = db.query(Video).filter(Video.id == cited['video_id']).first()
            if video:
                cited_videos.append(VideoDTO(
                    id=str(video.id),
                    title=video.title,
                    youtube_id=video.youtube_id,
                    status=VideoStatus(video.status.upper()) if video.status else VideoStatus.PROCESSED,
                    duration=video.duration_sec or 0,
                    created_at=video.created_at.isoformat() if video.created_at else "",
                    processed_at=video.processed_at.isoformat() if video.processed_at else None,
                    thumbnail_url=f"https://img.youtube.com/vi/{video.youtube_id}/mqdefault.jpg",
                    channel_id=str(video.channel_id)
                ))

        # Build ChatResponseDTO
        chat_response = ChatResponseDTO(
            response=response_data['response'],
            cited_videos=cited_videos,
            relevance_scores=response_data.get('relevance_scores', []),
            session_id=response_data['session_id']
        )

        return ApiSuccessResponse(
            data=chat_response.dict(),
            message="Chat response generated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error for channel {channel_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chat response: {str(e)}"
        )


@router.get(
    "/channels/{channel_id}/chat/history",
    response_model=ApiSuccessResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Channel not found"}
    }
)
async def get_chat_history(
    channel_id: str,
    session_id: str,
    limit: int = 10,
    db: Session = Depends(get_db_session)
):
    """
    Retrieve chat history for a session

    Args:
        channel_id: Channel ID
        session_id: Session ID
        limit: Maximum number of messages to retrieve (default: 10)

    Returns:
        List of chat messages in chronological order
    """
    from app.common.models import GeminiChatHistory

    try:
        # Validate channel exists
        channel = db.query(Channel).filter(Channel.id == int(channel_id)).first()
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel {channel_id} not found"
            )

        # Query history
        history = db.query(GeminiChatHistory).filter(
            GeminiChatHistory.channel_id == int(channel_id),
            GeminiChatHistory.session_id == session_id
        ).order_by(
            GeminiChatHistory.created_at.asc()
        ).limit(limit).all()

        messages = []
        for entry in history:
            messages.append({
                "role": "user",
                "content": entry.user_message,
                "timestamp": entry.created_at.isoformat()
            })
            messages.append({
                "role": "assistant",
                "content": entry.assistant_response,
                "timestamp": entry.created_at.isoformat(),
                "cited_videos": entry.cited_videos
            })

        return ApiSuccessResponse(
            data={"messages": messages},
            message=f"Retrieved {len(messages)} messages"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat history: {str(e)}"
        )
