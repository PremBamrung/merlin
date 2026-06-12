"""
SQLAlchemy engine and session factory.
Uses synchronous SQLite (same as the existing merlin.db).
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from merlin.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


# Journal mode is configurable: WAL gives better read concurrency on native
# runs, but DELETE is required on a macOS Docker bind mount where WAL can lose
# uncheckpointed commits on restart (see Settings.sqlite_journal_mode).
# busy_timeout lets the background workers + UI wait out a lock instead of
# failing with "database is locked" (notably under DELETE's coarser locking).
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute(f"PRAGMA journal_mode={settings.sqlite_journal_mode}")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager that yields a DB session with automatic commit/rollback."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI Depends()-compatible session generator."""
    with get_db() as session:
        yield session
