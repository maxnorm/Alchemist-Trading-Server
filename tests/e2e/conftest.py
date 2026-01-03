"""
Pytest fixtures for E2E tests
"""
import pytest
import subprocess
import time
import os
from pathlib import Path


@pytest.fixture(scope="session")
def docker_compose():
    """Start Docker Compose services for E2E tests"""
    # Check if docker-compose is available
    try:
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("docker-compose not available")
    
    # Start services
    project_root = Path(__file__).parent.parent.parent
    compose_file = project_root / "docker-compose.yml"
    
    if not compose_file.exists():
        pytest.skip("docker-compose.yml not found")
    
    # Start services
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "up", "-d"],
        cwd=project_root,
        check=True
    )
    
    # Wait for services to be healthy
    time.sleep(10)
    
    yield
    
    # Cleanup: stop services
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "down"],
        cwd=project_root,
        check=False
    )


@pytest.fixture
def test_database(docker_compose):
    """Create test database with migrations"""
    # In real implementation, would:
    # 1. Run all migration scripts
    # 2. Seed test data
    # 3. Cleanup after tests
    
    # For now, return mock
    yield None
    
    # Cleanup would happen here
