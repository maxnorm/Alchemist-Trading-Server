"""
Feature Catalog

Manages feature metadata in the database.
Stores and retrieves features discovered from data providers.
"""

import logging
import mariadb
from typing import List, Optional
from datetime import datetime
from data_providers.base_provider import Feature
from database import Database

logger = logging.getLogger(__name__)


class FeatureCatalog:
    """
    Catalog for managing feature metadata in the database.

    Stores features discovered from data providers and provides
    query methods to retrieve features by various criteria.
    """

    def __init__(self, database: Database):
        """
        Initialize feature catalog.

        :param database: Database instance for queries
        """
        self.db = database

    def store_features(self, features: List[Feature]) -> None:
        """
        Store features in the database.

        If a feature with the same name exists, it will be updated.
        Otherwise, a new feature will be inserted.

        :param features: List of Feature objects to store
        """
        if not features:
            return

        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            for feature in features:
                try:
                    # Check if feature exists
                    cursor.execute(
                        "SELECT id FROM features WHERE name = %s", (feature.name,)
                    )
                    existing = cursor.fetchone()

                    # Convert Python type to string representation
                    data_type_str = self._type_to_string(feature.data_type)

                    if existing:
                        # Update existing feature
                        cursor.execute(
                            """
                            UPDATE features
                            SET data_type = %s, source = %s, description = %s,
                                category = %s, updated_at = %s
                            WHERE name = %s
                            """,
                            (
                                data_type_str,
                                feature.source,
                                feature.description,
                                feature.category,
                                datetime.utcnow(),
                                feature.name,
                            ),
                        )
                        logger.debug(f"Updated feature: {feature.name}")
                    else:
                        # Insert new feature
                        cursor.execute(
                            """
                            INSERT INTO features
                            (name, data_type, source, description, category, available, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s)
                            """,
                            (
                                feature.name,
                                data_type_str,
                                feature.source,
                                feature.description,
                                feature.category,
                                datetime.utcnow(),
                                datetime.utcnow(),
                            ),
                        )
                        logger.debug(f"Inserted feature: {feature.name}")
                except mariadb.Error as e:
                    logger.error(
                        f"Error storing feature '{feature.name}': {e}", exc_info=True
                    )
                    continue

            conn.commit()
            cursor.close()
            logger.info(f"Stored {len(features)} features in catalog")
        except Exception as e:
            logger.error(f"Error storing features: {e}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def get_all_features(self) -> List[Feature]:
        """
        Retrieve all features from the database.

        :return: List of Feature objects
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT name, data_type, source, description, category, available
                FROM features
                ORDER BY source, category, name
                """
            )

            rows = cursor.fetchall()
            features = []

            for row in rows:
                name, data_type_str, source, description, category, available = row

                # Skip unavailable features
                if not available:
                    continue

                # Convert string type back to Python type
                data_type = self._string_to_type(data_type_str)

                feature = Feature(
                    name=name,
                    data_type=data_type,
                    source=source,
                    description=description or "",
                    category=category,
                )
                features.append(feature)

            cursor.close()
            return features
        except Exception as e:
            logger.error(f"Error retrieving features: {e}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()

    def get_features_by_source(self, source: str) -> List[Feature]:
        """
        Get features filtered by provider source.

        :param source: Provider source name
        :return: List of Feature objects
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT name, data_type, source, description, category, available
                FROM features
                WHERE source = %s AND available = TRUE
                ORDER BY category, name
                """,
                (source,),
            )

            rows = cursor.fetchall()
            features = []

            for row in rows:
                name, data_type_str, source_val, description, category, available = row
                data_type = self._string_to_type(data_type_str)

                feature = Feature(
                    name=name,
                    data_type=data_type,
                    source=source_val,
                    description=description or "",
                    category=category,
                )
                features.append(feature)

            cursor.close()
            return features
        except Exception as e:
            logger.error(
                f"Error retrieving features by source '{source}': {e}", exc_info=True
            )
            return []
        finally:
            if conn:
                conn.close()

    def get_features_by_category(self, category: str) -> List[Feature]:
        """
        Get features filtered by category.

        :param category: Feature category
        :return: List of Feature objects
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT name, data_type, source, description, category, available
                FROM features
                WHERE category = %s AND available = TRUE
                ORDER BY source, name
                """,
                (category,),
            )

            rows = cursor.fetchall()
            features = []

            for row in rows:
                name, data_type_str, source, description, category_val, available = row
                data_type = self._string_to_type(data_type_str)

                feature = Feature(
                    name=name,
                    data_type=data_type,
                    source=source,
                    description=description or "",
                    category=category_val,
                )
                features.append(feature)

            cursor.close()
            return features
        except Exception as e:
            logger.error(
                f"Error retrieving features by category '{category}': {e}",
                exc_info=True,
            )
            return []
        finally:
            if conn:
                conn.close()

    def get_feature(self, name: str) -> Optional[Feature]:
        """
        Get a single feature by name.

        :param name: Feature name
        :return: Feature object or None if not found
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT name, data_type, source, description, category, available
                FROM features
                WHERE name = %s AND available = TRUE
                """,
                (name,),
            )

            row = cursor.fetchone()
            cursor.close()

            if row:
                name_val, data_type_str, source, description, category, available = row
                data_type = self._string_to_type(data_type_str)

                return Feature(
                    name=name_val,
                    data_type=data_type,
                    source=source,
                    description=description or "",
                    category=category,
                )

            return None
        except Exception as e:
            logger.error(f"Error retrieving feature '{name}': {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()

    def update_feature_availability(self, name: str, available: bool) -> None:
        """
        Update feature availability status.

        :param name: Feature name
        :param available: Availability status
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE features
                SET available = %s, updated_at = %s
                WHERE name = %s
                """,
                (available, datetime.utcnow(), name),
            )

            conn.commit()
            cursor.close()
            logger.info(f"Updated availability for feature '{name}': {available}")
        except Exception as e:
            logger.error(
                f"Error updating feature availability '{name}': {e}", exc_info=True
            )
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def sync_with_registry(self, registry) -> None:
        """
        Sync catalog with features discovered from registry.

        :param registry: DataProviderRegistry instance
        """
        try:
            features = registry.discover_features()
            self.store_features(features)
            logger.info(f"Synced {len(features)} features from registry to catalog")
        except Exception as e:
            logger.error(f"Error syncing registry with catalog: {e}", exc_info=True)

    def _type_to_string(self, data_type: type) -> str:
        """
        Convert Python type to string representation for database storage.

        :param data_type: Python type
        :return: String representation
        """
        type_map = {
            float: "float",
            int: "int",
            str: "str",
            bool: "bool",
        }
        return type_map.get(data_type, str(data_type.__name__))

    def _string_to_type(self, type_str: str) -> type:
        """
        Convert string type representation back to Python type.

        :param type_str: String type representation
        :return: Python type
        """
        type_map = {
            "float": float,
            "int": int,
            "str": str,
            "bool": bool,
        }
        return type_map.get(type_str.lower(), float)  # Default to float if unknown
