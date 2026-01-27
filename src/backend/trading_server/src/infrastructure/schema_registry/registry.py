"""
Schema Registry - Versioned schema management with compatibility checking
"""

import json
import logging
from typing import Dict, Optional, List, Any
from enum import Enum

from ...database import Database
from .compatibility import CompatibilityChecker, CompatibilityMode, CompatibilityError

logger = logging.getLogger(__name__)


class SchemaStatus(str, Enum):
    """Schema status enumeration"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class SchemaRegistry:
    """
    Schema Registry for managing versioned JSON schemas with compatibility checking.

    Provides Confluent-style schema registry functionality:
    - Register schemas with versioning
    - Retrieve schemas by version or latest
    - Compatibility checking before registration
    - List all versions for a data type
    """

    def __init__(self, database: Optional[Database] = None):
        """
        Initialize Schema Registry

        :param database: Database instance (creates new if not provided)
        """
        self.db = database or Database()
        self.compatibility_checker = CompatibilityChecker()
        logger.info("Schema Registry initialized")

    def register_schema(
        self,
        data_type: str,
        version: str,
        schema: Dict[str, Any],
        compatibility_mode: CompatibilityMode = CompatibilityMode.NONE,
    ) -> bool:
        """
        Register a new schema version with compatibility checking

        :param data_type: Data type identifier (e.g., "tick", "bar")
        :param version: Semantic version (MAJOR.MINOR.PATCH)
        :param schema: JSON Schema definition (Draft 7 format)
        :param compatibility_mode: Compatibility mode (BACKWARD, FORWARD, FULL, NONE)
        :return: True if registered successfully, False otherwise
        :raises CompatibilityError: If compatibility check fails
        """
        # Validate version format (semantic versioning)
        if not self._validate_version_format(version):
            raise ValueError(
                f"Invalid version format: {version}. Expected MAJOR.MINOR.PATCH"
            )

        # Check if version already exists
        existing = self.get_schema(data_type, version)
        if existing:
            raise ValueError(f"Schema version {data_type}:{version} already exists")

        # Get latest version for compatibility check
        latest_schema = self.get_schema(data_type)

        # Perform compatibility check if there's a previous version
        if latest_schema and compatibility_mode != CompatibilityMode.NONE:
            try:
                self.compatibility_checker.validate_compatibility(
                    old_schema=latest_schema["schema_json"],
                    new_schema=schema,
                    mode=compatibility_mode,
                )
            except CompatibilityError as e:
                raise CompatibilityError(
                    f"Compatibility check failed for {data_type}:{version}: {str(e)}"
                ) from e

        # Register schema in database
        try:
            query = """
                INSERT INTO schema_registry (data_type, version, schema_json, compatibility_mode, status)
                VALUES (:data_type, :version, :schema_json, :compatibility_mode, :status)
            """
            params = {
                "data_type": data_type,
                "version": version,
                "schema_json": json.dumps(schema),
                "compatibility_mode": compatibility_mode.value,
                "status": SchemaStatus.ACTIVE.value,
            }

            self.db.execute_one(query, params)
            logger.info(
                f"Registered schema {data_type}:{version} with mode {compatibility_mode.value}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to register schema {data_type}:{version}: {e}")
            raise

    def get_schema(
        self, data_type: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve schema for a data type

        :param data_type: Data type identifier
        :param version: Specific version (None for latest)
        :return: Schema dictionary with keys: id, data_type, version, schema_json,
                 compatibility_mode, status, created_at, updated_at
        """
        if version:
            # Get specific version
            query = """
                SELECT id, data_type, version, schema_json, compatibility_mode, status,
                       created_at, updated_at
                FROM schema_registry
                WHERE data_type = :data_type AND version = :version
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = {"data_type": data_type, "version": version}
        else:
            # Get latest active version
            query = """
                SELECT id, data_type, version, schema_json, compatibility_mode, status,
                       created_at, updated_at
                FROM schema_registry
                WHERE data_type = :data_type AND status = :status
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = {"data_type": data_type, "status": SchemaStatus.ACTIVE.value}

        try:
            result = self.db.execute_one(query, params)
            if not result:
                return None

            # Parse result
            schema_dict = {
                "id": result[0],
                "data_type": result[1],
                "version": result[2],
                "schema_json": (
                    json.loads(result[3]) if isinstance(result[3], str) else result[3]
                ),
                "compatibility_mode": result[4],
                "status": result[5],
                "created_at": result[6],
                "updated_at": result[7],
            }
            return schema_dict

        except Exception as e:
            logger.error(f"Failed to retrieve schema {data_type}:{version}: {e}")
            return None

    def validate_compatibility(
        self,
        old_schema: Dict[str, Any],
        new_schema: Dict[str, Any],
        mode: CompatibilityMode,
    ) -> bool:
        """
        Validate compatibility between two schemas

        :param old_schema: Old schema definition
        :param new_schema: New schema definition
        :param mode: Compatibility mode
        :return: True if compatible, False otherwise
        :raises CompatibilityError: If incompatible
        """
        return self.compatibility_checker.validate_compatibility(
            old_schema, new_schema, mode
        )

    def list_versions(self, data_type: str) -> List[Dict[str, Any]]:
        """
        List all versions for a data type

        :param data_type: Data type identifier
        :return: List of schema dictionaries (sorted by created_at DESC)
        """
        query = """
            SELECT id, data_type, version, schema_json, compatibility_mode, status,
                   created_at, updated_at
            FROM schema_registry
            WHERE data_type = :data_type
            ORDER BY created_at DESC
        """
        params = {"data_type": data_type}

        try:
            results = self.db.execute_with_result(query, params)
            versions = []
            for result in results:
                versions.append(
                    {
                        "id": result[0],
                        "data_type": result[1],
                        "version": result[2],
                        "schema_json": (
                            json.loads(result[3])
                            if isinstance(result[3], str)
                            else result[3]
                        ),
                        "compatibility_mode": result[4],
                        "status": result[5],
                        "created_at": result[6],
                        "updated_at": result[7],
                    }
                )
            return versions

        except Exception as e:
            logger.error(f"Failed to list versions for {data_type}: {e}")
            return []

    def get_latest_version(self, data_type: str) -> Optional[str]:
        """
        Get latest version string for a data type

        :param data_type: Data type identifier
        :return: Latest version string or None
        """
        schema = self.get_schema(data_type)
        return schema["version"] if schema else None

    def _validate_version_format(self, version: str) -> bool:
        """
        Validate semantic version format (MAJOR.MINOR.PATCH)

        :param version: Version string
        :return: True if valid format
        """
        try:
            parts = version.split(".")
            if len(parts) != 3:
                return False
            for part in parts:
                int(part)  # Must be integer
            return True
        except (ValueError, AttributeError):
            return False
