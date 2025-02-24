from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, scoped_session

from merlin.database.models import SessionLocal
from merlin.utils import logger


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self):
        self.SessionLocal = SessionLocal

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session using context manager for automatic cleanup."""
        session = scoped_session(self.SessionLocal)
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            session.remove()

    def execute_with_session(self, operation):
        """Execute a database operation within a session context."""
        with self.get_session() as session:
            return operation(session)
