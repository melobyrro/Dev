"""
API routes for AJAX calls and programmatic access
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
import redis
import json

from app.web.auth import get_current_user, require_auth, verify_password
from app.common.database import get_db_session
from app.common.models import Video, Job, Channel, ExcludedVideo, Transcript, SermonReport, ChannelRollup, ScheduleConfig, Speaker, YouTubeSubscription
from app.worker.report_generators import generate_daily_sermon_report, generate_channel_rollup
from app.worker.youtube_subscription_service import get_subscription_service
from app.ai.chatbot_service import ChatbotService
import os
import logging
from datetime import datetime, timezone, date

logger = logging.getLogger(__name__)

# Initialize chatbot service
chatbot_service = ChatbotService()

router = APIRouter()

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


class TranscribeRequest(BaseModel):
    url: HttpUrl
    channel_id: Optional[int] = None


class TranscriptUpdateRequest(BaseModel):
    text: str


class SermonDateUpdateRequest(BaseModel):
    sermon_actual_date: Optional[date]


class ReprocessRequest(BaseModel):
    password: str


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    progress: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None


class SpeakerUpdateRequest(BaseModel):
    speaker: str


class ScheduleConfigRequest(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    time_of_day: str  # HH:MM format
    enabled: bool = True


class ScheduleConfigResponse(BaseModel):
    id: int
    schedule_type: str
    day_of_week: Optional[int]
    time_of_day: str
    enabled: bool


@router.post("/transcribe")
async def start_transcription(
    request: TranscribeRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """
    Start video transcription job

    Queues a background job to transcribe the video
    """
    try:
        # Create job in database
        job = Job(
            job_type="transcribe_video",
            status="queued",
            meta={"url": str(request.url), "channel_id": request.channel_id}
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue job in Redis for worker
        job_data = {
            "job_id": job.id,
            "url": str(request.url),
            "channel_id": request.channel_id
        }
        redis_client.rpush("transcription_queue", json.dumps(job_data))

        return {
            "success": True,
            "job_id": job.id,
            "message": "Transcrição iniciada"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar transcrição: {str(e)}")


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Get status of a transcription job"""
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    # Get metadata value - SQLAlchemy JSON column returns it as dict already
    job_meta = job.__dict__.get('meta', None)

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job_meta.get("step_message") if job_meta else None,
        error=job.error_message,
        metadata=job_meta
    )


@router.get("/videos")
async def list_videos(
    skip: int = 0,
    limit: int = 20,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """List videos with pagination"""
    videos = db.query(Video).order_by(Video.published_at.desc()).offset(skip).limit(limit).all()

    return {
        "videos": [
            {
                "id": v.id,
                "title": v.title,
                "youtube_id": v.youtube_id,
                "status": v.status,
                "duration_sec": v.duration_sec,
                "published_at": v.published_at.isoformat(),
                "sermon_actual_date": v.sermon_actual_date.isoformat() if v.sermon_actual_date else None,
                "created_at": v.created_at.isoformat()
            }
            for v in videos
        ]
    }


@router.get("/speakers/autocomplete")
async def autocomplete_speakers(
    q: str = "",
    limit: int = 10,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Autocomplete speakers by name prefix

    If no query provided, returns most popular speakers (by video count).
    If query provided, searches by name prefix (case-insensitive).
    """
    if not q:
        # Return most frequent speakers if no query (popular speakers)
        speakers = db.query(Speaker).order_by(Speaker.video_count.desc()).limit(limit).all()
    else:
        # Search by name prefix (case-insensitive)
        speakers = db.query(Speaker).filter(
            Speaker.name.ilike(f"{q}%")
        ).order_by(Speaker.video_count.desc()).limit(limit).all()

    return {
        "suggestions": [
            {
                "id": s.id,
                "name": s.name,
                "video_count": s.video_count
            }
            for s in speakers
        ]
    }


@router.get("/channels")
async def list_channels(
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """List all channels"""
    channels = db.query(Channel).filter(Channel.active == True).all()

    return {
        "channels": [
            {
                "id": c.id,
                "title": c.title,
                "youtube_url": c.youtube_url,
                "youtube_channel_id": c.youtube_channel_id,
                "active": c.active
            }
            for c in channels
        ]
    }


class DeleteRequest(BaseModel):
    password: str


@router.delete("/videos/{video_id}")
async def delete_video(
    video_id: int,
    request: DeleteRequest,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Completely delete a video and all related data (transcript, verses, themes, jobs).
    Video can be re-imported later if needed.
    Requires admin password for authentication.
    """
    # Verify password
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Senha incorreta")

    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    try:
        video_title = video.title

        # Delete the video (cascade will handle related records)
        db.delete(video)
        db.commit()

        logger.info(f"Completely deleted video {video_id}: {video_title}")

        return {
            "success": True,
            "message": f"Vídeo '{video_title}' removido completamente"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir vídeo: {str(e)}")


@router.delete("/videos/{video_id}/exclude")
async def exclude_video(
    video_id: int,
    request: DeleteRequest,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Exclude (permanently delete) a video and all related data.
    This endpoint does the same as DELETE /videos/{video_id} but provides
    a semantically different name for UI purposes.
    Requires admin password for authentication.
    """
    # Verify password
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Senha incorreta")

    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    try:
        video_title = video.title

        # Delete the video (cascade will handle related records)
        db.delete(video)
        db.commit()

        logger.info(f"Excluded (permanently deleted) video {video_id}: {video_title}")

        return {
            "success": True,
            "message": f"Vídeo '{video_title}' excluído permanentemente"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir vídeo: {str(e)}")


@router.post("/videos/{video_id}/reprocess")
async def reprocess_video(
    video_id: int,
    request: ReprocessRequest,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Reprocess a video - re-runs sermon detection and analytics
    Requires admin password for authentication
    """
    # Verify password
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Senha incorreta")

    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    try:
        # Delete existing SermonReport to clear cached analysis
        existing_report = db.query(SermonReport).filter(SermonReport.video_id == video_id).first()
        if existing_report:
            db.delete(existing_report)
            logger.info(f"Deleted existing report for video {video_id} for reprocessing")

        # Delete existing SermonClassification to avoid unique constraint violation
        from app.common.models import SermonClassification
        existing_classification = db.query(SermonClassification).filter(SermonClassification.video_id == video_id).first()
        if existing_classification:
            db.delete(existing_classification)
            logger.info(f"Deleted existing classification for video {video_id} for reprocessing")

        # Reset video fields that will be regenerated
        video.sermon_start_time = None
        video.ai_summary = None
        video.status = 'processing'

        db.commit()

        # Queue transcribe_video job for full reprocessing
        # This will re-run: sermon detection, analytics, AI summary, embeddings
        job = Job(
            job_type="transcribe_video",
            status="queued",
            video_id=video_id,
            meta={"reprocess": True, "youtube_id": video.youtube_id}
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue in Redis
        job_data = {
            "job_id": job.id,
            "video_id": video_id,
            "youtube_id": video.youtube_id,
            "reprocess": True
        }
        redis_client.rpush("transcription_queue", json.dumps(job_data))

        logger.info(f"Queued reprocessing job {job.id} for video {video_id}")

        return {
            "success": True,
            "job_id": job.id,
            "message": "Reprocessamento iniciado"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error reprocessing video {video_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao reprocessar vídeo: {str(e)}")


@router.get("/channels/{channel_id}/import-status")
async def get_channel_import_status(
    channel_id: int,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Get channel import progress status"""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    # Check for channel import job
    import_job = db.query(Job).filter(
        Job.channel_id == channel_id,
        Job.job_type == "check_channel"
    ).order_by(Job.created_at.desc()).first()

    if not import_job:
        # Create new import job if none exists
        logger.info(f"Creating channel import job for channel {channel_id}")
        import_job = Job(
            job_type="check_channel",
            status="queued",
            channel_id=channel_id,
            meta={
                "progress": 0,
                "status": "queued",
                "message": "Aguardando início...",
                "steps": {}
            }
        )
        db.add(import_job)
        db.commit()
        db.refresh(import_job)

        # Queue job in Redis
        job_data = {
            "job_id": import_job.id,
            "channel_id": channel_id,
            "job_type": "check_channel"
        }
        redis_client.rpush("transcription_queue", json.dumps(job_data))
        logger.info(f"Queued channel import job {import_job.id}")

    # Get metadata
    job_meta = import_job.__dict__.get('meta') or {}

    return {
        "job_id": import_job.id,
        "status": import_job.status,
        "progress": job_meta.get("progress", 0),
        "message": job_meta.get("message", "Processando..."),
        "details": job_meta.get("details", ""),
        "steps": job_meta.get("steps", {}),
        "error": import_job.error_message
    }


@router.put("/videos/{video_id}/transcript")
async def update_transcript(
    video_id: int,
    request: TranscriptUpdateRequest,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Update transcript text for a video and trigger re-analysis"""
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcrição não encontrada")

    try:
        # Update transcript
        transcript.text = request.text
        transcript.word_count = len(request.text.split())
        transcript.char_count = len(request.text)

        # Delete existing SermonReport to trigger re-analysis
        existing_report = db.query(SermonReport).filter(SermonReport.video_id == video_id).first()
        if existing_report:
            db.delete(existing_report)
            logger.info(f"Deleted existing analysis for video {video_id} to trigger re-analysis")

        db.commit()

        # Queue new V2 analytics job
        try:
            job_data = {
                "job_type": "analyze_video_v2",
                "video_id": video_id,
                "youtube_id": video.youtube_id,
                "priority": 5  # Medium priority for re-analysis
            }
            redis_client.rpush("job_queue", json.dumps(job_data))
            logger.info(f"Queued analyze_video_v2 job for video {video_id} after transcript update")
        except Exception as queue_error:
            logger.error(f"Failed to queue re-analysis job: {queue_error}")
            # Don't fail the request if queueing fails

        logger.info(f"Updated transcript for video {video_id}")

        return {
            "success": True,
            "message": "Transcrição atualizada com sucesso. Análise será regerada automaticamente.",
            "word_count": transcript.word_count,
            "char_count": transcript.char_count,
            "reanalysis_queued": True
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating transcript: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar transcrição: {str(e)}")


@router.get("/videos/{video_id}/detailed-report")
async def get_detailed_report(
    video_id: int,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Get comprehensive DailySermonReport for a video

    Returns full analysis including:
    - Biblical content (citations, readings, mentions)
    - Themes with confidence scores
    - Inconsistencies and suggestions
    - Highlights and discussion questions
    - Sensitivity flags and transcription errors
    """
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    try:
        # Check for cached report
        cached_report = db.query(SermonReport).filter(
            SermonReport.video_id == video_id
        ).first()

        # Return cached if not expired
        if cached_report and cached_report.cache_expires_at > datetime.now(timezone.utc):
            logger.info(f"Returning cached report for video {video_id}")
            return {
                "success": True,
                "cached": True,
                "report": cached_report.report_json,
                "video_info": {
                    "speaker": video.speaker,
                    "sermon_actual_date": video.sermon_actual_date.isoformat() if video.sermon_actual_date else None
                }
            }

        # Generate new report
        logger.info(f"Generating new report for video {video_id}")
        report = generate_daily_sermon_report(video_id)

        return {
            "success": True,
            "cached": False,
            "report": report,
            "video_info": {
                "speaker": video.speaker,
                "sermon_actual_date": video.sermon_actual_date.isoformat() if video.sermon_actual_date else None
            }
        }

    except Exception as e:
        logger.error(f"Error generating report for video {video_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório: {str(e)}")


@router.get("/channels/{channel_id}/rollup")
async def get_channel_rollup(
    channel_id: int,
    month_year: Optional[str] = None,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Get ChannelRollup analytics for a channel

    Args:
        month_year: Month in YYYY-MM format (defaults to current month)

    Returns channel-wide analytics including:
    - Top books and themes for the month
    - Book frequency analysis
    - Recurring passages
    - Style metrics (avg WPM, duration, word count)
    - Automated alerts
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    # Default to current month if not specified
    if not month_year:
        month_year = datetime.now().strftime('%Y-%m')

    try:
        # Check for cached rollup
        cached_rollup = db.query(ChannelRollup).filter(
            ChannelRollup.channel_id == channel_id,
            ChannelRollup.month_year == month_year
        ).first()

        # If cached and recent (within 24 hours), return it
        if cached_rollup and (datetime.now() - cached_rollup.generated_at).total_seconds() < 86400:
            logger.info(f"Returning cached rollup for channel {channel_id}, month {month_year}")
            return {
                "success": True,
                "cached": True,
                "rollup": cached_rollup.rollup_json
            }

        # Generate new rollup
        logger.info(f"Generating new rollup for channel {channel_id}, month {month_year}")
        rollup = generate_channel_rollup(channel_id, month_year)

        if not rollup:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhum vídeo encontrado para {month_year}"
            )

        return {
            "success": True,
            "cached": False,
            "rollup": rollup
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating rollup for channel {channel_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório mensal: {str(e)}")


@router.post("/videos/{video_id}/reanalyze")
async def reanalyze_video(
    video_id: int,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """
    Queue a single video for re-analysis with V2 analytics

    Creates a job to re-run advanced analytics on this video
    """
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    try:
        # Create re-analysis job
        job = Job(
            job_type="analyze_video_v2",
            status="queued",
            meta={
                "video_ids": [video_id],
                "total_videos": 1,
                "message": "Aguardando re-análise..."
            }
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue in Redis
        job_data = {
            "job_id": job.id,
            "job_type": "analyze_video_v2",
            "video_ids": [video_id]
        }
        redis_client.rpush("transcription_queue", json.dumps(job_data))

        logger.info(f"Queued re-analysis job {job.id} for video {video_id}")

        return {
            "success": True,
            "job_id": job.id,
            "message": f"Vídeo '{video.title}' enfileirado para re-análise"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error queueing re-analysis for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar re-análise: {str(e)}")


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChannelSetupRequest(BaseModel):
    title: str
    youtube_url: HttpUrl


class BulkImportRequest(BaseModel):
    channel_id: int
    date_start: str  # YYYY-MM-DD format
    date_end: str    # YYYY-MM-DD format
    max_videos: Optional[int] = None


@router.post("/channels/{channel_id}/chat")
async def chat_with_channel(
    channel_id: int,
    request: ChatRequest,
    db=Depends(get_db_session)
):
    """
    Channel-specific chatbot using RAG

    Answers questions about sermons from this channel using:
    - Semantic search over sermon transcripts
    - Gemini AI for contextual response generation
    - Conversation history tracking

    Returns response with cited sermon sources
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    if not request.message or len(request.message.strip()) == 0:
        raise HTTPException(status_code=400, detail="Mensagem não pode estar vazia")

    try:
        # Call chatbot service
        result = chatbot_service.chat(
            channel_id=channel_id,
            user_message=request.message,
            session_id=request.session_id
        )

        logger.info(f"Chatbot response for channel {channel_id}: {len(result['response'])} chars")

        return {
            "success": True,
            "response": result['response'],
            "cited_videos": result['cited_videos'],
            "session_id": result['session_id'],
            "relevance_scores": result['relevance_scores']
        }

    except Exception as e:
        logger.error(f"Error in chatbot for channel {channel_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro no chatbot: {str(e)}")


@router.post("/channels/setup")
async def setup_channel(
    request: ChannelSetupRequest,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """
    Setup/configure a channel for the first time

    Extracts channel ID from YouTube URL and creates channel record
    """
    import subprocess

    try:
        # Extract channel_id from URL using yt-dlp
        logger.info(f"Extracting channel ID from URL: {request.youtube_url}")

        cmd = [
            "yt-dlp",
            "--dump-json",
            "--playlist-end", "1",
            str(request.youtube_url)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise ValueError(f"Failed to extract channel info: {result.stderr}")

        # Parse first line of JSON output
        channel_id = None
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                data = json.loads(line)
                channel_id = data.get('channel_id') or data.get('uploader_id')
                if channel_id:
                    break

        if not channel_id:
            raise ValueError("Could not find channel_id in YouTube data")

        logger.info(f"Extracted channel ID: {channel_id}")

        # Get first user as creator
        from app.common.models import User
        creator = db.query(User).first()

        # Create channel
        channel = Channel(
            title=request.title,
            youtube_url=str(request.youtube_url),
            channel_id=channel_id,
            created_by=creator.id if creator else None,
            active=True
        )

        db.add(channel)
        db.commit()
        db.refresh(channel)

        logger.info(f"Channel created: {channel.id} - {channel.title}")

        return {
            "success": True,
            "channel_id": channel.id,
            "message": f"Canal '{request.title}' configurado com sucesso"
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout ao extrair informações do canal")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        raise HTTPException(status_code=500, detail="Falha ao processar dados do YouTube")
    except Exception as e:
        db.rollback()
        logger.error(f"Error setting up channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao configurar canal: {str(e)}")


@router.get("/channels/{channel_id}/videos")
async def get_channel_videos(
    channel_id: int,
    limit: int = 50,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Get videos for a specific channel"""
    from app.common.models import Video

    videos = db.query(Video).filter(
        Video.channel_id == channel_id
    ).order_by(
        Video.published_at.desc()
    ).limit(limit).all()

    return {
        "videos": [
            {
                "id": v.id,
                "title": v.title,
                "youtube_id": v.youtube_id,
                "status": v.status,
                "duration_sec": v.duration_sec,
                "published_at": v.published_at.isoformat(),
                "video_created_at": v.video_created_at.isoformat() if v.video_created_at else v.published_at.isoformat(),
                "created_at": v.created_at.isoformat()
            }
            for v in videos
        ]
    }


@router.post("/channels/bulk-import")
async def bulk_import_channel_videos(
    request: BulkImportRequest,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """
    Bulk import videos from channel with date range filtering

    Queues a job to list all videos from the channel published within
    the specified date range and creates transcription jobs for new videos
    """
    channel = db.query(Channel).filter(Channel.id == request.channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    try:
        # Create channel import job with date range
        job = Job(
            job_type="check_channel",
            status="queued",
            channel_id=request.channel_id,
            meta={
                "progress": 0,
                "status": "queued",
                "message": "Aguardando início...",
                "date_start": request.date_start,
                "date_end": request.date_end,
                "max_videos": request.max_videos,
                "steps": {}
            }
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue job in Redis
        job_data = {
            "job_id": job.id,
            "channel_id": request.channel_id,
            "job_type": "check_channel",
            "date_start": request.date_start,
            "date_end": request.date_end,
            "max_videos": request.max_videos
        }
        redis_client.rpush("transcription_queue", json.dumps(job_data))

        logger.info(f"Queued bulk import job {job.id} for channel {request.channel_id} "
                    f"({request.date_start} to {request.date_end})")

        return {
            "success": True,
            "job_id": job.id,
            "message": f"Importação em lote iniciada para {request.date_start} até {request.date_end}"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error queueing bulk import: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar importação: {str(e)}")


@router.get("/videos/{video_id}/transcript")
async def get_video_transcript(
    video_id: int,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Get transcript for a specific video (for inline expansion)

    Returns:
        Dictionary with transcript text, word count, and video info
    """
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()

    if not transcript:
        return {
            "success": False,
            "message": "Transcrição não disponível para este vídeo"
        }

    return {
        "success": True,
        "video_id": video.id,
        "video_title": video.title,
        "transcript_text": transcript.text,
        "word_count": transcript.word_count,
        "char_count": transcript.char_count,
        "source": transcript.source
    }


@router.put("/videos/{video_id}/speaker")
async def update_video_speaker(
    video_id: int,
    request: SpeakerUpdateRequest,
    db=Depends(get_db_session)
    # Authentication removed - allow public updates (CSRF token still required)
):
    """
    Update the speaker name for a video and sync with speakers table

    Args:
        video_id: Video ID
        request: Speaker update request with speaker name

    Returns:
        Success response with updated speaker name
    """
    from sqlalchemy import func

    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    try:
        # Update video speaker
        old_speaker = video.speaker
        new_speaker = request.speaker.strip() if request.speaker else None
        video.speaker = new_speaker

        # Update or create speaker in speakers table
        if new_speaker:
            speaker = db.query(Speaker).filter(Speaker.name == new_speaker).first()

            if speaker:
                # Update existing speaker stats
                speaker.video_count = db.query(Video).filter(
                    Video.speaker == new_speaker
                ).count()
                speaker.last_seen_at = func.now()
            else:
                # Create new speaker
                speaker = Speaker(
                    name=new_speaker,
                    video_count=1,
                    first_seen_at=video.published_at if video.published_at else func.now(),
                    last_seen_at=video.published_at if video.published_at else func.now()
                )
                db.add(speaker)

        # Update old speaker stats if it changed
        if old_speaker and old_speaker != new_speaker:
            old_speaker_obj = db.query(Speaker).filter(Speaker.name == old_speaker).first()
            if old_speaker_obj:
                old_speaker_obj.video_count = db.query(Video).filter(
                    Video.speaker == old_speaker
                ).count()

        db.commit()

        logger.info(f"Speaker updated for video {video_id}: {old_speaker} -> {new_speaker}")

        return {
            "success": True,
            "video_id": video.id,
            "speaker": video.speaker
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating speaker for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar pregador: {str(e)}")


@router.put("/videos/{video_id}/sermon-date")
async def update_sermon_actual_date(
    video_id: int,
    request: SermonDateUpdateRequest,
    db=Depends(get_db_session)
):
    """
    Update the sermon_actual_date for a video. This allows aligning the service date
    when the upload happens on a different day (e.g., Monday).
    """
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    try:
        video.sermon_actual_date = request.sermon_actual_date
        db.commit()
        logger.info(f"Sermon date updated for video {video_id}: {video.sermon_actual_date}")

        return {
            "success": True,
            "video_id": video.id,
            "sermon_actual_date": video.sermon_actual_date.isoformat() if video.sermon_actual_date else None
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating sermon date for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar data do culto: {str(e)}")


@router.get("/schedule-config", response_model=ScheduleConfigResponse)
async def get_schedule_config(
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Get the current schedule configuration

    Returns:
        Schedule configuration object
    """
    config = db.query(ScheduleConfig).filter(
        ScheduleConfig.schedule_type == 'weekly_check'
    ).first()

    if not config:
        # Return default if not configured
        return ScheduleConfigResponse(
            id=0,
            schedule_type='weekly_check',
            day_of_week=0,  # Monday
            time_of_day='02:00:00',
            enabled=True
        )

    return ScheduleConfigResponse(
        id=config.id,
        schedule_type=config.schedule_type,
        day_of_week=config.day_of_week,
        time_of_day=str(config.time_of_day),  # Convert datetime.time to string
        enabled=config.enabled
    )


@router.put("/schedule-config")
async def update_schedule_config(
    request: ScheduleConfigRequest,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """
    Update the schedule configuration (Admin only)

    Args:
        request: Schedule configuration request

    Returns:
        Success response with updated configuration
    """
    # Validate day_of_week
    if request.day_of_week < 0 or request.day_of_week > 6:
        raise HTTPException(status_code=400, detail="day_of_week deve estar entre 0 (Segunda) e 6 (Domingo)")

    # Validate time format (HH:MM)
    import re
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', request.time_of_day):
        raise HTTPException(status_code=400, detail="time_of_day deve estar no formato HH:MM")

    # Convert HH:MM to HH:MM:SS for database
    time_with_seconds = request.time_of_day + ':00'

    # Get or create config
    config = db.query(ScheduleConfig).filter(
        ScheduleConfig.schedule_type == 'weekly_check'
    ).first()

    if config:
        # Update existing
        config.day_of_week = request.day_of_week
        config.time_of_day = time_with_seconds
        config.enabled = request.enabled
        config.updated_at = datetime.now()
    else:
        # Create new
        config = ScheduleConfig(
            schedule_type='weekly_check',
            day_of_week=request.day_of_week,
            time_of_day=time_with_seconds,
            enabled=request.enabled
        )
        db.add(config)

    db.commit()

    logger.info(f"Schedule config updated: Day {request.day_of_week}, Time {request.time_of_day}, Enabled {request.enabled}")

    return {
        "success": True,
        "message": "Configuração atualizada com sucesso",
        "config": {
            "day_of_week": config.day_of_week,
            "time_of_day": config.time_of_day[:5],  # Return HH:MM format
            "enabled": config.enabled
        }
    }


@router.get("/scheduler-status")
async def get_scheduler_status(
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """Get current scheduler status and next run time."""
    try:
        # Try to reach scheduler health endpoint
        import requests
        response = requests.get("http://culto_scheduler:8001/health", timeout=2)
        scheduler_data = response.json()

        # Get schedule config from database
        schedule_config = db.query(ScheduleConfig).filter(
            ScheduleConfig.schedule_type == "weekly_check"
        ).first()

        # Get last check time from channels
        last_check = db.query(Channel.last_checked_at).filter(
            Channel.active == True
        ).order_by(Channel.last_checked_at.desc()).first()

        return {
            "scheduler_running": True,
            "next_run": scheduler_data.get("next_run"),
            "last_check": last_check[0].isoformat() if last_check and last_check[0] else None,
            "schedule_enabled": schedule_config.enabled if schedule_config else False,
            "schedule_config": {
                "day_of_week": schedule_config.day_of_week if schedule_config else None,
                "time_of_day": str(schedule_config.time_of_day)[:5] if schedule_config else None  # HH:MM format
            }
        }
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        return {
            "scheduler_running": False,
            "error": str(e),
            "next_run": None,
            "last_check": None,
            "schedule_enabled": False,
            "schedule_config": {
                "day_of_week": None,
                "time_of_day": None
            }
        }


@router.get("/websub/subscriptions")
async def list_websub_subscriptions(
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """List all YouTube WebSub subscriptions (Admin only)."""
    subscriptions = db.query(YouTubeSubscription).join(Channel).all()

    return {
        "subscriptions": [
            {
                "id": sub.id,
                "channel_id": sub.channel_id,
                "channel_name": sub.channel.title if sub.channel else None,
                "youtube_channel_id": sub.youtube_channel_id,
                "status": sub.subscription_status,
                "last_notification": sub.last_notification_at.isoformat() if sub.last_notification_at else None,
                "notification_count": sub.notification_count,
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                "last_subscribed_at": sub.last_subscribed_at.isoformat() if sub.last_subscribed_at else None
            }
            for sub in subscriptions
        ]
    }


@router.post("/websub/subscribe/{channel_id}")
async def subscribe_channel_websub(
    channel_id: int,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Manually subscribe to a channel's WebSub notifications (Admin only)."""
    channel = db.query(Channel).filter_by(id=channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    if not channel.youtube_channel_id:
        raise HTTPException(status_code=400, detail="Canal não possui youtube_channel_id")

    service = get_subscription_service()
    result = service.subscribe_to_channel(channel_id, channel.youtube_channel_id, db=db)

    if result.get("success"):
        return {
            "success": True,
            "channel_id": channel_id,
            "youtube_channel_id": channel.youtube_channel_id,
            "message": result.get("message", "Inscrição realizada com sucesso")
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Erro ao realizar inscrição")
        )


@router.post("/websub/unsubscribe/{channel_id}")
async def unsubscribe_channel_websub(
    channel_id: int,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Manually unsubscribe from a channel's WebSub notifications (Admin only)."""
    channel = db.query(Channel).filter_by(id=channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    if not channel.youtube_channel_id:
        raise HTTPException(status_code=400, detail="Canal não possui youtube_channel_id")

    service = get_subscription_service()
    result = service.unsubscribe_from_channel(channel.youtube_channel_id, db=db)

    if result.get("success"):
        return {
            "success": True,
            "channel_id": channel_id,
            "youtube_channel_id": channel.youtube_channel_id,
            "message": result.get("message", "Desinscrição realizada com sucesso")
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Erro ao realizar desinscrição")
        )


# ============================================================================
# API Configuration Endpoints
# ============================================================================

@router.get("/admin/settings/api-config")
async def get_api_config(
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Get current API configuration with masked credentials"""
    from app.common.models import SystemSettings

    # Retrieve from database
    ai_service_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "ai_service_provider"
    ).first()

    gemini_key_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "gemini_api_key"
    ).first()

    # Mask API key for security
    gemini_key = os.getenv("GEMINI_API_KEY") or (
        gemini_key_setting.setting_value if gemini_key_setting else None
    )
    masked_key = None
    if gemini_key and len(gemini_key) > 4:
        masked_key = f"...{gemini_key[-4:]}"

    # Get usage stats from LLM client
    try:
        from app.ai.llm_client import get_llm_client
        llm_client = get_llm_client()
        stats = llm_client.get_stats()
    except Exception as e:
        logger.error(f"Error getting LLM stats: {e}")
        stats = {}

    return {
        "ai_service": ai_service_setting.setting_value if ai_service_setting else "gemini",
        "gemini_api_key": masked_key,
        "gemini_stats": {
            "tokens_input": stats.get("gemini_tokens", 0),
            "tokens_output": 0,  # Not tracked separately currently
            "total_calls": stats.get("gemini_calls", 0),
            "fallback_count": stats.get("fallback_count", 0),
            "model_name": os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        }
    }


@router.post("/admin/settings/api-config")
async def update_api_config(
    request: Request,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Update API configuration settings"""
    from app.common.models import SystemSettings

    try:
        data = await request.json()
        ai_service = data.get("ai_service")
        gemini_api_key = data.get("gemini_api_key")

        # Validate AI service
        if ai_service and ai_service not in ["gemini", "ollama"]:
            return {"success": False, "message": "Serviço de IA inválido. Use 'gemini' ou 'ollama'."}

        # Update AI service provider
        if ai_service:
            service_setting = db.query(SystemSettings).filter(
                SystemSettings.setting_key == "ai_service_provider"
            ).first()

            if service_setting:
                service_setting.setting_value = ai_service
                service_setting.updated_at = datetime.utcnow()
                service_setting.updated_by = user
            else:
                service_setting = SystemSettings(
                    setting_key="ai_service_provider",
                    setting_value=ai_service,
                    encrypted=False,
                    updated_by=user,
                    description="Primary AI service (gemini or ollama)"
                )
                db.add(service_setting)

        # Update Gemini API key
        if gemini_api_key:
            key_setting = db.query(SystemSettings).filter(
                SystemSettings.setting_key == "gemini_api_key"
            ).first()

            if key_setting:
                key_setting.setting_value = gemini_api_key
                key_setting.updated_at = datetime.utcnow()
                key_setting.updated_by = user
            else:
                key_setting = SystemSettings(
                    setting_key="gemini_api_key",
                    setting_value=gemini_api_key,
                    encrypted=True,
                    updated_by=user,
                    description="Google Gemini API key"
                )
                db.add(key_setting)

            # Also update environment variable for immediate effect
            os.environ["GEMINI_API_KEY"] = gemini_api_key

        db.commit()

        return {
            "success": True,
            "message": "Configurações salvas com sucesso!"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating API config: {e}")
        return {
            "success": False,
            "message": f"Erro ao salvar configurações: {str(e)}"
        }


@router.get("/admin/gemini-usage")
async def get_gemini_usage(user: str = Depends(require_auth)):
    """Get Gemini API token usage statistics"""
    try:
        from app.ai.llm_client import get_llm_client
        llm_client = get_llm_client()
        stats = llm_client.get_stats()

        return {
            "tokens_input": stats.get("gemini_tokens", 0),
            "tokens_output": 0,  # Not tracked separately
            "total_calls": stats.get("gemini_calls", 0),
            "fallback_count": stats.get("fallback_count", 0),
            "model_name": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            "active_backend": "gemini" if stats.get("gemini_calls", 0) > 0 else "ollama"
        }
    except Exception as e:
        logger.error(f"Error getting Gemini usage: {e}")
        return {"error": str(e)}
