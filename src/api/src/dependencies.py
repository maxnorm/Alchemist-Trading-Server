"""
Dependency injection for FastAPI
"""

from typing import Generator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
import logging
from services.database import get_db_session

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.

    Services handle their own commits. SQLAlchemy automatically rolls back
    uncommitted transactions when the session is closed.
    
    Raises HTTPException with 503 status if database is unavailable.
    """
    try:
        db = get_db_session()
    except RuntimeError as e:
        logger.error(f"Database not initialized: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable. Please try again later."
        )
    except Exception as e:
        logger.error(f"Failed to get database session: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection error. Please try again later."
        )
    
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error during request: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database operation failed. Please try again later."
        )
    finally:
        try:
            db.close()
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")
