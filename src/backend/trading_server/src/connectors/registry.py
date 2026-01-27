"""
Connector Registry

Manages registration and discovery of data source connectors.
Enables auto-discovery of features from connector schemas.
"""

import logging
import threading
from typing import Dict, List, Optional
from connectors.base import IDataSourceConnector
from domain.models.feature import Feature

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """
    Registry for managing data source connectors and feature discovery.

    Thread-safe registry that allows connectors to be registered,
    and automatically discovers features from connector schemas.
    """

    def __init__(self) -> None:
        """Initialize the registry with thread-safe storage."""
        self._connectors: Dict[str, IDataSourceConnector] = {}
        self._lock = threading.Lock()
        self._metadata: Dict[str, Dict] = (
            {}
        )  # Connector metadata (version, description, etc.)

    def register_connector(
        self,
        name: str,
        connector: IDataSourceConnector,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Register a data source connector instance.

        :param name: Unique name for the connector
        :param connector: IDataSourceConnector instance
        :param metadata: Optional metadata dict (version, description, etc.)
        :raises ValueError: If name is empty or connector is None
        """
        if not name:
            raise ValueError("Connector name cannot be empty")
        if connector is None:
            raise ValueError("Connector cannot be None")

        with self._lock:
            if name in self._connectors:
                logger.warning(f"Connector '{name}' already registered, overwriting")
            self._connectors[name] = connector
            if metadata:
                self._metadata[name] = metadata
            logger.info(f"Registered connector: {name}")

    def discover_features(self) -> List[Feature]:
        """
        Discover features from all registered connectors.

        Extracts features from connector schemas. Each connector's schema
        defines the fields it provides, which are converted to Feature objects.

        :return: List of all discovered features
        """
        all_features = []

        with self._lock:
            connectors_copy = dict(self._connectors)

        for name, connector in connectors_copy.items():
            try:
                schema = connector.get_schema()
                if not isinstance(schema, dict):
                    logger.warning(
                        f"Connector '{name}' returned non-dict from get_schema()"
                    )
                    continue

                # Extract features from schema
                features = self._extract_features_from_schema(name, schema, connector)
                all_features.extend(features)

                logger.debug(
                    f"Discovered {len(features)} features from connector '{name}'"
                )
            except Exception as e:
                logger.error(
                    f"Error discovering features from connector '{name}': {e}",
                    exc_info=True,
                )

        logger.info(
            f"Discovered {len(all_features)} total features from {len(connectors_copy)} connectors"
        )
        return all_features

    def _extract_features_from_schema(
        self, connector_name: str, schema: Dict, connector: IDataSourceConnector
    ) -> List[Feature]:
        """
        Extract Feature objects from connector schema.

        :param connector_name: Name of the connector
        :param schema: Schema dictionary from connector.get_schema()
        :param connector: Connector instance (for accessing config.symbol)
        :return: List of Feature objects
        """
        features = []

        # Get symbol from connector config
        config = getattr(connector, "config", None)
        symbol = getattr(config, "symbol", "unknown") if config else "unknown"
        source = schema.get("source", connector_name)
        data_type = schema.get("data_type", "unknown")

        # Extract fields from schema
        fields = schema.get("fields", {})
        if isinstance(fields, dict):
            for field_name, field_type in fields.items():
                # Skip timestamp and symbol fields (they're metadata, not features)
                if field_name in ["timestamp", "symbol", "datetime"]:
                    continue

                # Map schema types to Python types
                python_type = self._map_schema_type_to_python(field_type)

                feature = Feature(
                    name=f"{field_name}_{symbol}",
                    data_type=python_type,
                    source=f"{source}_{symbol}",
                    description=f"{field_name} for {symbol} from {source}",
                    category=data_type,
                )
                features.append(feature)

        return features

    def _map_schema_type_to_python(self, schema_type: str) -> type:
        """
        Map schema type string to Python type.

        :param schema_type: Type string from schema (e.g., "float", "string")
        :return: Python type
        """
        type_mapping = {
            "float": float,
            "int": int,
            "string": str,
            "bool": bool,
            "datetime": str,  # Datetime stored as string in features
            "datetime (UTC)": str,
        }

        # Handle case-insensitive matching
        schema_type_lower = str(schema_type).lower()
        for key, python_type in type_mapping.items():
            if key in schema_type_lower:
                return python_type

        # Default to float for numeric types
        if any(
            keyword in schema_type_lower for keyword in ["number", "numeric", "decimal"]
        ):
            return float

        # Default to string
        return str

    def get_connector(self, name: str) -> Optional[IDataSourceConnector]:
        """
        Retrieve a connector by name.

        :param name: Connector name
        :return: IDataSourceConnector instance or None if not found
        """
        with self._lock:
            return self._connectors.get(name)

    def list_connectors(self) -> List[str]:
        """
        List all registered connector names.

        :return: List of connector names
        """
        with self._lock:
            return list(self._connectors.keys())

    def get_all_connectors(self) -> Dict[str, IDataSourceConnector]:
        """
        Get all registered connectors.

        :return: Dictionary mapping connector names to instances
        """
        with self._lock:
            return dict(self._connectors)

    def health_check(self, name: Optional[str] = None) -> Dict[str, bool]:
        """
        Check health status of connectors.

        For a specific connector if name is provided, or all connectors if None.
        Checks connection status and data staleness if available.

        :param name: Optional connector name to check (if None, checks all)
        :return: Dictionary mapping connector names to health status (True = healthy)
        """
        health_status = {}

        with self._lock:
            if name:
                connectors_to_check = (
                    {name: self._connectors.get(name)}
                    if name in self._connectors
                    else {}
                )
            else:
                connectors_to_check = dict(self._connectors)

        for connector_name, connector in connectors_to_check.items():
            if connector is None:
                health_status[connector_name] = False
                continue

            try:
                # Check if connector is connected
                if hasattr(connector, "is_connected"):
                    is_connected = connector.is_connected()
                    if not is_connected:
                        health_status[connector_name] = False
                        continue

                # Check if data is stale (if connector supports it)
                if hasattr(connector, "is_stale"):
                    is_stale = connector.is_stale(max_age_seconds=60.0)
                    health_status[connector_name] = not is_stale
                else:
                    # Connector exists and is connected - assume healthy
                    health_status[connector_name] = True
            except Exception as e:
                logger.error(
                    f"Error checking health for connector '{connector_name}': {e}",
                    exc_info=True,
                )
                health_status[connector_name] = False

        return health_status

    def unregister_connector(self, name: str) -> None:
        """
        Unregister a connector.

        :param name: Connector name to remove
        """
        with self._lock:
            if name in self._connectors:
                # Disconnect connector before removing
                connector = self._connectors[name]
                try:
                    if hasattr(connector, "disconnect"):
                        connector.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting connector '{name}': {e}")

                del self._connectors[name]
                if name in self._metadata:
                    del self._metadata[name]
                logger.info(f"Unregistered connector: {name}")
            else:
                logger.warning(
                    f"Attempted to unregister non-existent connector: {name}"
                )

    def get_connector_count(self) -> int:
        """
        Get the number of registered connectors.

        :return: Number of registered connectors
        """
        with self._lock:
            return len(self._connectors)

    def get_connector_metadata(self, name: str) -> Optional[Dict]:
        """
        Get metadata for a connector.

        :param name: Connector name
        :return: Metadata dict or None if not found
        """
        with self._lock:
            return self._metadata.get(name)
