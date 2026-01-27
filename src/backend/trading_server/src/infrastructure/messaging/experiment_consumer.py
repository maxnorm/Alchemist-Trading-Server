"""
Experiment Consumer for Redis Pub/Sub

Consumes experiment start events from Redis channel and triggers training in ExperimentRunner.
"""

import os
import json
import threading
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - experiment events will not be consumed")


class ExperimentConsumer:
    """
    Synchronous Redis Pub/Sub consumer for experiment events.

    Subscribes to Redis channel and triggers ExperimentRunner.start_experiment().
    Runs in background thread with retry logic.
    Handles connection failures with exponential backoff.
    """

    def __init__(
        self,
        experiment_runner,
        redis_host: Optional[str] = None,
        redis_port: int = 6379,
        redis_db: int = 0,
        channel: str = "experiments:start",
    ):
        """
        Initialize experiment consumer.

        :param experiment_runner: ExperimentRunner instance to trigger training
        :param redis_host: Redis host (defaults to REDIS_HOST env var or 'redis')
        :param redis_port: Redis port (defaults to REDIS_PORT env var or 6379)
        :param redis_db: Redis database number (defaults to REDIS_DB env var or 0)
        :param channel: Redis channel name for experiment events (default: 'experiments:start')
        """
        self.experiment_runner = experiment_runner
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", str(redis_port)))
        self.redis_db = int(os.getenv("REDIS_DB", str(redis_db)))
        self.channel = channel
        self._redis_client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

    def start(self):
        """Start consuming experiment events from Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available - experiment consumer will not start")
            return

        if self._running:
            logger.warning("Experiment consumer is already running")
            return

        self._running = True
        self._shutdown_event.clear()
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"Experiment consumer started, subscribing to channel '{self.channel}'"
        )

    def stop(self):
        """Stop consuming experiment events and close connections."""
        if not self._running:
            return

        self._running = False
        self._shutdown_event.set()

        if self._pubsub is not None:
            try:
                self._pubsub.unsubscribe(self.channel)
                self._pubsub.close()
            except Exception as e:
                logger.warning(f"Error closing pubsub: {e}")
            self._pubsub = None

        if self._redis_client is not None:
            try:
                self._redis_client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
            self._redis_client = None

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("Experiment consumer thread did not stop within timeout")

        logger.info("Experiment consumer stopped")

    def _connect(self) -> bool:
        """
        Connect to Redis.

        :return: True if connected successfully, False otherwise
        """
        try:
            self._redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                socket_connect_timeout=5,
                socket_timeout=5,
                decode_responses=True,
            )

            # Test connection
            self._redis_client.ping()
            logger.debug(
                f"Connected to Redis at {self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            if self._redis_client is not None:
                try:
                    self._redis_client.close()
                except Exception:
                    pass
                self._redis_client = None
            return False

    def _consume_loop(self):
        """Main consumption loop with retry logic."""
        retry_delay = 1.0
        max_retry_delay = 60.0

        while self._running and not self._shutdown_event.is_set():
            try:
                # Connect to Redis
                if self._redis_client is None:
                    connected = self._connect()
                    if not connected:
                        # Exponential backoff for reconnection
                        if self._shutdown_event.wait(timeout=retry_delay):
                            break
                        retry_delay = min(retry_delay * 2, max_retry_delay)
                        continue

                    # Reset retry delay on successful connection
                    retry_delay = 1.0

                # Create pubsub and subscribe
                if self._pubsub is None:
                    self._pubsub = self._redis_client.pubsub()
                    self._pubsub.subscribe(self.channel)
                    logger.info(f"Subscribed to Redis channel '{self.channel}'")

                # Consume messages with timeout to allow checking shutdown event
                try:
                    message = self._pubsub.get_message(timeout=1.0)
                    if message is None:
                        continue  # Timeout, check again

                    if message["type"] == "message":
                        try:
                            self._handle_experiment_start(message["data"])
                        except Exception as e:
                            logger.error(
                                f"Error handling experiment start event: {e}",
                                exc_info=True,
                            )

                except redis.TimeoutError:
                    # Timeout is expected, continue loop
                    continue
                except Exception as e:
                    logger.error(
                        f"Error receiving message from Redis: {e}", exc_info=True
                    )
                    # Reset connections on error
                    if self._pubsub is not None:
                        try:
                            self._pubsub.close()
                        except Exception:
                            pass
                        self._pubsub = None

                    if self._redis_client is not None:
                        try:
                            self._redis_client.close()
                        except Exception:
                            pass
                        self._redis_client = None

                    # Wait before retrying
                    if self._shutdown_event.wait(timeout=retry_delay):
                        break
                    retry_delay = min(retry_delay * 2, max_retry_delay)

            except Exception as e:
                logger.error(f"Error in experiment consumer loop: {e}", exc_info=True)
                # Reset connections on error
                if self._pubsub is not None:
                    try:
                        self._pubsub.close()
                    except Exception:
                        pass
                    self._pubsub = None

                if self._redis_client is not None:
                    try:
                        self._redis_client.close()
                    except Exception:
                        pass
                    self._redis_client = None

                # Wait before retrying
                if self._shutdown_event.wait(timeout=retry_delay):
                    break
                retry_delay = min(retry_delay * 2, max_retry_delay)

        logger.info("Experiment consumer loop exited")

    def _handle_experiment_start(self, data: str):
        """
        Handle incoming experiment start event.

        :param data: JSON string containing event data
        """
        try:
            # Parse event payload
            event = json.loads(data)

            event_type = event.get("event_type")
            if event_type != "experiment_start":
                logger.warning(f"Unknown event type: {event_type}")
                return

            experiment_id = event.get("experiment_id")
            if experiment_id is None:
                logger.error("Experiment start event missing experiment_id")
                return

            timestamp = event.get("timestamp", "unknown")
            logger.info(
                f"Received experiment start event: experiment_id={experiment_id}, timestamp={timestamp}"
            )

            # Trigger experiment start
            if self.experiment_runner is None:
                logger.error("ExperimentRunner not available - cannot start experiment")
                return

            success = self.experiment_runner.start_experiment(experiment_id)
            if success:
                logger.info(f"Successfully started experiment {experiment_id}")
            else:
                logger.warning(f"Failed to start experiment {experiment_id}")

        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse experiment start event JSON: {e}, data: {data}"
            )
        except Exception as e:
            logger.error(f"Error handling experiment start event: {e}", exc_info=True)
