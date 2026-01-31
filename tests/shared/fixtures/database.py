"""
Database fixtures for integration tests using testcontainers
"""
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def postgres_container():
    """Create a PostgreSQL testcontainer"""
    with PostgresContainer("timescale/timescaledb:latest-pg16") as postgres:
        yield postgres


@pytest.fixture(scope="function")
def test_database(postgres_container):
    """Create test database connection"""
    connection_url = postgres_container.get_connection_url()
    engine = create_engine(connection_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture(scope="function")
def db_connection_string(postgres_container):
    """Get database connection string for tests"""
    return postgres_container.get_connection_url()
