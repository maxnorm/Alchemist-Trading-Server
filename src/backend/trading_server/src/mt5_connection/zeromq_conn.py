import asyncio
import json
from typing import Literal, Optional

import zmq


class ZeroMQConnection:
    """
    ZeroMQ connection wrapper for MT5 communication.
    Supports REQ for trading and SUB for streaming.
    """

    def __init__(
        self,
        zmq_socket,
        socket_type: Literal["REQ", "SUB", "PUB"],
        timeout: float = 30.0,
        subscription_symbol: Optional[str] = None,
    ):
        self._socket = zmq_socket
        self._socket_type = socket_type
        self._timeout = timeout
        self._last_send_ts: Optional[float] = None
        self._last_recv_ts: Optional[float] = None
        self._subscription_symbol = subscription_symbol  # Store for topic comparison

        # Set socket options
        self._socket.setsockopt(zmq.LINGER, 1000)
        self._socket.setsockopt(zmq.SNDTIMEO, int(timeout * 1000))
        self._socket.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))

    def send_msg(self, msg: dict):
        """
        Send JSON message via ZeroMQ.
        For PUB, send multipart with topic as symbol.
        """
        import time

        self._last_send_ts = time.time()

        try:
            if self._socket_type == "REQ":
                self._socket.send_json(msg, zmq.NOBLOCK)
            elif self._socket_type == "PUB":
                topic = msg.get("symbol", "tick").encode()
                self._socket.send_multipart(
                    [topic, json.dumps(msg).encode()], zmq.NOBLOCK
                )
            else:
                raise ValueError(
                    f"Unsupported socket type for send: {self._socket_type}"
                )
        except zmq.Again:
            raise TimeoutError(f"Timeout sending message after {self._timeout}s")
        except Exception as exc:
            raise ConnectionError(f"Error sending ZeroMQ message: {exc}")

    async def get_response(self, timeout: Optional[float] = None) -> dict:
        """
        Get JSON response via ZeroMQ.
        """
        response_timeout = timeout or self._timeout

        try:
            if self._socket_type == "REQ":
                response = await asyncio.wait_for(
                    self._receive_req_response(), timeout=response_timeout
                )
            elif self._socket_type == "SUB":
                response = await asyncio.wait_for(
                    self._receive_sub_message(), timeout=response_timeout
                )
            else:
                raise ValueError(
                    f"Unsupported socket type for receive: {self._socket_type}"
                )

            import time

            self._last_recv_ts = time.time()
            return response
        except TimeoutError:
            # Re-raise TimeoutError from receive methods (for tick_processor.py compatibility)
            raise
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Timeout waiting for response after {response_timeout}s"
            )
        except Exception as exc:
            raise ConnectionError(f"Error receiving ZeroMQ message: {exc}")

    async def _receive_req_response(self) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._socket.recv_json, zmq.NOBLOCK)

    async def _receive_sub_message(self) -> dict:
        """
        Receive message from SUB socket with subscription filter.
        
        Uses blocking receive (respects RCVTIMEO socket option).
        When subscribing to a specific topic, ZeroMQ filters messages at the
        socket level. recv_multipart() returns complete multipart messages
        atomically when the subscription filter matches.
        
        Important: Use blocking receive (no NOBLOCK) to ensure complete
        multipart messages are received. The RCVTIMEO socket option handles
        timeouts automatically.
        """
        try:
            # Get or create event loop for this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in current thread, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Use blocking receive - RCVTIMEO socket option handles timeout
            # This ensures we receive complete multipart messages atomically
            parts = await loop.run_in_executor(
                None, self._socket.recv_multipart
            )
            
            # Handle multipart messages: [topic, message]
            if len(parts) == 2:
                topic_bytes, message_bytes = parts
                topic = topic_bytes.decode('utf-8', errors='ignore')
                
                # Log topic for debugging (first few messages only)
                # This helps verify subscription filter is working
                import logging
                logger = logging.getLogger("zeromq_conn")
                if not hasattr(self, '_message_count'):
                    self._message_count = 0
                self._message_count += 1
                # ALWAYS log first 20 messages to diagnose reception issues
                if self._message_count <= 20:
                    logger.info(f"✓ ZeroMQ SUB socket received message #{self._message_count} with topic: '{topic}'")
                elif self._message_count <= 100:
                    logger.debug(f"Received message #{self._message_count} with topic: '{topic}'")
                elif self._message_count % 100 == 0:
                    logger.debug(f"Received message #{self._message_count} with topic: '{topic}'")
                
                # Validate message is not empty
                if not message_bytes or len(message_bytes) == 0:
                    raise TimeoutError("Received empty message part")
                
                message_str = message_bytes.decode('utf-8', errors='ignore')
                if not message_str or message_str.strip() == '':
                    raise TimeoutError("Received whitespace-only message")
                
                try:
                    return json.loads(message_str)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in message: {e}") from e
                    
            elif len(parts) == 1:
                # Single part - might be topic only (shouldn't happen with proper subscription)
                part_str = parts[0].decode('utf-8', errors='ignore')
                
                # If it looks like a topic (short string, not JSON), this is an error
                if len(part_str) < 20 and not part_str.strip().startswith('{'):
                    raise TimeoutError(
                        f"Received incomplete multipart message (topic only: '{part_str}'). "
                        f"This may indicate a ZeroMQ subscription timing issue."
                    )
                # Otherwise try to parse as JSON
                try:
                    return json.loads(part_str)
                except json.JSONDecodeError as e:
                    raise TimeoutError(f"Single-part message is not valid JSON: {e}")
            else:
                raise ValueError(f"Unexpected multipart format: {len(parts)} parts")
                
        except zmq.Again:
            # This should not happen with blocking receive, but handle it
            raise TimeoutError("No message available (socket timeout)")
        except TimeoutError:
            # Re-raise TimeoutError for tick_processor.py compatibility
            raise
        except (ValueError, json.JSONDecodeError) as exc:
            # Convert to ConnectionError for other error handling paths
            raise ConnectionError(f"Malformed ZeroMQ message: {exc}") from exc

    def is_alive(self) -> bool:
        """Check if socket is connected."""
        return not self._socket.closed

    def last_recv_ts(self):
        return self._last_recv_ts

    def last_send_ts(self):
        return self._last_send_ts
