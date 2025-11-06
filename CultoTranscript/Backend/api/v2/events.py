"""
SSE Events Endpoint

Server-Sent Events endpoint for real-time updates to clients.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import Optional

from Backend.services.sse_manager import sse_manager
from Backend.dtos import VideoStatusEventDTO, VideoStatus, ApiSuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter()


async def event_stream(request: Request, client_id: str, queue: asyncio.Queue) -> AsyncGenerator[dict, None]:
    """
    Generate Server-Sent Events stream.

    Args:
        request: FastAPI request object (used to detect client disconnection)
        client_id: Unique client identifier
        queue: Client's message queue

    Yields:
        Event dictionaries in SSE format
    """
    logger.info(f"Starting event stream for client {client_id}")

    try:
        while True:
            # Check if client is still connected
            if await request.is_disconnected():
                logger.info(f"Client {client_id} disconnected")
                break

            try:
                # Wait for event with timeout to allow checking for disconnection
                event_data = await asyncio.wait_for(queue.get(), timeout=1.0)

                # Yield event in SSE format
                yield {
                    "event": event_data.get("type", "message"),
                    "data": json.dumps(event_data),
                }

            except asyncio.TimeoutError:
                # No event received, continue loop to check connection
                continue

            except Exception as e:
                logger.error(f"Error processing event for client {client_id}: {e}")
                break

    finally:
        # Clean up client connection
        await sse_manager.remove_client(client_id)
        logger.info(f"Event stream ended for client {client_id}")


@router.get("/stream")
async def sse_stream(request: Request):
    """
    SSE endpoint for real-time event updates.

    Returns a Server-Sent Events stream that pushes real-time updates to the client.

    **Event Types:**
    - `video.status`: Video processing status updates
    - `summary.ready`: Video summary completed
    - `error`: Error notifications
    - `heartbeat`: Connection keep-alive (every 30s)

    **Usage:**
    ```javascript
    const eventSource = new EventSource('/api/v2/events/stream');

    eventSource.addEventListener('video.status', (event) => {
        const data = JSON.parse(event.data);
        console.log('Video status:', data);
    });

    eventSource.addEventListener('heartbeat', (event) => {
        console.log('Connection alive');
    });
    ```

    **Response Format:**
    Each event follows the SSE standard format:
    ```
    event: video.status
    data: {"type": "video.status", "video_id": "123", "status": "PROCESSING", ...}
    ```

    **Connection Notes:**
    - Heartbeats sent every 30 seconds to keep connection alive
    - Client should reconnect on disconnect
    - Multiple clients can connect simultaneously
    """
    # Register new client
    client_id, queue = await sse_manager.add_client()

    logger.info(f"New SSE connection from client {client_id}. IP: {request.client.host}")

    # Return SSE stream
    return EventSourceResponse(
        event_stream(request, client_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for SSE service.

    Returns:
        JSON with service status and connected client count
    """
    return {
        "status": "healthy",
        "service": "sse_events",
        "connected_clients": sse_manager.get_client_count()
    }


class BroadcastVideoStatusRequest(BaseModel):
    """Request body for broadcasting video status"""
    video_id: str
    status: VideoStatus
    message: Optional[str] = None
    progress: Optional[int] = None


async def verify_internal_request(request: Request, x_internal_token: Optional[str] = Header(None)):
    """
    Verify request is from internal service (worker/scheduler).

    This is a simple security measure. In production, you might want:
    - JWT tokens
    - Mutual TLS
    - Network-level restrictions (localhost only)
    """
    # Allow requests from localhost (Docker internal network)
    if request.client.host.startswith("172.") or request.client.host in ["127.0.0.1", "localhost"]:
        return True

    # Check for internal token
    internal_token = x_internal_token
    expected_token = "internal-broadcast-token-change-in-production"  # TODO: Move to env var

    if internal_token != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid internal token")

    return True


@router.post("/broadcast", response_model=ApiSuccessResponse)
async def broadcast_video_status(
    request: BroadcastVideoStatusRequest,
    req: Request,
    _: bool = Depends(verify_internal_request)
):
    """
    Broadcast a video status update to all connected SSE clients.

    This endpoint is for internal use only (worker/scheduler services).

    **Security:**
    - Only accessible from internal Docker network (172.x.x.x)
    - Requires X-Internal-Token header for external requests

    **Request Body:**
    ```json
    {
        "video_id": "123",
        "status": "PROCESSING",
        "message": "Extracting audio...",
        "progress": 25
    }
    ```

    **Example Usage (from worker):**
    ```python
    import httpx

    async with httpx.AsyncClient() as client:
        await client.post(
            "http://culto_web:8000/api/v2/events/broadcast",
            json={
                "video_id": "123",
                "status": "PROCESSING",
                "message": "Transcribing audio...",
                "progress": 50
            }
        )
    ```
    """
    try:
        # Broadcast the event
        await sse_manager.broadcast_video_status(
            video_id=request.video_id,
            status=request.status,
            message=request.message,
            progress=request.progress
        )

        logger.info(f"Broadcasted video status from {req.client.host}: {request.video_id} -> {request.status}")

        return ApiSuccessResponse(
            success=True,
            data={
                "video_id": request.video_id,
                "status": request.status.value,
                "clients_notified": sse_manager.get_client_count()
            },
            message=f"Video status broadcast to {sse_manager.get_client_count()} clients"
        )

    except Exception as e:
        logger.error(f"Error broadcasting video status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
