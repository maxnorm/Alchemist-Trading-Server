"""
MT5 price connector implementing IDataSourceConnector
Replaces PriceDataProvider with iterator-based pattern
"""

import threading
import queue
import time
from typing import Dict, Any, Iterator, Optional, Tuple
from datetime import datetime
from utils.logging_config import get_logger
from utils.time_utils import get_utc_time
from events.normalizer import EventNormalizer
from .base import IDataSourceConnector, ConnectorConfig
from models.currency_pair import CurrencyPair


class MT5PriceConnector(IDataSourceConnector):
    """
    MT5 price connector implementing IDataSourceConnector interface
    """

    def __init__(
        self,
        currency_pair: CurrencyPair,
        config: ConnectorConfig,
    ):
        """
        Initialize MT5 price connector

        :param currency_pair: CurrencyPair instance to subscribe to
        :param config: Connector configuration (must have symbol matching currency_pair)
        """
        if config.symbol != currency_pair.symbol:
            raise ValueError(
                f"Config symbol {config.symbol} does not match currency_pair symbol {currency_pair.symbol}"
            )

        self.currency_pair = currency_pair
        self.config = config
        self.normalizer = EventNormalizer()
        self.logger = get_logger("mt5_price_connector", "mt5_price_connector.log")

        # Event queue for streaming
        self._event_queue: queue.Queue = queue.Queue(maxsize=1000)
        self._shutdown_flag = threading.Event()
        self._is_connected = False

        # Background thread for consuming CurrencyPair updates
        self._consumer_thread: Optional[threading.Thread] = None

        # Track latest timestamp
        self._latest_timestamp: Optional[datetime] = None
        self._last_update_time: Optional[float] = None

        # Initialize lineage service
        try:
            from infrastructure.lineage.lineage_service import LineageService

            self.lineage_service = LineageService()
            self.current_run_id: Optional[str] = None
        except Exception as e:
            self.logger.warning(f"Failed to initialize lineage service: {e}")
            self.lineage_service = None
            self.current_run_id = None

    def connect(self) -> bool:
        """
        Establish connection to MT5 data source
        Starts background thread to consume CurrencyPair updates

        :return: True if connection successful, False otherwise
        """
        if self.is_connected():
            return True

        try:
            # Subscribe to currency pair updates
            self.currency_pair.subscribe(self._on_price_update)

            # Start consumer thread (though we're using callbacks, this thread
            # ensures the queue is being consumed)
            self._consumer_thread = threading.Thread(
                target=self._consumer_worker, daemon=True
            )
            self._consumer_thread.start()

            self._is_connected = True
            self.logger.info(f"Connected to MT5 price stream for {self.config.symbol}")
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to connect to MT5 price stream: {e}", exc_info=True
            )
            self._is_connected = False
            return False

    def disconnect(self) -> None:
        """Close connection to MT5 data source"""
        if not self.is_connected():
            return

        self._shutdown_flag.set()
        self._is_connected = False

        # Unsubscribe from currency pair (if it supports it)
        # Note: CurrencyPair may not have unsubscribe, so we'll just stop consuming

        # Wait for consumer thread to finish (with timeout)
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5.0)

        # Put None in queue to signal shutdown
        try:
            self._event_queue.put_nowait(None)
        except queue.Full:
            pass

        self.logger.info(f"Disconnected from MT5 price stream for {self.config.symbol}")

    def is_connected(self) -> bool:
        """Check if connector is currently connected"""
        return self._is_connected and not self._shutdown_flag.is_set()

    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """
        Stream normalized MT5 price events in real-time

        :param start_time: Optional start time (ignored for real-time streaming)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to MT5 price stream")

        # Start lineage run
        run_id = None
        if self.lineage_service:
            try:
                job_name = f"mt5_price_collection_{self.config.symbol}"
                run_id = self.lineage_service.start_run(
                    job_name=job_name,
                    namespace="trading_data",
                    inputs=[],
                    metadata={
                        "symbol": self.config.symbol,
                        "source": "mt5",
                        "data_type": "price",
                        "mode": "stream",
                    },
                )
                self.current_run_id = run_id
            except Exception as e:
                self.logger.warning(f"Failed to start lineage run: {e}")

        event_count = 0
        try:
            # Stream events from queue
            while not self._shutdown_flag.is_set():
                try:
                    # Get event from queue with timeout
                    event = self._event_queue.get(timeout=1.0)
                    if event is None:  # Shutdown signal
                        break

                    yield event
                    event_count += 1
                    self._event_queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error streaming event: {e}", exc_info=True)
                    continue

            # Complete lineage run
            if self.lineage_service and run_id:
                try:
                    dataset_name = f"prices_forex_{self.config.symbol}"
                    self.lineage_service.emit_dataset(
                        dataset_name=dataset_name,
                        namespace="trading_data",
                        schema=self.get_schema(),
                    )
                    self.lineage_service.complete_run(
                        run_id=run_id,
                        outputs=[
                            {
                                "dataset_id": f"trading_data:{dataset_name}",
                                "namespace": "trading_data",
                            }
                        ],
                        metadata={"event_count": event_count},
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to complete lineage run: {e}")

        except Exception as e:
            # Fail lineage run on error
            if self.lineage_service and run_id:
                try:
                    self.lineage_service.fail_run(run_id, str(e))
                except Exception as lineage_error:
                    self.logger.warning(f"Failed to fail lineage run: {lineage_error}")
            raise

    def batch(
        self, start_time: datetime, end_time: datetime
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical price data from database

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :return: Iterator of normalized event dictionaries
        """
        if start_time >= end_time:
            raise ValueError("start_time must be < end_time")

        # Start lineage run
        run_id = None
        if self.lineage_service:
            try:
                job_name = f"mt5_price_batch_{self.config.symbol}"
                run_id = self.lineage_service.start_run(
                    job_name=job_name,
                    namespace="trading_data",
                    inputs=[],
                    metadata={
                        "symbol": self.config.symbol,
                        "source": "mt5",
                        "data_type": "price",
                        "mode": "batch",
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                    },
                )
                self.current_run_id = run_id
            except Exception as e:
                self.logger.warning(f"Failed to start lineage run: {e}")

        # Query database for historical ticks
        from database import Database

        db = Database()
        event_count = 0

        try:
            # Calculate hours to look back
            time_diff = end_time - start_time
            hours = max(1, int(time_diff.total_seconds() / 3600) + 1)

            # Get recent ticks
            ticks = db.get_recent_ticks(
                symbol=self.config.symbol,
                limit=self.config.batch_size * 10,
                hours=hours,
            )

            # Filter ticks by time range and normalize
            for tick in ticks:
                tick_datetime = tick.get("datetime")
                if not tick_datetime:
                    continue

                # Convert to datetime if string
                if isinstance(tick_datetime, str):
                    try:
                        tick_datetime = datetime.strptime(
                            tick_datetime, "%Y-%m-%d %H:%M:%S"
                        )
                    except ValueError:
                        continue

                # Filter by time range
                if tick_datetime < start_time or tick_datetime > end_time:
                    continue

                # Convert to raw event format
                mid_price = tick.get("mid_price", 0.0)
                spread = 0.0001  # Default spread (1 pip)
                raw_event = {
                    "symbol": self.config.symbol,
                    "datetime": tick_datetime,  # Pass datetime object directly (preserves microseconds)
                    "ask": mid_price + spread / 2,
                    "bid": mid_price - spread / 2,
                }

                # Normalize
                normalized = self.normalizer.normalize(raw_event, source="mt5")

                # Validate
                if self.normalizer.validate(normalized):
                    event_count += 1
                    yield normalized

            # Complete lineage run
            if self.lineage_service and run_id:
                try:
                    dataset_name = f"prices_forex_{self.config.symbol}"
                    self.lineage_service.emit_dataset(
                        dataset_name=dataset_name,
                        namespace="trading_data",
                        schema=self.get_schema(),
                    )
                    self.lineage_service.complete_run(
                        run_id=run_id,
                        outputs=[
                            {
                                "dataset_id": f"trading_data:{dataset_name}",
                                "namespace": "trading_data",
                            }
                        ],
                        metadata={"event_count": event_count},
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to complete lineage run: {e}")

        except Exception as e:
            # Fail lineage run on error
            if self.lineage_service and run_id:
                try:
                    self.lineage_service.fail_run(run_id, str(e))
                except Exception as lineage_error:
                    self.logger.warning(f"Failed to fail lineage run: {lineage_error}")
            self.logger.error(f"Error fetching historical data: {e}", exc_info=True)
            raise

    def get_schema(self) -> Dict[str, Any]:
        """
        Return MT5 price schema definition

        :return: Schema dictionary
        """
        return {
            "source": "mt5",
            "data_type": "price",
            "symbol": self.config.symbol,
            "fields": {
                "symbol": "string",
                "timestamp": "datetime (UTC)",
                "bid": "float",
                "ask": "float",
                "mid": "float",
            },
            "required_fields": ["symbol", "timestamp", "bid", "ask"],
        }

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data

        :return: Datetime of most recent price update, or None if no data
        """
        return self._latest_timestamp

    def backfill(
        self, start_time: datetime, end_time: datetime, batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Backfill is not supported for MT5PriceConnector.
        Use MT5TickConnector for historical backfill.

        :raises NotImplementedError: This connector does not support backfill
        """
        raise NotImplementedError(
            "MT5PriceConnector does not support backfill. Use MT5TickConnector instead."
        )

    def get_available_range(self) -> Tuple[datetime, datetime]:
        """
        Get available range is not supported for MT5PriceConnector.
        Use MT5TickConnector for historical data range queries.

        :raises NotImplementedError: This connector does not support range queries
        """
        raise NotImplementedError(
            "MT5PriceConnector does not support get_available_range. Use MT5TickConnector instead."
        )

    def _on_price_update(self, pair: CurrencyPair) -> None:
        """
        Callback for when CurrencyPair price is updated
        Normalizes the price update and adds it to the event queue

        :param pair: CurrencyPair instance that was updated
        """
        try:
            # Track update time
            self._last_update_time = time.time()

            # Get current price data
            raw_event = {
                "symbol": pair.symbol,
                "datetime": get_utc_time(),  # Pass datetime object directly (preserves microseconds)
                "bid": pair.bid,
                "ask": pair.ask,
            }

            # Normalize event
            normalized = self.normalizer.normalize(raw_event, source="mt5")

            # Validate
            if self.normalizer.validate(normalized):
                # Update latest timestamp
                timestamp = normalized.get("timestamp")
                if timestamp:
                    if isinstance(timestamp, str):
                        try:
                            timestamp = datetime.fromisoformat(
                                timestamp.replace("Z", "+00:00")
                            )
                        except ValueError:
                            timestamp = get_utc_time()
                    self._latest_timestamp = timestamp

                # Add to queue (non-blocking)
                try:
                    self._event_queue.put_nowait(normalized)
                except queue.Full:
                    # Queue full - log warning and drop oldest
                    try:
                        self._event_queue.get_nowait()
                        self._event_queue.put_nowait(normalized)
                        self.logger.warning("Event queue full, dropped oldest event")
                    except queue.Empty:
                        pass
            else:
                self.logger.warning("Normalized price event failed validation")

        except Exception as e:
            self.logger.error(f"Error processing price update: {e}", exc_info=True)

    def _consumer_worker(self) -> None:
        """
        Background worker thread
        Currently just ensures the queue is being monitored
        Actual consumption happens via callbacks
        """
        self.logger.debug("Consumer worker started")

        # This thread mainly serves to keep the connection alive
        # The actual event production happens via _on_price_update callback
        while not self._shutdown_flag.is_set():
            try:
                # Just wait - events come via callback
                self._shutdown_flag.wait(timeout=1.0)
            except Exception as e:
                self.logger.error(f"Error in consumer worker: {e}", exc_info=True)
                break

        self.logger.debug("Consumer worker stopped")

    def is_stale(self, max_age_seconds: float = 60.0) -> bool:
        """
        Check if data is stale
        :param max_age_seconds: Maximum age in seconds before considered stale
        :return: True if stale, False otherwise
        """
        if self._last_update_time is None:
            return True  # Never updated

        age = time.time() - self._last_update_time
        return age > max_age_seconds

    def get_data_age(self) -> Optional[float]:
        """
        Get age of data in seconds
        :return: Age in seconds, or None if never updated
        """
        if self._last_update_time is None:
            return None
        return time.time() - self._last_update_time
