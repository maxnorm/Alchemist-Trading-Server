"""
ZeroMQ Broker for Multi-Symbol Tick Streaming

Routes messages from multiple EA streamers (PUSH) to a single PUB socket,
allowing multiple symbols to share the same port.
"""

import json
import threading
import time
from typing import Optional

import zmq

from utils.logging_config import get_logger


class ZeroMQBroker:
    """
    ZeroMQ broker that forwards messages from EA streamers (PUSH) to subscribers (PUB).

    Architecture:
    - EAs connect via PUSH sockets to broker_port (default: 5557)
    - Broker republishes via PUB socket on tick_port (default: 5555)
    - Python subscribers connect via SUB sockets to tick_port
    - Broker extracts symbol from message JSON and uses it as the topic
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        broker_port: int = 5557,
        tick_port: int = 5555,
        verbose: bool = False,
    ):
        """
        Initialize ZeroMQ broker.

        :param host: Host address for sockets
        :param broker_port: Port for PULL socket (EAs connect here)
        :param tick_port: Port for PUB socket (Python subscribers connect here)
        :param verbose: Enable verbose logging
        """
        self.host = host
        self.broker_port = broker_port
        self.tick_port = tick_port
        self.verbose = verbose
        self._logger = get_logger("zeromq_broker", "zeromq_broker.log")

        self.context = zmq.Context()
        self._pull_socket: Optional[zmq.Socket] = None
        self._pub_socket: Optional[zmq.Socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.RLock()

        # Statistics
        self._messages_forwarded = 0
        self._errors = 0
        self._start_time: Optional[float] = None

    def start(self):
        """Start the broker in a background thread."""
        with self._lock:
            if self._running:
                self._logger.warning("Broker is already running")
                return

            try:
                # Create PULL socket to receive from EAs
                self._pull_socket = self.context.socket(zmq.PULL)
                pull_endpoint = f"tcp://*:{self.broker_port}"
                try:
                    self._pull_socket.bind(pull_endpoint)
                    self._logger.debug(
                        f"✓ PULL socket successfully bound to {pull_endpoint}"
                    )
                except Exception as e:
                    self._logger.error(
                        f"✗ Failed to bind PULL socket to {pull_endpoint}: {e}",
                        exc_info=True,
                    )
                    raise

                # Create PUB socket to publish to subscribers
                self._pub_socket = self.context.socket(zmq.PUB)
                pub_endpoint = f"tcp://*:{self.tick_port}"
                try:
                    self._pub_socket.bind(pub_endpoint)
                    self._logger.debug(
                        f"✓ PUB socket successfully bound to {pub_endpoint}"
                    )
                except Exception as e:
                    self._logger.error(
                        f"✗ Failed to bind PUB socket to {pub_endpoint}: {e}",
                        exc_info=True,
                    )
                    raise

                # ZeroMQ PUB/SUB "slow joiner" fix: small delay after binding
                # This ensures the socket is fully ready before receiving messages
                time.sleep(0.1)

                # Verify sockets are actually listening
                try:
                    # Get the actual bound address (ZeroMQ returns the actual interface)
                    pull_bound = (
                        self._pull_socket.getsockopt_string(zmq.LAST_ENDPOINT)
                        if hasattr(zmq, "LAST_ENDPOINT")
                        else pull_endpoint
                    )
                    pub_bound = (
                        self._pub_socket.getsockopt_string(zmq.LAST_ENDPOINT)
                        if hasattr(zmq, "LAST_ENDPOINT")
                        else pub_endpoint
                    )
                    self._logger.debug(f"PULL socket bound address: {pull_bound}")
                    self._logger.debug(f"PUB socket bound address: {pub_bound}")
                except Exception as e:
                    self._logger.warning(f"Could not get bound addresses: {e}")

                self._running = True
                self._start_time = time.time()

                # Start forwarding thread
                self._thread = threading.Thread(target=self._forward_loop, daemon=True)
                self._thread.start()

                self._logger.info(
                    f"ZeroMQ broker started: PULL={pull_endpoint}, PUB={pub_endpoint}. "
                    f"EAs connect to: tcp://{self.host}:{self.broker_port}, "
                    f"Subscribers connect to: tcp://{self.host}:{self.tick_port}"
                )
                if self.verbose:
                    print(
                        f"ZeroMQ broker started on ports {self.broker_port} (PULL) -> {self.tick_port} (PUB)"
                    )
                    print(
                        f"EAs should connect to: tcp://{self.host}:{self.broker_port}"
                    )
                    print(
                        f"Subscribers should connect to: tcp://{self.host}:{self.tick_port}"
                    )

            except Exception as e:
                self._running = False
                self._logger.error(f"Failed to start broker: {e}", exc_info=True)
                raise

    def stop(self):
        """Stop the broker and cleanup sockets."""
        with self._lock:
            if not self._running:
                return

            self._running = False

            # Close sockets
            if self._pull_socket:
                try:
                    self._pull_socket.close()
                except Exception as e:
                    self._logger.warning(f"Error closing PULL socket: {e}")

            if self._pub_socket:
                try:
                    self._pub_socket.close()
                except Exception as e:
                    self._logger.warning(f"Error closing PUB socket: {e}")

            # Wait for thread to finish (with timeout)
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
                if self._thread.is_alive():
                    self._logger.warning("Broker thread did not stop within timeout")

            # Terminate context
            try:
                self.context.term()
            except Exception as e:
                self._logger.warning(f"Error terminating context: {e}")

            runtime = time.time() - self._start_time if self._start_time else 0
            self._logger.info(
                f"ZeroMQ broker stopped. Runtime: {runtime:.1f}s, "
                f"Messages forwarded: {self._messages_forwarded}, Errors: {self._errors}"
            )

            if self.verbose:
                print(
                    f"ZeroMQ broker stopped. "
                    f"Messages forwarded: {self._messages_forwarded}, Errors: {self._errors}"
                )

    def _forward_loop(self):
        """Main forwarding loop running in background thread."""
        poller = zmq.Poller()
        poller.register(self._pull_socket, zmq.POLLIN)

        self._logger.debug("Broker forwarding loop started")
        self._logger.debug(
            f"PULL socket bound to tcp://*:{self.broker_port}, waiting for EA connections..."
        )

        # Periodic stats logging
        last_stats_log = time.time()
        stats_interval = 300.0  # Log stats every 5 minutes (only when meaningful)

        # Diagnostic: Log when poller detects activity
        last_poll_log = time.time()
        poll_log_interval = 300.0  # Log poll status every 5 minutes if no messages

        while self._running:
            try:
                # Poll with timeout to allow checking _running flag
                socks = dict(poller.poll(timeout=100))  # 100ms timeout

                # Diagnostic logging: Log if poller is working but no messages
                now = time.time()
                if now - last_poll_log >= poll_log_interval:
                    if self._messages_forwarded == 0:
                        self._logger.warning(
                            f"Broker PULL socket polling active but no messages received in {poll_log_interval:.0f}s. "
                            f"Check if EA is connected and sending ticks. "
                            f"EA should connect PUSH socket to: tcp://127.0.0.1:{self.broker_port}"
                        )
                    last_poll_log = now

                if (
                    self._pull_socket in socks
                    and socks[self._pull_socket] == zmq.POLLIN
                ):
                    # Receive message from EA
                    try:
                        # EAs may send multipart (topic + message) or single part (just message)
                        # We'll handle both cases
                        # Use blocking receive since POLLIN confirmed data is available
                        parts = self._pull_socket.recv_multipart()

                        # Log that we received a message (first few only)
                        if self._messages_forwarded < 5:
                            self._logger.debug(
                                f"✓ Received message from EA ({len(parts)} parts)"
                            )
                            # Log raw message preview for debugging
                            if len(parts) > 0:
                                preview = (
                                    parts[-1][:200]
                                    if len(parts[-1]) > 200
                                    else parts[-1]
                                )
                                self._logger.debug(f"Message preview: {preview}")

                        # Extract message payload (last part)
                        if len(parts) == 0:
                            continue

                        # If multipart, use last part as message; if single part, use it directly
                        message_bytes = parts[-1] if len(parts) > 1 else parts[0]

                        # Extract symbol from JSON message
                        try:
                            message_str = message_bytes.decode("utf-8", errors="ignore")
                            message_json = json.loads(message_str)
                            symbol = message_json.get("symbol", "UNKNOWN")

                            # Republish with symbol as topic (multipart: [topic, message])
                            topic_bytes = symbol.encode("utf-8")
                            try:
                                self._pub_socket.send_multipart(
                                    [topic_bytes, message_bytes], zmq.NOBLOCK
                                )
                                self._messages_forwarded += 1
                            except zmq.Again:
                                # PUB socket buffer full - this is normal under high load
                                # Log only occasionally to avoid spam
                                if self._errors % 100 == 0 or self._errors < 5:
                                    self._logger.warning(
                                        f"PUB socket buffer full "
                                        f"(message {self._messages_forwarded}, error #{self._errors})"
                                    )
                                self._errors += 1
                                continue

                            # Log first few messages and then periodically
                            if (
                                self._messages_forwarded <= 10
                                or self._messages_forwarded % 100 == 0
                            ):
                                self._logger.debug(
                                    f"Forwarded message for symbol: {symbol} "
                                    f"(total: {self._messages_forwarded})"
                                )

                        except json.JSONDecodeError as e:
                            self._errors += 1
                            self._logger.warning(
                                f"Failed to parse message JSON: {e}. "
                                f"Message preview: {message_bytes[:100] if len(message_bytes) > 100 else message_bytes}"
                            )
                        except KeyError:
                            self._errors += 1
                            self._logger.warning(
                                f"Message missing 'symbol' field. "
                                f"Message preview: {message_bytes[:100] if len(message_bytes) > 100 else message_bytes}"
                            )
                    except zmq.Again:
                        # No message available (shouldn't happen after POLLIN, but handle gracefully)
                        continue
                    except Exception as e:
                        self._errors += 1
                        self._logger.error(
                            f"Error forwarding message: {e}", exc_info=True
                        )

            except Exception as e:
                if self._running:  # Only log if we're supposed to be running
                    self._errors += 1
                    self._logger.error(f"Error in forwarding loop: {e}", exc_info=True)
                # Small delay before retrying
                time.sleep(0.01)

            # Periodic stats logging (only when meaningful: activity, errors, or diagnostics)
            now = time.time()
            if now - last_stats_log >= stats_interval:
                with self._lock:
                    stats = self.get_stats()
                    # Only log stats if there's activity, errors, or diagnostic conditions
                    if (
                        stats["messages_forwarded"] > 0
                        or stats["errors"] > 0
                        or (
                            stats["messages_forwarded"] == 0
                            and stats["runtime_seconds"] > 120
                        )
                    ):
                        self._logger.info(
                            f"Broker stats: {stats['messages_forwarded']} messages forwarded, "
                            f"{stats['errors']} errors, "
                            f"{stats['messages_per_second']:.2f} msg/s"
                        )
                    # Diagnostic: If no messages after 2 minutes, provide troubleshooting info
                    if (
                        stats["messages_forwarded"] == 0
                        and stats["runtime_seconds"] > 120
                    ):
                        self._logger.warning(
                            f"⚠️  No messages received from EA after {stats['runtime_seconds']:.0f} seconds. "
                            f"Troubleshooting:\n"
                            f"  1. Verify EA is running and connected to tcp://127.0.0.1:{self.broker_port}\n"
                            f"  2. Check EA logs for OnTick() calls or errors\n"
                            f"  3. Verify market is open and symbol has price updates\n"
                            f"  4. Check EA debug_logging is enabled to see tick processing\n"
                            f"  5. Verify EA's broker_host setting matches this server"
                        )
                last_stats_log = now

        self._logger.info("Broker forwarding loop stopped")

    def is_running(self) -> bool:
        """Check if broker is running."""
        with self._lock:
            return self._running

    def get_stats(self) -> dict:
        """Get broker statistics."""
        with self._lock:
            runtime = time.time() - self._start_time if self._start_time else 0
            return {
                "running": self._running,
                "messages_forwarded": self._messages_forwarded,
                "errors": self._errors,
                "runtime_seconds": runtime,
                "messages_per_second": (
                    self._messages_forwarded / runtime if runtime > 0 else 0
                ),
            }

    def log_status(self):
        """Log current broker status for debugging."""
        with self._lock:
            stats = self.get_stats()
            self._logger.info(
                f"Broker status: running={self._running}, "
                f"messages_forwarded={stats['messages_forwarded']}, "
                f"errors={stats['errors']}, "
                f"runtime={stats['runtime_seconds']:.1f}s"
            )
            if self._pull_socket:
                try:
                    # Check if PULL socket is bound
                    self._logger.info(
                        f"PULL socket: bound to tcp://*:{self.broker_port}"
                    )
                except Exception as e:
                    self._logger.warning(f"PULL socket check failed: {e}")
            if self._pub_socket:
                try:
                    # Check if PUB socket is bound
                    self._logger.info(f"PUB socket: bound to tcp://*:{self.tick_port}")
                except Exception as e:
                    self._logger.warning(f"PUB socket check failed: {e}")
