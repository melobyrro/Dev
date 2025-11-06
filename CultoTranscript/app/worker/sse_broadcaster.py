"""
SSE Broadcaster Module

Helper module for worker to broadcast status updates via SSE.
Provides a simple interface to notify clients of video processing progress.
"""
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration
WEB_SERVICE_URL = "http://culto_web:8000"
BROADCAST_ENDPOINT = f"{WEB_SERVICE_URL}/api/v2/events/broadcast"
TIMEOUT = 5.0


async def broadcast_status(
    video_id: str,
    status: str,
    message: Optional[str] = None,
    progress: Optional[int] = None
):
    """
    Broadcast video status to SSE clients.

    Args:
        video_id: Video ID being processed
        status: Status string (QUEUED, PROCESSING, PROCESSED, FAILED)
        message: Optional status message
        progress: Optional progress percentage (0-100)

    Note:
        This function fails silently if broadcast fails. We don't want
        SSE failures to break video processing.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                BROADCAST_ENDPOINT,
                json={
                    "video_id": str(video_id),
                    "status": status.upper(),
                    "message": message,
                    "progress": progress
                }
            )

            if response.status_code == 200:
                logger.debug(
                    f"SSE broadcast successful: video={video_id}, "
                    f"status={status}, message={message}"
                )
            else:
                logger.warning(
                    f"SSE broadcast failed: status={response.status_code}, "
                    f"video={video_id}"
                )

    except httpx.TimeoutException:
        logger.warning(f"SSE broadcast timeout for video {video_id}")
    except Exception as e:
        logger.warning(f"SSE broadcast failed for video {video_id}: {e}")
        # Don't raise - we don't want broadcast failures to break processing


def broadcast_status_sync(
    video_id: str,
    status: str,
    message: Optional[str] = None,
    progress: Optional[int] = None
):
    """
    Synchronous version of broadcast_status.

    Uses synchronous httpx client for compatibility with non-async code.

    Args:
        video_id: Video ID being processed
        status: Status string (QUEUED, PROCESSING, PROCESSED, FAILED)
        message: Optional status message
        progress: Optional progress percentage (0-100)
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                BROADCAST_ENDPOINT,
                json={
                    "video_id": str(video_id),
                    "status": status.upper(),
                    "message": message,
                    "progress": progress
                }
            )

            if response.status_code == 200:
                logger.debug(
                    f"SSE broadcast successful: video={video_id}, "
                    f"status={status}, message={message}"
                )
            else:
                logger.warning(
                    f"SSE broadcast failed: status={response.status_code}, "
                    f"video={video_id}"
                )

    except httpx.TimeoutException:
        logger.warning(f"SSE broadcast timeout for video {video_id}")
    except Exception as e:
        logger.warning(f"SSE broadcast failed for video {video_id}: {e}")
        # Don't raise - we don't want broadcast failures to break processing


# Convenience functions for common status updates

def broadcast_queued(video_id: str, message: str = "Vídeo enfileirado"):
    """Broadcast QUEUED status"""
    broadcast_status_sync(video_id, "QUEUED", message, progress=0)


def broadcast_processing(video_id: str, message: str, progress: Optional[int] = None):
    """Broadcast PROCESSING status with custom message"""
    broadcast_status_sync(video_id, "PROCESSING", message, progress)


def broadcast_processed(video_id: str, message: str = "Processamento concluído"):
    """Broadcast PROCESSED status"""
    broadcast_status_sync(video_id, "PROCESSED", message, progress=100)


def broadcast_failed(video_id: str, message: str = "Falha no processamento"):
    """Broadcast FAILED status"""
    broadcast_status_sync(video_id, "FAILED", message)
