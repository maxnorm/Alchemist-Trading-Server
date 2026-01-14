"""
Database service layer with SQLAlchemy connection pool

Uses local database connector package for connection management.
Maintains backward-compatible interface for API service.
"""

from sqlalchemy.orm import Session

# Import from local database connector package
from database.core import (
    init_db as _init_db,
    close_db as _close_db,
    check_db_health as _check_db_health,
    get_engine as _get_engine,
)
from database.session import get_session as _get_session

# Re-export with same names for backward compatibility
def init_db():
    """Initialize database connection pool"""
    _init_db()


def get_db_session() -> Session:
    """Get a database session with retry logic"""
    return _get_session()


def close_db():
    """Close database connections"""
    _close_db()


def check_db_health() -> bool:
    """Check database connection health"""
    return _check_db_health()


# Note: _engine is no longer exported as a module variable
# Use get_engine() from database.core if direct engine access is needed
