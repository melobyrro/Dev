"""
SSE Manager Service

Manages Server-Sent Events connections and broadcasts events to connected clients.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Set
from uuid import uuid4

from Backend.dtos import (
    SSEEventDTO,
    EventType,
    HeartbeatEventDTO,
    VideoStatusEventDTO,
    VideoStatus
)

logger = logging.getLogger(__name__)


class SSEManager:
    """
    Manages SSE connections and event broadcasting.

    This class maintains a registry of connected clients and provides methods
    to broadcast events to all clients or send heartbeats to keep connections alive.
    """

    def __init__(self):
        """Initialize the SSE manager"""
        self._clients: Dict[str, asyncio.Queue] = {}
        self._heartbeat_task: asyncio.Task = None
        self._shutdown_event = asyncio.Event()
        logger.info("SSEManager initialized")

    async def add_client(self, client_id: str = None) -> tuple[str, asyncio.Queue]:
        """
        Register a new SSE connection.

        Args:
            client_id: Optional client identifier. If not provided, generates a new UUID.

        Returns:
            Tuple of (client_id, message_queue)
        """
        if client_id is None:
            client_id = str(uuid4())

        queue = asyncio.Queue()
        self._clients[client_id] = queue
        logger.info(f"Client {client_id} connected. Total clients: {len(self._clients)}")

        return client_id, queue

    async def remove_client(self, client_id: str):
        """
        Clean up on client disconnect.

        Args:
            client_id: The client identifier to remove
        """
        if client_id in self._clients:
            del self._clients[client_id]
            logger.info(f"Client {client_id} disconnected. Total clients: {len(self._clients)}")

    async def broadcast_event(self, event: SSEEventDTO):
        """
        Send event to all connected clients.

        Args:
            event: The event DTO to broadcast
        """
        if not self._clients:
            logger.debug(f"No clients connected. Event {event.type} not sent.")
            return

        logger.info(f"Broadcasting event {event.type} to {len(self._clients)} clients")

        # Convert event to dict for JSON serialization
        event_data = event.model_dump(mode="json")

        # Send to all clients
        disconnected_clients = []
        for client_id, queue in self._clients.items():
            try:
                await queue.put(event_data)
            except Exception as e:
                logger.error(f"Failed to send event to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.remove_client(client_id)

    async def broadcast_video_status(
        self,
        video_id: str,
        status: VideoStatus,
        message: str = None,
        progress: int = None
    ):
        """
        Broadcast a video status update to all connected clients.

        Args:
            video_id: The video identifier
            status: The new video status
            message: Optional status message
            progress: Optional progress percentage (0-100)
        """
        event = VideoStatusEventDTO(
            type=EventType.VIDEO_STATUS,
            timestamp=datetime.utcnow().isoformat() + "Z",
            video_id=video_id,
            status=status,
            message=message,
            progress=progress
        )
        await self.broadcast_event(event)
        logger.info(f"Broadcasted video status: {video_id} -> {status}")

    async def send_heartbeat(self):
        """
        Send heartbeat to all connected clients to keep connections alive.

        This should be called periodically (e.g., every 30 seconds) to prevent
        connection timeouts.
        """
        heartbeat_event = HeartbeatEventDTO(
            type=EventType.HEARTBEAT,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        await self.broadcast_event(heartbeat_event)

    async def start_heartbeat_task(self, interval: int = 30):
        """
        Start periodic heartbeat task.

        Args:
            interval: Heartbeat interval in seconds (default: 30)
        """
        if self._heartbeat_task is not None:
            logger.warning("Heartbeat task already running")
            return

        async def heartbeat_loop():
            logger.info(f"Starting heartbeat task with {interval}s interval")
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(interval)
                    if self._clients:  # Only send if there are connected clients
                        await self.send_heartbeat()
                except asyncio.CancelledError:
                    logger.info("Heartbeat task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def stop_heartbeat_task(self):
        """Stop the heartbeat task"""
        if self._heartbeat_task:
            self._shutdown_event.set()
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
            logger.info("Heartbeat task stopped")

    def get_client_count(self) -> int:
        """Get the number of connected clients"""
        return len(self._clients)

    async def shutdown(self):
        """Cleanup all connections and stop heartbeat"""
        logger.info("Shutting down SSE manager")
        await self.stop_heartbeat_task()
        self._clients.clear()


# Global singleton instance
sse_manager = SSEManager()
