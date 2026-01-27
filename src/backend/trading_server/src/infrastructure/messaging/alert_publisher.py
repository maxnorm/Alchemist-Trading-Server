"""
Alert Publisher for Redis Pub/Sub

Publishes alerts to Redis channel for consumption by API service.
"""

import os
import json
import threading
from datetime import datetime
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - alerts will not be published")


class AlertPublisher:
    """
    Thread-safe Redis Pub/Sub publisher for alerts.

    Publishes alerts to Redis channel for consumption by API service.
    Handles connection failures gracefully - logs warnings but doesn't crash.
    """

    _instance: Optional["AlertPublisher"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: int = 6379,
        redis_db: int = 0,
        channel: str = "alerts",
    ):
        """
        Initialize alert publisher.

        :param redis_host: Redis host (defaults to REDIS_HOST env var or 'redis')
        :param redis_port: Redis port (defaults to REDIS_PORT env var or 6379)
        :param redis_db: Redis database number (defaults to REDIS_DB env var or 0)
        :param channel: Redis channel name for alerts (default: 'alerts')
        """
        self.redis_host: str = redis_host or os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", str(redis_port)))
        self.redis_db = int(os.getenv("REDIS_DB", str(redis_db)))
        self.channel = channel
        self._redis_client: Optional[redis.Redis] = None
        self._connection_lock = threading.Lock()
        self._connected = False

    @classmethod
    def get_instance(cls) -> "AlertPublisher":
        """
        Get singleton instance of AlertPublisher.

        :return: AlertPublisher instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_redis_client(self) -> Optional[redis.Redis]:
        """
        Get or create Redis client connection.

        :return: Redis client or None if unavailable
        """
        if not REDIS_AVAILABLE:
            return None

        with self._connection_lock:
            if self._redis_client is None or not self._connected:
                try:
                    self._redis_client = redis.Redis(
                        host=self.redis_host,
                        port=self.redis_port,
                        db=self.redis_db,
                        socket_connect_timeout=2,
                        socket_timeout=2,
                        decode_responses=False,  # We'll encode JSON ourselves
                    )
                    # Test connection
                    self._redis_client.ping()
                    self._connected = True
                    logger.debug(
                        f"Connected to Redis at {self.redis_host}:{self.redis_port}/{self.redis_db}"
                    )
                except Exception as e:
                    self._connected = False
                    self._redis_client = None
                    logger.warning(
                        f"Failed to connect to Redis: {e}. Alerts will not be published."
                    )

        return self._redis_client

    def publish_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "info",
        metrics: Optional[Dict] = None,
    ) -> bool:
        """
        Publish alert to Redis channel.

        :param alert_type: Type of alert (e.g., 'data_gap', 'system_error')
        :param message: Alert message
        :param severity: Alert severity ('info', 'warning', 'error')
        :param metrics: Optional additional metrics dictionary
        :return: True if published successfully, False otherwise
        """
        if not REDIS_AVAILABLE:
            return False

        try:
            client = self._get_redis_client()
            if client is None:
                return False

            # Build alert payload
            payload: Dict[str, Any] = {
                "alert_type": alert_type,
                "message": message,
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if metrics:
                payload["metrics"] = metrics

            # Serialize and publish
            json_payload = json.dumps(payload)
            client.publish(self.channel, json_payload)

            logger.debug(
                f"Published alert to Redis channel '{self.channel}': {alert_type}"
            )
            return True

        except Exception as e:
            # Reset connection on error
            with self._connection_lock:
                self._connected = False
                self._redis_client = None

            logger.warning(f"Failed to publish alert to Redis: {e}")
            return False

    def close(self):
        """Close Redis connection."""
        with self._connection_lock:
            if self._redis_client is not None:
                try:
                    self._redis_client.close()
                except Exception:
                    pass
                self._redis_client = None
                self._connected = False
