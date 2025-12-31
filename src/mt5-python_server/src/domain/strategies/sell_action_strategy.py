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
        :param context: Execution context
        :return: Tuple of (can_execute, reason)
        """
        if context.has_position:
            return False, f"Already have position on {context.pair.symbol}"
        
        # Check if market is open
        if not check_if_market_open():
            return False, "Market is closed"
        
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
            try:
                trade = context.account.send_order(OrderType.SELL, context.pair, lot_size, None, sl, tp)
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
