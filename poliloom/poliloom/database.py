"""Database configuration and session management."""

import os
from contextlib import contextmanager
from typing import Generator, Optional

import pg8000
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Global variables for lazy initialization
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None
_connector: Optional[Connector] = None


def _get_cloud_sql_connection():
    """Create a connection using the Cloud SQL Python Connector."""
    global _connector
    if _connector is None:
        _connector = Connector(refresh_strategy="lazy")

    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
    db_iam_user = os.getenv("DB_IAM_USER")
    db_name = os.getenv("DB_NAME")

    if not all([instance_connection_name, db_iam_user, db_name]):
        raise ValueError(
            "Cloud SQL configuration incomplete. Required: "
            "INSTANCE_CONNECTION_NAME, DB_IAM_USER, DB_NAME"
        )

    return _connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_iam_user,
        db=db_name,
        enable_iam_auth=True,
    )


def _get_local_connection():
    """Create a direct pg8000 connection for local development."""
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_name = os.getenv("DB_NAME", "poliloom")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    return pg8000.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password,
    )


def get_engine() -> Engine:
    """Get or create the database engine with lazy initialization."""
    global _engine
    if _engine is None:
        # Determine if we should use Cloud SQL or local connection
        use_cloud_sql = bool(os.getenv("INSTANCE_CONNECTION_NAME"))

        if use_cloud_sql:
            creator = _get_cloud_sql_connection
        else:
            creator = _get_local_connection

        _engine = create_engine(
            "postgresql+pg8000://",
            creator=creator,
            pool_size=20,
            max_overflow=30,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
        )

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
