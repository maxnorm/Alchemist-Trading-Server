"""
Model Assignment Consumer for Redis Pub/Sub

Consumes model assignment events from Redis channel and creates TradingController
instances for live trading with trained models.
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
    logger.warning("Redis not available - model assignment events will not be consumed")


class ModelAssignmentConsumer:
    """
    Synchronous Redis Pub/Sub consumer for model assignment events.

    Subscribes to Redis channel and triggers ModelAssignmentService.handle_model_assignment().
    Runs in background thread with retry logic.
    Handles connection failures with exponential backoff.
    """

    def __init__(
        self,
        model_assignment_service,
        redis_host: Optional[str] = None,
        redis_port: int = 6379,
        redis_db: int = 0,
        channel: str = "model_assignments",
    ):
        """
        Initialize model assignment consumer.

        :param model_assignment_service: ModelAssignmentService instance
        :param redis_host: Redis host (defaults to REDIS_HOST env var or 'redis')
        :param redis_port: Redis port (defaults to REDIS_PORT env var or 6379)
        :param redis_db: Redis database number (defaults to REDIS_DB env var or 0)
        :param channel: Redis channel name for model assignment events (default: 'model_assignments')
        """
        self.model_assignment_service = model_assignment_service
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
        """Start consuming model assignment events from Redis."""
        if not REDIS_AVAILABLE:
            logger.warning(
                "Redis not available - model assignment consumer will not start"
            )
            return

        if self._running:
            logger.warning("Model assignment consumer is already running")
            return

        self._running = True
        self._shutdown_event.clear()
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"Model assignment consumer started, subscribing to channel '{self.channel}'"
        )

    def stop(self):
        """Stop consuming model assignment events and close connections."""
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
                logger.warning(
                    "Model assignment consumer thread did not stop within timeout"
                )

        logger.info("Model assignment consumer stopped")

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
                            self._handle_model_assignment(message["data"])
                        except Exception as e:
                            logger.error(
                                f"Error handling model assignment event: {e}",
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
                logger.error(
                    f"Error in model assignment consumer loop: {e}", exc_info=True
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

        logger.info("Model assignment consumer loop exited")

    def _handle_model_assignment(self, data: str):
        """
        Handle incoming model assignment event.

        :param data: JSON string containing event data
        """
        try:
            # Parse event payload
            event = json.loads(data)

            event_type = event.get("event_type")
            if event_type != "model_assignment":
                logger.warning(f"Unknown event type: {event_type}")
                return

            account_id = event.get("account_id")
            account_login = event.get("account_login")
            model_id = event.get("model_id")
            trading_mode = event.get("trading_mode", "live")

            if account_id is None or account_login is None or model_id is None:
                logger.error(
                    "Model assignment event missing required fields: "
                    f"account_id={account_id}, account_login={account_login}, model_id={model_id}"
                )
                return

            timestamp = event.get("timestamp", "unknown")
            logger.info(
                f"Received model assignment event: account_id={account_id}, "
                f"account_login={account_login}, model_id={model_id}, "
                f"trading_mode={trading_mode}, timestamp={timestamp}"
            )

            # Trigger model assignment handling
            if self.model_assignment_service is None:
                logger.error(
                    "ModelAssignmentService not available - cannot handle assignment"
                )
                return

            success = self.model_assignment_service.handle_model_assignment(
                account_id=account_id,
                account_login=account_login,
                model_id=model_id,
                trading_mode=trading_mode,
            )
            if success:
                logger.info(
                    f"Successfully handled model assignment: account_login={account_login}, model_id={model_id}"
                )
            else:
                logger.warning(
                    f"Failed to handle model assignment: account_login={account_login}, model_id={model_id}"
                )

        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse model assignment event JSON: {e}, data: {data}"
            )
        except Exception as e:
            logger.error(f"Error handling model assignment event: {e}", exc_info=True)
