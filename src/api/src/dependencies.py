"""
Dependency injection for FastAPI
"""

from typing import Generator
from sqlalchemy.orm import Session
from services.database import get_db_session


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.

    Services handle their own commits. SQLAlchemy automatically rolls back
    uncommitted transactions when the session is closed.
    """
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()
