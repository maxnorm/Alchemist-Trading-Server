"""
Session management for API service (ORM-style access).

Provides SQLAlchemy session management with retry logic for FastAPI
dependency injection.
"""

import logging
import time
from typing import Optional
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, DisconnectionError
from sqlalchemy import text

from .core import get_engine, init_db
from .config import get_retry_config

logger = logging.getLogger(__name__)

# Session factory (created after engine initialization)
_SessionLocal: Optional[sessionmaker] = None


def _get_session_factory() -> sessionmaker:
    """
    Get or create session factory.

    Returns:
        SQLAlchemy sessionmaker instance

    Raises:
        RuntimeError: If engine is not initialized
    """
    global _SessionLocal

    if _SessionLocal is None:
        # Ensure engine is initialized
        init_db()
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return _SessionLocal


def get_session() -> Session:
    """
    Get a database session with retry logic.

    Creates a new SQLAlchemy session and tests the connection.
    Implements exponential backoff retry on connection failures.

    Returns:
        SQLAlchemy Session instance

    Raises:
        RuntimeError: If database is not initialized
        OperationalError: If connection fails after all retries
    """
    SessionLocal = _get_session_factory()
    retry_config = get_retry_config()

    # Try to get a session with retry logic
    max_retries = min(retry_config["max_retries"], 3)  # Cap at 3 for sessions
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            session = SessionLocal()
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
                logger.error(
                    f"Database connection failed after {max_retries} attempts: {e}"
                )
                raise
        except Exception as e:
            logger.error(f"Unexpected error getting database session: {e}")
            raise

    # This should never be reached, but MyPy needs it for type checking
    raise RuntimeError("Failed to get database session after all retries")


# Export SessionLocal as a callable for dependency injection patterns
def SessionLocal() -> Session:
    """
    Get a new database session (for dependency injection).

    This is a convenience function that creates a new session.
    For direct access to the sessionmaker, use _get_session_factory().

    Returns:
        SQLAlchemy Session instance
    """
    return _get_session_factory()()
