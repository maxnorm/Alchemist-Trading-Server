"""
Feature Registry Module

Centralized registry for feature pipeline versions and metadata.
Tracks feature computation code versions, stores feature definitions,
and enables feature rollback and reproducibility.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import Database

logger = logging.getLogger(__name__)


@dataclass
class FeaturePipelineVersion:
    """Feature pipeline version metadata"""

    version: str  # Semantic version: "v1.2.0"
    pipeline_hash: str  # Hash of feature computation code
    feature_list: List[str]  # List of feature names
    feature_definitions: Dict[str, Any]  # Feature metadata
    created_at: datetime
    code_commit: Optional[str] = None  # Git commit hash
    id: Optional[int] = None  # Database ID

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "version": self.version,
            "pipeline_hash": self.pipeline_hash,
            "feature_list": self.feature_list,
            "feature_definitions": self.feature_definitions,
            "created_at": (
                self.created_at.isoformat()
                if isinstance(self.created_at, datetime)
                else self.created_at
            ),
            "code_commit": self.code_commit,
        }


class FeatureRegistry:
    """
    Centralized registry for feature pipeline versions.

    Provides methods for:
    - Registering new feature pipeline versions
    - Retrieving pipeline versions by version or hash
    - Listing all registered versions
    - Getting features for a specific version
    """

    def __init__(self, database: Database):
        """
        Initialize feature registry.

        :param database: Database instance for queries
        """
        self.db = database

    def register_pipeline(
        self,
        version: str,
        pipeline_hash: str,
        feature_list: List[str],
        feature_definitions: Dict[str, Any],
        code_commit: Optional[str] = None,
    ) -> FeaturePipelineVersion:
        """
        Register a new feature pipeline version.

        :param version: Semantic version string (e.g., "v1.2.0")
        :param pipeline_hash: Hash of feature computation code
        :param feature_list: List of feature names
        :param feature_definitions: Feature metadata dictionary
        :param code_commit: Optional git commit hash
        :return: Registered FeaturePipelineVersion
        """
        try:
            # Check if version already exists
            existing = self.db.execute_one(
                "SELECT id FROM feature_pipelines WHERE version = :version",
                {"version": version},
            )

            if existing:
                logger.warning(
                    f"Pipeline version {version} already exists, updating..."
                )
                # Update existing version
                query = """
                    UPDATE feature_pipelines
                    SET pipeline_hash = :pipeline_hash,
                        feature_list = :feature_list,
                        feature_definitions = :feature_definitions,
                        code_commit = :code_commit
                    WHERE version = :version
                """
                params = {
                    "pipeline_hash": pipeline_hash,
                    "feature_list": json.dumps(feature_list),
                    "feature_definitions": json.dumps(feature_definitions),
                    "code_commit": code_commit,
                    "version": version,
                }
                with self.db.execute_query() as conn:
                    conn.execute(text(query), params)
                pipeline_id = existing[0]
            else:
                # Insert new version
                query = """
                    INSERT INTO feature_pipelines
                    (version, pipeline_hash, feature_list, feature_definitions, code_commit)
                    VALUES (:version, :pipeline_hash, :feature_list, :feature_definitions, :code_commit)
                    RETURNING id
                """
                params = {
                    "version": version,
                    "pipeline_hash": pipeline_hash,
                    "feature_list": json.dumps(feature_list),
                    "feature_definitions": json.dumps(feature_definitions),
                    "code_commit": code_commit,
                }
                result = self.db.execute_one(query, params)
                if result:
                    pipeline_id = result[0]
                else:
                    raise RuntimeError("Failed to insert pipeline version")

            logger.info(
                f"Registered feature pipeline version {version} (ID: {pipeline_id})"
            )

            # Return the registered version
            registered_version = self.get_pipeline_version(version)
            if registered_version is None:
                raise RuntimeError(
                    f"Failed to retrieve registered pipeline version {version}"
                )
            return registered_version

        except SQLAlchemyError as e:
            logger.error(f"Error registering pipeline version: {e}", exc_info=True)
            raise

    def get_pipeline_version(self, version: str) -> Optional[FeaturePipelineVersion]:
        """
        Retrieve pipeline version by version string.

        :param version: Version string (e.g., "v1.2.0")
        :return: FeaturePipelineVersion or None if not found
        """
        try:
            query = """
                SELECT id, version, pipeline_hash, feature_list, feature_definitions,
                       code_commit, created_at
                FROM feature_pipelines
                WHERE version = :version
            """

            row = self.db.execute_one(query, {"version": version})

            if row:
                (
                    pipeline_id,
                    version_str,
                    pipeline_hash,
                    feature_list_json,
                    feature_definitions_json,
                    code_commit,
                    created_at,
                ) = row

                return FeaturePipelineVersion(
                    id=pipeline_id,
                    version=version_str,
                    pipeline_hash=pipeline_hash,
                    feature_list=(
                        json.loads(feature_list_json) if feature_list_json else []
                    ),
                    feature_definitions=(
                        json.loads(feature_definitions_json)
                        if feature_definitions_json
                        else {}
                    ),
                    code_commit=code_commit,
                    created_at=created_at,
                )

            return None

        except SQLAlchemyError as e:
            logger.error(f"Error retrieving pipeline version: {e}", exc_info=True)
            return None

    def get_pipeline_by_hash(
        self, pipeline_hash: str
    ) -> Optional[FeaturePipelineVersion]:
        """
        Retrieve pipeline version by pipeline hash.

        :param pipeline_hash: Pipeline hash string
        :return: FeaturePipelineVersion or None if not found
        """
        try:
            query = """
                SELECT id, version, pipeline_hash, feature_list, feature_definitions,
                       code_commit, created_at
                FROM feature_pipelines
                WHERE pipeline_hash = :pipeline_hash
                ORDER BY created_at DESC
                LIMIT 1
            """

            row = self.db.execute_one(query, {"pipeline_hash": pipeline_hash})

            if row:
                (
                    pipeline_id,
                    version_str,
                    pipeline_hash_val,
                    feature_list_json,
                    feature_definitions_json,
                    code_commit,
                    created_at,
                ) = row

                return FeaturePipelineVersion(
                    id=pipeline_id,
                    version=version_str,
                    pipeline_hash=pipeline_hash_val,
                    feature_list=(
                        json.loads(feature_list_json) if feature_list_json else []
                    ),
                    feature_definitions=(
                        json.loads(feature_definitions_json)
                        if feature_definitions_json
                        else {}
                    ),
                    code_commit=code_commit,
                    created_at=created_at,
                )

            return None

        except SQLAlchemyError as e:
            logger.error(f"Error retrieving pipeline by hash: {e}", exc_info=True)
            return None

    def get_latest_version(self) -> Optional[FeaturePipelineVersion]:
        """
        Get the most recent pipeline version.

        :return: FeaturePipelineVersion or None if no versions exist
        """
        try:
            query = """
                SELECT id, version, pipeline_hash, feature_list, feature_definitions,
                       code_commit, created_at
                FROM feature_pipelines
                ORDER BY created_at DESC
                LIMIT 1
            """

            row = self.db.execute_one(query)

            if row:
                (
                    pipeline_id,
                    version_str,
                    pipeline_hash,
                    feature_list_json,
                    feature_definitions_json,
                    code_commit,
                    created_at,
                ) = row

                return FeaturePipelineVersion(
                    id=pipeline_id,
                    version=version_str,
                    pipeline_hash=pipeline_hash,
                    feature_list=(
                        json.loads(feature_list_json) if feature_list_json else []
                    ),
                    feature_definitions=(
                        json.loads(feature_definitions_json)
                        if feature_definitions_json
                        else {}
                    ),
                    code_commit=code_commit,
                    created_at=created_at,
                )

            return None

        except SQLAlchemyError as e:
            logger.error(f"Error retrieving latest version: {e}", exc_info=True)
            return None

    def list_versions(self) -> List[FeaturePipelineVersion]:
        """
        List all registered pipeline versions.

        :return: List of FeaturePipelineVersion objects
        """
        try:
            query = """
                SELECT id, version, pipeline_hash, feature_list, feature_definitions,
                       code_commit, created_at
                FROM feature_pipelines
                ORDER BY created_at DESC
            """

            rows = self.db.execute_with_result(query)

            versions = []
            for row in rows:
                (
                    pipeline_id,
                    version_str,
                    pipeline_hash,
                    feature_list_json,
                    feature_definitions_json,
                    code_commit,
                    created_at,
                ) = row

                versions.append(
                    FeaturePipelineVersion(
                        id=pipeline_id,
                        version=version_str,
                        pipeline_hash=pipeline_hash,
                        feature_list=(
                            json.loads(feature_list_json) if feature_list_json else []
                        ),
                        feature_definitions=(
                            json.loads(feature_definitions_json)
                            if feature_definitions_json
                            else {}
                        ),
                        code_commit=code_commit,
                        created_at=created_at,
                    )
                )

            return versions

        except SQLAlchemyError as e:
            logger.error(f"Error listing versions: {e}", exc_info=True)
            return []

    def get_features_for_version(self, version: str) -> List[str]:
        """
        Get feature list for a specific pipeline version.

        :param version: Version string
        :return: List of feature names
        """
        pipeline_version = self.get_pipeline_version(version)
        if pipeline_version:
            return pipeline_version.feature_list
        return []

    @staticmethod
    def compute_pipeline_hash(feature_files: List[str]) -> str:
        """
        Compute hash of feature computation code.

        :param feature_files: List of file paths to feature computation code
        :return: SHA256 hash string
        """
        hasher = hashlib.sha256()

        for file_path in sorted(feature_files):
            try:
                with open(file_path, "rb") as f:
                    hasher.update(f.read())
            except FileNotFoundError:
                logger.warning(f"Feature file not found: {file_path}")
                # Include file path in hash even if file doesn't exist
                hasher.update(file_path.encode())

        return hasher.hexdigest()

    @staticmethod
    def get_git_commit() -> Optional[str]:
        """
        Get current git commit hash.

        :return: Git commit hash or None if not available
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
