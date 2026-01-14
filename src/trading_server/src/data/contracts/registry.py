"""
Contract registry for managing and retrieving validators
"""

import logging
from typing import Dict, Optional
from .base import IContractValidator
from .tick_contract import TickContractValidator
from .bar_contract import BarContractValidator
from .news_contract import NewsContractValidator
from .economic_contract import EconomicContractValidator

logger = logging.getLogger(__name__)


class ContractRegistry:
    """
    Registry for schema contract validators
    Provides a central place to register and retrieve validators by data type

    Integrates with Schema Registry for versioned schema management
    """

    def __init__(self, schema_registry=None) -> None:
        """
        Initialize registry with default validators

        :param schema_registry: Optional SchemaRegistry instance for schema versioning
        """
        self._validators: Dict[str, IContractValidator] = {}
        self._schema_registry = schema_registry
        self._register_default_validators()

        # Register contracts with Schema Registry if available
        if self._schema_registry:
            self._register_with_schema_registry()

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

    def _register_with_schema_registry(self):
        """Register all validators with Schema Registry"""
        if not self._schema_registry:
            return

        try:
            from infrastructure.schema_registry.schema_converter import (
                contract_to_json_schema,
            )
            from infrastructure.schema_registry.compatibility import CompatibilityMode

            for data_type, validator in self._validators.items():
                try:
                    # Convert contract to JSON Schema
                    json_schema = contract_to_json_schema(validator)
                    version = validator.get_contract_version()

                    # Check if schema already exists
                    existing = self._schema_registry.get_schema(data_type, version)
                    if existing:
                        logger.debug(f"Schema {data_type}:{version} already registered")
                        continue

                    # Register with BACKWARD compatibility by default
                    # This allows adding optional fields in future versions
                    self._schema_registry.register_schema(
                        data_type=data_type,
                        version=version,
                        schema=json_schema,
                        compatibility_mode=CompatibilityMode.BACKWARD,
                    )
                    logger.info(
                        f"Registered schema {data_type}:{version} with Schema Registry"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to register schema for {data_type}:{version}: {e}"
                    )
        except ImportError as e:
            logger.warning(f"Schema Registry integration not available: {e}")

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

        Optionally checks schema version if Schema Registry is available

        :param data_type: Data type identifier
        :param data: Data dictionary to validate
        :return: Tuple of (is_valid, error_message)
        """
        validator = self.get_validator(data_type)
        if validator is None:
            return False, f"No validator registered for data type: {data_type}"

        # Optional: Check schema version if Schema Registry is available
        # This is a lightweight check - full validation still done by contract validator
        if self._schema_registry:
            try:
                latest_schema = self._schema_registry.get_schema(data_type)
                if latest_schema:
                    # Schema version check passed (schema exists)
                    # Full validation will be done by contract validator below
                    pass
            except Exception as e:
                logger.debug(f"Schema version check skipped for {data_type}: {e}")

        return validator.validate(data)

    def get_schema_info(self, data_type: str) -> Dict[str, Optional[str]]:
        """
        Get schema version and type information for a data type.
        Useful for storing schema metadata in data records.

        :param data_type: Data type identifier
        :return: Dictionary with 'schema_version' and 'schema_type' keys
        """
        return {
            "schema_version": self.get_schema_version(data_type),
            "schema_type": self.get_schema_type(data_type),
        }

    def get_schema_version(self, data_type: str) -> Optional[str]:
        """
        Get schema version for a data type

        :param data_type: Data type identifier
        :return: Schema version string or None
        """
        validator = self.get_validator(data_type)
        if validator:
            return validator.get_contract_version()
        return None

    def get_schema_type(self, data_type: str) -> Optional[str]:
        """
        Get schema type (same as data_type) for a data type

        :param data_type: Data type identifier
        :return: Schema type string or None
        """
        validator = self.get_validator(data_type)
        if validator:
            return validator.get_data_type()
        return None

    def list_data_types(self) -> list[str]:
        """
        List all registered data types

        :return: List of data type identifiers
        """
        return list(self._validators.keys())


# Global registry instance
_global_registry: Optional[ContractRegistry] = None


def get_contract_registry() -> ContractRegistry:
    """
    Get global contract registry instance.
    Initializes with Schema Registry integration if available.
    """
    global _global_registry

    if _global_registry is None:
        # Try to initialize with Schema Registry
        schema_registry = None
        try:
            from infrastructure.schema_registry.registry import SchemaRegistry

            schema_registry = SchemaRegistry()
            logger.info(
                "Contract Registry initialized with Schema Registry integration"
            )
        except Exception as e:
            logger.warning(
                f"Schema Registry not available, initializing without it: {e}"
            )

        _global_registry = ContractRegistry(schema_registry=schema_registry)

    return _global_registry
