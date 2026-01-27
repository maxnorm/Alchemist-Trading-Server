"""
Alert Consumer for Redis Pub/Sub

Consumes alerts from Redis channel and broadcasts via WebSocket.
"""

import asyncio
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis async client not available - alerts will not be consumed")


class AlertConsumer:
    """
    Async Redis Pub/Sub consumer for alerts.

    Subscribes to Redis channel and broadcasts alerts via WebSocket.
    Handles connection failures with retry logic.
    """

    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: int = 6379,
        redis_db: int = 0,
        channel: str = "alerts",
    ):
        """
        Initialize alert consumer.

        :param redis_host: Redis host (defaults to REDIS_HOST env var or 'redis')
        :param redis_port: Redis port (defaults to REDIS_PORT env var or 6379)
        :param redis_db: Redis database number (defaults to REDIS_DB env var or 0)
        :param channel: Redis channel name for alerts (default: 'alerts')
        """
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", str(redis_port)))
        self.redis_db = int(os.getenv("REDIS_DB", str(redis_db)))
        self.channel = channel
        self._redis_client: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start consuming alerts from Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available - alert consumer will not start")
            return

        if self._running:
            logger.warning("Alert consumer is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info(f"Alert consumer started, subscribing to channel '{self.channel}'")

    async def stop(self):
        """Stop consuming alerts and close connections."""
        self._running = False

        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(self.channel)
                await self._pubsub.close()
            except Exception as e:
                logger.warning(f"Error closing pubsub: {e}")
            self._pubsub = None

        if self._redis_client is not None:
            try:
                await self._redis_client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
            self._redis_client = None

        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Alert consumer task did not stop within timeout")
            except Exception as e:
                logger.warning(f"Error stopping alert consumer task: {e}")
            self._task = None

        logger.info("Alert consumer stopped")

    async def _connect(self) -> bool:
        """
        Connect to Redis.

        :return: True if connected successfully, False otherwise
        """
        try:
            self._redis_client = aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                socket_connect_timeout=5,
                socket_timeout=5,
                decode_responses=True,
            )

            # Test connection
            await self._redis_client.ping()
            logger.debug(
                f"Connected to Redis at {self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            if self._redis_client is not None:
                try:
                    await self._redis_client.close()
                except Exception:
                    pass
                self._redis_client = None
            return False

    async def _consume_loop(self):
        """Main consumption loop with retry logic."""
        retry_delay = 1.0
        max_retry_delay = 60.0

        while self._running:
            try:
                # Connect to Redis
                if self._redis_client is None:
                    connected = await self._connect()
                    if not connected:
                        # Exponential backoff for reconnection
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, max_retry_delay)
                        continue

                    # Reset retry delay on successful connection
                    retry_delay = 1.0

                # Create pubsub and subscribe
                if self._pubsub is None:
                    self._pubsub = self._redis_client.pubsub()
                    await self._pubsub.subscribe(self.channel)
                    logger.info(f"Subscribed to Redis channel '{self.channel}'")

                # Consume messages
                async for message in self._pubsub.listen():
                    if not self._running:
                        break

                    if message["type"] == "message":
                        try:
                            await self._handle_alert(message["data"])
                        except Exception as e:
                            logger.error(f"Error handling alert: {e}", exc_info=True)

            except asyncio.CancelledError:
                logger.info("Alert consumer task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in alert consumer loop: {e}", exc_info=True)
                # Reset connections on error
                if self._pubsub is not None:
                    try:
                        await self._pubsub.close()
                    except Exception:
                        pass
                    self._pubsub = None

                if self._redis_client is not None:
                    try:
                        await self._redis_client.close()
                    except Exception:
                        pass
                    self._redis_client = None

                # Wait before retrying
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    async def _handle_alert(self, data: str):
        """
        Handle incoming alert message.

        :param data: JSON string containing alert data
        """
        try:
            # Parse alert payload
            alert = json.loads(data)

            alert_type = alert.get("alert_type", "unknown")
            message = alert.get("message", "")
            severity = alert.get("severity", "info")
            metrics = alert.get("metrics")

            # Import here to avoid circular imports
            from websocket.channels import broadcast_alert

            # Broadcast via WebSocket
            await broadcast_alert(
                alert_type=alert_type,
                message=message,
                severity=severity,
                metrics=metrics,
            )

            logger.debug(f"Broadcast alert: {alert_type} - {message}")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse alert JSON: {e}, data: {data}")
        except Exception as e:
            logger.error(f"Error handling alert: {e}", exc_info=True)
