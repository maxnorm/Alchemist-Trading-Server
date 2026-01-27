"""
Base action strategy interface
"""

from abc import ABC, abstractmethod
from typing import Tuple

from domain.execution_context import ExecutionContext


class ActionStrategy(ABC):
    """Abstract base class for action strategies"""

    @abstractmethod
    def execute(self, context: ExecutionContext) -> float:
        """
        Execute the action strategy
        :param context: Execution context
        :return: Reward value
        """
        pass

    @abstractmethod
    def can_execute(self, context: ExecutionContext) -> Tuple[bool, str]:
        """
        Check if action can be executed
        :param context: Execution context
        :return: Tuple of (can_execute: bool, reason: str)
        """
        pass

    @property
    @abstractmethod
    def action_type(self):
        """Get the action type this strategy handles"""
        pass
