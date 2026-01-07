"""
Base broker adapter interface
Defines unified interface enabling plug-and-play broker support
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
from risk.oms import Order, Position, Discrepancy, OrderState
from domain.entities.account_info import AccountInfo


class OrderStatus:
    """
    Standardized order status across all brokers
    """

    def __init__(
        self,
        order_id: str,
        state: OrderState,
        filled_quantity: float = 0.0,
        average_fill_price: Optional[float] = None,
        broker_order_id: Optional[str] = None,
        reject_reason: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Initialize order status

        :param order_id: Internal order ID
        :param state: Order state
        :param filled_quantity: Quantity filled so far
        :param average_fill_price: Average fill price
        :param broker_order_id: Broker-specific order ID
        :param reject_reason: Reason for rejection (if rejected)
        :param timestamp: Timestamp of status update
        """
        self.order_id = order_id
        self.state = state
        self.filled_quantity = filled_quantity
        self.average_fill_price = average_fill_price
        self.broker_order_id = broker_order_id
        self.reject_reason = reject_reason
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "order_id": self.order_id,
            "state": self.state.value,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": self.average_fill_price,
            "broker_order_id": self.broker_order_id,
            "reject_reason": self.reject_reason,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class IBrokerAdapter(ABC):
    """
    Unified interface for broker adapters
    All brokers must implement this interface to enable plug-and-play broker support

    This interface provides a broker-agnostic way to:
    - Submit orders with idempotency support
    - Get positions and account information
    - Reconcile positions
    - Cancel orders
    """

    @abstractmethod
    def submit_order(self, order: Order, idempotency_key: str) -> OrderStatus:
        """
        Submit an order to the broker with idempotency support

        :param order: Order object to submit
        :param idempotency_key: Unique key for idempotency (same key = same order)
        :return: OrderStatus object with order state and fill information
        :raises ValueError: If order is invalid
        :raises ConnectionError: If broker connection fails
        """
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Get all open positions from the broker

        :return: List of Position objects
        :raises ConnectionError: If broker connection fails
        """
        pass

    @abstractmethod
    def reconcile(self, expected_positions: Dict[str, float]) -> List[Discrepancy]:
        """
        Reconcile expected positions with actual broker positions

        :param expected_positions: Dictionary mapping symbol -> expected quantity
        :return: List of Discrepancy objects for any mismatches
        :raises ConnectionError: If broker connection fails
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """
        Get current status of an order

        :param order_id: Order ID (internal or broker-specific)
        :return: OrderStatus object
        :raises ValueError: If order_id not found
        :raises ConnectionError: If broker connection fails
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order

        :param order_id: Order ID to cancel
        :return: True if cancellation successful, False otherwise
        :raises ValueError: If order_id not found
        :raises ConnectionError: If broker connection fails
        """
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """
        Get account information from broker

        :return: AccountInfo object
        :raises ConnectionError: If broker connection fails
        """
        pass
