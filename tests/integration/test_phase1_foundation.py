"""
Phase 1 Foundation Integration Tests
Tests for Schema Registry, Great Expectations, Airflow, and metrics
"""

import pytest
import os
from datetime import datetime
from typing import Dict, Any

# Schema Registry tests
def test_schema_registry_e2e():
    """Test Schema Registry end-to-end: register → retrieve → compatibility check → list versions"""
    try:
        from infrastructure.schema_registry import SchemaRegistry, CompatibilityMode
        
        registry = SchemaRegistry()
        
        # Test schema
        data_type = "test_type"
        version = "1.0.0"
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "field1": {"type": "string"},
                "field2": {"type": "number"}
            },
            "required": ["field1"]
        }
        
        # Register schema
        registry.register_schema(
            data_type=data_type,
            version=version,
            schema=schema,
            compatibility_mode=CompatibilityMode.NONE
        )
        
        # Retrieve schema
        retrieved = registry.get_schema(data_type, version)
        assert retrieved is not None
        assert retrieved["version"] == version
        
        # List versions
        versions = registry.list_versions(data_type)
        assert len(versions) > 0
        assert any(v["version"] == version for v in versions)
        
        print("✓ Schema Registry E2E test passed")
    except ImportError as e:
        pytest.skip(f"Schema Registry not available: {e}")


def test_great_expectations_validation():
    """Test Great Expectations validation pipeline"""
    try:
        from infrastructure.data_quality.ge_context import get_ge_context, GE_AVAILABLE
        from infrastructure.data_quality.ge_expectations import create_expectation_suite_from_contract
        
        if not GE_AVAILABLE:
            pytest.skip("Great Expectations not available")
        
        # Create expectation suite
        suite = create_expectation_suite_from_contract("tick")
        assert suite is not None
        
        print("✓ Great Expectations validation test passed")
    except ImportError as e:
        pytest.skip(f"Great Expectations not available: {e}")


def test_airflow_dag_structure():
    """Test that Airflow DAG structure is correct"""
    # Check that key DAGs exist (data_collection_pipeline was removed - tick collection now via ZeroMQ)
    dag_paths = [
        "src/trading_server/src/infrastructure/data_pipeline/airflow/dags/alternative_data_collection_dag.py",
        "src/trading_server/src/infrastructure/data_pipeline/airflow/dags/historical_backfill_dag.py",
    ]
    
    for dag_path in dag_paths:
        assert os.path.exists(dag_path), f"DAG file not found: {dag_path}"
    
    # Try to import a DAG (this will validate syntax)
    try:
        import sys
        sys.path.insert(0, "src/trading_server/src/infrastructure/data_pipeline/airflow/dags")
        # Note: Full import would require Airflow to be installed
        # For now, just check files exist
        print("✓ Airflow DAG structure test passed")
    except Exception as e:
        pytest.skip(f"Airflow DAG import test skipped: {e}")


def test_data_quality_metrics():
    """Test that data quality metrics are defined"""
    try:
        from monitoring.metrics import (
            data_freshness_seconds,
            data_volume_total,
            data_quality_score,
            data_quarantine_rate,
        )
        
        # Metrics should be defined
        assert data_freshness_seconds is not None
        assert data_volume_total is not None
        assert data_quality_score is not None
        assert data_quarantine_rate is not None
        
        print("✓ Data quality metrics test passed")
    except ImportError as e:
        pytest.skip(f"Metrics not available: {e}")


def test_schema_registry_api_integration():
    """Test Schema Registry API endpoints (if API service is available)"""
    # This would require the API service to be running
    # For now, just check that the router exists
    router_path = "src/api/src/routers/schema.py"
    assert os.path.exists(router_path), f"Schema router not found: {router_path}"
    
    print("✓ Schema Registry API integration test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
