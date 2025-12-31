"""
Trade executor
Executes trades via terminal
"""
import asyncio
from typing import Optional

from codes.order_type import OrderType
from models.currency_pair import CurrencyPair
from mt5_connection.terminal import MT5Terminal
from models.trade import Trade
from utils.time_utils import print_with_datetime
from utils.market_utils import check_if_market_open


class TradeExecutor:
    """Executes trades via terminal"""
    
    def __init__(self, terminal: MT5Terminal):
        """
        Initialize trade executor
        :param terminal: MT5 terminal connection
        """
        self.terminal = terminal
    
    def send_order(
        self,
        order_type: OrderType,
        pair: CurrencyPair,
        lotsize: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None
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
        
        try:
            trade = asyncio.run(
                self.terminal.send_order(order_type, pair, lotsize, price, sl, tp)
            )
            return trade
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
        self,
        trade: Trade,
        lotsize: Optional[float] = None
    ) -> Optional[dict]:
        """
        Close order via terminal
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
            
            result = asyncio.run(self.terminal.close_order(trade, lotsize))
            return result
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
        tp: Optional[float] = None
    ) -> Optional[Trade]:
        """Alias for send_order"""
        return self.send_order(order_type, pair, lotsize, price, sl, tp)
    
    def close_position(self, trade: Trade) -> Optional[dict]:
        """Alias for close_order with full close"""
        return self.close_order(trade, None)
