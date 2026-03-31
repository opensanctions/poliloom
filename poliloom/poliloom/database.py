"""Database configuration and session management."""

import os
from typing import Optional

import psycopg
import sqlalchemy
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

# Global variable for lazy initialization
_engine: Optional[Engine] = None


def get_conn_params() -> dict:
    """Build psycopg connection parameters from DB_* environment variables."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "poliloom"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
    }


def create_engine(pool_size: int = 5, max_overflow: int = 10) -> Engine:
    """Create a new database engine.

    Args:
        pool_size: Number of connections to maintain in the pool
        max_overflow: Maximum overflow connections allowed

    Returns:
        A new SQLAlchemy Engine instance
    """
    conn_params = get_conn_params()

    engine = sqlalchemy.create_engine(
        "postgresql+psycopg://",
        creator=lambda: psycopg.connect(**conn_params),
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
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


def create_timestamp_triggers(engine: Engine):
    """Create PostgreSQL triggers for timestamp management."""
    with engine.connect() as conn:
        # Create the updated_at trigger function
        conn.execute(
            text(
                """
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """
            )
        )

        # Current tables with updated_at columns (based on actual database schema)
        tables_with_updated_at = [
            "sources",
            "countries",
            "evaluations",
            "locations",
            "politicians",
            "positions",
            "properties",
            "property_references",
            "wikidata_dumps",
            "wikidata_entities",
            "wikidata_relations",
            "wikipedia_links",
        ]

        # Create updated_at triggers for each table (replace if exists)
        for table in tables_with_updated_at:
            conn.execute(
                text(
                    f"""
                CREATE OR REPLACE TRIGGER trigger_update_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
            """
                )
            )

        conn.commit()


def create_import_tracking_triggers(engine: Engine):
    """Create PostgreSQL triggers for import tracking functionality."""
    with engine.connect() as conn:
        # Create simple tracking functions and triggers
        conn.execute(
            text(
                """
            -- Function to track entity access during imports
            CREATE OR REPLACE FUNCTION track_entity_access()
            RETURNS TRIGGER AS $$
            BEGIN
                -- Track entity access in simple tracking table
                INSERT INTO current_import_entities (entity_id)
                VALUES (NEW.wikidata_id)
                ON CONFLICT (entity_id) DO NOTHING;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """
            )
        )

        conn.execute(
            text(
                """
            -- Function to track statement access during imports
            CREATE OR REPLACE FUNCTION track_statement_access()
            RETURNS TRIGGER AS $$
            BEGIN
                -- Only track if statement_id exists
                IF NEW.statement_id IS NOT NULL THEN
                    INSERT INTO current_import_statements (statement_id)
                    VALUES (NEW.statement_id)
                    ON CONFLICT (statement_id) DO NOTHING;
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """
            )
        )

        # Create triggers for entity tracking (replace if exists)
        conn.execute(
            text(
                """
            CREATE OR REPLACE TRIGGER track_wikidata_entity_access
            AFTER INSERT OR UPDATE ON wikidata_entities
            FOR EACH ROW EXECUTE FUNCTION track_entity_access();
        """
            )
        )

        # Create triggers for statement tracking (replace if exists)
        conn.execute(
            text(
                """
            CREATE OR REPLACE TRIGGER track_property_access
            AFTER INSERT OR UPDATE ON properties
            FOR EACH ROW EXECUTE FUNCTION track_statement_access();
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE OR REPLACE TRIGGER track_relation_access
            AFTER INSERT OR UPDATE ON wikidata_relations
            FOR EACH ROW EXECUTE FUNCTION track_statement_access();
        """
            )
        )

        conn.commit()


def get_db_session():
    """FastAPI dependency for database sessions.

    Yields a database session that will be automatically closed after use.
    This can be overridden in tests to use a transaction-based session.
    """
    with Session(get_engine()) as session:
        yield session
