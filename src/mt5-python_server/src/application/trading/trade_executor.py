"""
Trade executor
Executes trades via broker adapter
"""

import asyncio
from typing import Optional

from codes.order_type import OrderType
from models.currency_pair import CurrencyPair
from trading.brokers.base import IBrokerAdapter
from mt5_connection.terminal import MT5Terminal  # Keep for backward compatibility
from models.trade import Trade
from risk.oms import Order, OrderSide
from utils.time_utils import print_with_datetime
from utils.market_utils import check_if_market_open
import uuid


class TradeExecutor:
    """Executes trades via broker adapter"""

    def __init__(self, broker_adapter: Optional[IBrokerAdapter] = None, terminal: Optional[MT5Terminal] = None):
        """
        Initialize trade executor
        :param broker_adapter: IBrokerAdapter instance (preferred)
        :param terminal: MT5Terminal instance (for backward compatibility)
        """
        if broker_adapter:
            self.broker_adapter = broker_adapter
        elif terminal:
            # Create adapter from terminal for backward compatibility
            from trading.brokers.mt5_adapter import MT5BrokerAdapter
            self.broker_adapter = MT5BrokerAdapter.from_terminal(terminal)
        else:
            raise ValueError("Either broker_adapter or terminal must be provided")
        
        # Keep terminal reference for backward compatibility
        self.terminal = getattr(self.broker_adapter, 'terminal', None) if hasattr(self.broker_adapter, 'terminal') else terminal

    def send_order(
        self,
        order_type: OrderType,
        pair: CurrencyPair,
        lotsize: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> Optional[Trade]:
        """
        Send order via terminal
        :param order_type: Order type (BUY/SELL)
        :param pair: Currency pair
        :param lotsize: Lot size
        :param price: Order price (optional for market orders)
        :param sl: Stop loss (optional)
        :param tp: Take profit (optional)
        :return: Trade object or None if failed
        """
        # Check if market is open before sending order
        if not check_if_market_open():
            print_with_datetime(
                f"Order blocked: Market is closed. "
                f"[ORDER:{order_type}|PAIR:{pair.symbol}|LOTSIZE:{lotsize}]"
            )
            return None
        
        # Convert to Order model and use broker adapter
        try:
            order_side = "BUY" if order_type == OrderType.BUY else "SELL"
            order = Order(
                order_id=str(uuid.uuid4()),
                client_order_id=str(uuid.uuid4()),
                symbol=pair.symbol,
                side=order_side,
                quantity=lotsize,
                order_type="MARKET",
                price=price,
                stop_loss=sl,
                take_profit=tp,
            )
            
            # Submit order via broker adapter
            idempotency_key = order.client_order_id
            order_status = self.broker_adapter.submit_order(order, idempotency_key)
            
            # Convert OrderStatus back to Trade for backward compatibility
            if order_status.state.value in ["filled", "partially_filled"]:
                trade = Trade(
                    ticket=int(order_status.broker_order_id) if order_status.broker_order_id else 0,
                    ordertype=order_type,
                    pair=pair,
                    lotsize=order_status.filled_quantity,
                    open_price=order_status.average_fill_price or price or 0.0,
                    sl=sl,
                    tp=tp,
                )
                return trade
            else:
                print_with_datetime(
                    f"Order rejected: {order_status.reject_reason}. "
                    f"[ORDER:{order_type}|PAIR:{pair.symbol}|LOTSIZE:{lotsize}]"
                )
                return None
        except TimeoutError as e:
            error_msg = (
                f"Trade execution timeout: {e}\n"
                f"[ORDER:{order_type}|PAIR:{pair.symbol}|LOTSIZE:{lotsize}|PRICE:{price}|SL:{sl}|TP:{tp}]\n"
                f"The MT5 terminal did not respond within the timeout period."
            )
            print_with_datetime(error_msg)
            return None
        except ConnectionError as e:
            error_msg = (
                f"Trade execution connection error: {e}\n"
                f"[ORDER:{order_type}|PAIR:{pair.symbol}|LOTSIZE:{lotsize}|PRICE:{price}|SL:{sl}|TP:{tp}]\n"
                f"The connection to MT5 terminal may be lost."
            )
            print_with_datetime(error_msg)
            return None
        except Exception as e:
            error_msg = (
                f"Trade execution error: {e}\n"
                f"[ORDER:{order_type}|PAIR:{pair.symbol}|LOTSIZE:{lotsize}|PRICE:{price}|SL:{sl}|TP:{tp}]"
            )
            print_with_datetime(error_msg)
            return None

    def close_order(
        self, trade: Trade, lotsize: Optional[float] = None
    ) -> Optional[dict]:
        """
        Close order via broker adapter
        :param trade: Trade to close
        :param lotsize: Lot size to close (None for full close)
        :return: Result dictionary or None if failed
        """
        # Check if market is open before closing order
        # Note: Closing positions might be allowed even when market is closed for some brokers
        # but we'll check anyway to be safe
        if not check_if_market_open():
            print_with_datetime(
                f"Close order blocked: Market is closed. "
                f"[TICKET:{trade.ticket}|LOTSIZE:{lotsize}]"
            )
            return None

        try:
            if lotsize is None:
                lotsize = trade.lotsize

            # Use broker adapter to cancel order
            order_id = str(trade.ticket)
            success = self.broker_adapter.cancel_order(order_id)
            
            if success:
                # Return result in expected format for backward compatibility
                return {
                    "order": {
                        "ticket": trade.ticket,
                        "lotsize": trade.lotsize - lotsize if lotsize < trade.lotsize else 0,
                        "close_price": trade.open_price,  # Approximate
                    }
                }
            else:
                # Fallback to terminal if adapter doesn't support cancel
                if self.terminal:
                    result = asyncio.run(self.terminal.close_order(trade, lotsize))
                    return result
                return None
        except Exception as e:
            print_with_datetime(f"Close order error: {e}.\n[TICKET:{trade.ticket}]")
            return None

    def execute_order(
        self,
        order_type: OrderType,
        pair: CurrencyPair,
        lotsize: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> Optional[Trade]:
        """Alias for send_order"""
        return self.send_order(order_type, pair, lotsize, price, sl, tp)

    def close_position(self, trade: Trade) -> Optional[dict]:
        """Alias for close_order with full close"""
        return self.close_order(trade, None)
