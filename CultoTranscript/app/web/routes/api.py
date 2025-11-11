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
from app.common.models import (
    Video, Job, Channel, ExcludedVideo, Transcript, SermonReport,
    ChannelRollup, ScheduleConfig, Speaker, YouTubeSubscription,
    ChatbotQueryMetrics, ChatbotFeedback
)
from app.worker.report_generators import generate_daily_sermon_report, generate_channel_rollup
from app.worker.youtube_subscription_service import get_subscription_service
from app.ai.chatbot_service import ChatbotService
import os
import logging
from datetime import datetime, timezone, date
from pathlib import Path
import docker

logger = logging.getLogger(__name__)

# Initialize chatbot service
chatbot_service = ChatbotService()

router = APIRouter()

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


# ============================================================================
# Helper Functions for API Key Management
# ============================================================================

def update_env_file(key: str, value: str):
    """Update a key in the .env file for persistence across restarts"""
    try:
        # Try multiple possible .env file locations
        possible_paths = [
            Path("/app/../docker/.env"),  # Docker context
            Path("/app/.env"),             # Docker app directory
            Path(__file__).parent.parent.parent.parent / "docker" / ".env",  # Relative to this file
            Path(__file__).parent.parent.parent.parent / ".env",  # Root .env
        ]

        env_path = None
        for path in possible_paths:
            if path.exists():
                env_path = path
                logger.info(f"Found .env file at: {env_path}")
                break

        if not env_path:
            logger.warning(f".env file not found in any of: {[str(p) for p in possible_paths]}")
            return False

        # Read current .env content
        lines = env_path.read_text().split('\n')

        # Update or add the key
        key_found = False
        for i, line in enumerate(lines):
            # Match lines that start with the key (handle comments and whitespace)
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                key_found = True
                logger.info(f"Updated existing {key} in .env file")
                break

        if not key_found:
            # Add to end of file (before any trailing newlines)
            while lines and not lines[-1].strip():
                lines.pop()
            lines.append(f"{key}={value}")
            lines.append('')  # Add trailing newline
            logger.info(f"Added new {key} to .env file")

        # Write back
        env_path.write_text('\n'.join(lines))
        logger.info(f"✅ Successfully updated {key} in .env file at {env_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to update .env file: {e}")
        return False


def restart_worker_container():
    """Restart the worker container to pick up new environment variables"""
    try:
        client = docker.from_env()

        # Try to find worker container by name patterns
        worker_patterns = ['culto_worker', 'worker', 'cultotranscript-worker', 'cultotranscript_worker']

        containers = client.containers.list()
        logger.info(f"Found {len(containers)} running containers")

        for container in containers:
            container_name = container.name.lower()
            logger.info(f"Checking container: {container_name}")

            # Check if container name matches any worker pattern
            for pattern in worker_patterns:
                if pattern.lower() in container_name:
                    logger.info(f"🔄 Restarting worker container: {container.name}")
                    container.restart()
                    logger.info(f"✅ Successfully restarted {container.name}")
                    return True

        logger.warning("⚠️ Worker container not found among running containers")
        return False

    except docker.errors.DockerException as e:
        logger.error(f"Docker error while restarting worker: {e}")
        logger.info("💡 This is expected in development mode without Docker socket access")
        return False
    except Exception as e:
        logger.error(f"Failed to restart worker container: {e}")
        return False


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


class ChatbotFeedbackRequest(BaseModel):
    session_id: str
    query: str
    rating: str  # 'helpful' or 'not_helpful'
    response_summary: Optional[str] = None
    feedback_text: Optional[str] = None
    segments_shown: Optional[List[int]] = None


class ChannelSetupRequest(BaseModel):
    title: str
    youtube_url: HttpUrl


class BulkImportRequest(BaseModel):
    channel_id: int
    date_start: str  # YYYY-MM-DD format
    date_end: str    # YYYY-MM-DD format
    max_videos: Optional[int] = None


class MergeVideosRequest(BaseModel):
    video_ids: List[int]
    primary_video_id: int
    password: str


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


@router.post("/chatbot/feedback")
async def submit_chatbot_feedback(
    request: ChatbotFeedbackRequest,
    http_request: Request,
    db=Depends(get_db_session)
):
    """
    Submit feedback for a chatbot response (Phase 2: User Feedback System)

    Ratings: 'helpful', 'not_helpful'
    Optional feedback text for additional context
    """
    from app.common.models import ChatbotFeedback

    # Validate rating
    if request.rating not in ['helpful', 'not_helpful']:
        raise HTTPException(status_code=400, detail="Rating deve ser 'helpful' ou 'not_helpful'")

    try:
        # Extract user IP for analytics (optional)
        user_ip = http_request.client.host if http_request.client else None

        # Create feedback record
        feedback = ChatbotFeedback(
            session_id=request.session_id,
            query=request.query,
            response_summary=request.response_summary,
            rating=request.rating,
            feedback_text=request.feedback_text,
            segments_shown=request.segments_shown or [],
            channel_id=None,  # Can be extracted from session if needed
            user_ip=user_ip,
            metadata={}
        )

        db.add(feedback)
        db.commit()

        logger.info(f"Chatbot feedback submitted: {request.rating} (session={request.session_id})")

        return {
            "success": True,
            "message": "Obrigado pelo seu feedback!"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting chatbot feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao salvar feedback: {str(e)}")


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
    # Always read from database first (source of truth), fall back to env var if DB is empty
    gemini_key = (
        gemini_key_setting.setting_value if gemini_key_setting and gemini_key_setting.setting_value
        else os.getenv("GEMINI_API_KEY")
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

            # Reset LLM client singleton to pick up new API key
            try:
                from app.ai.llm_client import reset_llm_client
                reset_llm_client()
                logger.info("✅ LLM client reset - new API key will be used on next request")
            except Exception as e:
                logger.warning(f"⚠️ Failed to reset LLM client: {e}")

            # Update .env file for persistence across restarts
            logger.info("Updating .env file with new GEMINI_API_KEY...")
            env_updated = update_env_file("GEMINI_API_KEY", gemini_api_key)

            if env_updated:
                logger.info("✅ .env file updated successfully")
            else:
                logger.warning("⚠️ Failed to update .env file - changes will not persist after restart")

            # Restart worker container to pick up new API key
            logger.info("Attempting to restart worker container...")
            worker_restarted = restart_worker_container()

            if worker_restarted:
                logger.info("✅ Worker container restarted successfully")
            else:
                logger.warning("⚠️ Could not restart worker container - it will use old API key until manually restarted")

        # Commit the database changes
        db.commit()

        # Verify the save by re-reading from database
        if gemini_api_key:
            saved_setting = db.query(SystemSettings).filter(
                SystemSettings.setting_key == "gemini_api_key"
            ).first()

            if not saved_setting or saved_setting.setting_value != gemini_api_key:
                logger.error("❌ Database verification failed - API key not saved correctly")
                return {
                    "success": False,
                    "message": "Erro ao verificar salvamento da chave API no banco de dados"
                }

        # Build response with any warnings
        warnings = []
        if gemini_api_key and not env_updated:
            warnings.append("Chave API salva no banco mas .env não foi atualizado - pode não persistir após reinicialização")
        if gemini_api_key and not worker_restarted:
            warnings.append("Worker não foi reiniciado - usando chave antiga até reinicialização manual")

        return {
            "success": True,
            "message": "Configurações salvas com sucesso!",
            "warnings": warnings if warnings else None
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
    """Get Gemini API token usage statistics including daily quota"""
    try:
        from app.ai.llm_client import get_llm_client
        from app.ai.gemini_client import get_gemini_client

        # Get session stats from LLM client
        llm_client = get_llm_client()
        stats = llm_client.get_stats()

        # Get daily quota stats from Gemini client
        gemini_client = get_gemini_client()
        quota_stats = gemini_client.get_daily_quota_stats()

        # Merge both stats
        return {
            # Session stats
            "tokens_input": stats.get("gemini_tokens", 0),
            "tokens_output": 0,  # Not tracked separately
            "total_calls": stats.get("gemini_calls", 0),
            "fallback_count": stats.get("fallback_count", 0),
            "model_name": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            "active_backend": "gemini" if stats.get("gemini_calls", 0) > 0 else "ollama",

            # Daily quota stats
            "daily_requests_used": quota_stats.get("daily_requests_used", 0),
            "daily_requests_limit": quota_stats.get("daily_requests_limit", 250),
            "daily_quota_percentage": quota_stats.get("daily_quota_percentage", 0),
            "estimated_videos_remaining": quota_stats.get("estimated_videos_remaining", 25),
            "time_until_reset_hours": quota_stats.get("time_until_reset_hours", 0),
            "time_until_reset_formatted": quota_stats.get("time_until_reset_formatted", "N/A")
        }
    except Exception as e:
        logger.error(f"Error getting Gemini usage: {e}")
        return {"error": str(e)}


@router.get("/admin/settings/video-duration")
async def get_video_duration_settings(
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Get current min/max video duration settings."""
    from app.common.models import SystemSettings

    min_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "min_video_duration_sec"
    ).first()

    max_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "max_video_duration_sec"
    ).first()

    min_sec = int(min_setting.setting_value) if min_setting else 300
    max_sec = int(max_setting.setting_value) if max_setting else 9000

    return {
        "min_duration_sec": min_sec,
        "max_duration_sec": max_sec,
        "min_duration_min": min_sec / 60,
        "max_duration_min": max_sec / 60
    }


@router.put("/admin/settings/video-duration")
async def update_video_duration_settings(
    request: Request,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Update video duration thresholds."""
    from app.common.models import SystemSettings

    try:
        data = await request.json()
        min_sec = data.get("min_duration_sec")
        max_sec = data.get("max_duration_sec")

        # Validation
        if min_sec is None or max_sec is None:
            raise HTTPException(400, "Ambos min_duration_sec e max_duration_sec são obrigatórios")

        if min_sec < 0 or min_sec > 3600:
            raise HTTPException(400, "Duração mínima deve estar entre 0 e 3600 segundos (60 min)")

        if max_sec < 300 or max_sec > 18000:
            raise HTTPException(400, "Duração máxima deve estar entre 300 e 18000 segundos (300 min)")

        if min_sec >= max_sec:
            raise HTTPException(400, "Duração mínima deve ser menor que a máxima")

        # Update min duration
        min_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "min_video_duration_sec"
        ).first()

        if min_setting:
            min_setting.setting_value = str(min_sec)
            min_setting.updated_at = datetime.utcnow()
            min_setting.updated_by = user
        else:
            min_setting = SystemSettings(
                setting_key="min_video_duration_sec",
                setting_value=str(min_sec),
                encrypted=False,
                updated_by=user,
                description="Duração mínima de vídeo em segundos"
            )
            db.add(min_setting)

        # Update max duration
        max_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "max_video_duration_sec"
        ).first()

        if max_setting:
            max_setting.setting_value = str(max_sec)
            max_setting.updated_at = datetime.utcnow()
            max_setting.updated_by = user
        else:
            max_setting = SystemSettings(
                setting_key="max_video_duration_sec",
                setting_value=str(max_sec),
                encrypted=False,
                updated_by=user,
                description="Duração máxima de vídeo em segundos"
            )
            db.add(max_setting)

        db.commit()

        return {"success": True, "message": "Configurações atualizadas com sucesso"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating video duration settings: {e}")
        raise HTTPException(500, f"Erro ao salvar configurações: {str(e)}")


@router.post("/videos/merge")
async def merge_videos(
    request: MergeVideosRequest,
    db=Depends(get_db_session),
    user: str = Depends(get_current_user)
):
    """
    Merge multiple videos into one

    - Validates videos belong to same channel
    - Concatenates transcripts in chronological order
    - Merges basic analytics (verses, themes)
    - Deletes advanced analytics (will regenerate)
    - Deletes secondary videos
    - Queues re-analysis job
    """
    from app.common.models import (
        Verse, Theme,
        BiblicalPassage, SermonThemeV2, SermonInconsistency,
        SermonSuggestion, SermonHighlight, DiscussionQuestion,
        SensitivityFlag, TranscriptionError, SermonClassification,
        TranscriptEmbedding, AuditLog
    )
    from sqlalchemy import func

    # Verify password
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Senha incorreta")

    # Validate inputs
    if len(request.video_ids) < 2:
        raise HTTPException(status_code=400, detail="Selecione pelo menos 2 vídeos para mesclar")

    if request.primary_video_id not in request.video_ids:
        raise HTTPException(status_code=400, detail="Vídeo principal deve estar na lista de vídeos selecionados")

    try:
        # Fetch all videos
        videos = db.query(Video).filter(Video.id.in_(request.video_ids)).all()

        if len(videos) != len(request.video_ids):
            raise HTTPException(status_code=404, detail="Alguns vídeos não foram encontrados")

        # Validate same channel
        channels = set(v.channel_id for v in videos)
        if len(channels) > 1:
            raise HTTPException(status_code=400, detail="Todos os vídeos devem ser do mesmo canal")

        # Validate all have transcripts
        for video in videos:
            transcript = db.query(Transcript).filter(Transcript.video_id == video.id).first()
            if not transcript:
                raise HTTPException(
                    status_code=400,
                    detail=f"Vídeo '{video.title}' não possui transcrição"
                )

        # Get primary and secondary videos
        primary = next(v for v in videos if v.id == request.primary_video_id)
        secondaries = [v for v in videos if v.id != request.primary_video_id]

        # Sort by published_at for chronological merge
        sorted_videos = sorted(videos, key=lambda v: v.published_at)

        logger.info(f"Starting merge of {len(videos)} videos into primary video {primary.id}")

        # ========== BEGIN TRANSACTION ==========

        # 1. Merge transcripts (concatenate)
        merged_text_parts = []
        total_word_count = 0
        total_char_count = 0

        for video in sorted_videos:
            transcript = db.query(Transcript).filter(Transcript.video_id == video.id).first()
            merged_text_parts.append(
                f"\n\n=== {video.title} ({video.published_at.strftime('%d/%m/%Y')}) ===\n\n"
            )
            merged_text_parts.append(transcript.text)
            total_word_count += transcript.word_count or 0
            total_char_count += transcript.char_count or 0

        merged_text = "".join(merged_text_parts)

        # Update primary video's transcript
        primary_transcript = db.query(Transcript).filter(
            Transcript.video_id == primary.id
        ).first()
        primary_transcript.text = merged_text
        primary_transcript.word_count = total_word_count
        primary_transcript.char_count = total_char_count
        primary_transcript.source = 'merged'

        # 2. Update primary video metadata (keep title and speaker, reset timestamps)
        primary.duration_sec = sum(v.duration_sec for v in videos)
        primary.published_at = min(v.published_at for v in videos)
        primary.video_created_at = primary.published_at

        # Sermon date - keep earliest if exists
        sermon_dates = [v.sermon_actual_date for v in videos if v.sermon_actual_date]
        if sermon_dates:
            primary.sermon_actual_date = min(sermon_dates)

        # Reset metadata timestamps
        primary.ingested_at = func.now()
        primary.created_at = func.now()
        primary.updated_at = func.now()

        # Reset AI-generated fields
        primary.wpm = 0
        primary.ai_summary = None
        primary.sermon_start_time = 0
        primary.transcript_hash = None
        primary.status = 'completed'

        # 3. Merge Verses (deduplicate and sum counts)
        verse_map = {}
        for video in videos:
            verses = db.query(Verse).filter(Verse.video_id == video.id).all()
            for verse in verses:
                key = (verse.book, verse.chapter, verse.verse)
                if key in verse_map:
                    verse_map[key]['count'] += verse.count
                else:
                    verse_map[key] = {
                        'book': verse.book,
                        'chapter': verse.chapter,
                        'verse': verse.verse,
                        'count': verse.count
                    }

        # Delete all verses for primary and re-insert merged
        db.query(Verse).filter(Verse.video_id == primary.id).delete()
        for verse_data in verse_map.values():
            new_verse = Verse(
                video_id=primary.id,
                book=verse_data['book'],
                chapter=verse_data['chapter'],
                verse=verse_data['verse'],
                count=verse_data['count']
            )
            db.add(new_verse)

        # 4. Merge Themes (deduplicate and average scores)
        theme_map = {}
        for video in videos:
            themes = db.query(Theme).filter(Theme.video_id == video.id).all()
            for theme in themes:
                if theme.tag in theme_map:
                    theme_map[theme.tag]['scores'].append(theme.score)
                else:
                    theme_map[theme.tag] = {'scores': [theme.score]}

        # Delete all themes for primary and re-insert merged
        db.query(Theme).filter(Theme.video_id == primary.id).delete()
        for tag, data in theme_map.items():
            avg_score = sum(data['scores']) / len(data['scores'])
            new_theme = Theme(
                video_id=primary.id,
                tag=tag,
                score=avg_score
            )
            db.add(new_theme)

        # 5. Delete advanced analytics (will be regenerated)
        # These tables will regenerate via re-analysis job
        for video in videos:
            db.query(BiblicalPassage).filter(BiblicalPassage.video_id == video.id).delete()
            db.query(SermonThemeV2).filter(SermonThemeV2.video_id == video.id).delete()
            db.query(SermonInconsistency).filter(SermonInconsistency.video_id == video.id).delete()
            db.query(SermonSuggestion).filter(SermonSuggestion.video_id == video.id).delete()
            db.query(SermonHighlight).filter(SermonHighlight.video_id == video.id).delete()
            db.query(DiscussionQuestion).filter(DiscussionQuestion.video_id == video.id).delete()
            db.query(SensitivityFlag).filter(SensitivityFlag.video_id == video.id).delete()
            db.query(TranscriptionError).filter(TranscriptionError.video_id == video.id).delete()
            db.query(SermonReport).filter(SermonReport.video_id == video.id).delete()
            db.query(SermonClassification).filter(SermonClassification.video_id == video.id).delete()
            db.query(TranscriptEmbedding).filter(TranscriptEmbedding.video_id == video.id).delete()

        # 6. Delete secondary videos (cascade will handle remaining relations)
        for video in secondaries:
            logger.info(f"Deleting secondary video {video.id}: {video.title}")
            db.delete(video)

        # 7. Create audit log entry
        audit_entry = AuditLog(
            user_id=user if user != "anonymous" else None,
            action="merge_videos",
            target_type="video",
            target_id=primary.id,
            meta={
                "merged_video_ids": request.video_ids,
                "primary_video_id": primary.id,
                "video_titles": [v.title for v in videos],
                "total_duration_sec": primary.duration_sec,
                "total_word_count": total_word_count
            }
        )
        db.add(audit_entry)

        # Commit transaction
        db.commit()

        # ========== END TRANSACTION ==========

        logger.info(f"Successfully merged {len(videos)} videos into video {primary.id}")

        # 8. Queue re-analysis job (post-transaction)
        try:
            job = Job(
                job_type="transcribe_video",
                status="queued",
                video_id=primary.id,
                channel_id=primary.channel_id,
                meta={"reprocess": True, "merged": True, "youtube_id": primary.youtube_id}
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            # Queue in Redis
            job_data = {
                "job_id": job.id,
                "video_id": primary.id,
                "youtube_id": primary.youtube_id,
                "reprocess": True,
                "merged": True
            }
            redis_client.rpush("transcription_queue", json.dumps(job_data))

            logger.info(f"Queued re-analysis job {job.id} for merged video {primary.id}")
        except Exception as e:
            logger.error(f"Failed to queue re-analysis job: {e}")
            # Non-fatal - merge was successful

        return {
            "success": True,
            "merged_video_id": primary.id,
            "message": f"{len(videos)} vídeos mesclados com sucesso!",
            "details": {
                "total_duration": primary.duration_sec,
                "total_word_count": total_word_count,
                "videos_merged": [v.title for v in videos]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error merging videos: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao mesclar vídeos: {str(e)}"
        )


# ============================================================================
# PHASE 2: CHATBOT METRICS ENDPOINTS
# ============================================================================

@router.get("/admin/chatbot-metrics/data")
async def get_chatbot_metrics_data(
    days: int = 30,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """
    Get chatbot analytics data for dashboard (Phase 2)

    Returns:
    - Top 20 most common queries
    - Average response time
    - Feedback summary (% helpful vs not helpful)
    - Popular topics and keywords
    - Query volume over time
    - Cache hit rate
    """
    from sqlalchemy import func, desc
    from datetime import timedelta

    try:
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # 1. Top 20 most common queries
        top_queries = db.query(
            ChatbotQueryMetrics.query_normalized,
            func.count(ChatbotQueryMetrics.id).label('count'),
            func.avg(ChatbotQueryMetrics.response_time_ms).label('avg_response_time')
        ).filter(
            ChatbotQueryMetrics.created_at >= start_date
        ).group_by(
            ChatbotQueryMetrics.query_normalized
        ).order_by(
            desc('count')
        ).limit(20).all()

        # 2. Overall metrics
        total_queries = db.query(func.count(ChatbotQueryMetrics.id)).filter(
            ChatbotQueryMetrics.created_at >= start_date
        ).scalar() or 0

        avg_response_time = db.query(
            func.avg(ChatbotQueryMetrics.response_time_ms)
        ).filter(
            ChatbotQueryMetrics.created_at >= start_date
        ).scalar() or 0

        cache_hits = db.query(func.count(ChatbotQueryMetrics.id)).filter(
            ChatbotQueryMetrics.created_at >= start_date,
            ChatbotQueryMetrics.cache_hit == True
        ).scalar() or 0

        cache_hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0

        # 3. Feedback summary
        total_feedback = db.query(func.count(ChatbotFeedback.id)).filter(
            ChatbotFeedback.created_at >= start_date
        ).scalar() or 0

        helpful_feedback = db.query(func.count(ChatbotFeedback.id)).filter(
            ChatbotFeedback.created_at >= start_date,
            ChatbotFeedback.rating == 'helpful'
        ).scalar() or 0

        not_helpful_feedback = total_feedback - helpful_feedback

        helpful_percentage = (helpful_feedback / total_feedback * 100) if total_feedback > 0 else 0

        # 4. Query type distribution
        query_types = db.query(
            ChatbotQueryMetrics.query_type,
            func.count(ChatbotQueryMetrics.id).label('count')
        ).filter(
            ChatbotQueryMetrics.created_at >= start_date,
            ChatbotQueryMetrics.query_type.isnot(None)
        ).group_by(
            ChatbotQueryMetrics.query_type
        ).all()

        # 5. Filter usage statistics
        date_filter_usage = db.query(func.count(ChatbotQueryMetrics.id)).filter(
            ChatbotQueryMetrics.created_at >= start_date,
            ChatbotQueryMetrics.date_filters_used == True
        ).scalar() or 0

        speaker_filter_usage = db.query(func.count(ChatbotQueryMetrics.id)).filter(
            ChatbotQueryMetrics.created_at >= start_date,
            ChatbotQueryMetrics.speaker_filter_used == True
        ).scalar() or 0

        biblical_filter_usage = db.query(func.count(ChatbotQueryMetrics.id)).filter(
            ChatbotQueryMetrics.created_at >= start_date,
            ChatbotQueryMetrics.biblical_filter_used == True
        ).scalar() or 0

        theme_filter_usage = db.query(func.count(ChatbotQueryMetrics.id)).filter(
            ChatbotQueryMetrics.created_at >= start_date,
            ChatbotQueryMetrics.theme_filter_used == True
        ).scalar() or 0

        # 6. Backend distribution
        backend_distribution = db.query(
            ChatbotQueryMetrics.backend_used,
            func.count(ChatbotQueryMetrics.id).label('count')
        ).filter(
            ChatbotQueryMetrics.created_at >= start_date,
            ChatbotQueryMetrics.backend_used.isnot(None)
        ).group_by(
            ChatbotQueryMetrics.backend_used
        ).all()

        # 7. Daily query volume (last 30 days)
        daily_volume = db.execute(text("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM chatbot_query_metrics
            WHERE created_at >= :start_date
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """), {'start_date': start_date}).fetchall()

        return {
            "success": True,
            "period_days": days,
            "summary": {
                "total_queries": total_queries,
                "avg_response_time_ms": round(avg_response_time, 2),
                "cache_hit_rate": round(cache_hit_rate, 2),
                "total_feedback": total_feedback,
                "helpful_feedback": helpful_feedback,
                "not_helpful_feedback": not_helpful_feedback,
                "helpful_percentage": round(helpful_percentage, 2)
            },
            "top_queries": [
                {
                    "query": q[0],
                    "count": q[1],
                    "avg_response_time_ms": round(q[2], 2) if q[2] else 0
                }
                for q in top_queries
            ],
            "query_types": [
                {"type": qt[0], "count": qt[1]}
                for qt in query_types
            ],
            "filter_usage": {
                "date_filters": date_filter_usage,
                "speaker_filters": speaker_filter_usage,
                "biblical_filters": biblical_filter_usage,
                "theme_filters": theme_filter_usage
            },
            "backend_distribution": [
                {"backend": bd[0], "count": bd[1]}
                for bd in backend_distribution
            ],
            "daily_volume": [
                {"date": str(dv[0]), "count": dv[1]}
                for dv in daily_volume
            ]
        }

    except Exception as e:
        logger.error(f"Error fetching chatbot metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao buscar métricas: {str(e)}")


@router.get("/admin/chatbot-metrics/feedback")
async def get_recent_feedback(
    limit: int = 50,
    db=Depends(get_db_session),
    user: str = Depends(require_auth)
):
    """Get recent chatbot feedback entries with details"""
    try:
        feedback = db.query(ChatbotFeedback).order_by(
            ChatbotFeedback.created_at.desc()
        ).limit(limit).all()

        return {
            "success": True,
            "feedback": [
                {
                    "id": f.id,
                    "query": f.query,
                    "rating": f.rating,
                    "feedback_text": f.feedback_text,
                    "created_at": f.created_at.isoformat(),
                    "session_id": f.session_id
                }
                for f in feedback
            ]
        }

    except Exception as e:
        logger.error(f"Error fetching feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao buscar feedback: {str(e)}")
