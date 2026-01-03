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
        # #region agent log
        try:
            import json as json_log, os, time
            log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
            with open(log_path, 'a') as f:
                f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"trade_executor.py:26","message":"TradeExecutor.send_order entry","data":{"order_type":order_type,"symbol":pair.symbol,"lotsize":lotsize,"price":price,"sl":sl,"tp":tp},"timestamp":int(time.time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        # Check if market is open before sending order
        market_open = check_if_market_open()
        # #region agent log
        try:
            import json as json_log, os, time
            log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
            with open(log_path, 'a') as f:
                f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"trade_executor.py:46","message":"Market check result","data":{"market_open":market_open,"symbol":pair.symbol},"timestamp":int(time.time()*1000)}) + '\n')
        except: pass
        # #endregion
        if not check_if_market_open():
            print_with_datetime(
                f"Order blocked: Market is closed. "
                f"[ORDER:{order_type}|PAIR:{pair.symbol}|LOTSIZE:{lotsize}]"
            )
            return None
        
        # #region agent log
        try:
            import json as json_log, os, time
            log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
            with open(log_path, 'a') as f:
                f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"trade_executor.py:62","message":"Before asyncio.run terminal.send_order","data":{"order_type":order_type,"symbol":pair.symbol},"timestamp":int(time.time()*1000)}) + '\n')
        except: pass
        # #endregion
        # #region agent log
        try:
            import json as json_log, os, time as _t
            payload = {"sessionId":"debug-session","runId":"run-debug","hypothesisId":"H4","location":"trade_executor.py:send_order","message":"before_asyncio_run","data":{"order_type":order_type,"symbol":pair.symbol,"lotsize":lotsize},"timestamp":int(_t.time()*1000)}
            try:
                host_log = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                with open(host_log, 'a') as f:
                    f.write(json_log.dumps(payload) + '\n')
            except: pass
            try:
                log_path = os.path.join(os.getenv('LOG_DIR', '/app/logs'), 'debug.log')
                with open(log_path, 'a') as f:
                    f.write(json_log.dumps(payload) + '\n')
            except: pass
        except:  # pragma: no cover
            pass
        # #endregion
        try:
            trade = asyncio.run(
                self.terminal.send_order(order_type, pair, lotsize, price, sl, tp)
            )
            # #region agent log
            try:
                import json as json_log, os, time
                log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                with open(log_path, 'a') as f:
                    f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"trade_executor.py:73","message":"After asyncio.run terminal.send_order","data":{"trade_is_none":trade is None,"trade_ticket":trade.ticket if trade else None},"timestamp":int(time.time()*1000)}) + '\n')
            except: pass
            # #endregion
            # #region agent log
            try:
                import json as json_log, os, time as _t
                payload = {"sessionId":"debug-session","runId":"run-debug","hypothesisId":"H4","location":"trade_executor.py:send_order","message":"after_asyncio_run","data":{"trade_is_none":trade is None,"trade_ticket":trade.ticket if trade else None},"timestamp":int(_t.time()*1000)}
                try:
                    host_log = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                    with open(host_log, 'a') as f:
                        f.write(json_log.dumps(payload) + '\n')
                except: pass
                try:
                    log_path = os.path.join(os.getenv('LOG_DIR', '/app/logs'), 'debug.log')
                    with open(log_path, 'a') as f:
                        f.write(json_log.dumps(payload) + '\n')
                except: pass
            except:  # pragma: no cover
                pass
            # #endregion
            return trade
        except TimeoutError as e:
            # #region agent log
            try:
                import json as json_log, os
                log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                with open(log_path, 'a') as f:
                    f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"trade_executor.py:58","message":"TimeoutError caught","data":{"error":str(e)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            error_msg = (
                f"Trade execution timeout: {e}\n"
                f"[ORDER:{order_type}|PAIR:{pair.symbol}|LOTSIZE:{lotsize}|PRICE:{price}|SL:{sl}|TP:{tp}]\n"
                f"The MT5 terminal did not respond within the timeout period."
            )
            print_with_datetime(error_msg)
            return None
        except ConnectionError as e:
            # #region agent log
            try:
                import json as json_log, os
                log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                with open(log_path, 'a') as f:
                    f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"trade_executor.py:66","message":"ConnectionError caught","data":{"error":str(e)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            # #region agent log
            try:
                import json as json_log, os, time as _t
                payload = {"sessionId":"debug-session","runId":"run-debug","hypothesisId":"H4","location":"trade_executor.py:send_order","message":"connection_error","data":{"error":str(e)},"timestamp":int(_t.time()*1000)}
                try:
                    host_log = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                    with open(host_log, 'a') as f:
                        f.write(json_log.dumps(payload) + '\n')
                except: pass
                try:
                    log_path = os.path.join(os.getenv('LOG_DIR', '/app/logs'), 'debug.log')
                    with open(log_path, 'a') as f:
                        f.write(json_log.dumps(payload) + '\n')
                except: pass
            except:  # pragma: no cover
                pass
            # #endregion
            error_msg = (
                f"Trade execution connection error: {e}\n"
                f"[ORDER:{order_type}|PAIR:{pair.symbol}|LOTSIZE:{lotsize}|PRICE:{price}|SL:{sl}|TP:{tp}]\n"
                f"The connection to MT5 terminal may be lost."
            )
            print_with_datetime(error_msg)
            return None
        except Exception as e:
            # #region agent log
            try:
                import json as json_log, os, time
                log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                with open(log_path, 'a') as f:
                    f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"trade_executor.py:115","message":"Exception caught in send_order","data":{"error_type":type(e).__name__,"error":str(e)},"timestamp":int(time.time()*1000)}) + '\n')
            except: pass
            # #endregion
            # #region agent log
            try:
                import json as json_log, os, time as _t
                payload = {"sessionId":"debug-session","runId":"run-debug","hypothesisId":"H4","location":"trade_executor.py:send_order","message":"generic_exception","data":{"error_type":type(e).__name__,"error":str(e)},"timestamp":int(_t.time()*1000)}
                try:
                    host_log = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                    with open(host_log, 'a') as f:
                        f.write(json_log.dumps(payload) + '\n')
                except: pass
                try:
                    log_path = os.path.join(os.getenv('LOG_DIR', '/app/logs'), 'debug.log')
                    with open(log_path, 'a') as f:
                        f.write(json_log.dumps(payload) + '\n')
                except: pass
            except:  # pragma: no cover
                pass
            # #endregion
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
