"""
Feature Catalog

Manages feature metadata in the database.
Stores and retrieves features discovered from data providers.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
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

        try:
            with self.db.execute_query() as conn:
                for feature in features:
                    try:
                        # Check if feature exists
                        existing = conn.execute(
                            text("SELECT id FROM features WHERE name = :name"),
                            {"name": feature.name},
                        ).fetchone()

                        # Convert Python type to string representation
                        data_type_str = self._type_to_string(feature.data_type)

                        if existing:
                            # Update existing feature
                            query = """
                                UPDATE features
                                SET data_type = :data_type, source = :source, description = :description,
                                    category = :category, updated_at = :updated_at
                                WHERE name = :name
                            """
                            params = {
                                "data_type": data_type_str,
                                "source": feature.source,
                                "description": feature.description,
                                "category": feature.category,
                                "updated_at": datetime.utcnow(),
                                "name": feature.name,
                            }
                            conn.execute(text(query), params)
                            logger.debug(f"Updated feature: {feature.name}")
                        else:
                            # Insert new feature
                            query = """
                                INSERT INTO features
                                (name, data_type, source, description, category, available,
                                 created_at, updated_at)
                                VALUES (:name, :data_type, :source, :description, :category, TRUE,
                                        :created_at, :updated_at)
                            """
                            params = {
                                "name": feature.name,
                                "data_type": data_type_str,
                                "source": feature.source,
                                "description": feature.description,
                                "category": feature.category,
                                "created_at": datetime.utcnow(),
                                "updated_at": datetime.utcnow(),
                            }
                            conn.execute(text(query), params)
                            logger.debug(f"Inserted feature: {feature.name}")
                    except SQLAlchemyError as e:
                        logger.error(
                            f"Error storing feature '{feature.name}': {e}",
                            exc_info=True,
                        )
                        continue

            logger.info(f"Stored {len(features)} features in catalog")
        except SQLAlchemyError as e:
            logger.error(f"Error storing features: {e}", exc_info=True)

    def get_all_features(self) -> List[Feature]:
        """
        Retrieve all features from the database.

        :return: List of Feature objects
        """
        try:
            query = """
                SELECT name, data_type, source, description, category, available
                FROM features
                ORDER BY source, category, name
            """

            rows = self.db.execute_with_result(query)
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

            return features
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving features: {e}", exc_info=True)
            return []

    def get_features_by_source(self, source: str) -> List[Feature]:
        """
        Get features filtered by provider source.

        :param source: Provider source name
        :return: List of Feature objects
        """
        try:
            query = """
                SELECT name, data_type, source, description, category, available
                FROM features
                WHERE source = :source AND available = TRUE
                ORDER BY category, name
            """

            params = {"source": source}
            rows = self.db.execute_with_result(query, params)
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

            return features
        except SQLAlchemyError as e:
            logger.error(
                f"Error retrieving features by source '{source}': {e}", exc_info=True
            )
            return []

    def get_features_by_category(self, category: str) -> List[Feature]:
        """
        Get features filtered by category.

        :param category: Feature category
        :return: List of Feature objects
        """
        try:
            query = """
                SELECT name, data_type, source, description, category, available
                FROM features
                WHERE category = :category AND available = TRUE
                ORDER BY source, name
            """

            params = {"category": category}
            rows = self.db.execute_with_result(query, params)
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

            return features
        except SQLAlchemyError as e:
            logger.error(
                f"Error retrieving features by category '{category}': {e}",
                exc_info=True,
            )
            return []

    def get_feature(self, name: str) -> Optional[Feature]:
        """
        Get a single feature by name.

        :param name: Feature name
        :return: Feature object or None if not found
        """
        try:
            query = """
                SELECT name, data_type, source, description, category, available
                FROM features
                WHERE name = :name AND available = TRUE
            """

            params = {"name": name}
            row = self.db.execute_one(query, params)

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
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving feature '{name}': {e}", exc_info=True)
            return None

    def update_feature_availability(self, name: str, available: bool) -> None:
        """
        Update feature availability status.

        :param name: Feature name
        :param available: Availability status
        """
        try:
            query = """
                UPDATE features
                SET available = :available, updated_at = :updated_at
                WHERE name = :name
            """

            params = {
                "available": available,
                "updated_at": datetime.utcnow(),
                "name": name,
            }

            with self.db.execute_query() as conn:
                conn.execute(text(query), params)

            logger.info(f"Updated availability for feature '{name}': {available}")
        except SQLAlchemyError as e:
            logger.error(
                f"Error updating feature availability '{name}': {e}", exc_info=True
            )

    def sync_with_registry(self, registry) -> None:
        """
        Sync catalog with features discovered from registry.

        :param registry: DataProviderRegistry or ConnectorRegistry instance
        """
        try:
            features = registry.discover_features()
            self.store_features(features)
            logger.info(f"Synced {len(features)} features from registry to catalog")
        except Exception as e:
            logger.error(f"Error syncing registry with catalog: {e}", exc_info=True)

    def sync_with_connector_registry(self, connector_registry) -> None:
        """
        Sync catalog with features discovered from connector registry.

        :param connector_registry: ConnectorRegistry instance
        """
        try:
            features = connector_registry.discover_features()
            self.store_features(features)
            logger.info(
                f"Synced {len(features)} features from connector registry to catalog"
            )
        except Exception as e:
            logger.error(
                f"Error syncing connector registry with catalog: {e}", exc_info=True
            )

    def get_features_by_pipeline_version(self, pipeline_version: str) -> List[Feature]:
        """
        Get features for a specific pipeline version.

        :param pipeline_version: Pipeline version string
        :return: List of Feature objects
        """
        try:
            query = """
                SELECT name, data_type, source, description, category, available
                FROM features
                WHERE pipeline_version = :pipeline_version AND available = TRUE
                ORDER BY category, name
            """

            params = {"pipeline_version": pipeline_version}
            rows = self.db.execute_with_result(query, params)
            features = []

            for row in rows:
                name, data_type_str, source, description, category, available = row
                data_type = self._string_to_type(data_type_str)

                feature = Feature(
                    name=name,
                    data_type=data_type,
                    source=source,
                    description=description or "",
                    category=category,
                )
                features.append(feature)

            return features
        except SQLAlchemyError as e:
            logger.error(
                f"Error retrieving features by pipeline version '{pipeline_version}': {e}",
                exc_info=True,
            )
            return []

    def get_feature_history(self, feature_name: str) -> List[Dict[str, Any]]:
        """
        Track feature changes across pipeline versions.

        :param feature_name: Feature name
        :return: List of dictionaries with version history
        """
        try:
            query = """
                SELECT pipeline_version, first_seen_version, created_at, updated_at
                FROM features
                WHERE name = :feature_name
                ORDER BY created_at
            """

            params = {"feature_name": feature_name}
            rows = self.db.execute_with_result(query, params)
            history = []

            for row in rows:
                pipeline_version, first_seen_version, created_at, updated_at = row
                history.append(
                    {
                        "pipeline_version": pipeline_version,
                        "first_seen_version": first_seen_version,
                        "created_at": created_at.isoformat() if created_at else None,
                        "updated_at": updated_at.isoformat() if updated_at else None,
                    }
                )

            return history
        except SQLAlchemyError as e:
            logger.error(
                f"Error retrieving feature history for '{feature_name}': {e}",
                exc_info=True,
            )
            return []

    def compare_versions(self, version1: str, version2: str) -> Dict[str, Any]:
        """
        Compare feature sets between two pipeline versions.

        :param version1: First pipeline version
        :param version2: Second pipeline version
        :return: Dictionary with comparison results
        """
        features1 = {f.name for f in self.get_features_by_pipeline_version(version1)}
        features2 = {f.name for f in self.get_features_by_pipeline_version(version2)}

        added = features2 - features1
        removed = features1 - features2
        common = features1 & features2

        return {
            "version1": version1,
            "version2": version2,
            "added_features": list(added),
            "removed_features": list(removed),
            "common_features": list(common),
            "version1_count": len(features1),
            "version2_count": len(features2),
            "added_count": len(added),
            "removed_count": len(removed),
            "common_count": len(common),
        }

    def update_feature_pipeline_version(
        self, feature_name: str, pipeline_version: str
    ) -> None:
        """
        Update the pipeline version for a feature.

        :param feature_name: Feature name
        :param pipeline_version: Pipeline version string
        """
        try:
            # Check if feature exists and get current first_seen_version
            row = self.db.execute_one(
                "SELECT first_seen_version FROM features WHERE name = :feature_name",
                {"feature_name": feature_name},
            )

            with self.db.execute_query() as conn:
                if row:
                    first_seen_version = row[0]
                    # If first_seen_version is not set, set it to current version
                    if not first_seen_version:
                        first_seen_version = pipeline_version

                    query = """
                        UPDATE features
                        SET pipeline_version = :pipeline_version,
                            first_seen_version = :first_seen_version,
                            updated_at = :updated_at
                        WHERE name = :feature_name
                    """
                    params = {
                        "pipeline_version": pipeline_version,
                        "first_seen_version": first_seen_version,
                        "updated_at": datetime.utcnow(),
                        "feature_name": feature_name,
                    }
                    conn.execute(text(query), params)
                else:
                    # Feature doesn't exist, create it with pipeline version
                    query = """
                        INSERT INTO features
                        (name, data_type, source, description, category, available,
                         pipeline_version, first_seen_version, created_at, updated_at)
                        VALUES (:name, :data_type, :source, :description, :category, TRUE,
                                :pipeline_version, :first_seen_version, :created_at, :updated_at)
                    """
                    params = {
                        "name": feature_name,
                        "data_type": "float",  # Default type
                        "source": "feature_engine",  # Default source
                        "description": f"Feature from pipeline {pipeline_version}",
                        "category": None,
                        "pipeline_version": pipeline_version,
                        "first_seen_version": pipeline_version,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                    conn.execute(text(query), params)

            logger.info(
                f"Updated feature '{feature_name}' to pipeline version {pipeline_version}"
            )
        except SQLAlchemyError as e:
            logger.error(f"Error updating feature pipeline version: {e}", exc_info=True)

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
