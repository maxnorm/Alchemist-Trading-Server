"""
Connection State Management

Manages connection state transitions and logging for MT5 tick streamers.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict
from utils.time_utils import get_utc_time


class ConnectionState(Enum):
    """Connection state enumeration"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class ConnectionStateManager:
    """
    Manages connection state transitions and metrics
    """

    def __init__(self, symbol: str):
        """
        Initialize connection state manager

        :param symbol: Symbol for this connection
        """
        self.symbol = symbol
        self.current_state = ConnectionState.DISCONNECTED
        self.state_history: list[Dict] = []
        self.connection_start_time: Optional[datetime] = None
        self.reconnection_attempts = 0
        self.reconnection_success_count = 0
        self.reconnection_failure_count = 0
        self.total_uptime_seconds = 0.0
        self.last_state_change_time = get_utc_time()

    def transition_to(self, new_state: ConnectionState, reason: Optional[str] = None):
        """
        Transition to a new state

        :param new_state: New connection state
        :param reason: Reason for state transition
        """
        if new_state == self.current_state:
            return  # No change

        old_state = self.current_state
        transition_time = get_utc_time()

        # Calculate uptime if transitioning from connected
        if old_state == ConnectionState.CONNECTED and self.connection_start_time:
            uptime = (transition_time - self.connection_start_time).total_seconds()
            self.total_uptime_seconds += uptime
            self.connection_start_time = None

        # Update state
        self.current_state = new_state
        self.last_state_change_time = transition_time

        # Track reconnection attempts
        if new_state == ConnectionState.RECONNECTING:
            self.reconnection_attempts += 1
        elif new_state == ConnectionState.CONNECTED:
            if old_state == ConnectionState.RECONNECTING:
                self.reconnection_success_count += 1
            self.connection_start_time = transition_time
        elif new_state == ConnectionState.FAILED:
            if old_state == ConnectionState.RECONNECTING:
                self.reconnection_failure_count += 1

        # Record state transition
        transition_record = {
            "timestamp": transition_time.isoformat(),
            "from_state": old_state.value,
            "to_state": new_state.value,
            "reason": reason,
        }
        self.state_history.append(transition_record)

        # Keep only last 100 transitions
        if len(self.state_history) > 100:
            self.state_history = self.state_history[-100:]

    def get_metrics(self) -> Dict:
        """
        Get connection metrics

        :return: Dictionary with connection metrics
        """
        current_uptime = 0.0
        if (
            self.current_state == ConnectionState.CONNECTED
            and self.connection_start_time
        ):
            current_uptime = (
                get_utc_time() - self.connection_start_time
            ).total_seconds()

        return {
            "symbol": self.symbol,
            "current_state": self.current_state.value,
            "reconnection_attempts": self.reconnection_attempts,
            "reconnection_success_count": self.reconnection_success_count,
            "reconnection_failure_count": self.reconnection_failure_count,
            "total_uptime_seconds": self.total_uptime_seconds + current_uptime,
            "current_uptime_seconds": current_uptime,
            "last_state_change": self.last_state_change_time.isoformat(),
            "state_history_count": len(self.state_history),
        }

    def is_connected(self) -> bool:
        """
        Check if connection is currently active

        :return: True if connected
        """
        return self.current_state == ConnectionState.CONNECTED
