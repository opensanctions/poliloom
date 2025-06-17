"""Database configuration and session management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from .vector_search import setup_vector_extensions

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./poliloom.db")

engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    ),
)

# Setup vector extensions (pgvector for PostgreSQL)
setup_vector_extensions(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()