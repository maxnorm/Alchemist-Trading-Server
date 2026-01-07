"""
WebSocket connection manager
"""

from fastapi import WebSocket
from typing import Dict, Set
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and channels"""

    def __init__(self) -> None:
        # Map channel -> set of WebSocket connections
        self.channels: Dict[str, Set[WebSocket]] = {}
        self.connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str, accept: bool = True) -> None:
        """Connect a WebSocket to a channel"""
        if accept:
            await websocket.accept()

        async with self._lock:
            if channel not in self.channels:
                self.channels[channel] = set()
            self.channels[channel].add(websocket)
            self.connections.add(websocket)

        logger.info(f"WebSocket connected to channel: {channel}")

    async def disconnect(self, websocket: WebSocket, channel: str):
        """Disconnect a WebSocket from a channel"""
        async with self._lock:
            if channel in self.channels:
                self.channels[channel].discard(websocket)
                if not self.channels[channel]:
                    del self.channels[channel]
            self.connections.discard(websocket)

        logger.info(f"WebSocket disconnected from channel: {channel}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")

    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast message to all connections in a channel"""
        if channel not in self.channels:
            return

        # Wrap message with channel info for frontend routing (if message doesn't already have channel field)
        wrapped_message = message.copy()
        if "channel" not in wrapped_message:
            # Map backend channel names to frontend channel paths
            channel_path_mapping = {
                "training": "/ws/training/metrics",
                "positions": "/ws/trading/positions",
                "performance": "/ws/performance/updates",
                "alerts": "/ws/alerts",
                "mt5_accounts": "/ws/accounts/mt5",
                "trading": "/ws/trading/status",
            }
            frontend_channel = channel_path_mapping.get(channel, f"/ws/{channel}")
            wrapped_message = {
                "channel": frontend_channel,
                "data": message
            }

        disconnected = set()
        async with self._lock:
            connections = self.channels[channel].copy()

        for connection in connections:
            try:
                await connection.send_json(wrapped_message)
            except Exception as e:
                logger.warning(f"Failed to broadcast to connection: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    self.channels[channel].discard(conn)
                    self.connections.discard(conn)

    async def disconnect_all(self):
        """Disconnect all WebSocket connections"""
        async with self._lock:
            for connection in list(self.connections):
                try:
                    await connection.close()
                except Exception:
                    pass
            self.connections.clear()
            self.channels.clear()

        logger.info("All WebSocket connections disconnected")

    def get_channel_count(self, channel: str) -> int:
        """Get number of connections in a channel"""
        return len(self.channels.get(channel, set()))

    def get_total_connections(self) -> int:
        """Get total number of connections"""
        return len(self.connections)


# Global WebSocket manager instance
websocket_manager = ConnectionManager()
