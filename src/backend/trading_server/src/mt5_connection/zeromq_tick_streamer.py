"""
ZeroMQ-based tick streamer using shared TickProcessor logic.
Queue-based forwarding from discovery service.
"""

import os
import queue
from typing import Dict, Any

from mt5_connection.tick_processor import TickProcessor


class ZeroMQTickStreamer:
    """
    MT5 tick streamer with queue-based forwarding from discovery service.

    Streamers receive ticks via internal queues. The discovery service
    consumes all messages from the broker and forwards them to registered
    streamers via put_tick().

    All streamers are queue-based - no SUB sockets needed.
    """

    def __init__(
        self,
        zmq_conn=None,  # Kept for backward compatibility but must be None
        asset=None,
        stop_char: str = "\n",
        verbose: bool = False,
        console_lock=None,
        db=None,
    ):
        _ = stop_char
        if zmq_conn is not None:
            raise ValueError(
                "Legacy SUB socket mode is no longer supported. "
                "Streamers must use queue-based forwarding (zmq_conn must be None)."
            )
        self._timeout = float(os.getenv("MT5_SOCKET_TIMEOUT", "30.0"))
        # Queue for receiving ticks from discovery service
        self._tick_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1000)
        self._processor = TickProcessor(
            asset=asset,
            verbose=verbose,
            console_lock=console_lock,
            db=db,
        )

    def put_tick(self, tick_data: dict):
        """
        Called by discovery service to forward a tick to this streamer.

        :param tick_data: Tick data dictionary
        """
        try:
            self._tick_queue.put_nowait(tick_data)
        except queue.Full:
            symbol = (
                self._processor._asset.symbol if self._processor._asset else "unknown"
            )
            if hasattr(self._processor, "_logger"):
                self._processor._logger.warning(
                    f"Tick queue full for {symbol} - dropping tick"
                )

    def _read_message(self):
        """
        Read message from queue (discovery-based forwarding).
        """
        symbol = self._processor._asset.symbol if self._processor._asset else "unknown"

        try:
            tick_timeout = float(os.getenv("TICK_STREAMING_TIMEOUT", "1.0"))
            message = self._tick_queue.get(timeout=tick_timeout)
            if hasattr(self._processor, "_logger"):
                self._processor._logger.debug(
                    f"ZeroMQTickStreamer received message from queue for {symbol}"
                )
            return message
        except queue.Empty:
            raise TimeoutError("No tick available in queue")
        except Exception as e:
            if hasattr(self._processor, "_logger"):
                self._processor._logger.error(
                    f"Error in _read_message for {symbol}: {e}", exc_info=True
                )
            raise

    def receive_tick(self):
        symbol = self._processor._asset.symbol if self._processor._asset else "unknown"
        if hasattr(self._processor, "_logger"):
            self._processor._logger.info(
                f"ZeroMQTickStreamer.receive_tick() started for {symbol} "
                f"(queue-based forwarding)"
            )
        return self._processor.receive_tick(self._read_message)
