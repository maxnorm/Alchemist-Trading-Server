"""
Close action strategy
Closes an open position
"""

import logging
from typing import Tuple

from domain.action_type import ActionType
from domain.execution_context import ExecutionContext
from domain.strategies.action_strategy import ActionStrategy
from utils.market_utils import check_if_market_open


class CloseActionStrategy(ActionStrategy):
    """Strategy for CLOSE action (close open position)"""

    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)

    @property
    def action_type(self):
        return ActionType.CLOSE

    def can_execute(self, context: ExecutionContext) -> Tuple[bool, str]:
        """
        Check if close action can be executed
        :param context: Execution context
        :return: Tuple of (can_execute, reason)
        """
        if not context.has_position:
            return False, f"No position to close on {context.pair.symbol}"

        if not context.account.current_trade:
            return False, "No trades found in account"

        # Check if market is open
        # Note: Some brokers allow closing positions even when market is closed
        # but we'll check to be safe
        if not check_if_market_open():
            return False, "Market is closed"

        return True, "Close action allowed"

    def execute(self, context: ExecutionContext) -> float:
        """
        Execute close action
        :param context: Execution context
        :return: Reward value
        """
        can_execute, reason = self.can_execute(context)
        if not can_execute:
            if hasattr(self.logger, "log_event"):
                self.logger.log_event(
                    event_type="close_action_ignored",
                    message=f"CLOSE action ignored: {reason}",
                    symbol=context.pair.symbol,
                    level="DEBUG",
                )
            else:
                self.logger.debug(f"CLOSE action ignored: {reason}")
            return 0.0

        try:
            # Get information from existing trade before closing
            trade = list(context.account.current_trade.values())[0]
            entry_price = trade.open_price
            lot_size = trade.lotsize
            # Determine if long or short from order type
            # OrderType.BUY = 0, OrderType.SELL = 1
            is_long = trade.ordertype.value == 0  # 0 = BUY
            # Exit price is the opposite of entry (bid for long, ask for short)
            exit_price = context.pair.bid if is_long else context.pair.ask

            # Log trade exit to performance tracking if available
            performance_trade_id = None
            if context.trade_logger and context.session_id and context.model_id:
                try:
                    # Try to find the trade_id from the trade object or look it up by ticket
                    if (
                        hasattr(trade, "performance_trade_id")
                        and trade.performance_trade_id
                    ):
                        performance_trade_id = trade.performance_trade_id
                    else:
                        # Try to find trade by ticket/uuid
                        # For now, we'll need to track this mapping - this is a limitation
                        # In Phase 7, we'll have better order tracking via OMS
                        pass

                    if performance_trade_id:
                        # Calculate P&L in pips (simplified - would need proper pip calculation)
                        pnl = trade.profit if hasattr(trade, "profit") else 0.0
                        pnl_pips = 0.0  # Would need proper calculation based on symbol

                        # Calculate duration (would need entry time from trade)
                        duration_seconds = 0  # Would need to track entry time

                        context.trade_logger.log_trade_exit(
                            trade_id=performance_trade_id,
                            exit_price=exit_price,
                            pnl=pnl,
                            pnl_pips=pnl_pips,
                            duration_seconds=duration_seconds,
                        )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to log trade exit to performance tracking: {e}"
                    )

            if hasattr(self.logger, "log_trade"):
                self.logger.log_trade(
                    action="close",
                    symbol=context.pair.symbol,
                    account_login=context.account.login if context.account else None,
                    lots=lot_size,
                    price=exit_price,
                    profit=trade.profit,
                    order_id=trade.ticket,
                    metrics={
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "is_long": is_long,
                    },
                )
            else:
                self.logger.info(
                    f"🟡 CLOSING POSITION: {context.pair.symbol} | "
                    f"Lot size: {lot_size:.2f} | "
                    f"Entry: {entry_price:.5f} | "
                    f"Exit: {exit_price:.5f} | "
                    f"P/L: {trade.profit:.2f}"
                )

            # Close all open positions
            for ticket in list(context.account.current_trade.keys()):
                context.account.close_order(ticket)

            # Reward will be calculated by environment based on balance change
            return 0.0

        except Exception as e:
            error_msg = f"❌ ERROR executing CLOSE action on {context.pair.symbol}: {e}"
            if hasattr(self.logger, "log_error"):
                self.logger.log_error(
                    event_type="close_action_error",
                    error=error_msg,
                    symbol=context.pair.symbol,
                    account_login=context.account.login if context.account else None,
                    exc_info=True,
                )
            else:
                self.logger.error(error_msg, exc_info=True)
            return 0.0
