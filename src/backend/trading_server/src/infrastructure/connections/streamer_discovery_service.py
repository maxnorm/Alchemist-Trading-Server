"""
Streamer Discovery Service
Automatically discovers and registers tick streamers when they connect via ZeroMQ.
"""
import os
import json
import threading
import time
from typing import Dict, Optional, Set

import zmq

from utils.logging_config import get_logger
from models.currency_pair import CurrencyPair


class StreamerDiscoveryService:
    """
    Auto-discovers and registers tick streamers when they start publishing.
    
    Discovery service subscribes to all topics and consumes ALL messages from the broker.
    For registered symbols, it forwards ticks to streamers via queues.
    For unregistered symbols, it processes ticks to auto-register new streamers.
    
    This architecture ensures:
    - No message loss (discovery forwards all ticks)
    - Auto-registration works for all symbols (discovery never stops)
    - Streamers receive all their ticks via queues (no SUB sockets needed)
    """

    def __init__(
        self,
        zmq_manager,
        database,
        host: str = "127.0.0.1",
        tick_port: int = 5555,
        timeout: float = 0.1,  # 100ms polling timeout
        verbose: bool = False,
        server=None,  # Optional server reference for connector registration
    ):
        """
        Initialize streamer discovery service.
        
        :param zmq_manager: ZeroMQConnectionManager instance
        :param database: Database instance
        :param host: ZeroMQ host
        :param tick_port: ZeroMQ tick port
        :param timeout: Polling timeout in seconds
        :param verbose: Enable verbose logging
        :param server: Optional Server instance for connector registration
        """
        self._zmq_manager = zmq_manager
        self._database = database
        self._host = host
        self._tick_port = tick_port
        self._timeout = timeout
        self._verbose = verbose
        self._server = server  # Server reference for connector registration
        
        self._logger = get_logger("streamer_discovery", "streamer_discovery.log")
        
        # Track registered streamers by symbol
        self._registered_streamers: Dict[str, Dict] = {}  # symbol -> {streamer, digits, token}
        self._registration_lock = threading.RLock()
        
        # Discovery socket (subscribes to all topics)
        self._context = zmq.Context()
        self._discovery_socket: Optional[zmq.Socket] = None
        
        # Control
        self._running = False
        self._discovery_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Read expected token from environment
        self._expected_token = os.getenv("STREAMER_AUTH_TOKEN")
        if not self._expected_token:
            self._logger.warning(
                "STREAMER_AUTH_TOKEN not set - all streamers will be rejected"
            )

    def start(self):
        """Start the discovery service in a background thread."""
        if self._running:
            self._logger.warning("Discovery service already running")
            return
        
        self._running = True
        self._shutdown_event.clear()
        
        # Create discovery socket - subscribes to all topics to receive all messages
        # Discovery service forwards ticks to registered streamers via queues
        self._discovery_socket = self._context.socket(zmq.SUB)
        self._discovery_socket.setsockopt(zmq.RCVTIMEO, int(self._timeout * 1000))
        self._discovery_socket.connect(f"tcp://{self._host}:{self._tick_port}")
        # Subscribe to all topics - discovery consumes all messages and forwards them
        self._discovery_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # Start discovery thread
        self._discovery_thread = threading.Thread(
            target=self._discover_streamers, daemon=True
        )
        self._discovery_thread.start()
        
        self._logger.info(
            f"Streamer discovery service started on {self._host}:{self._tick_port}"
        )

    def stop(self):
        """Stop the discovery service."""
        if not self._running:
            return
        
        self._running = False
        self._shutdown_event.set()
        
        # Close socket
        if self._discovery_socket:
            try:
                self._discovery_socket.close()
            except Exception:
                pass
            self._discovery_socket = None
        
        # Wait for thread to finish
        if self._discovery_thread and self._discovery_thread.is_alive():
            self._discovery_thread.join(timeout=5.0)
        
        self._logger.info("Streamer discovery service stopped")

    def _discover_streamers(self):
        """Main discovery loop - runs in background thread."""
        self._logger.info("Starting streamer discovery loop")
        
        # Use poller to check for messages without blocking
        poller = zmq.Poller()
        if self._discovery_socket:
            poller.register(self._discovery_socket, zmq.POLLIN)
        
        while self._running and not self._shutdown_event.is_set():
            # Discovery socket should always be open - it never closes
            if not self._discovery_socket:
                self._logger.error("Discovery socket unexpectedly closed - stopping discovery loop")
                break
                
            try:
                # Poll with timeout to check for messages
                socks = dict(poller.poll(timeout=100))  # 100ms timeout
                
                if self._discovery_socket not in socks:
                    # No message available, continue
                    continue
                
                # Receive multipart message: [topic, data]
                parts = self._discovery_socket.recv_multipart(zmq.NOBLOCK)
                
                if len(parts) == 2:
                    topic_bytes, message_bytes = parts
                    topic = topic_bytes.decode('utf-8', errors='ignore')
                    message_str = message_bytes.decode('utf-8', errors='ignore')
                    
                    if not message_str or message_str.strip() == '':
                        continue
                    
                    try:
                        tick_data = json.loads(message_str)
                        symbol = tick_data.get("symbol") or topic
                        
                        # Check if symbol is already registered
                        with self._registration_lock:
                            is_registered = symbol in self._registered_streamers
                            
                            if is_registered:
                                # Forward tick to registered streamer's queue
                                streamer_info = self._registered_streamers[symbol]
                                streamer = streamer_info.get("streamer")
                                if streamer and hasattr(streamer, "put_tick"):
                                    try:
                                        streamer.put_tick(tick_data)
                                        self._logger.debug(
                                            f"Forwarded tick to registered streamer for {symbol}"
                                        )
                                    except Exception as e:
                                        self._logger.warning(
                                            f"Failed to forward tick to {symbol}: {e}"
                                        )
                                else:
                                    self._logger.warning(
                                        f"Registered streamer for {symbol} missing put_tick method"
                                    )
                            else:
                                # Not registered - process for auto-registration
                                self._logger.debug(
                                    f"Discovery service received tick for unregistered {symbol} (topic: {topic})"
                                )
                                self._process_tick_message(tick_data, topic)
                    except json.JSONDecodeError as e:
                        self._logger.warning(f"Failed to parse tick message: {e}")
                        continue
                elif len(parts) == 1:
                    # Single part message (fallback)
                    try:
                        message_str = parts[0].decode('utf-8', errors='ignore')
                        if message_str and message_str.strip():
                            tick_data = json.loads(message_str)
                            self._process_tick_message(tick_data, "")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                        
            except zmq.Again:
                # Timeout - continue polling
                time.sleep(0.01)  # Small sleep to avoid busy-waiting
                continue
            except Exception as e:
                if self._running:
                    self._logger.error(f"Error in discovery loop: {e}", exc_info=True)
                time.sleep(0.1)
        
        self._logger.info("Streamer discovery loop stopped")

    def _process_tick_message(self, tick_data: Dict, topic: str):
        """
        Process a tick message and register streamer if needed.
        
        This method is only called for unregistered symbols. Once registered,
        ticks are forwarded directly via put_tick() in the discovery loop.
        
        :param tick_data: Parsed tick data dictionary
        :param topic: ZeroMQ topic (usually symbol)
        """
        symbol = tick_data.get("symbol") or topic
        if not symbol:
            return
        
        # Validate token first (before acquiring lock)
        token = tick_data.get("token", "")
        if not self._validate_streamer_token(token):
            self._logger.warning(
                f"Invalid streamer token for {symbol} - rejecting connection"
            )
            return
        
        # Double-check not already registered (race condition protection)
        with self._registration_lock:
            if symbol in self._registered_streamers:
                # Already registered - forward this tick and return
                streamer_info = self._registered_streamers[symbol]
                streamer = streamer_info.get("streamer")
                if streamer and hasattr(streamer, "put_tick"):
                    streamer.put_tick(tick_data)
                return
        
        # Extract price data for digit inference
        bid = tick_data.get("bid")
        ask = tick_data.get("ask")
        
        if bid is None or ask is None:
            self._logger.warning(
                f"Tick message missing bid/ask for {symbol} - cannot infer digits"
            )
            return
        
        # Use digits from tick data if available (more accurate), otherwise infer from price
        digits = tick_data.get("digits")
        if digits is None:
            # Infer digits from price format
            digits = self._infer_digits_from_price(bid, ask)
            self._logger.debug(
                f"Inferred digits={digits} for {symbol} from price (bid={bid}, ask={ask})"
            )
        else:
            digits = int(digits)
            self._logger.debug(
                f"Using digits={digits} for {symbol} from tick data"
            )
        
        # Register streamer
        self._auto_register_streamer(symbol, digits, token)
        
        # After registration, forward the tick that triggered registration
        # The streamer's receive_tick() thread will process it from the queue
        with self._registration_lock:
            if symbol in self._registered_streamers:
                streamer_info = self._registered_streamers[symbol]
                streamer = streamer_info.get("streamer")
                
                if streamer and hasattr(streamer, "put_tick"):
                    try:
                        streamer.put_tick(tick_data)
                        self._logger.debug(
                            f"Forwarded initial tick to newly registered {symbol}"
                        )
                    except Exception as e:
                        self._logger.error(
                            f"Error forwarding initial tick for {symbol}: {e}",
                            exc_info=True
                        )

    def _validate_streamer_token(self, received_token: str) -> bool:
        """
        Validate streamer token against environment variable.
        
        :param received_token: Token received from streamer EA
        :return: True if token is valid
        """
        if not self._expected_token:
            return False  # Reject all if token not configured
        
        return received_token == self._expected_token

    def _infer_digits_from_price(self, bid: float, ask: float) -> int:
        """
        Infer digits (decimal precision) from price format.
        
        :param bid: Bid price
        :param ask: Ask price
        :return: Number of decimal digits
        """
        # Try both bid and ask, use the one with more precision
        prices = [bid, ask]
        max_digits = 0  # Start at 0, not 5, to detect actual precision
        
        for price in prices:
            if price is None:
                continue
            
            # Convert to string and count decimal places
            price_str = f"{price:.10f}".rstrip('0')
            if '.' in price_str:
                decimal_part = price_str.split('.')[1]
                digits = len(decimal_part)
                max_digits = max(max_digits, digits)
        
        # If no decimal places detected, default based on price magnitude
        # JPY pairs (high price > 10): typically 2-3 digits
        # Standard pairs (low price < 10): typically 4-5 digits
        if max_digits == 0:
            mid_price = (bid + ask) / 2 if bid and ask else 0
            if mid_price > 10:
                max_digits = 3  # JPY-like pairs default
            else:
                max_digits = 5  # Standard pairs default
        
        # Common cases: 5 digits (EURUSD), 3 digits (USDJPY), 2 digits (XAUUSD)
        # Clamp to reasonable range
        return min(max(max_digits, 2), 10)

    def _auto_register_streamer(self, symbol: str, digits: int, token: str):
        """
        Auto-register a discovered streamer.
        
        :param symbol: Symbol name
        :param digits: Decimal precision
        :param token: Validated token
        """
        with self._registration_lock:
            # Double-check not already registered
            if symbol in self._registered_streamers:
                return
            
            try:
                # Connect streamer via ZeroMQ manager
                streamer = self._zmq_manager.connect_streamer_by_symbol(
                    symbol=symbol,
                    digits=digits,
                    port_offset=0,  # Default port
                    token=token,
                    db=self._database,  # Pass database for tick storage
                )
                
                # Start tick reception in background thread
                import threading
                thread = threading.Thread(
                    target=streamer.receive_tick,
                    daemon=True,
                    name=f"streamer_{symbol}"
                )
                thread.start()
                self._logger.info(
                    f"Started receive_tick thread for {symbol} (thread: {thread.name})"
                )
                # Discovery service continues running and forwarding ticks to this streamer
                # No need to close socket - discovery forwards all ticks via queue
                
                # Store registration info
                self._registered_streamers[symbol] = {
                    "streamer": streamer,
                    "digits": digits,
                    "token": token,
                    "thread": thread,
                    "registered_at": time.time(),
                }
                
                # Create currency pair
                pair = CurrencyPair(symbol, digits)
                
                # Register connector with server if available
                if self._server:
                    try:
                        # Add to server's currency pairs
                        if hasattr(self._server, '_Server__all_currency_pairs'):
                            self._server._Server__all_currency_pairs[symbol] = pair
                        
                        # Create and register price connector
                        from connectors.mt5_price_connector import MT5PriceConnector
                        from connectors.base import ConnectorConfig
                        
                        connector_config = ConnectorConfig(
                            source="mt5",
                            symbol=symbol,
                            extra_config={"digits": digits},
                        )
                        price_connector = MT5PriceConnector(
                            currency_pair=pair,
                            config=connector_config,
                        )
                        price_connector.connect()
                        
                        # Add to server connectors
                        if hasattr(self._server, '_connectors'):
                            self._server._connectors.append(price_connector)
                        
                        # Register in connector registry
                        if hasattr(self._server, '_connector_registry'):
                            connector_name = f"price_{symbol}"
                            self._server._connector_registry.register_connector(
                                connector_name, price_connector
                            )
                            
                            # Sync feature catalog
                            if hasattr(self._server, '_Server__feature_catalog'):
                                try:
                                    self._server._Server__feature_catalog.sync_with_connector_registry(
                                        self._server._connector_registry
                                    )
                                except Exception as e:
                                    self._logger.warning(
                                        f"Failed to sync feature catalog for {symbol}: {e}"
                                    )
                    except Exception as e:
                        self._logger.warning(
                            f"Failed to register connector for {symbol}: {e}"
                        )
                
                self._logger.info(
                    f"Auto-registered streamer for {symbol} "
                    f"(digits: {digits}, token validated)"
                )
                
            except Exception as e:
                self._logger.error(
                    f"Failed to auto-register streamer for {symbol}: {e}",
                    exc_info=True
                )

    def get_registered_streamers(self) -> Dict[str, Dict]:
        """Get all registered streamers."""
        with self._registration_lock:
            return self._registered_streamers.copy()

    def is_registered(self, symbol: str) -> bool:
        """Check if a symbol is already registered."""
        with self._registration_lock:
            return symbol in self._registered_streamers

    def unregister_streamer(self, symbol: str):
        """Unregister a streamer (cleanup)."""
        with self._registration_lock:
            if symbol in self._registered_streamers:
                info = self._registered_streamers[symbol]
                # Cleanup would be handled by zmq_manager
                del self._registered_streamers[symbol]
                self._logger.info(f"Unregistered streamer for {symbol}")
