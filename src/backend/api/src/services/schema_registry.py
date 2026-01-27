"""
Schema Registry Service
Wraps the Schema Registry for use in the FastAPI service
"""

import json
import logging
from typing import Dict, Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class SchemaRegistryService:
    """
    Service layer for Schema Registry operations
    Uses SQLAlchemy sessions for database access
    """

    @staticmethod
    def get_schema(
        db: Session, data_type: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve schema for a data type

        :param db: Database session
        :param data_type: Data type identifier
        :param version: Specific version (None for latest)
        :return: Schema dictionary or None
        """
        if version:
            query = text("""
                SELECT id, data_type, version, schema_json, compatibility_mode, status,
                       created_at, updated_at
                FROM schema_registry
                WHERE data_type = :data_type AND version = :version
                ORDER BY created_at DESC
                LIMIT 1
            """)
            params = {"data_type": data_type, "version": version}
        else:
            query = text("""
                SELECT id, data_type, version, schema_json, compatibility_mode, status,
                       created_at, updated_at
                FROM schema_registry
                WHERE data_type = :data_type AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
            """)
            params = {"data_type": data_type}

        try:
            result = db.execute(query, params)
            row = result.fetchone()
            if not row:
                return None

            return {
                "id": row[0],
                "data_type": row[1],
                "version": row[2],
                "schema_json": (
                    json.loads(row[3]) if isinstance(row[3], str) else row[3]
                ),
                "compatibility_mode": row[4],
                "status": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
        except Exception as e:
            logger.error(f"Failed to retrieve schema {data_type}:{version}: {e}")
            raise

    @staticmethod
    def list_versions(db: Session, data_type: str) -> List[Dict[str, Any]]:
        """
        List all versions for a data type

        :param db: Database session
        :param data_type: Data type identifier
        :return: List of schema dictionaries
        """
        query = text("""
            SELECT id, data_type, version, schema_json, compatibility_mode, status,
                   created_at, updated_at
            FROM schema_registry
            WHERE data_type = :data_type
            ORDER BY created_at DESC
        """)
        params = {"data_type": data_type}

        try:
            result = db.execute(query, params)
            versions = []
            for row in result:
                versions.append(
                    {
                        "id": row[0],
                        "data_type": row[1],
                        "version": row[2],
                        "schema_json": (
                            json.loads(row[3]) if isinstance(row[3], str) else row[3]
                        ),
                        "compatibility_mode": row[4],
                        "status": row[5],
                        "created_at": row[6],
                        "updated_at": row[7],
                    }
                )
            return versions
        except Exception as e:
            logger.error(f"Failed to list versions for {data_type}: {e}")
            raise

    @staticmethod
    def register_schema(
        db: Session,
        data_type: str,
        version: str,
        schema: Dict[str, Any],
        compatibility_mode: str = "NONE",
    ) -> Dict[str, Any]:
        """
        Register a new schema version

        :param db: Database session
        :param data_type: Data type identifier
        :param version: Semantic version
        :param schema: JSON Schema definition
        :param compatibility_mode: Compatibility mode
        :return: Registered schema dictionary
        """
        # Validate version format
        parts = version.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid version format: {version}. Expected MAJOR.MINOR.PATCH"
            )
        for part in parts:
            int(part)  # Validate it's an integer

        # Check if version already exists
        existing = SchemaRegistryService.get_schema(db, data_type, version)
        if existing:
            raise ValueError(f"Schema version {data_type}:{version} already exists")

        # Insert new schema
        query = text("""
            INSERT INTO schema_registry (data_type, version, schema_json, compatibility_mode, status)
            VALUES (:data_type, :version, :schema_json, :compatibility_mode, 'active')
            RETURNING id, data_type, version, schema_json, compatibility_mode, status,
                      created_at, updated_at
        """)
        params = {
            "data_type": data_type,
            "version": version,
            "schema_json": json.dumps(schema),
            "compatibility_mode": compatibility_mode,
        }

        try:
            result = db.execute(query, params)
            db.commit()
            row = result.fetchone()
            return {
                "id": row[0],
                "data_type": row[1],
                "version": row[2],
                "schema_json": (
                    json.loads(row[3]) if isinstance(row[3], str) else row[3]
                ),
                "compatibility_mode": row[4],
                "status": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to register schema {data_type}:{version}: {e}")
            raise
