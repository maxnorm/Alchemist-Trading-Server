"""
MT5 Python API Broker Adapter
Implements IBrokerAdapter using MetaTrader5 Python package (no EA required)
"""

import MetaTrader5 as mt5
from typing import Dict, List, Optional
from datetime import datetime
from risk.oms import Order, Position, Discrepancy, OrderState
from trading.brokers.base import IBrokerAdapter, OrderStatus
from domain.entities.account_info import AccountInfo
from infrastructure.security.credential_manager import CredentialManager
from utils.logging_config import get_logger


class MT5PythonAPIBrokerAdapter(IBrokerAdapter):
    """MT5 broker adapter using Python API (no EA required)"""

    def __init__(self, login: int, password: str, server: str, credential_manager: CredentialManager):
        """
        Initialize MT5 Python API broker adapter

        :param login: MT5 account login
        :param password: Decrypted MT5 account password
        :param server: MT5 broker server name
        :param credential_manager: CredentialManager instance (for future use)
        """
        self.login = login
        self.password = password
        self.server = server
        self.credential_manager = credential_manager
        self.logger = get_logger("mt5_python_api_adapter", "mt5_python_api_adapter.log")
        self._idempotency_map: Dict[str, str] = {}
        self._order_id_map: Dict[str, Order] = {}
        self._initialized = False
        self._connection_id = None

    def _ensure_connected(self):
        """Ensure MT5 connection is established"""
        if not self._initialized:
            if not mt5.initialize():
                error = mt5.last_error()
                raise ConnectionError(f"Failed to initialize MT5: {error}")
            self._initialized = True

        # Login if not already logged in
        if not mt5.login(self.login, password=self.password, server=self.server):
            error = mt5.last_error()
            raise ConnectionError(f"Failed to login to MT5: {error}")

    def submit_order(self, order: Order, idempotency_key: str) -> OrderStatus:
        """
        Submit order via MT5 Python API

        :param order: Order object
        :param idempotency_key: Unique idempotency key
        :return: OrderStatus
        """
        # Check idempotency
        if idempotency_key in self._idempotency_map:
            existing_order_id = self._idempotency_map[idempotency_key]
            return self.get_order_status(existing_order_id)

        self._ensure_connected()

        try:
            # Convert Order to MT5 request structure
            request = self._convert_order_to_mt5_request(order)

            # Send order
            result = mt5.order_send(request)
            if result is None:
                error = mt5.last_error()
                self.logger.error(f"Order send returned None: {error}")
                return OrderStatus(
                    order_id=order.order_id,
                    state=OrderState.REJECTED,
                    reject_reason=f"MT5 order_send failed: {error}",
                )

            # Check result
            if result.retcode != mt5.TRADE_RETCODE_DONE and result.retcode != mt5.TRADE_RETCODE_PLACED:
                error_desc = self._get_retcode_description(result.retcode)
                self.logger.warning(f"Order rejected: {result.retcode} - {error_desc}")
                return OrderStatus(
                    order_id=order.order_id,
                    state=OrderState.REJECTED,
                    reject_reason=f"MT5 rejected order: {error_desc} (code: {result.retcode})",
                )

            # Store idempotency mapping
            broker_order_id = str(result.order)
            self._idempotency_map[idempotency_key] = broker_order_id
            order.broker_order_id = broker_order_id
            self._order_id_map[broker_order_id] = order

            # Determine order state
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                state = OrderState.FILLED
            else:  # TRADE_RETCODE_PLACED
                state = OrderState.NEW

            return OrderStatus(
                order_id=order.order_id,
                state=state,
                filled_quantity=result.volume if state == OrderState.FILLED else 0.0,
                average_fill_price=result.price if state == OrderState.FILLED else None,
                broker_order_id=broker_order_id,
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(f"Error submitting order: {e}", exc_info=True)
            return OrderStatus(
                order_id=order.order_id,
                state=OrderState.REJECTED,
                reject_reason=str(e),
            )

    def _convert_order_to_mt5_request(self, order: Order) -> Dict:
        """
        Convert Order to MT5 order_send request dictionary

        :param order: Order object
        :return: Dictionary for mt5.order_send()
        """
        # Determine order type
        if order.order_type == "MARKET":
            if order.side.upper() == "BUY":
                order_type = mt5.ORDER_TYPE_BUY
            else:
                order_type = mt5.ORDER_TYPE_SELL
        elif order.order_type == "LIMIT":
            if order.side.upper() == "BUY":
                order_type = mt5.ORDER_TYPE_BUY_LIMIT
            else:
                order_type = mt5.ORDER_TYPE_SELL_LIMIT
        elif order.order_type == "STOP":
            if order.side.upper() == "BUY":
                order_type = mt5.ORDER_TYPE_BUY_STOP
            else:
                order_type = mt5.ORDER_TYPE_SELL_STOP
        else:
            # Default to market order
            order_type = mt5.ORDER_TYPE_BUY if order.side.upper() == "BUY" else mt5.ORDER_TYPE_SELL

        # Get symbol info for lot size conversion
        symbol_info = mt5.symbol_info(order.symbol)
        if symbol_info is None:
            raise ValueError(f"Symbol {order.symbol} not found in MT5")

        # Build request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.quantity,
            "type": order_type,
            "deviation": 20,  # Slippage in points
            "magic": 234000,  # Magic number for order identification
            "comment": f"Python API order {order.order_id}",
            "type_time": mt5.ORDER_TIME_GTC,  # Good till cancelled
            "type_filling": mt5.ORDER_FILLING_IOC,  # Immediate or Cancel
        }

        # Add price for limit/stop orders
        if order.price is not None:
            request["price"] = order.price

        # Add stop loss and take profit
        if order.stop_loss is not None:
            request["sl"] = order.stop_loss
        if order.take_profit is not None:
            request["tp"] = order.take_profit

        return request

    def get_positions(self) -> List[Position]:
        """
        Get all open positions from MT5

        :return: List of Position objects
        """
        self._ensure_connected()

        try:
            positions = mt5.positions_get()
            if positions is None:
                error = mt5.last_error()
                self.logger.warning(f"Failed to get positions: {error}")
                return []

            result = []
            for pos in positions:
                # Determine quantity (positive for long, negative for short)
                quantity = pos.volume if pos.type == mt5.ORDER_TYPE_BUY else -pos.volume

                position = Position(
                    symbol=pos.symbol,
                    quantity=quantity,
                    average_price=pos.price_open,
                    unrealized_pnl=pos.profit,
                    realized_pnl=0.0,  # MT5 doesn't provide this directly
                )
                result.append(position)

            return result

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
            broker_order_id = order.broker_order_id

            if broker_order_id:
                # Try to get order from MT5
                self._ensure_connected()
                order_info = mt5.orders_get(ticket=int(broker_order_id))
                if order_info and len(order_info) > 0:
                    # Order still pending
                    return OrderStatus(
                        order_id=order.order_id,
                        state=OrderState.NEW,
                        filled_quantity=0.0,
                        broker_order_id=broker_order_id,
                    )

                # Check if it's a position (filled order)
                position = mt5.positions_get(ticket=int(broker_order_id))
                if position and len(position) > 0:
                    pos = position[0]
                    return OrderStatus(
                        order_id=order.order_id,
                        state=OrderState.FILLED,
                        filled_quantity=pos.volume,
                        average_fill_price=pos.price_open,
                        broker_order_id=broker_order_id,
                    )

            # Default: assume filled if we have it in our map
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

            self._ensure_connected()

            # Try to cancel pending order
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": int(broker_order_id),
            }

            result = mt5.order_send(request)
            if result is None:
                error = mt5.last_error()
                self.logger.error(f"Failed to cancel order: {error}")
                return False

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.warning(f"Order cancellation failed: {result.retcode}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error canceling order: {e}", exc_info=True)
            return False

    def get_account_info(self) -> AccountInfo:
        """
        Get account information from MT5

        :return: AccountInfo object
        """
        self._ensure_connected()

        try:
            account_info = mt5.account_info()
            if account_info is None:
                error = mt5.last_error()
                raise ConnectionError(f"Failed to get account info: {error}")

            return AccountInfo(
                login=account_info.login,
                currency=account_info.currency,
                leverage=account_info.leverage,
                balance=account_info.balance,
                equity=account_info.equity,
                profit=account_info.profit,
                margin=account_info.margin,
                margin_free=account_info.margin_free,
            )

        except Exception as e:
            self.logger.error(f"Error getting account info: {e}", exc_info=True)
            # Return default AccountInfo on error
            return AccountInfo(
                login=self.login,
                currency="USD",
                leverage=1,
                balance=0.0,
                equity=0.0,
                profit=0.0,
                margin=0.0,
                margin_free=0.0,
            )

    def _get_retcode_description(self, retcode: int) -> str:
        """
        Get human-readable description for MT5 retcode

        :param retcode: MT5 return code
        :return: Description string
        """
        retcode_descriptions = {
            mt5.TRADE_RETCODE_REQUOTE: "Requote",
            mt5.TRADE_RETCODE_REJECT: "Request rejected",
            mt5.TRADE_RETCODE_ERROR: "Common error",
            mt5.TRADE_RETCODE_TIMEOUT: "Request timeout",
            mt5.TRADE_RETCODE_INVALID: "Invalid request",
            mt5.TRADE_RETCODE_INVALID_VOLUME: "Invalid volume",
            mt5.TRADE_RETCODE_INVALID_PRICE: "Invalid price",
            mt5.TRADE_RETCODE_INVALID_STOPS: "Invalid stops",
            mt5.TRADE_RETCODE_TRADE_DISABLED: "Trade disabled",
            mt5.TRADE_RETCODE_MARKET_CLOSED: "Market closed",
            mt5.TRADE_RETCODE_NO_MONEY: "Not enough money",
            mt5.TRADE_RETCODE_PRICE_OFF: "Price changed",
            mt5.TRADE_RETCODE_PRICE_OVER: "Off quotes",
            mt5.TRADE_RETCODE_INVALID_EXPIRATION: "Invalid expiration",
            mt5.TRADE_RETCODE_ORDER_CHANGED: "Order changed",
            mt5.TRADE_RETCODE_TOO_MANY_REQUESTS: "Too many requests",
            mt5.TRADE_RETCODE_NO_CHANGES: "No changes",
            mt5.TRADE_RETCODE_SERVER_DISABLES_AT: "Autotrading disabled",
            mt5.TRADE_RETCODE_CLIENT_DISABLES_AT: "Client autotrading disabled",
            mt5.TRADE_RETCODE_LOCKED: "Request locked",
            mt5.TRADE_RETCODE_FROZEN: "Order or position frozen",
            mt5.TRADE_RETCODE_INVALID_FILL: "Invalid fill",
            mt5.TRADE_RETCODE_CONNECTION: "No connection",
            mt5.TRADE_RETCODE_ONLY_REAL: "Only real accounts allowed",
            mt5.TRADE_RETCODE_LIMIT_ORDERS: "Limit orders reached",
            mt5.TRADE_RETCODE_LIMIT_VOLUME: "Limit volume reached",
            mt5.TRADE_RETCODE_INVALID_ORDER: "Invalid order",
            mt5.TRADE_RETCODE_POSITION_CLOSED: "Position already closed",
        }

        return retcode_descriptions.get(retcode, f"Unknown error code: {retcode}")

    def __del__(self):
        """Cleanup: logout and shutdown"""
        if self._initialized:
            try:
                mt5.logout()
                mt5.shutdown()
            except Exception:
                pass  # Ignore errors during cleanup
