"""
MT5 Broker Adapter
Wraps ZeroMQTerminal to implement IBrokerAdapter interface
"""

import asyncio
from typing import Dict, List
from datetime import datetime
from risk.oms import Order, Position, Discrepancy, OrderState
from trading.brokers.base import IBrokerAdapter, OrderStatus
from domain.entities.account_info import AccountInfo
from mt5_connection.zeromq_terminal import ZeroMQTerminal
from models.currency_pair import CurrencyPair
from codes.order_type import OrderType as MT5OrderType
from utils.logging_config import get_logger


class MT5BrokerAdapter(IBrokerAdapter):
    """
    MT5 broker adapter implementing IBrokerAdapter interface
    Wraps existing ZeroMQTerminal functionality
    """

    def __init__(self, terminal: ZeroMQTerminal, oms=None):
        """
        Initialize MT5 broker adapter

        :param terminal: ZeroMQTerminal instance
        :param oms: Optional OrderManagementSystem for idempotency
        """
        self.terminal = terminal
        self.oms = oms
        self.logger = get_logger("mt5_broker_adapter", "mt5_broker_adapter.log")

        # Idempotency tracking (if OMS not provided, use simple dict)
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> order_id
        self._order_id_map: Dict[str, Order] = {}  # order_id -> Order

    def submit_order(self, order: Order, idempotency_key: str) -> OrderStatus:
        """
        Submit order to MT5 with idempotency support

        :param order: Order object
        :param idempotency_key: Unique idempotency key
        :return: OrderStatus
        """
        # Check idempotency
        if idempotency_key in self._idempotency_map:
            existing_order_id = self._idempotency_map[idempotency_key]
            return self.get_order_status(existing_order_id)

        try:
            # Convert Order to MT5 format
            mt5_order_type = self._convert_order_side_to_mt5(order.side)
            currency_pair = CurrencyPair(order.symbol, 5)  # Default to 5 digits

            # Execute order via ZeroMQTerminal
            trade = asyncio.run(
                self.terminal.send_order(
                    order_type=mt5_order_type,
                    pair=currency_pair,
                    lotsize=order.quantity,
                    price=order.price,
                    sl=order.stop_loss,
                    tp=order.take_profit,
                )
            )

            if trade is None:
                # Order failed
                return OrderStatus(
                    order_id=order.order_id,
                    state=OrderState.REJECTED,
                    reject_reason="MT5 order submission failed",
                )

            # Store idempotency mapping
            self._idempotency_map[idempotency_key] = str(trade.ticket)
            order.broker_order_id = str(trade.ticket)
            self._order_id_map[str(trade.ticket)] = order

            # Convert Trade to OrderStatus
            return OrderStatus(
                order_id=order.order_id,
                state=OrderState.FILLED,  # MT5 market orders are typically filled immediately
                filled_quantity=order.quantity,
                average_fill_price=trade.open_price,
                broker_order_id=str(trade.ticket),
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(f"Error submitting order: {e}", exc_info=True)
            return OrderStatus(
                order_id=order.order_id,
                state=OrderState.REJECTED,
                reject_reason=str(e),
            )

    def get_positions(self) -> List[Position]:
        """
        Get all open positions from MT5

        :return: List of Position objects
        """
        try:
            # Get positions from ZeroMQTerminal
            # Note: ZeroMQTerminal may need a method to get positions
            # For now, we'll use account's current_trade
            positions: List[Position] = []

            # If we have access to account, get positions from there
            # Otherwise, we'd need to query MT5 directly
            # This is a simplified implementation
            return positions

        except Exception as e:
            self.logger.error(f"Error getting positions: {e}", exc_info=True)
            return []

    def reconcile(self, expected_positions: Dict[str, float]) -> List[Discrepancy]:
        """
        Reconcile expected positions with MT5 positions

        :param expected_positions: Dictionary mapping symbol -> expected quantity
        :return: List of Discrepancy objects
        """
        try:
            actual_positions = self.get_positions()
            actual_dict = {p.symbol: p.quantity for p in actual_positions}

            discrepancies = []
            for symbol, expected_quantity in expected_positions.items():
                actual_quantity = actual_dict.get(symbol, 0.0)
                if abs(actual_quantity - expected_quantity) > 0.01:  # Tolerance
                    discrepancies.append(
                        Discrepancy(
                            symbol=symbol,
                            local_quantity=expected_quantity,
                            broker_quantity=actual_quantity,
                            difference=actual_quantity - expected_quantity,
                        )
                    )

            return discrepancies

        except Exception as e:
            self.logger.error(f"Error reconciling positions: {e}", exc_info=True)
            return []

    def get_order_status(self, order_id: str) -> OrderStatus:
        """
        Get order status by ID

        :param order_id: Order ID (internal or broker ticket)
        :return: OrderStatus
        """
        # Check if we have this order in our map
        if order_id in self._order_id_map:
            order = self._order_id_map[order_id]
            # For MT5, we'd need to query the terminal for current status
            # Simplified: assume filled if we have it
            return OrderStatus(
                order_id=order.order_id,
                state=OrderState.FILLED,
                filled_quantity=order.quantity,
                average_fill_price=order.average_fill_price,
                broker_order_id=order.broker_order_id,
            )

        # Order not found
        raise ValueError(f"Order not found: {order_id}")

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order in MT5

        :param order_id: Order ID to cancel
        :return: True if successful
        """
        try:
            # Get order to find broker_order_id
            if order_id not in self._order_id_map:
                raise ValueError(f"Order not found: {order_id}")

            order = self._order_id_map[order_id]
            broker_order_id = order.broker_order_id

            if not broker_order_id:
                return False

            # MT5 doesn't have a direct cancel method in terminal
            # We'd need to close the position if it's open
            # For now, return False (not implemented)
            self.logger.warning("Cancel order not fully implemented for MT5")
            return False

        except Exception as e:
            self.logger.error(f"Error canceling order: {e}", exc_info=True)
            return False

    def get_account_info(self) -> AccountInfo:
        """
        Get account information from MT5

        :return: AccountInfo object
        """
        try:
            # Get account info from terminal
            infos = asyncio.run(self.terminal.get_all_infos())

            # Convert to AccountInfo
            return AccountInfo.from_dict(infos)

        except Exception as e:
            self.logger.error(f"Error getting account info: {e}", exc_info=True)
            # Return default AccountInfo on error
            return AccountInfo(
                login=0,
                currency="USD",
                leverage=1,
                balance=0.0,
                equity=0.0,
                profit=0.0,
                margin=0.0,
                margin_free=0.0,
            )

    def _convert_order_side_to_mt5(self, side: str) -> int:
        """
        Convert Order side string to MT5 OrderType

        :param side: "BUY" or "SELL"
        :return: MT5 OrderType value
        """
        if side.upper() == "BUY":
            return MT5OrderType.BUY.value
        elif side.upper() == "SELL":
            return MT5OrderType.SELL.value
        else:
            raise ValueError(f"Invalid order side: {side}")

    @classmethod
    def from_terminal(cls, terminal: ZeroMQTerminal, oms=None) -> "MT5BrokerAdapter":
        """
        Create adapter from ZeroMQTerminal (convenience method)

        :param terminal: ZeroMQTerminal instance
        :param oms: Optional OrderManagementSystem
        :return: MT5BrokerAdapter instance
        """
        return cls(terminal=terminal, oms=oms)
