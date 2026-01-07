"""
Database service layer with SQLAlchemy connection pool
"""

from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, DisconnectionError
import logging
import time
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
    # Add connection arguments for PostgreSQL
    connect_args = {
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000 -c client_encoding=utf8",
    }

    _engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_reset_on_return="commit",  # Reset connections when returned to pool
        echo=False,
        connect_args=connect_args,
    )

    # Create session factory
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # Test connection with retry logic
    max_retries = 5
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return
        except (OperationalError, DisconnectionError) as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Database connection test failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Database connection test failed after {max_retries} attempts: {e}")
                logger.error(f"Database URL: {database_url.split('@')[0]}@***")
                logger.error("Connection pool created, but database is not available")
                logger.error("The API will start, but database operations will fail until the database is available")
        except Exception as e:
            logger.error(f"Unexpected error during database connection test: {e}")
            logger.error("Connection pool created, but connection test failed")
            break


def get_db_session() -> Session:
    """Get a database session with retry logic"""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    # Try to get a session with retry logic
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            session = _SessionLocal()
            # Test the connection by executing a simple query
            session.execute(text("SELECT 1"))
            return session
        except (OperationalError, DisconnectionError) as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error getting database session: {e}")
            raise


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
