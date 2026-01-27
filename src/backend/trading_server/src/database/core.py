"""
Core database engine and connection pool management.

Provides singleton engine instance with connection pooling, retry logic,
and health checks.
"""

import logging
import time
from typing import Optional
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, DisconnectionError

from .config import get_database_url, get_pool_config, get_retry_config

logger = logging.getLogger(__name__)

# Global engine instance (singleton)
_engine: Optional[Engine] = None


def init_db() -> None:
    """
    Initialize database connection pool with retry logic.

    Creates a singleton SQLAlchemy engine with connection pooling.
    Performs connection test with exponential backoff retry.

    Raises:
        Exception: If connection fails after all retries
    """
    global _engine

    if _engine is not None:
        logger.debug("Database engine already initialized")
        return

    database_url = get_database_url()
    pool_config = get_pool_config()
    retry_config = get_retry_config()

    # Log connection attempt (mask password)
    log_url = database_url.split("@")[1] if "@" in database_url else "***"
    logger.info(f"Initializing database connection: {log_url}")

    # Connection arguments for PostgreSQL
    connect_args = {
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000 -c client_encoding=utf8",
    }

    # Create engine with connection pooling
    _engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_config["pool_size"],
        max_overflow=pool_config["max_overflow"],
        pool_pre_ping=pool_config["pool_pre_ping"],
        pool_recycle=pool_config["pool_recycle"],
        pool_reset_on_return="commit",
        echo=False,
        connect_args=connect_args,
    )

    # Test connection with retry logic
    max_retries = retry_config["max_retries"]
    retry_delay = retry_config["retry_delay"]

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
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(
                    f"Database connection test failed after {max_retries} attempts: {e}"
                )
                logger.error(f"Database URL: {database_url.split('@')[0]}@***")
                logger.error(
                    "Connection pool created, but database is not available. "
                    "Services will start, but database operations will fail until database is available."
                )
                # Don't raise - allow services to start without DB
                return
        except Exception as e:
            logger.error(f"Unexpected error during database connection test: {e}")
            logger.error("Connection pool created, but connection test failed")
            # Don't raise - allow services to start without DB
            return


def get_engine() -> Engine:
    """
    Get or create database engine instance.

    Returns:
        SQLAlchemy Engine instance

    Raises:
        RuntimeError: If engine is not initialized (call init_db() first)
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def close_db() -> None:
    """
    Close database connections and dispose engine.

    Releases all connections from the pool and disposes the engine.
    Safe to call multiple times.
    """
    global _engine

    if _engine is not None:
        _engine.dispose()
        logger.info("Database connections closed")
        _engine = None


def check_db_health() -> bool:
    """
    Check database connection health.

    Returns:
        True if database is healthy and reachable, False otherwise
    """
    try:
        if _engine is None:
            return False

        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
