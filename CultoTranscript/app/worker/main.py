"""
Worker service - processes transcription jobs from Redis queue
"""
import os
import sys
import logging
import json
import time
import random
import redis
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.worker.transcription_service import TranscriptionService
from app.worker.analytics_service import AnalyticsService  # Legacy v1
from app.worker.advanced_analytics_service import AdvancedAnalyticsService  # New v2
from app.ai.embedding_service import EmbeddingService
from app.ai.sermon_detector import detect_sermon_start
from app.common.database import get_db
from app.common.models import Job, Video, Transcript
from app.worker.sse_broadcaster import (
    broadcast_queued,
    broadcast_processing,
    broadcast_processed,
    broadcast_failed
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Feature flags
ENABLE_LAZY_ANALYTICS = os.getenv("ENABLE_LAZY_ANALYTICS", "false").lower() == "true"

# Services
transcription_service = TranscriptionService()
analytics_service = AnalyticsService()  # Legacy v1
advanced_analytics_service = AdvancedAnalyticsService()  # New v2
embedding_service = EmbeddingService()


def cleanup_abandoned_jobs(db):
    """Reset abandoned jobs from previous worker crashes"""
    logger.info("Checking for abandoned jobs...")
    try:
        abandoned = db.query(Job).filter(
            Job.status == 'running',
            Job.started_at < datetime.now() - timedelta(minutes=10)
        ).all()

        for job in abandoned:
            logger.warning(f"Resetting abandoned job {job.id} for video {job.video_id}")
            job.status = 'failed'
            job.error_message = 'Job abandoned due to worker restart'
            job.completed_at = datetime.now()

            # Also update the video status if needed
            if job.video_id:
                video = db.query(Video).filter_by(id=job.video_id).first()
                if video and video.status == 'processing':
                    # Check if there's a completed job for this video
                    completed_job = db.query(Job).filter(
                        Job.video_id == job.video_id,
                        Job.status == 'completed',
                        Job.job_type == 'transcribe_video'
                    ).first()

                    if completed_job:
                        logger.info(f"Setting video {video.id} to completed (has completed job)")
                        video.status = 'completed'
                    else:
                        logger.info(f"Setting video {video.id} to failed (no completed jobs)")
                        video.status = 'failed'

        db.commit()
        logger.info(f"Reset {len(abandoned)} abandoned jobs")
        return len(abandoned)
    except Exception as e:
        logger.error(f"Error cleaning up abandoned jobs: {e}")
        db.rollback()
        return 0


def update_job_progress(job_id: int, step: str, status: str, message: str):
    """Update job metadata with current progress"""
    try:
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                # Get current metadata from __dict__ to avoid SQLAlchemy MetaData conflict
                current_metadata = job.__dict__.get('meta') or {}
                if not isinstance(current_metadata, dict):
                    current_metadata = {}

                # Update with new values
                current_metadata.update({
                    "current_step": step,
                    "step_status": status,
                    "step_message": message,
                    "updated_at": datetime.now().isoformat()
                })

                # Reassign to trigger SQLAlchemy update
                job.meta = current_metadata
                db.commit()
    except Exception as e:
        logger.error(f"Failed to update job progress: {e}")


def process_transcription_job(job_data: dict):
    """
    Process a single transcription job

    Args:
        job_data: dict with job_id, url, channel_id
    """
    job_id = job_data.get("job_id")
    url = job_data.get("url")
    channel_id = job_data.get("channel_id")
    video_id = job_data.get("video_id")

    # If URL is not provided but video_id is, construct URL from existing video
    if not url and video_id:
        with get_db() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video and video.youtube_id:
                url = f"https://www.youtube.com/watch?v={video.youtube_id}"
                logger.info(f"Constructed URL from video {video_id}: {url}")
            else:
                raise Exception(f"Video {video_id} not found or missing youtube_id")

    logger.info(f"Processing job {job_id}: {url}")

    try:
        # Broadcast QUEUED status (if video_id is known)
        if video_id:
            broadcast_queued(video_id, "Iniciando processamento")

        # Update job status to running
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "running"
                job.started_at = datetime.now()
                job.meta = {
                    "total_steps": 6,
                    "current_step": "1",
                    "step_status": "running",
                    "step_message": "Extraindo informações do vídeo",
                    "steps": {
                        "1": {"name": "Extrair metadados", "status": "running", "estimate": "5-10s"},
                        "2": {"name": "Validar duração", "status": "pending", "estimate": "1s"},
                        "3": {"name": "Obter transcrição", "status": "pending", "estimate": "10-30s"},
                        "4": {"name": "Detectar início do sermão", "status": "pending", "estimate": "5-10s"},
                        "5": {"name": "Análise avançada com IA", "status": "pending", "estimate": "30-60s"},
                        "6": {"name": "Gerar embeddings", "status": "pending", "estimate": "10-20s"}
                    }
                }
                db.commit()

        # Step 1: Extract metadata
        update_job_progress(job_id, "1", "running", "Extraindo informações do vídeo")
        logger.info(f"Step 1/5: Extracting video metadata")
        if video_id:
            broadcast_processing(video_id, "Extraindo informações do vídeo", 10)
        time.sleep(1)  # Simulate some work

        # Step 2: Validate duration
        update_job_progress(job_id, "2", "running", "Validando duração do vídeo")
        logger.info(f"Step 2/5: Validating video duration")
        if video_id:
            broadcast_processing(video_id, "Validando duração do vídeo", 20)

        # Step 3: Transcribe video
        update_job_progress(job_id, "3", "running", "Obtendo transcrição (pode demorar alguns minutos)")
        logger.info(f"Step 3/5: Transcribing video {url}")
        if video_id:
            broadcast_processing(video_id, "Obtendo transcrição", 30)
        transcription_result = transcription_service.process_video(url, channel_id)

        if not transcription_result["success"]:
            raise Exception(transcription_result.get("error", "Transcription failed"))

        video_id = transcription_result["video_id"]
        logger.info(f"Transcription completed. Video ID: {video_id}")
        broadcast_processing(video_id, "Transcrição concluída", 50)

        # Step 4: Detect sermon start time
        update_job_progress(job_id, "4", "running", "Detectando início do sermão")
        logger.info(f"Step 4/6: Detecting sermon start time for video {video_id}")
        broadcast_processing(video_id, "Detectando início do sermão", 60)
        try:
            with get_db() as db:
                video = db.query(Video).filter(Video.id == video_id).first()
                transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()

                if video and transcript:
                    sermon_start = detect_sermon_start(transcript.text, video.duration_sec)
                    if sermon_start is not None:
                        video.sermon_start_time = sermon_start
                        db.commit()
                        logger.info(f"Sermon starts at {sermon_start} seconds ({sermon_start // 60} minutes)")
                    else:
                        logger.warning("Could not detect sermon start time, leaving as NULL")
                else:
                    logger.warning("Video or transcript not found for sermon detection")
        except Exception as e:
            logger.error(f"Sermon detection failed: {e}", exc_info=True)
            # Non-critical, continue with processing

        # Check if lazy analytics is enabled
        if ENABLE_LAZY_ANALYTICS:
            logger.info(f"LAZY ANALYTICS ENABLED: Skipping analytics for video {video_id}")
            logger.info("Analytics will be triggered on first view")

            # Set video status to 'transcribed' (intermediate state)
            with get_db() as db:
                video = db.query(Video).filter(Video.id == video_id).first()
                if video:
                    video.status = 'transcribed'
                    db.commit()

            # Update job as completed (without analytics)
            with get_db() as db:
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.status = "completed"
                    job.completed_at = datetime.now()
                    job.video_id = video_id
                    job.meta = {
                        "total_steps": 4,
                        "current_step": "4",
                        "step_status": "completed",
                        "step_message": "Transcrição concluída (análise adiada)",
                        "transcript_source": transcription_result.get("transcript_source"),
                        "lazy_analytics": True,
                        "steps": {
                            "1": {"name": "Extrair metadados", "status": "completed"},
                            "2": {"name": "Validar duração", "status": "completed"},
                            "3": {"name": "Obter transcrição", "status": "completed"},
                            "4": {"name": "Detectar início do sermão", "status": "completed"}
                        }
                    }
                    db.commit()

            broadcast_processed(video_id, "Transcrição concluída (análise será feita ao visualizar)")
            logger.info(f"Job {job_id} completed with lazy analytics")
            return

        # Step 5: Advanced Analytics (only if lazy loading disabled)
        update_job_progress(job_id, "5", "running", "Executando análise avançada com IA")
        logger.info(f"Step 5/6: Running advanced analytics for video {video_id}")
        broadcast_processing(video_id, "Executando análise avançada com IA", 70)
        analytics_result = advanced_analytics_service.analyze_video(video_id)

        if not analytics_result.get("success"):
            logger.warning(f"Advanced analytics failed: {analytics_result}")
        else:
            logger.info(
                f"Analysis completed - Citations: {analytics_result['citacoes']}, "
                f"Readings: {analytics_result['leituras']}, Mentions: {analytics_result['mencoes']}, "
                f"Themes: {analytics_result['themes_count']}, "
                f"Suggestions: {analytics_result['suggestions_count']}"
            )

        # Step 6: Generate embeddings for chatbot
        update_job_progress(job_id, "6", "running", "Gerando embeddings para chatbot")
        logger.info(f"Step 6/6: Generating embeddings")
        broadcast_processing(video_id, "Gerando embeddings para chatbot", 90)
        try:
            embedding_service.generate_embeddings_for_video(video_id)
            logger.info("Embeddings generated successfully")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            # Non-critical, continue

        # Update job status to completed
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.now()
                job.video_id = video_id
                job.meta = {
                    "total_steps": 6,
                    "current_step": "6",
                    "step_status": "completed",
                    "step_message": "Processamento concluído",
                    "transcript_source": transcription_result.get("transcript_source"),
                    "bible_references": analytics_result.get("bible_references", 0),
                    "themes": analytics_result.get("themes_detected", 0),
                    "steps": {
                        "1": {"name": "Extrair metadados", "status": "completed", "estimate": "5-10s"},
                        "2": {"name": "Validar duração", "status": "completed", "estimate": "1s"},
                        "3": {"name": "Obter transcrição", "status": "completed", "estimate": "10-30s"},
                        "4": {"name": "Detectar início do sermão", "status": "completed", "estimate": "5-10s"},
                        "5": {"name": "Análise avançada com IA", "status": "completed", "estimate": "30-60s"},
                        "6": {"name": "Gerar embeddings", "status": "completed", "estimate": "10-20s"}
                    }
                }
                db.commit()

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)

        # Update job status to failed
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.completed_at = datetime.now()
                job.error_message = str(e)
                db.commit()


def process_channel_import_job(job_data: dict):
    """
    Process a channel import job - list videos and queue transcription jobs

    Args:
        job_data: dict with job_id, channel_id, and optional date_start/date_end
    """
    import subprocess
    from app.common.models import Channel, Video, ExcludedVideo

    job_id = job_data.get("job_id")
    channel_id = job_data.get("channel_id")
    date_start = job_data.get("date_start")  # YYYY-MM-DD format
    date_end = job_data.get("date_end")      # YYYY-MM-DD format
    max_videos = job_data.get("max_videos")   # Optional limit

    logger.info(f"Processing channel import job {job_id} for channel {channel_id}")
    if date_start and date_end:
        logger.info(f"Date range filter: {date_start} to {date_end}")

    try:
        # Step 1: Read channel data
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            job.status = "running"
            job.started_at = datetime.now()
            job.meta = {
                "progress": 10,
                "message": "Lendo dados do canal...",
                "details": "Obtendo informações do canal",
                "steps": {
                    "1": {"name": "Ler dados do canal", "status": "running"},
                    "2": {"name": "Listar vídeos", "status": "pending"},
                    "3": {"name": "Filtrar vídeos excluídos", "status": "pending"},
                    "4": {"name": "Enfileirar jobs de transcrição", "status": "pending"}
                }
            }
            db.commit()

            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel or not channel.active:
                raise Exception(f"Canal {channel_id} não encontrado ou inativo")

            logger.info(f"Channel: {channel.title} ({channel.youtube_url})")

        # Step 2: List videos from channel
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            job.meta = {
                "progress": 30,
                "message": "Listando vídeos do canal...",
                "details": f"Buscando vídeos de {channel.title}",
                "steps": {
                    "1": {"name": "Ler dados do canal", "status": "completed"},
                    "2": {"name": "Listar vídeos", "status": "running"},
                    "3": {"name": "Filtrar vídeos excluídos", "status": "pending"},
                    "4": {"name": "Enfileirar jobs de transcrição", "status": "pending"}
                }
            }
            db.commit()

        # Use yt-dlp to list videos
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            f"{channel.youtube_url}/videos"
        ]

        # Add date filtering if provided
        if date_start:
            cmd.extend(["--dateafter", date_start])
        if date_end:
            # yt-dlp --datebefore is exclusive, so we add 1 day to include the end date
            from datetime import datetime, timedelta
            end_date_obj = datetime.strptime(date_end, '%Y-%m-%d') + timedelta(days=1)
            cmd.extend(["--datebefore", end_date_obj.strftime('%Y%m%d')])

        # Add limit if provided
        if max_videos:
            cmd.extend(["--playlist-end", str(max_videos)])
        else:
            # Default limit if no date range specified
            if not date_start and not date_end:
                cmd.extend(["--playlist-end", "50"])

        logger.info(f"Running yt-dlp command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            raise Exception(f"Falha ao listar vídeos: {result.stderr}")

        # Parse video list and apply early duration filtering
        from app.worker.yt_dlp_service import YtDlpService

        # Get duration thresholds for filtering
        min_duration, max_duration = YtDlpService.get_duration_thresholds()
        logger.info(f"Applying duration filter: {min_duration}s - {max_duration}s")

        videos_found = []
        skipped_short = 0
        skipped_long = 0

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                video_info = json.loads(line)
                upload_date = video_info.get("upload_date")  # Format: YYYYMMDD
                duration = video_info.get("duration", 0)

                # Additional date filtering (yt-dlp sometimes misses edge cases)
                if date_start or date_end:
                    if upload_date:
                        # Convert YYYYMMDD to YYYY-MM-DD for comparison
                        upload_date_str = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

                        if date_start and upload_date_str < date_start:
                            continue
                        if date_end and upload_date_str > date_end:
                            continue

                # Early duration validation (optimization)
                if duration < min_duration:
                    logger.info(f"Skipping short video {video_info.get('id')} - {duration}s")
                    skipped_short += 1
                    continue

                if duration > max_duration:
                    logger.info(f"Skipping long video {video_info.get('id')} - {duration}s")
                    skipped_long += 1
                    continue

                # Video passes all checks
                videos_found.append({
                    "youtube_id": video_info.get("id"),
                    "title": video_info.get("title", "Untitled"),
                    "duration": duration,
                    "upload_date": upload_date
                })
            except json.JSONDecodeError:
                continue

        logger.info(f"Duration filtering: {skipped_short} too short, {skipped_long} too long, {len(videos_found)} valid")
        logger.info(f"Found {len(videos_found)} videos in channel"
                    f"{' (filtered by date range)' if date_start or date_end else ''}")

        # Step 3: Filter excluded videos
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            job.meta = {
                "progress": 60,
                "message": "Filtrando vídeos já existentes...",
                "details": f"Verificando {len(videos_found)} vídeos",
                "total_videos": len(videos_found),  # Track total count
                "steps": {
                    "1": {"name": "Ler dados do canal", "status": "completed"},
                    "2": {"name": "Listar vídeos", "status": "completed"},
                    "3": {"name": "Filtrar vídeos excluídos", "status": "running"},
                    "4": {"name": "Enfileirar jobs de transcrição", "status": "pending"}
                }
            }
            db.commit()

            # Get existing and excluded video IDs
            existing_ids = set(
                v.youtube_id for v in db.query(Video.youtube_id).filter(
                    Video.youtube_id.in_([v["youtube_id"] for v in videos_found])
                ).all()
            )

            excluded_ids = set(
                e.youtube_id for e in db.query(ExcludedVideo.youtube_id).filter(
                    ExcludedVideo.channel_id == channel_id,
                    ExcludedVideo.youtube_id.in_([v["youtube_id"] for v in videos_found])
                ).all()
            )

            new_videos = [
                v for v in videos_found
                if v["youtube_id"] not in existing_ids and v["youtube_id"] not in excluded_ids
            ]

            logger.info(f"After filtering: {len(new_videos)} new videos to process")

        # Step 4: Enqueue transcription jobs
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            total_new = len(new_videos)

            queued_count = 0
            for idx, video in enumerate(new_videos, 1):
                # Calculate progress: 80% to 100% spread across videos
                progress = 80 + int((idx / total_new) * 20)

                # Update job metadata with current video progress
                job.meta = {
                    "progress": progress,
                    "message": f"Enfileirando vídeos ({idx}/{total_new})",
                    "details": f"Processando: {video['title'][:80]}...",
                    "total_videos": len(videos_found),
                    "new_videos": total_new,
                    "current_video": idx,
                    "current_video_title": video['title'],
                    "steps": {
                        "1": {"name": "Ler dados do canal", "status": "completed"},
                        "2": {"name": "Listar vídeos", "status": "completed"},
                        "3": {"name": "Filtrar vídeos excluídos", "status": "completed"},
                        "4": {"name": "Enfileirar jobs de transcrição", "status": "running"}
                    }
                }
                db.commit()

                video_url = f"https://www.youtube.com/watch?v={video['youtube_id']}"

                transcribe_job = Job(
                    job_type="transcribe_video",
                    status="queued",
                    channel_id=channel_id,
                    meta={"url": video_url, "channel_id": channel_id}
                )
                db.add(transcribe_job)
                db.flush()

                # Queue in Redis
                redis_client.rpush("transcription_queue", json.dumps({
                    "job_id": transcribe_job.id,
                    "url": video_url,
                    "channel_id": channel_id
                }))

                queued_count += 1
                logger.info(f"Queued {idx}/{total_new}: {video['title']} ({video['youtube_id']})")

            # Update channel last_checked_at
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if channel:
                channel.last_checked_at = datetime.now()

            db.commit()

        # Mark job as completed
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            job.status = "completed"
            job.completed_at = datetime.now()
            job.meta = {
                "progress": 100,
                "message": "Importação concluída!",
                "details": f"{queued_count} vídeos enfileirados para transcrição",
                "videos_found": len(videos_found),
                "videos_queued": queued_count,
                "steps": {
                    "1": {"name": "Ler dados do canal", "status": "completed"},
                    "2": {"name": "Listar vídeos", "status": "completed"},
                    "3": {"name": "Filtrar vídeos excluídos", "status": "completed"},
                    "4": {"name": "Enfileirar jobs de transcrição", "status": "completed"}
                }
            }
            db.commit()

        logger.info(f"Channel import job {job_id} completed. Queued {queued_count} videos")

    except Exception as e:
        logger.error(f"Channel import job {job_id} failed: {e}", exc_info=True)

        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now()
                db.commit()


def process_reanalysis_job(job_data: dict):
    """
    Process a re-analysis job - re-run advanced analytics on existing videos

    Args:
        job_data: dict with job_id and video_ids (list)
    """
    job_id = job_data.get("job_id")
    video_ids = job_data.get("video_ids", [])

    logger.info(f"Processing re-analysis job {job_id} for {len(video_ids)} videos")

    try:
        # Update job status to running
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            job.status = "running"
            job.started_at = datetime.now()
            job.meta = {
                "total_videos": len(video_ids),
                "processed": 0,
                "failed": 0,
                "message": "Iniciando re-análise..."
            }
            db.commit()

        processed = 0
        failed = 0

        for video_id in video_ids:
            try:
                logger.info(f"Re-analyzing video {video_id} ({processed + 1}/{len(video_ids)})")

                # Update progress
                with get_db() as db:
                    job = db.query(Job).filter(Job.id == job_id).first()
                    if job:
                        job.meta = {
                            "total_videos": len(video_ids),
                            "processed": processed,
                            "failed": failed,
                            "current_video_id": video_id,
                            "message": f"Analisando vídeo {processed + 1} de {len(video_ids)}..."
                        }
                        db.commit()

                # Run advanced analytics
                analytics_result = advanced_analytics_service.analyze_video(video_id)

                if analytics_result.get("success"):
                    # Generate embeddings
                    try:
                        embedding_service.generate_embeddings_for_video(video_id)
                        logger.info(f"Video {video_id} re-analyzed successfully")
                        processed += 1
                    except Exception as e:
                        logger.error(f"Failed to generate embeddings for video {video_id}: {e}")
                        failed += 1
                else:
                    logger.warning(f"Analytics failed for video {video_id}")
                    failed += 1

            except Exception as e:
                logger.error(f"Failed to re-analyze video {video_id}: {e}", exc_info=True)
                failed += 1

        # Mark job as completed
        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.now()
                job.meta = {
                    "total_videos": len(video_ids),
                    "processed": processed,
                    "failed": failed,
                    "message": f"Re-análise concluída! {processed} vídeos processados, {failed} falhas."
                }
                db.commit()

        logger.info(f"Re-analysis job {job_id} completed. Processed: {processed}, Failed: {failed}")

    except Exception as e:
        logger.error(f"Re-analysis job {job_id} failed: {e}", exc_info=True)

        with get_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now()
                db.commit()


def load_config_from_database():
    """Load configuration from database on worker startup"""
    try:
        from app.common.models import SystemSettings

        with get_db() as db:
            # Load Gemini API key from database
            api_key_setting = db.query(SystemSettings).filter(
                SystemSettings.setting_key == "gemini_api_key"
            ).first()

            if api_key_setting and api_key_setting.setting_value:
                os.environ["GEMINI_API_KEY"] = api_key_setting.setting_value
                logger.info("✅ Loaded Gemini API key from database")
            else:
                logger.warning("⚠️ No Gemini API key found in database, using .env value")

            # Load AI service provider setting
            service_setting = db.query(SystemSettings).filter(
                SystemSettings.setting_key == "ai_service_provider"
            ).first()

            if service_setting and service_setting.setting_value:
                os.environ["PRIMARY_LLM"] = service_setting.setting_value
                logger.info(f"✅ Loaded AI service provider from database: {service_setting.setting_value}")

    except Exception as e:
        logger.error(f"❌ Error loading config from database: {e}")


def worker_loop():
    """
    Main worker loop - polls Redis queue for jobs
    """
    logger.info("Worker starting...")

    # Load configuration from database
    load_config_from_database()

    # Clean up any abandoned jobs from previous crashes
    with get_db() as db:
        cleanup_abandoned_jobs(db)

    logger.info("Worker ready. Waiting for jobs...")

    while True:
        try:
            # Check for timed out jobs periodically (every 10th iteration)
            if random.randint(1, 10) == 1:
                with get_db() as db:
                    timed_out = db.query(Job).filter(
                        Job.status == 'running',
                        Job.started_at < datetime.now() - timedelta(hours=2)
                    ).all()

                    for job in timed_out:
                        logger.error(f"Job {job.id} timed out after 2 hours")
                        job.status = 'failed'
                        job.error_message = 'Job timed out after 2 hours'
                        job.completed_at = datetime.now()

                    if timed_out:
                        db.commit()
                        logger.info(f"Failed {len(timed_out)} timed out jobs")

            # Block and wait for job from queue (BLPOP with 5 second timeout)
            result = redis_client.blpop("transcription_queue", timeout=5)

            if result:
                _, job_json = result
                job_data = json.loads(job_json)

                logger.info(f"Received job: {job_data}")

                # Route to appropriate handler based on job_type
                job_type = job_data.get("job_type", "transcribe_video")

                if job_type == "check_channel":
                    process_channel_import_job(job_data)
                elif job_type == "analyze_video_v2":
                    process_reanalysis_job(job_data)
                else:
                    process_transcription_job(job_data)

        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
            break

        except Exception as e:
            logger.error(f"Error in worker loop: {e}", exc_info=True)
            time.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    logger.info("Starting CultoTranscript Worker...")
    worker_loop()
