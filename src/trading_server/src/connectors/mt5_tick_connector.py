"""
MT5 tick connector implementing IDataSourceConnector
Wraps MT5TickStreamer and adds normalization
"""

import threading
import queue
from typing import Dict, Any, Iterator, Optional, Tuple
from datetime import datetime, timedelta, timezone
import time
from utils.logging_config import get_logger
from events.normalizer import EventNormalizer
from .base import IDataSourceConnector, ConnectorConfig
from mt5_connection.tick_streamer import MT5TickStreamer
from models.currency_pair import CurrencyPair

# Connection state management (optional)
try:
    from mt5_connection.connection_state import ConnectionState, ConnectionStateManager
except ImportError:
    ConnectionState = None  # type: ignore
    ConnectionStateManager = None  # type: ignore


class MT5TickConnector(IDataSourceConnector):
    """
    MT5 tick connector implementing IDataSourceConnector interface
    Wraps MT5TickStreamer and adds event normalization
    """

    def __init__(
        self,
        socket,
        symbol: str,
        config: ConnectorConfig,
        streamer: Optional[MT5TickStreamer] = None,
    ):
        """
        Initialize MT5 tick connector

        :param socket: Socket connection to MT5
        :param symbol: Trading symbol (e.g., "EURUSD")
        :param config: Connector configuration
        :param streamer: Optional existing MT5TickStreamer instance (for backward compatibility)
        """
        self.socket = socket
        self.symbol = symbol
        self.config = config
        self.normalizer = EventNormalizer()
        self.logger = get_logger("mt5_tick_connector", "mt5_tick_connector.log")

        # Create currency pair
        digits = config.extra_config.get("digits", 5)
        self.currency_pair = CurrencyPair(symbol, digits)

        # Create or use provided streamer
        self.streamer = streamer
        self._streamer_thread: Optional[threading.Thread] = None
        self._is_connected = False

        # Initialize lineage service
        try:
            from infrastructure.lineage.lineage_service import LineageService

            self.lineage_service = LineageService()
            self.current_run_id: Optional[str] = None
        except Exception as e:
            self.logger.warning(f"Failed to initialize lineage service: {e}")
            self.lineage_service = None
            self.current_run_id = None

        # Event queue for streaming
        self._event_queue: queue.Queue = queue.Queue(maxsize=1000)
        self._shutdown_flag = threading.Event()

        # Track latest timestamp
        self._latest_timestamp: Optional[datetime] = None

        # Reconnection configuration
        self._max_reconnect_attempts = int(
            config.extra_config.get("max_reconnect_attempts", 10)
        )
        self._reconnect_backoff_base = float(
            config.extra_config.get("reconnect_backoff_base", 1.0)
        )
        self._reconnect_backoff_max = float(
            config.extra_config.get("reconnect_backoff_max", 60.0)
        )
        self._reconnect_attempts = 0
        self._reconnect_enabled = config.extra_config.get("auto_reconnect", True)

        # Connection state management
        if ConnectionStateManager is not None:
            self._state_manager = ConnectionStateManager(symbol)
        else:
            self._state_manager = None

    def connect(self) -> bool:
        """
        Establish connection to MT5 data source with retry logic

        :return: True if connection successful, False otherwise
        """
        if self.is_connected():
            return True

        if self._state_manager and ConnectionState is not None:
            self._state_manager.transition_to(
                ConnectionState.CONNECTING, reason="Connection attempt"
            )

        attempt = 0
        while attempt < self._max_reconnect_attempts:
            try:
                # If streamer not provided, create one
                if self.streamer is None:
                    from database import Database

                    db = Database()

                    self.streamer = MT5TickStreamer(
                        sock=self.socket,
                        asset=self.currency_pair,
                        stop_char="\n",
                        verbose=False,
                        console_lock=None,
                        db=db,
                    )

                # Start streamer thread
                self._streamer_thread = threading.Thread(
                    target=self._stream_worker, daemon=True
                )
                self._streamer_thread.start()

                self._is_connected = True
                self._reconnect_attempts = 0

                if self._state_manager and ConnectionState is not None:
                    self._state_manager.transition_to(
                        ConnectionState.CONNECTED, reason="Connection successful"
                    )

                self.logger.info(f"Connected to MT5 tick stream for {self.symbol}")
                return True

            except Exception as e:
                attempt += 1
                self._reconnect_attempts = attempt

                if self._state_manager and ConnectionState is not None:
                    if attempt < self._max_reconnect_attempts:
                        self._state_manager.transition_to(
                            ConnectionState.RECONNECTING,
                            reason=f"Connection failed: {e}, retrying",
                        )
                    else:
                        self._state_manager.transition_to(
                            ConnectionState.FAILED,
                            reason=f"Max reconnection attempts reached: {e}",
                        )

                if attempt < self._max_reconnect_attempts:
                    # Calculate backoff delay
                    backoff = min(
                        self._reconnect_backoff_base * (2 ** (attempt - 1)),
                        self._reconnect_backoff_max,
                    )
                    self.logger.warning(
                        f"Connection attempt {attempt}/{self._max_reconnect_attempts} "
                        f"failed for {self.symbol}: {e}. Retrying in {backoff:.1f}s"
                    )
                    import time

                    time.sleep(backoff)
                else:
                    self.logger.error(
                        f"Failed to connect to MT5 after {attempt} attempts: {e}",
                        exc_info=True,
                    )
                    self._is_connected = False
                    return False

        return False

    def disconnect(self) -> None:
        """Close connection to MT5 data source"""
        if not self.is_connected():
            return

        self._shutdown_flag.set()
        self._is_connected = False

        # Wait for streamer thread to finish (with timeout)
        if self._streamer_thread and self._streamer_thread.is_alive():
            self._streamer_thread.join(timeout=5.0)

        self.logger.info(f"Disconnected from MT5 tick stream for {self.symbol}")

    def is_connected(self) -> bool:
        """Check if connector is currently connected"""
        return self._is_connected and not self._shutdown_flag.is_set()

    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """
        Stream normalized MT5 ticks in real-time

        :param start_time: Optional start time (ignored for real-time streaming)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to MT5 data source")

        # Start lineage run
        run_id = None
        if self.lineage_service:
            try:
                job_name = f"mt5_tick_collection_{self.symbol}"
                run_id = self.lineage_service.start_run(
                    job_name=job_name,
                    namespace="trading_data",
                    inputs=[],  # No inputs for source connectors
                    metadata={
                        "symbol": self.symbol,
                        "source": "mt5",
                        "data_type": "tick",
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

            # Emit output dataset and complete lineage run
            if self.lineage_service and run_id:
                try:
                    dataset_name = f"ticks_forex_{self.symbol}"
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
        Fetch historical ticks from database

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
                job_name = f"mt5_tick_batch_{self.symbol}"
                run_id = self.lineage_service.start_run(
                    job_name=job_name,
                    namespace="trading_data",
                    inputs=[],  # No inputs for source connectors
                    metadata={
                        "symbol": self.symbol,
                        "source": "mt5",
                        "data_type": "tick",
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

            # Use existing get_recent_ticks method (limited by hours)
            # Note: This is a simplified implementation - a full implementation
            # would query with specific start/end times
            ticks = db.get_recent_ticks(
                symbol=self.symbol,
                limit=self.config.batch_size * 10,  # Get more than batch size
                hours=hours,
            )

            # Filter ticks by time range and normalize
            for tick in ticks:
                tick_datetime = tick.get("datetime")
                if not tick_datetime:
                    continue

                # Convert to datetime if string
                if isinstance(tick_datetime, str):
                    from datetime import datetime

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
                # Note: get_recent_ticks returns mid_price, so we'll estimate bid/ask
                mid_price = tick.get("mid_price", 0.0)
                spread = 0.0001  # Default spread (1 pip)
                raw_event = {
                    "symbol": self.symbol,
                    "datetime": tick_datetime,
                    "ask": mid_price + spread / 2,
                    "bid": mid_price - spread / 2,
                }

                # Normalize
                normalized = self.normalizer.normalize(raw_event, source="mt5")

                # Validate
                if self.normalizer.validate(normalized):
                    event_count += 1
                    yield normalized

            # Emit output dataset and complete lineage run
            if self.lineage_service and run_id:
                try:
                    dataset_name = f"ticks_forex_{self.symbol}"
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
        Return MT5 tick schema definition

        :return: Schema dictionary
        """
        return {
            "source": "mt5",
            "data_type": "tick",
            "fields": {
                "symbol": "string",
                "timestamp": "datetime (UTC)",
                "bid": "float",
                "ask": "float",
            },
            "required_fields": ["symbol", "timestamp", "bid", "ask"],
        }

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data

        :return: Datetime of most recent tick, or None if no data
        """
        return self._latest_timestamp

    def backfill(
        self, start_time: datetime, end_time: datetime, batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical tick data directly from MT5 API using MetaTrader5 Python API.

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :param batch_size: Number of records per batch (for rate limiting)
        :return: Iterator of normalized event dictionaries
        :raises ValueError: If start_time >= end_time
        :raises ConnectionError: If MT5 connection fails
        """
        if start_time >= end_time:
            raise ValueError("start_time must be < end_time")

        # Start lineage run
        run_id = None
        if self.lineage_service:
            try:
                job_name = f"mt5_tick_backfill_{self.symbol}"
                run_id = self.lineage_service.start_run(
                    job_name=job_name,
                    namespace="trading_data",
                    inputs=[],  # No inputs for source connectors
                    metadata={
                        "symbol": self.symbol,
                        "source": "mt5",
                        "data_type": "tick",
                        "mode": "backfill",
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "batch_size": batch_size,
                    },
                )
                self.current_run_id = run_id
            except Exception as e:
                self.logger.warning(f"Failed to start lineage run: {e}")

        event_count = 0
        try:
            import MetaTrader5 as mt5

            # Initialize MT5 if not already initialized
            if not mt5.initialize():
                raise ConnectionError(f"Failed to initialize MT5: {mt5.last_error()}")

            # Ensure times are timezone-aware (UTC)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            # Process in daily batches to avoid memory issues
            current_start = start_time
            rate_limit_delay = 0.1  # 0.1s delay between batches

            while current_start < end_time:
                # Calculate batch end (one day or until end_time)
                batch_end = min(current_start + timedelta(days=1), end_time)

                # Convert to MT5 timestamp format (Unix timestamp)
                from_time = int(current_start.timestamp())
                to_time = int(batch_end.timestamp())

                # Fetch ticks from MT5
                ticks = mt5.copy_ticks_range(
                    self.symbol, from_time, to_time, mt5.COPY_TICKS_ALL
                )

                if ticks is None or len(ticks) == 0:
                    self.logger.debug(
                        f"No ticks found for {self.symbol} from {current_start} to {batch_end}"
                    )
                    current_start = batch_end
                    time.sleep(rate_limit_delay)
                    continue

                # Process and normalize ticks
                for tick in ticks:
                    # Convert MT5 tick to raw event format
                    # MT5 tick structure: (time, bid, ask, last, volume, time_msc, flags, volume_real)
                    tick_time = datetime.fromtimestamp(tick[0], tz=timezone.utc)
                    bid = float(tick[1])
                    ask = float(tick[2])
                    volume = float(tick[4]) if len(tick) > 4 else 0.0

                    raw_event = {
                        "symbol": self.symbol,
                        "datetime": tick_time,
                        "bid": bid,
                        "ask": ask,
                        "volume": volume,
                    }

                    # Normalize
                    normalized = self.normalizer.normalize(raw_event, source="mt5")

                    # Validate
                    if self.normalizer.validate(normalized):
                        event_count += 1
                        yield normalized

                # Move to next batch
                current_start = batch_end
                time.sleep(rate_limit_delay)

            # Emit output dataset and complete lineage run
            if self.lineage_service and run_id:
                try:
                    dataset_name = f"ticks_forex_{self.symbol}"
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

        except ImportError:
            if self.lineage_service and run_id:
                try:
                    self.lineage_service.fail_run(
                        run_id, "MetaTrader5 Python package not installed"
                    )
                except Exception:
                    pass
            raise ConnectionError(
                "MetaTrader5 Python package not installed. Install with: pip install MetaTrader5"
            )
        except Exception as e:
            # Fail lineage run on error
            if self.lineage_service and run_id:
                try:
                    self.lineage_service.fail_run(run_id, str(e))
                except Exception as lineage_error:
                    self.logger.warning(f"Failed to fail lineage run: {lineage_error}")
            self.logger.error(f"Error in MT5 backfill: {e}", exc_info=True)
            raise ConnectionError(f"MT5 backfill failed: {e}")

    def get_available_range(self) -> Tuple[datetime, datetime]:
        """
        Get the available data range from MT5 for this symbol.

        :return: Tuple of (earliest_available_time, latest_available_time)
        :raises ConnectionError: If MT5 connection fails
        """
        try:
            import MetaTrader5 as mt5

            # Initialize MT5 if not already initialized
            if not mt5.initialize():
                raise ConnectionError(f"Failed to initialize MT5: {mt5.last_error()}")

            # Get symbol info
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                raise ConnectionError(f"Symbol {self.symbol} not found in MT5")

            # Get historical data range
            # MT5 doesn't provide direct range query, so we'll use a heuristic:
            # Try to get the earliest and latest available ticks
            # For now, return a reasonable default range (5 years back to now)
            now = datetime.now(timezone.utc)
            earliest = now - timedelta(days=5 * 365)  # 5 years back

            # Try to get actual range by querying a small sample
            # This is a best-effort approach
            try:
                # Try to get oldest available tick
                test_start = int((now - timedelta(days=365 * 5)).timestamp())
                test_end = int(now.timestamp())
                test_ticks = mt5.copy_ticks_range(
                    self.symbol, test_start, test_end, mt5.COPY_TICKS_ALL
                )

                if test_ticks is not None and len(test_ticks) > 0:
                    # Get first tick timestamp
                    first_tick_time = datetime.fromtimestamp(
                        test_ticks[0][0], tz=timezone.utc
                    )
                    earliest = first_tick_time
            except Exception:
                # If we can't determine, use default
                pass

            return (earliest, now)

        except ImportError:
            raise ConnectionError(
                "MetaTrader5 Python package not installed. Install with: pip install MetaTrader5"
            )
        except Exception as e:
            self.logger.error(f"Error getting MT5 available range: {e}", exc_info=True)
            raise ConnectionError(f"Failed to get MT5 available range: {e}")

    def _stream_worker(self) -> None:
        """
        Worker thread that receives ticks from streamer and normalizes them
        Handles reconnection on connection loss
        """
        if self.streamer is None:
            return

        self.logger.info("Stream worker started")

        while not self._shutdown_flag.is_set():
            try:
                # Start receiving ticks
                # Note: receive_tick() will block until connection is lost
                if self.streamer:
                    self.streamer.receive_tick()

                # If we get here, connection was lost
                if self._shutdown_flag.is_set():
                    break

                # Attempt reconnection if enabled
                if self._reconnect_enabled and not self._shutdown_flag.is_set():
                    if self._state_manager and ConnectionState is not None:
                        self._state_manager.transition_to(
                            ConnectionState.RECONNECTING,
                            reason="Connection lost, attempting reconnection",
                        )

                    self.logger.warning(
                        f"Connection lost for {self.symbol}, attempting reconnection..."
                    )
                    self._is_connected = False

                    # Attempt to reconnect
                    if self.connect():
                        self.logger.info(
                            f"Reconnected to MT5 tick stream for {self.symbol}"
                        )
                        continue
                    else:
                        self.logger.error(
                            f"Failed to reconnect to MT5 tick stream for {self.symbol}"
                        )
                        break
                else:
                    # Reconnection disabled or shutdown requested
                    break

            except Exception as e:
                self.logger.error(f"Error in stream worker: {e}", exc_info=True)

                # Attempt reconnection on error if enabled
                if (
                    self._reconnect_enabled
                    and not self._shutdown_flag.is_set()
                    and self._reconnect_attempts < self._max_reconnect_attempts
                ):
                    if self._state_manager and ConnectionState is not None:
                        self._state_manager.transition_to(
                            ConnectionState.RECONNECTING,
                            reason=f"Error in stream worker: {e}",
                        )

                    self.logger.warning(
                        f"Error in stream worker for {self.symbol}, attempting reconnection..."
                    )
                    self._is_connected = False

                    if self.connect():
                        self.logger.info(
                            f"Reconnected to MT5 tick stream for {self.symbol} after error"
                        )
                        continue
                    else:
                        break
                else:
                    break

        self.logger.info("Stream worker stopped")

    def _on_tick_received(self, raw_tick: Dict[str, Any]) -> None:
        """
        Callback for when a raw tick is received
        Normalizes the tick and adds it to the event queue

        :param raw_tick: Raw tick dictionary
        """
        try:
            # Normalize tick
            normalized = self.normalizer.normalize(raw_tick, source="mt5")

            # Validate
            if self.normalizer.validate(normalized):
                # Update latest timestamp
                self._latest_timestamp = normalized.get("timestamp")

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
                self.logger.warning("Normalized tick failed validation")

        except Exception as e:
            self.logger.error(f"Error processing tick: {e}", exc_info=True)
