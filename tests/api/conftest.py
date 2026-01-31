"""
Pytest fixtures for API tests
"""
import os
import pytest
from fastapi.testclient import TestClient
from fastapi import Request
from unittest.mock import Mock, patch, AsyncMock
from typing import Generator

# Set required environment variables before importing app
# These are needed for Settings initialization
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("MLFLOW_TRACKING_URI", "file:///tmp/mlflow_test")

from tests.shared.helpers.path_utils import setup_api_path

# Setup API path
setup_api_path()

# Mock models before importing app (models are not needed for unit tests)
# This prevents import errors when services try to import models
import sys
from unittest.mock import MagicMock

# Create a proper mock model class that supports attribute access
class MockModel:
    """Mock SQLAlchemy model class that supports attribute access"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __getattr__(self, name):
        # Return None for any missing attributes to prevent AttributeError
        return None

# Create mock models module with proper structure
mock_mt5_accounts = MagicMock()
mock_mt5_accounts.MT5Account = MockModel
mock_mt5_accounts.AccountModelAssignment = MockModel
mock_mt5_accounts.MT5Connection = MockModel

mock_models = MagicMock()
mock_models.mt5_accounts = mock_mt5_accounts

# Add to sys.modules before any imports
sys.modules['models'] = mock_models
sys.modules['models.mt5_accounts'] = mock_mt5_accounts

# Create proper infrastructure module structure
# This is needed because main.py imports infrastructure.messaging.alert_consumer
import types

# Create mock AlertConsumer class
class MockAlertConsumer:
    def __init__(self, *args, **kwargs):
        pass
    async def start(self):
        pass
    async def stop(self):
        pass

# Create mock CredentialManager class
class MockCredentialManager:
    def __init__(self, *args, **kwargs):
        pass

# Create infrastructure.messaging.alert_consumer module
alert_consumer_module = types.ModuleType('infrastructure.messaging.alert_consumer')
alert_consumer_module.AlertConsumer = MockAlertConsumer

# Create infrastructure.messaging.experiment_publisher module
class MockExperimentPublisher:
    @staticmethod
    def get_instance():
        return MockExperimentPublisher()
    def publish_experiment_start(self, experiment_id):
        return True

experiment_publisher_module = types.ModuleType('infrastructure.messaging.experiment_publisher')
experiment_publisher_module.ExperimentPublisher = MockExperimentPublisher

# Create infrastructure.messaging module
messaging_module = types.ModuleType('infrastructure.messaging')
messaging_module.alert_consumer = alert_consumer_module
messaging_module.AlertConsumer = MockAlertConsumer
messaging_module.experiment_publisher = experiment_publisher_module
messaging_module.ExperimentPublisher = MockExperimentPublisher

# Create infrastructure.security.credential_manager module
credential_manager_module = types.ModuleType('infrastructure.security.credential_manager')
credential_manager_module.CredentialManager = MockCredentialManager

# Create infrastructure.security module
security_module = types.ModuleType('infrastructure.security')
security_module.credential_manager = credential_manager_module
security_module.CredentialManager = MockCredentialManager

# Create infrastructure module
infrastructure_module = types.ModuleType('infrastructure')
infrastructure_module.messaging = messaging_module
infrastructure_module.security = security_module

# Add all to sys.modules in the correct order
sys.modules['infrastructure'] = infrastructure_module
sys.modules['infrastructure.messaging'] = messaging_module
sys.modules['infrastructure.messaging.alert_consumer'] = alert_consumer_module
sys.modules['infrastructure.messaging.experiment_publisher'] = experiment_publisher_module
sys.modules['infrastructure.security'] = security_module
sys.modules['infrastructure.security.credential_manager'] = credential_manager_module

from main import app
from dependencies import get_db


def override_get_db() -> Generator[Mock, None, None]:
    """Override database dependency for testing"""
    from collections.abc import Mapping
    
    class MockRow:
        """Mock SQLAlchemy row that supports dict conversion and indexing"""
        def __init__(self, data):
            # data can be a dict or a list/tuple for indexed access
            if isinstance(data, dict):
                self._mapping = data
                self._values = list(data.values())
            else:
                # For tuple/list access like row[0], row[1]
                self._values = list(data) if data else []
                self._mapping = {f"col_{i}": val for i, val in enumerate(self._values)}
        
        def __getitem__(self, key):
            # Support both dict key access and integer indexing
            if isinstance(key, int):
                if 0 <= key < len(self._values):
                    return self._values[key]
                raise IndexError(f"Index {key} out of range")
            return self._mapping.get(key)
        
        def __iter__(self):
            return iter(self._values)
        
        def __len__(self):
            return len(self._values)
        
        def __getattr__(self, name):
            # Support attribute access
            return self._mapping.get(name)
    
    mock_db = Mock()
    
    # Mock SQLAlchemy execute method
    mock_result = Mock()
    mock_result.fetchall.return_value = []
    mock_result.fetchone.return_value = None
    mock_result.lastrowid = 1
    mock_result.rowcount = 0
    
    # Make execute return the mock result
    def mock_execute(*args, **kwargs):
        return mock_result
    
    mock_db.execute = Mock(side_effect=mock_execute)
    mock_db.commit = Mock()
    mock_db.add = Mock()
    mock_db.refresh = Mock()
    mock_db.query = Mock()
    
    # Mock query chain for ORM queries
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []
    mock_db.query.return_value = mock_query
    
    yield mock_db


async def override_get_current_user(request: Request):
    """Override authentication dependency for testing"""
    user_data = {"id": "user_123", "email": "test@example.com"}
    # Set request state for access in route handlers
    request.state.user_id = "user_123"
    request.state.roles = []  # Regular user, not admin
    return user_data


@pytest.fixture
def api_client():
    """Create test FastAPI client"""
    # Mock database initialization to prevent lifespan from trying to connect
    with patch('services.database.init_db'), patch('services.database.close_db'):
        # Override the database dependency
        app.dependency_overrides[get_db] = override_get_db
        
        # Override authentication dependency
        from middleware.auth import get_current_user
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        client = TestClient(app)
        yield client
        
        # Clean up: remove dependency overrides
        app.dependency_overrides.clear()


@pytest.fixture
def mock_database():
    """Create mock database"""
    db = Mock()
    mock_conn = Mock()
    mock_cursor = Mock()
    db.get_connection = Mock(return_value=mock_conn)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 1
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    return db, mock_conn, mock_cursor


@pytest.fixture
def authenticated_client(api_client):
    """Create authenticated test client (for future auth implementation)"""
    # For now, return regular client
    # In future, add authentication headers
    return api_client
