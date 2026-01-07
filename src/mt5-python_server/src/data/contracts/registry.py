"""
Contract registry for managing and retrieving validators
"""

from typing import Dict, Optional
from .base import IContractValidator
from .tick_contract import TickContractValidator
from .bar_contract import BarContractValidator
from .news_contract import NewsContractValidator
from .economic_contract import EconomicContractValidator


class ContractRegistry:
    """
    Registry for schema contract validators
    Provides a central place to register and retrieve validators by data type
    """

    def __init__(self):
        """Initialize registry with default validators"""
        self._validators: Dict[str, IContractValidator] = {}
        self._register_default_validators()

    def _register_default_validators(self):
        """Register default validators for known data types"""
        # Register tick validator
        tick_validator = TickContractValidator()
        self.register(tick_validator.get_data_type(), tick_validator)

        # Register bar validator
        bar_validator = BarContractValidator()
        self.register(bar_validator.get_data_type(), bar_validator)

        # Register news validator
        news_validator = NewsContractValidator()
        self.register(news_validator.get_data_type(), news_validator)

        # Register economic validator
        economic_validator = EconomicContractValidator()
        self.register(economic_validator.get_data_type(), economic_validator)

    def register(self, data_type: str, validator: IContractValidator):
        """
        Register a validator for a data type

        :param data_type: Data type identifier (e.g., "tick", "bar")
        :param validator: Validator instance
        """
        self._validators[data_type] = validator

    def get_validator(self, data_type: str) -> Optional[IContractValidator]:
        """
        Get validator for a data type

        :param data_type: Data type identifier
        :return: Validator instance or None if not found
        """
        return self._validators.get(data_type)

    def validate(self, data_type: str, data: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate data using the appropriate validator

        :param data_type: Data type identifier
        :param data: Data dictionary to validate
        :return: Tuple of (is_valid, error_message)
        """
        validator = self.get_validator(data_type)
        if validator is None:
            return False, f"No validator registered for data type: {data_type}"

        return validator.validate(data)

    def list_data_types(self) -> list[str]:
        """
        List all registered data types

        :return: List of data type identifiers
        """
        return list(self._validators.keys())


# Global registry instance
_global_registry = ContractRegistry()


def get_contract_registry() -> ContractRegistry:
    """Get global contract registry instance"""
    return _global_registry
