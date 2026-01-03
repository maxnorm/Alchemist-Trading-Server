"""
Hold action strategy
No-op strategy for holding position
"""

import logging
from typing import Tuple

from domain.action_type import ActionType
from domain.execution_context import ExecutionContext
from domain.strategies.action_strategy import ActionStrategy


class HoldActionStrategy(ActionStrategy):
    """Strategy for HOLD action (no operation)"""

    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)

    @property
    def action_type(self):
        return ActionType.HOLD

    def can_execute(self, context: ExecutionContext) -> Tuple[bool, str]:
        """Hold can always be executed"""
        return True, "Hold action always allowed"

    def execute(self, context: ExecutionContext) -> float:
        """
        Execute hold action (no operation)
        :param context: Execution context
        :return: Reward (0.0 for hold)
        """
        symbol = context.pair.symbol if context.pair else "N/A"
        if hasattr(self.logger, "log_event"):
            self.logger.log_event(
                event_type="hold_action",
                message="HOLD action: No action taken",
                symbol=symbol if symbol != "N/A" else None,
                level="DEBUG",
            )
        else:
            self.logger.debug("HOLD action: No action taken")
        return 0.0
