"""
Experiment Publisher for Redis Pub/Sub

Publishes experiment start events to Redis channel for consumption by Trading Server.
"""

import os
import json
import threading
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - experiment events will not be published")


class ExperimentPublisher:
    """
    Thread-safe Redis Pub/Sub publisher for experiment events.

    Publishes experiment start events to Redis channel for consumption by Trading Server.
    Handles connection failures gracefully - logs warnings but doesn't crash.
    """

    _instance: Optional["ExperimentPublisher"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: int = 6379,
        redis_db: int = 0,
        channel: str = "experiments:start",
    ):
        """
        Initialize experiment publisher.

        :param redis_host: Redis host (defaults to REDIS_HOST env var or 'redis')
        :param redis_port: Redis port (defaults to REDIS_PORT env var or 6379)
        :param redis_db: Redis database number (defaults to REDIS_DB env var or 0)
        :param channel: Redis channel name for experiment events (default: 'experiments:start')
        """
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", str(redis_port)))
        self.redis_db = int(os.getenv("REDIS_DB", str(redis_db)))
        self.channel = channel
        self._redis_client: Optional[redis.Redis] = None
        self._connection_lock = threading.Lock()
        self._connected = False

    @classmethod
    def get_instance(cls) -> "ExperimentPublisher":
        """
        Get singleton instance of ExperimentPublisher.

        :return: ExperimentPublisher instance
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
                    # Ensure redis_host is not None
                    redis_host = self.redis_host or "redis"
                    self._redis_client = redis.Redis(
                        host=redis_host,
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
                        f"Failed to connect to Redis: {e}. Experiment events will not be published."
                    )

        return self._redis_client

    def publish_experiment_start(self, experiment_id: int) -> bool:
        """
        Publish experiment start event to Redis channel.

        :param experiment_id: Experiment ID to start
        :return: True if published successfully, False otherwise
        """
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available - experiment start event not published")
            return False

        try:
            client = self._get_redis_client()
            if client is None:
                logger.warning(
                    "Redis client unavailable - experiment start event not published"
                )
                return False

            # Build event payload
            payload = {
                "event_type": "experiment_start",
                "experiment_id": experiment_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Serialize and publish
            json_payload = json.dumps(payload)
            client.publish(self.channel, json_payload)

            logger.info(
                f"Published experiment start event to Redis channel '{self.channel}': experiment_id={experiment_id}"
            )
            return True

        except Exception as e:
            # Reset connection on error
            with self._connection_lock:
                self._connected = False
                self._redis_client = None

            logger.warning(f"Failed to publish experiment start event to Redis: {e}")
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
