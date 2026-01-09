"""
MT5 tick connector implementing IDataSourceConnector
Wraps MT5TickStreamer and adds normalization
"""

import threading
import queue
from typing import Dict, Any, Iterator, Optional
from datetime import datetime
from utils.logging_config import get_logger
from events.normalizer import EventNormalizer
from .base import IDataSourceConnector, ConnectorConfig
from mt5_connection.tick_streamer import MT5TickStreamer
from models.currency_pair import CurrencyPair


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
        try:
            from mt5_connection.connection_state import (
                ConnectionStateManager,
                ConnectionState,
            )

            self._state_manager = ConnectionStateManager(symbol)
        except ImportError:
            self._state_manager = None

    def connect(self) -> bool:
        """
        Establish connection to MT5 data source with retry logic

        :return: True if connection successful, False otherwise
        """
        if self.is_connected():
            return True

        if self._state_manager:
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

                if self._state_manager:
                    self._state_manager.transition_to(
                        ConnectionState.CONNECTED, reason="Connection successful"
                    )

                self.logger.info(f"Connected to MT5 tick stream for {self.symbol}")
                return True

            except Exception as e:
                attempt += 1
                self._reconnect_attempts = attempt

                if self._state_manager:
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

        # Stream events from queue
        while not self._shutdown_flag.is_set():
            try:
                # Get event from queue with timeout
                event = self._event_queue.get(timeout=1.0)
                if event is None:  # Shutdown signal
                    break

                yield event
                self._event_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error streaming event: {e}", exc_info=True)
                continue

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

        # Query database for historical ticks
        from database import Database

        db = Database()

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
                    yield normalized

        except Exception as e:
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
                    if self._state_manager:
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
                        self.logger.info(f"Reconnected to MT5 tick stream for {self.symbol}")
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
                    if self._state_manager:
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
