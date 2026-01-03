"""
Sell action strategy
Opens a short position
"""
import logging
from typing import Tuple

from codes.order_type import OrderType
from domain.action_type import ActionType
from domain.execution_context import ExecutionContext
from domain.strategies.action_strategy import ActionStrategy
from utils.market_utils import check_if_market_open


class SellActionStrategy(ActionStrategy):
    """Strategy for SELL action (open short position)"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
    
    @property
    def action_type(self):
        return ActionType.SELL
    
    def can_execute(self, context: ExecutionContext) -> Tuple[bool, str]:
        """
        Check if sell action can be executed
        Allows multiple positions up to max_open_positions limit
        :param context: Execution context
        :return: Tuple of (can_execute, reason)
        """
        # Check if market is open
        if not check_if_market_open():
            return False, "Market is closed"
        
        # Check risk limits (includes max_open_positions check)
        can_trade, reason = context.can_trade
        if not can_trade:
            return False, f"Risk management: {reason}"
        
        if not context.trading_enabled:
            return False, "Trading is disabled"
        
        return True, "Sell action allowed"
    
    def execute(self, context: ExecutionContext) -> float:
        """
        Execute sell action
        :param context: Execution context
        :return: Reward value
        """
        can_execute, reason = self.can_execute(context)
        if not can_execute:
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='sell_action_blocked',
                    message=f"SELL action blocked: {reason}",
                    symbol=context.pair.symbol,
                    account_login=context.account.login if context.account else None,
                    metrics={'reason': reason},
                    level='WARNING'
                )
            else:
                self.logger.warning(f"SELL action blocked: {reason}")
            return 0.0
        
        try:
            entry_price = context.pair.bid
            lot_size = context.risk_manager.calculate_position_size(
                context.account, context.pair, entry_price
            )
            sl = context.risk_manager.calculate_stop_loss(entry_price, False)
            tp = context.risk_manager.calculate_take_profit(entry_price, False)
            
            # Log attempt to open position
            if hasattr(self.logger, 'log_trade'):
                self.logger.log_trade(
                    action='sell',
                    symbol=context.pair.symbol,
                    account_login=context.account.login if context.account else None,
                    lots=lot_size,
                    price=entry_price,
                    metrics={
                        'stop_loss': sl,
                        'take_profit': tp
                    }
                )
            else:
                self.logger.info(f"🔴 ATTEMPTING SELL POSITION: {context.pair.symbol} | "
                               f"Lot size: {lot_size:.2f} | "
                               f"Entry: {entry_price:.5f} | "
                               f"SL: {sl:.5f} | "
                               f"TP: {tp:.5f}")
            
            # Send order and check result
            # #region agent log
            try:
                import json as json_log, os
                log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                with open(log_path, 'a') as f:
                    f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"sell_action_strategy.py:96","message":"Before send_order call","data":{"symbol":context.pair.symbol,"lot_size":lot_size,"entry_price":entry_price,"sl":sl,"tp":tp},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            try:
                trade = context.account.send_order(OrderType.SELL, context.pair, lot_size, None, sl, tp)
                # #region agent log
                try:
                    import json as json_log, os
                    log_path = r'c:\Users\maxno\Desktop\Projet\1.1\.cursor\debug.log'
                    with open(log_path, 'a') as f:
                        f.write(json_log.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"sell_action_strategy.py:98","message":"After send_order call","data":{"trade_is_none":trade is None,"trade_ticket":trade.ticket if trade else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
            except Exception as e:
                error_msg = f"❌ EXCEPTION sending SELL order: {e}"
                if hasattr(self.logger, 'log_error'):
                    self.logger.log_error(
                        event_type='sell_order_exception',
                        error=error_msg,
                        symbol=context.pair.symbol,
                        account_login=context.account.login if context.account else None,
                        exc_info=True
                    )
                else:
                    self.logger.error(error_msg, exc_info=True)
                return 0.0
            
            if trade:
                # Order succeeded
                # Log to performance tracking if available
                if context.trade_logger and context.session_id and context.model_id:
                    try:
                        import uuid
                        order_uuid = str(uuid.uuid4())  # Generate UUID for order tracking
                        # Store order_uuid in trade object if possible for later reference
                        if hasattr(trade, 'uuid'):
                            trade.uuid = order_uuid
                        
                        trade_id = context.trade_logger.log_trade_entry(
                            session_id=context.session_id,
                            model_id=context.model_id,
                            order_uuid=order_uuid,
                            symbol=context.pair.symbol,
                            action='SELL',
                            entry_price=trade.open_price,
                            volume=trade.lotsize,
                            commission=0.0,  # Can be extracted from trade if available
                            swap=0.0
                        )
                        # Store trade_id for later reference when closing
                        if hasattr(trade, 'performance_trade_id'):
                            trade.performance_trade_id = trade_id
                    except Exception as e:
                        self.logger.warning(f"Failed to log trade entry to performance tracking: {e}")
                
                if hasattr(self.logger, 'log_trade'):
                    self.logger.log_trade(
                        action='sell',
                        symbol=context.pair.symbol,
                        account_login=context.account.login if context.account else None,
                        lots=trade.lotsize,
                        price=trade.open_price,
                        metrics={
                            'ticket': trade.ticket,
                            'stop_loss': sl,
                            'take_profit': tp
                        }
                    )
                else:
                    self.logger.info(f"✅ SELL POSITION OPENED: {context.pair.symbol} | "
                                   f"Ticket: {trade.ticket} | "
                                   f"Lot size: {trade.lotsize:.2f} | "
                                   f"Entry: {trade.open_price:.5f} | "
                                   f"SL: {sl:.5f} | "
                                   f"TP: {tp:.5f}")
            else:
                # Order failed
                error_msg = f"❌ FAILED TO OPEN SELL POSITION: {context.pair.symbol} | " \
                           f"Lot size: {lot_size:.2f} | " \
                           f"Entry: {entry_price:.5f} | " \
                           f"SL: {sl:.5f} | " \
                           f"TP: {tp:.5f} | " \
                           f"Reason: Order returned None (check server logs for details)"
                if hasattr(self.logger, 'log_error'):
                    self.logger.log_error(
                        event_type='sell_order_failed',
                        error=error_msg,
                        symbol=context.pair.symbol,
                        account_login=context.account.login if context.account else None,
                        exc_info=False
                    )
                else:
                    self.logger.error(error_msg)
            
            # Reward will be calculated by environment based on balance change
            return 0.0
            
        except Exception as e:
            error_msg = f"❌ ERROR executing SELL action on {context.pair.symbol}: {e}"
            if hasattr(self.logger, 'log_error'):
                self.logger.log_error(
                    event_type='sell_action_error',
                    error=error_msg,
                    symbol=context.pair.symbol,
                    account_login=context.account.login if context.account else None,
                    exc_info=True
                )
            else:
                self.logger.error(error_msg, exc_info=True)
            return 0.0
