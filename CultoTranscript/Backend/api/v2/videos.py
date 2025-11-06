"""
Videos API Endpoints

REST API endpoints for video management.
"""
import logging
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

# Add app directory to path for imports
app_path = Path(__file__).parent.parent.parent.parent / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from app.common.database import get_db_session
from app.common.models import Video, Transcript, Verse, Theme, SermonReport

from Backend.dtos import (
    VideoDTO,
    VideoDetailDTO,
    SummaryDTO,
    BiblicalPassageDTO,
    CitationDTO,
    ApiSuccessResponse,
    VideoStatus,
    VideoDetailedReportDTO,
    SermonStatisticsDTO,
    ThemeDTO,
    HighlightDTO,
    DiscussionQuestionDTO
)

logger = logging.getLogger(__name__)

router = APIRouter()


def map_db_status_to_dto(db_status: str) -> VideoStatus:
    """
    Map database status values to DTO VideoStatus enum.

    Database uses: pending, processing, completed, failed, too_long, skipped
    DTO uses: PENDING, QUEUED, PROCESSING, PROCESSED, FAILED
    """
    status_map = {
        'pending': VideoStatus.PENDING,
        'processing': VideoStatus.PROCESSING,
        'completed': VideoStatus.PROCESSED,
        'failed': VideoStatus.FAILED,
        'too_long': VideoStatus.FAILED,  # Treat as failed
        'skipped': VideoStatus.FAILED,   # Treat as failed
    }
    return status_map.get(db_status.lower(), VideoStatus.PENDING)


def video_to_dto(video: Video) -> VideoDTO:
    """Convert Video ORM model to VideoDTO"""
    # Generate thumbnail URL from YouTube ID
    thumbnail_url = f"https://img.youtube.com/vi/{video.youtube_id}/mqdefault.jpg"

    return VideoDTO(
        id=str(video.id),
        title=video.title,
        youtube_id=video.youtube_id,
        status=map_db_status_to_dto(video.status),
        duration=video.duration_sec,
        published_at=video.published_at.isoformat() + "Z" if video.published_at else None,
        created_at=video.created_at.isoformat() + "Z" if video.created_at else None,
        processed_at=video.updated_at.isoformat() + "Z" if video.status == 'completed' and video.updated_at else None,
        thumbnail_url=thumbnail_url,
        channel_id=str(video.channel_id) if video.channel_id else "0"  # Default to "0" if no channel
    )


def video_to_detail_dto(video: Video) -> VideoDetailDTO:
    """Convert Video ORM model to VideoDetailDTO with full details"""
    # Get base video DTO
    base_dto = video_to_dto(video)

    # Build summary from database fields
    themes = []
    passages = []
    citations = []

    # Get themes
    if video.themes:
        themes = [theme.theme_name for theme in video.themes]

    # Get biblical passages
    if video.verses:
        for verse in video.verses:
            passages.append(BiblicalPassageDTO(
                book=verse.book,
                chapter=verse.chapter,
                verse_start=verse.verse,  # Verse model uses 'verse' not 'verse_start'
                verse_end=None,  # Verse model doesn't have verse_end
                text=None  # Verse model doesn't have text field
            ))

    # For now, citations are empty (could be extracted from analysis in future)
    # The database doesn't have a citations table yet

    # Build summary
    summary = SummaryDTO(
        themes=themes,
        passages=passages,
        citations=citations,
        speaker=video.speaker,
        word_count=video.wpm or 0,  # Using wpm field as word count for now
        key_points=[],  # Not stored in current schema
        suggestions=[]  # Not stored in current schema
    )

    # Get transcript text
    transcript_text = None
    if video.transcript:
        transcript_text = video.transcript.text

    # Convert to dict and add summary
    detail_dict = base_dto.model_dump()
    detail_dict['summary'] = summary
    detail_dict['transcript'] = transcript_text
    detail_dict['error_message'] = video.error_message

    return VideoDetailDTO(**detail_dict)


@router.get("/", response_model=ApiSuccessResponse)
async def list_videos(
    limit: int = Query(50, ge=1, le=100, description="Number of videos to return"),
    status: Optional[str] = Query(None, description="Filter by status (pending, processing, completed, failed)"),
    channel_id: Optional[int] = Query(None, description="Filter by channel ID"),
    db: Session = Depends(get_db_session)
):
    """
    List all videos with optional filtering.

    Args:
        limit: Maximum number of videos to return (1-100, default 50)
        status: Filter by status (optional)
        channel_id: Filter by channel ID (optional)
        db: Database session

    Returns:
        List of videos with pagination
    """
    try:
        # Build query
        query = db.query(Video)

        # Apply filters
        if status:
            query = query.filter(Video.status == status.lower())

        if channel_id:
            query = query.filter(Video.channel_id == channel_id)

        # Order by created_at DESC and limit
        videos = query.order_by(Video.created_at.desc()).limit(limit).all()

        # Convert to DTOs
        video_dtos = [video_to_dto(v) for v in videos]

        logger.info(f"Returning {len(video_dtos)} videos (limit={limit}, status={status}, channel_id={channel_id})")

        return ApiSuccessResponse(
            success=True,
            data={"videos": [v.model_dump() for v in video_dtos], "total": len(video_dtos)},
            message="Videos retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error listing videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{video_id}", response_model=ApiSuccessResponse)
async def get_video(
    video_id: int,
    db: Session = Depends(get_db_session)
):
    """
    Get video details by ID.

    Args:
        video_id: Video identifier
        db: Database session

    Returns:
        Complete video details including summary and transcript
    """
    try:
        # Query video with all relationships
        video = db.query(Video).filter(Video.id == video_id).first()

        if not video:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

        # Convert to detailed DTO
        detail_dto = video_to_detail_dto(video)

        logger.info(f"Returning details for video {video_id}")

        return ApiSuccessResponse(
            success=True,
            data=detail_dto.model_dump(),
            message="Video details retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ApiSuccessResponse)
async def create_video():
    """
    Submit a new video for processing.

    Returns:
        Created video object

    **Note:** Full implementation pending in Phase 3
    """
    return ApiSuccessResponse(
        success=True,
        data=None,
        message="Video creation endpoint - implementation pending"
    )


@router.get("/{video_id}/detailed-report", response_model=ApiSuccessResponse)
async def get_detailed_report(
    video_id: int,
    db: Session = Depends(get_db_session)
):
    """
    Get comprehensive video report for detail drawer.

    Args:
        video_id: Video identifier
        db: Database session

    Returns:
        Detailed report with themes, passages, highlights, questions, and statistics
    """
    try:
        # Query video with relationships
        video = db.query(Video).filter(Video.id == video_id).first()

        if not video:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

        # Get sermon report (contains highlights and discussion questions in JSONB)
        sermon_report = db.query(SermonReport).filter(SermonReport.video_id == video_id).first()

        # Build themes list with scores
        themes = []
        if video.themes:
            for theme in video.themes:
                themes.append(ThemeDTO(
                    theme=theme.theme_name,
                    score=theme.frequency / 100.0 if theme.frequency else 0.5  # Convert to 0-1 score
                ))

        # Build biblical passages list
        passages = []
        if video.verses:
            for verse in video.verses:
                passages.append(BiblicalPassageDTO(
                    book=verse.book,
                    chapter=verse.chapter,
                    verse_start=verse.verse,
                    verse_end=None,
                    text=None
                ))

        # Extract highlights and questions from sermon report JSONB
        highlights = []
        discussion_questions = []
        ai_summary = None

        if sermon_report and sermon_report.report_json:
            report_data = sermon_report.report_json

            # Extract AI summary
            ai_summary = report_data.get('ai_summary')

            # Extract highlights
            if 'highlights' in report_data:
                for h in report_data['highlights']:
                    highlights.append(HighlightDTO(
                        title=h.get('title', ''),
                        summary=h.get('summary', ''),
                        timestamp=h.get('timestamp')
                    ))

            # Extract discussion questions
            if 'discussion_questions' in report_data:
                for q in report_data['discussion_questions']:
                    discussion_questions.append(DiscussionQuestionDTO(
                        question=q.get('question', ''),
                        passage=q.get('passage')
                    ))

        # Calculate statistics
        duration_minutes = video.duration_sec // 60 if video.duration_sec else 0
        word_count = video.wpm or 0  # Using wpm field as word count for now
        wpm = (word_count // duration_minutes) if duration_minutes > 0 else 0

        statistics = SermonStatisticsDTO(
            word_count=word_count,
            duration_minutes=duration_minutes,
            wpm=wpm
        )

        # Generate thumbnail URL
        thumbnail_url = f"https://img.youtube.com/vi/{video.youtube_id}/mqdefault.jpg"

        # Build detailed report DTO
        report = VideoDetailedReportDTO(
            video_id=str(video.id),
            title=video.title,
            youtube_id=video.youtube_id,
            published_at=video.published_at.isoformat() + "Z" if video.published_at else None,
            duration=video.duration_sec or 0,
            status=map_db_status_to_dto(video.status),
            speaker=video.speaker,
            thumbnail_url=thumbnail_url,
            ai_summary=ai_summary,
            statistics=statistics,
            themes=themes,
            passages=passages,
            highlights=highlights,
            discussion_questions=discussion_questions,
            transcript=None,  # Lazy loaded separately
            error_message=video.error_message
        )

        logger.info(f"Returning detailed report for video {video_id}")

        return ApiSuccessResponse(
            success=True,
            data=report.model_dump(),
            message="Detailed report retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detailed report for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{video_id}/transcript", response_model=ApiSuccessResponse)
async def get_transcript(
    video_id: int,
    db: Session = Depends(get_db_session)
):
    """
    Get video transcript (lazy loaded for performance).

    Args:
        video_id: Video identifier
        db: Database session

    Returns:
        Video transcript text
    """
    try:
        # Query transcript
        transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()

        if not transcript:
            raise HTTPException(status_code=404, detail=f"Transcript for video {video_id} not found")

        logger.info(f"Returning transcript for video {video_id}")

        return ApiSuccessResponse(
            success=True,
            data={"transcript": transcript.text},
            message="Transcript retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcript for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{video_id}", response_model=ApiSuccessResponse)
async def delete_video(video_id: str):
    """
    Delete a video.

    Args:
        video_id: Video identifier

    Returns:
        Success confirmation

    **Note:** Full implementation pending in Phase 3
    """
    return ApiSuccessResponse(
        success=True,
        data=None,
        message=f"Video deletion endpoint for {video_id} - implementation pending"
    )
