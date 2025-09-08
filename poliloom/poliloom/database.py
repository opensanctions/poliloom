"""Database configuration and session management."""

import os
from typing import Optional

import pg8000
from google.cloud.sql.connector import Connector
from sqlalchemy import Engine
import sqlalchemy
from dotenv import load_dotenv

load_dotenv()

# Global variable for lazy initialization
_engine: Optional[Engine] = None


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


def _get_cloud_sql_connection():
    """Create a connection using the Cloud SQL Python Connector.

    Note: This creates a new connector instance per call to support
    multiprocessing scenarios where each worker needs its own connector.
    """
    connector = Connector(refresh_strategy="lazy")

    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
    db_iam_user = os.getenv("DB_IAM_USER")
    db_name = os.getenv("DB_NAME")

    if not all([instance_connection_name, db_iam_user, db_name]):
        raise ValueError(
            "Cloud SQL configuration incomplete. Required: "
            "INSTANCE_CONNECTION_NAME, DB_IAM_USER, DB_NAME"
        )

    return connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_iam_user,
        db=db_name,
        enable_iam_auth=True,
    )


def create_engine(pool_size: int = 5, max_overflow: int = 10) -> Engine:
    """Create a new database engine.

    Args:
        pool_size: Number of connections to maintain in the pool
        max_overflow: Maximum overflow connections allowed

    Returns:
        A new SQLAlchemy Engine instance
    """
    # Determine if we should use Cloud SQL or local connection
    use_cloud_sql = bool(os.getenv("INSTANCE_CONNECTION_NAME"))

    if use_cloud_sql:
        creator = _get_cloud_sql_connection
    else:
        creator = _get_local_connection

    engine = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=creator,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

    return engine


def get_engine() -> Engine:
    """Get or create the database engine with lazy initialization."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine
