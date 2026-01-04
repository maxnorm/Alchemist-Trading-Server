"""
Pytest fixtures for API tests
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from typing import Generator
import sys
import os

# Add API source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/api/src'))

from main import app
from dependencies import get_db


def override_get_db() -> Generator[Mock, None, None]:
    """Override database dependency for testing"""
    mock_db = Mock()
    yield mock_db


@pytest.fixture
def api_client():
    """Create test FastAPI client"""
    # Mock database initialization to prevent lifespan from trying to connect
    with patch('services.database.init_db'), patch('services.database.close_db'):
        # Override the database dependency
        app.dependency_overrides[get_db] = override_get_db
        
        client = TestClient(app)
        yield client
        
        # Clean up: remove dependency override
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
