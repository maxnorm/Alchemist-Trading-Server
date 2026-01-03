"""
Database service layer with SQLAlchemy connection pool
"""

from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def init_db():
    """Initialize database connection pool"""
    global _engine, _SessionLocal

    if _engine is not None:
        return

    database_url = settings.get_database_url

    logger.info(
        f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else '***'}"
    )

    # Create engine with connection pooling
    # Add connection arguments for better timeout handling
    connect_args = {
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 60,
        "charset": "utf8mb4",
    }

    _engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,  # Recycle connections after 1 hour (before MySQL wait_timeout)
        pool_reset_on_return="commit",  # Reset connections when returned to pool
        echo=False,
        connect_args=connect_args,
    )

    # Create session factory
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # Test connection - but don't fail if DB isn't ready yet
    # The connection pool will retry when actually used
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    except Exception as e:
        logger.warning(f"Database connection test failed: {e}")
        logger.info("Connection pool created, will retry on first use")
        # Don't raise - allow the engine to be created
        # The pool_pre_ping will verify connections when they're actually used


def get_db_session() -> Session:
    """Get a database session"""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()


def close_db():
    """Close database connections"""
    if _engine is not None:
        _engine.dispose()
        logger.info("Database connections closed")


def check_db_health() -> bool:
    """Check database connection health"""
    try:
        if _engine is None:
            return False
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
