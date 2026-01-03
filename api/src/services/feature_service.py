"""
Feature catalog service
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from schemas.features import FeatureResponse, DataSourceResponse
import logging

logger = logging.getLogger(__name__)


def get_all_features(
    db: Session, source: Optional[str] = None, category: Optional[str] = None
) -> List[FeatureResponse]:
    """Get all features with optional filtering"""
    query = "SELECT * FROM features WHERE 1=1"
    params = {}

    if source:
        query += " AND source = :source"
        params["source"] = source

    if category:
        query += " AND category = :category"
        params["category"] = category

    query += " ORDER BY name"

    result = db.execute(text(query), params)
    rows = result.fetchall()

    features = []
    for row in rows:
        # Convert row to dict
        row_dict = dict(row._mapping)
        # Parse JSON statistics if present
        if row_dict.get("statistics") and isinstance(row_dict["statistics"], str):
            import json

            try:
                row_dict["statistics"] = json.loads(row_dict["statistics"])
            except:
                row_dict["statistics"] = None
        features.append(FeatureResponse(**row_dict))

    return features


def get_feature_by_name(db: Session, name: str) -> Optional[FeatureResponse]:
    """Get feature by name"""
    result = db.execute(
        text("SELECT * FROM features WHERE name = :name"), {"name": name}
    )
    row = result.fetchone()

    if not row:
        return None

    row_dict = dict(row._mapping)
    # Parse JSON statistics if present
    if row_dict.get("statistics") and isinstance(row_dict["statistics"], str):
        import json

        try:
            row_dict["statistics"] = json.loads(row_dict["statistics"])
        except:
            row_dict["statistics"] = None

    return FeatureResponse(**row_dict)


def get_all_data_sources(db: Session) -> List[DataSourceResponse]:
    """Get all data sources"""
    result = db.execute(text("SELECT * FROM data_providers ORDER BY name"))
    rows = result.fetchall()

    sources = []
    for row in rows:
        row_dict = dict(row._mapping)
        # Parse JSON config if present
        if row_dict.get("config") and isinstance(row_dict["config"], str):
            import json

            try:
                row_dict["config"] = json.loads(row_dict["config"])
            except:
                row_dict["config"] = None
        sources.append(DataSourceResponse(**row_dict))

    return sources


def get_data_source_health(db: Session, source_id: int) -> Optional[DataSourceResponse]:
    """Get data source health status"""
    result = db.execute(
        text("SELECT * FROM data_providers WHERE id = :id"), {"id": source_id}
    )
    row = result.fetchone()

    if not row:
        return None

    row_dict = dict(row._mapping)
    # Parse JSON config if present
    if row_dict.get("config") and isinstance(row_dict["config"], str):
        import json

        try:
            row_dict["config"] = json.loads(row_dict["config"])
        except:
            row_dict["config"] = None

    return DataSourceResponse(**row_dict)
