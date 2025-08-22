"""Database configuration and session management."""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/poliloom"
)

# Global variables for lazy initialization
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create the database engine with lazy initialization."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            pool_size=20,
            max_overflow=30,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
        )

        # Setup pgvector extension
        with _engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create the session factory with lazy initialization."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine()
        )
    return _SessionLocal


def get_db():
    """Get database session for FastAPI dependency injection."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.

    Automatically handles:
    - Session creation
    - Commit on success
    - Rollback on error
    - Session cleanup

    Usage:
        with get_db_session() as session:
            # Do database operations
            user = session.query(User).first()
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_db_session_no_commit() -> Generator[Session, None, None]:
    """
    Provide a database session without automatic commit.

    Useful for read-only operations or when manual commit control is needed.

    Usage:
        with get_db_session_no_commit() as session:
            # Do database operations
            user = session.query(User).first()
            # Manually commit if needed
            session.commit()
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
