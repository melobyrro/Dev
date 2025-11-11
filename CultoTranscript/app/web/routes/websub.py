"""
YouTube WebSub (PubSubHubbub) webhook endpoints.

Handles subscription verification and video notification callbacks from YouTube.
"""

import logging
import re
import json
import os
import xmltodict
from fastapi import APIRouter, Request, Response, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.common.database import get_db
from app.worker.youtube_subscription_service import get_subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/websub", tags=["websub"])


@router.get("/callback/{youtube_channel_id}")
@router.get("/callback")
async def verify_subscription(request: Request, youtube_channel_id: str = None, db: Session = Depends(get_db)):
    """
    Handle YouTube PubSubHubbub subscription verification (hub.challenge).

    YouTube sends a GET request with hub.challenge parameter to verify
    our callback URL. We must echo it back to confirm the subscription.

    Path params:
        youtube_channel_id: Optional YouTube channel ID in path

    Query params:
        hub.mode: "subscribe" or "unsubscribe"
        hub.topic: YouTube channel feed URL
        hub.challenge: Random string to echo back
        hub.lease_seconds: Subscription duration
    """
    challenge = request.query_params.get("hub.challenge")
    mode = request.query_params.get("hub.mode")
    topic = request.query_params.get("hub.topic")
    lease_seconds = request.query_params.get("hub.lease_seconds")

    logger.info(f"WebSub verification: mode={mode}, topic={topic}")

    if not challenge:
        logger.error("No hub.challenge in verification request")
        return Response(content="Missing hub.challenge", status_code=400)

    # Extract YouTube channel ID from topic URL
    # Format: https://www.youtube.com/xml/feeds/videos.xml?channel_id=UCxxxxx
    match = re.search(r'channel_id=([^&]+)', topic or "")

    if match:
        youtube_channel_id = match.group(1)
        logger.info(f"Verifying subscription for channel: {youtube_channel_id}")

        # Mark subscription as verified
        service = get_subscription_service()
        lease_sec = int(lease_seconds) if lease_seconds else 864000  # Default 10 days

        # Use context manager properly for database session
        from app.common.database import SessionLocal
        db_session = SessionLocal()
        try:
            service.mark_verified(youtube_channel_id, lease_sec, db=db_session)
            logger.info(f"Subscription verified for {youtube_channel_id}, lease={lease_seconds}s")
        finally:
            db_session.close()
    else:
        logger.warning(f"Could not extract channel ID from topic: {topic}")

    # Echo challenge back to YouTube to confirm
    return Response(content=challenge, media_type="text/plain")


@router.post("/callback/{youtube_channel_id}")
@router.post("/callback")
async def receive_notification(
    request: Request,
    background_tasks: BackgroundTasks,
    youtube_channel_id: str = None,
    db: Session = Depends(get_db)
):
    """
    Handle YouTube video upload/update notifications.

    YouTube sends POST requests with Atom XML feed containing video metadata
    when a new video is uploaded or an existing video is updated.

    Path params:
        youtube_channel_id: Optional YouTube channel ID in path

    Body: Atom XML feed with video entry
    """
    try:
        # Parse Atom XML feed
        xml_body = await request.body()

        if not xml_body:
            logger.warning("Empty notification body received")
            return Response(status_code=200)  # Return 200 to avoid retries

        # Parse XML to dict
        data = xmltodict.parse(xml_body)

        # Extract feed and entry
        feed = data.get("feed", {})
        entry = feed.get("entry")

        if not entry:
            logger.info("Notification with no entry (likely deletion or update)")
            return Response(status_code=200)

        # Extract video metadata
        video_id = entry.get("yt:videoId")
        channel_id = entry.get("yt:channelId")
        title = entry.get("title")
        published = entry.get("published")
        updated = entry.get("updated")
        link = entry.get("link", {})
        video_url = link.get("@href") if isinstance(link, dict) else None

        logger.info(f"WebSub notification: channel={channel_id}, video={video_id}, title={title}")

        # Record notification received
        service = get_subscription_service()

        # Use a separate session for recording notification
        from app.common.database import SessionLocal
        db_session = SessionLocal()
        try:
            service.record_notification(channel_id, db=db_session)
        finally:
            db_session.close()

        # Process video in background (don't block YouTube's callback)
        background_tasks.add_task(
            process_video_notification,
            video_id=video_id,
            channel_id=channel_id,
            title=title,
            published=published,
            video_url=video_url or f"https://www.youtube.com/watch?v={video_id}"
        )

        # Always return 200 quickly to avoid YouTube retries
        return Response(status_code=200)

    except Exception as e:
        logger.error(f"Error processing WebSub notification: {e}", exc_info=True)
        # Still return 200 to avoid retries (we'll catch it via polling)
        return Response(status_code=200)


async def process_video_notification(
    video_id: str,
    channel_id: str,
    title: str,
    published: str,
    video_url: str
):
    """
    Process video notification in background.

    This runs asynchronously after responding to YouTube to avoid
    blocking the webhook callback.

    Args:
        video_id: YouTube video ID
        channel_id: YouTube channel ID
        title: Video title
        published: Publication timestamp
        video_url: Full YouTube URL
    """
    from app.common.database import SessionLocal
    from app.common.models import Video, Channel, Job
    import redis

    db = SessionLocal()

    try:
        logger.info(f"Processing video notification: {video_id} - {title}")

        # Check if video already exists in database
        existing_video = db.query(Video).filter_by(youtube_id=video_id).first()

        if existing_video:
            logger.info(f"Video {video_id} already exists (status: {existing_video.status})")

            # If video was updated (title/description change), we might re-analyze
            # For now, skip if already processed
            if existing_video.status == "completed":
                logger.info(f"Video {video_id} already completed, skipping")
                return

            # If it failed before, retry
            if existing_video.status == "failed":
                logger.info(f"Video {video_id} previously failed, retrying")
                queue_video_for_transcription(video_url, existing_video.channel_id, db)
                return

        # Find internal channel ID
        channel = db.query(Channel).filter_by(youtube_channel_id=channel_id).first()

        if not channel:
            logger.warning(f"Channel {channel_id} not found in database")
            return

        if not channel.active:
            logger.info(f"Channel {channel_id} is inactive, skipping video")
            return

        # Queue video for transcription
        logger.info(f"Queueing new video for transcription: {video_url}")
        queue_video_for_transcription(video_url, channel.id, db)

        logger.info(f"Successfully queued video {video_id} from WebSub notification")

    except Exception as e:
        logger.error(f"Error in background video processing: {e}", exc_info=True)
    finally:
        db.close()


def queue_video_for_transcription(video_url: str, channel_id: int, db: Session):
    """
    Queue a video for transcription processing.

    Args:
        video_url: Full YouTube URL
        channel_id: Database channel ID
        db: Database session
    """
    from app.common.models import Video, Job
    import redis

    try:
        # Extract YouTube ID from URL
        youtube_id = extract_youtube_id(video_url)

        if not youtube_id:
            logger.error(f"Could not extract YouTube ID from URL: {video_url}")
            return

        # Check if video already queued/processed
        existing = db.query(Video).filter_by(youtube_id=youtube_id).first()

        if existing and existing.status in ["queued", "processing", "completed"]:
            logger.info(f"Video {youtube_id} already {existing.status}")
            return

        # Create job in database
        job = Job(
            job_type="transcribe_video",
            status="queued",
            channel_id=channel_id,
            meta={"url": video_url, "channel_id": channel_id, "source": "websub"}
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue in Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)

        job_data = {
            "job_id": job.id,
            "url": video_url,
            "channel_id": channel_id,
            "source": "websub"
        }

        r.rpush("transcription_queue", json.dumps(job_data))
        logger.info(f"Queued video {youtube_id} for transcription (job_id={job.id})")

    except Exception as e:
        logger.error(f"Error queueing video for transcription: {e}", exc_info=True)
        db.rollback()


def extract_youtube_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None
