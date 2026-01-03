"""
Action executor service
Centralized service for executing trading actions using strategies
"""
import logging
from typing import Optional, Any

from domain.action_type import ActionType
from domain.execution_context import ExecutionContext
from domain.strategies.action_strategy import ActionStrategy
from domain.strategies.hold_action_strategy import HoldActionStrategy
from domain.strategies.buy_action_strategy import BuyActionStrategy
from domain.strategies.sell_action_strategy import SellActionStrategy
from domain.strategies.close_action_strategy import CloseActionStrategy


class ActionExecutor:
    """
    Service for executing trading actions using strategy pattern
    """
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        self._strategies = {
            ActionType.HOLD: HoldActionStrategy(self.logger),
            ActionType.BUY: BuyActionStrategy(self.logger),
            ActionType.SELL: SellActionStrategy(self.logger),
            ActionType.CLOSE: CloseActionStrategy(self.logger),
        }
    
    def execute(
        self,
        action: int,
        environment,
        account,
        risk_manager,
        previous_balance: float,
        trading_enabled: bool = False,
        model_id: Optional[int] = None,
        session_id: Optional[int] = None,
        trade_logger: Optional[Any] = None
    ) -> float:
        """
        Execute an action and return reward
        :param action: Encoded action
                0 = Global HOLD (no pair)
                1+ = 1 + (pair_index * 3 + action_type_offset)
        :param environment: Trading environment
        :param account: Account instance
        :param risk_manager: Risk manager instance
        :param previous_balance: Previous account balance
        :param trading_enabled: Whether trading is enabled
        :return: Reward value
        """
        # Handle global HOLD action (action 0)
        if action == 0:
            # HOLD doesn't need a pair - execute directly
            has_position = len(account.current_trade) > 0 if account else False
            # Use first pair for context if available, or None
            pair = environment.data_providers[0].currency_pair if environment.data_providers else None
            context = ExecutionContext(
                account=account,
                pair=pair,
                environment=environment,
                risk_manager=risk_manager,
                previous_balance=previous_balance,
                has_position=has_position,
                trading_enabled=trading_enabled,
                model_id=model_id,
                session_id=session_id,
                trade_logger=trade_logger
            )
            strategy = self._strategies.get(ActionType.HOLD)
            if strategy:
                try:
                    return strategy.execute(context)
                except Exception as e:
                    if hasattr(self.logger, 'log_error'):
                        self.logger.log_error(
                            event_type='action_execution_error',
                            error=f"Error executing HOLD action: {e}",
                            exc_info=True
                        )
                    else:
                        self.logger.error(f"Error executing HOLD action: {e}", exc_info=True)
            return 0.0
        
        # Decode action to get pair_index and action_type
        pair_index, action_type = environment.decode_action(action)
        
        # Validate pair_index
        if pair_index is None or not environment.data_providers or pair_index >= len(environment.data_providers):
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='invalid_pair_index',
                    message=f"Invalid pair_index: {pair_index}",
                    metrics={'pair_index': pair_index},
                    level='WARNING'
                )
            else:
                self.logger.warning(f"Invalid pair_index: {pair_index}")
            return 0.0
        
        # Get currency pair for the selected pair_index
        pair = environment.data_providers[pair_index].currency_pair
        
        if pair is None:
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='pair_not_found',
                    message=f"Pair is None for index {pair_index}",
                    metrics={'pair_index': pair_index},
                    level='WARNING'
                )
            else:
                self.logger.warning(f"Pair is None for index {pair_index}")
            return 0.0
        
        # Create execution context
        has_position = len(account.current_trade) > 0 if account else False
        context = ExecutionContext(
            account=account,
            pair=pair,
            environment=environment,
            risk_manager=risk_manager,
            previous_balance=previous_balance,
            has_position=has_position,
            trading_enabled=trading_enabled,
            model_id=model_id,
            session_id=session_id,
            trade_logger=trade_logger
        )
        
        # Get strategy for action type
        strategy = self._strategies.get(action_type)
        if strategy is None:
            if hasattr(self.logger, 'log_error'):
                self.logger.log_error(
                    event_type='strategy_not_found',
                    error=f"No strategy found for action type: {action_type}",
                    metrics={'action_type': str(action_type)},
                    exc_info=False
                )
            else:
                self.logger.error(f"No strategy found for action type: {action_type}")
            return 0.0
        
        # Execute strategy
        try:
            reward = strategy.execute(context)
            return reward
        except Exception as e:
            if hasattr(self.logger, 'log_error'):
                self.logger.log_error(
                    event_type='action_execution_error',
                    error=f"Error executing action {action} ({action_type} on {pair.symbol}): {e}",
                    symbol=pair.symbol,
                    account_login=account.login if account else None,
                    metrics={
                        'action': action,
                        'action_type': str(action_type)
                    },
                    exc_info=True
                )
            else:
                self.logger.error(
                    f"Error executing action {action} ({action_type} on {pair.symbol}): {e}",
                    exc_info=True
                )
            return 0.0
    
    def get_strategy(self, action_type: ActionType) -> Optional[ActionStrategy]:
        """
        Get strategy for action type
        :param action_type: Action type enum
        :return: Strategy instance or None
        """
        return self._strategies.get(action_type)
    
    def register_strategy(self, action_type: ActionType, strategy: ActionStrategy):
        """
        Register a custom strategy (for extensibility)
        :param action_type: Action type enum
        :param strategy: Strategy instance
        """
        self._strategies[action_type] = strategy
        if hasattr(self.logger, 'log_event'):
            self.logger.log_event(
                event_type='strategy_registered',
                message=f"Registered custom strategy for {action_type}",
                metrics={'action_type': str(action_type)}
            )
        else:
            self.logger.info(f"Registered custom strategy for {action_type}")
