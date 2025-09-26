"""Database configuration and session management."""

import os
from typing import Optional

import pg8000
from google.cloud.sql.connector import Connector
from sqlalchemy import Engine, text
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
        # Create ONE connector for this engine
        connector = Connector(refresh_strategy="lazy")

        instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
        db_iam_user = os.getenv("DB_IAM_USER")
        db_name = os.getenv("DB_NAME")

        if not all([instance_connection_name, db_iam_user, db_name]):
            raise ValueError(
                "Cloud SQL configuration incomplete. Required: "
                "INSTANCE_CONNECTION_NAME, DB_IAM_USER, DB_NAME"
            )

        # Create a closure that uses the same connector instance
        def get_cloud_sql_connection():
            return connector.connect(
                instance_connection_name,
                "pg8000",
                user=db_iam_user,
                db=db_name,
                enable_iam_auth=True,
            )

        creator = get_cloud_sql_connection
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


def create_timestamp_triggers(engine: Engine):
    """Create PostgreSQL triggers for timestamp and embedding management."""
    with engine.connect() as conn:
        # Create the updated_at trigger function
        conn.execute(
            text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        )

        # Create the embedding reset trigger function
        conn.execute(
            text("""
            CREATE OR REPLACE FUNCTION reset_embedding_on_name_change()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.name IS DISTINCT FROM NEW.name THEN
                    -- Reset embedding for positions if the entity exists
                    UPDATE positions SET embedding = NULL WHERE wikidata_id = NEW.wikidata_id;
                    -- Reset embedding for locations if the entity exists
                    UPDATE locations SET embedding = NULL WHERE wikidata_id = NEW.wikidata_id;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        )

        # Current tables with updated_at columns (based on actual database schema)
        tables_with_updated_at = [
            "archived_pages",
            "countries",
            "evaluations",
            "locations",
            "politicians",
            "positions",
            "properties",
            "wikidata_dumps",
            "wikidata_entities",
            "wikidata_relations",
            "wikipedia_links",
        ]

        # Create updated_at triggers for each table
        for table in tables_with_updated_at:
            conn.execute(
                text(f"""
                CREATE TRIGGER trigger_update_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
            """)
            )

        # Create the embedding reset trigger on wikidata_entities table
        conn.execute(
            text("""
            CREATE TRIGGER wikidata_entity_name_change_trigger
                AFTER UPDATE ON wikidata_entities
                FOR EACH ROW
                EXECUTE FUNCTION reset_embedding_on_name_change();
        """)
        )

        conn.commit()


def create_import_tracking_triggers(engine: Engine):
    """Create PostgreSQL triggers for import tracking functionality."""
    with engine.connect() as conn:
        # Create simple tracking functions and triggers
        conn.execute("""
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
        """)

        conn.execute("""
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
        """)

        # Create triggers for entity tracking
        conn.execute("""
            CREATE TRIGGER track_wikidata_entity_access
            AFTER INSERT OR UPDATE ON wikidata_entities
            FOR EACH ROW EXECUTE FUNCTION track_entity_access();
        """)

        # Create triggers for statement tracking
        conn.execute("""
            CREATE TRIGGER track_property_access
            AFTER INSERT OR UPDATE ON properties
            FOR EACH ROW EXECUTE FUNCTION track_statement_access();
        """)

        conn.execute("""
            CREATE TRIGGER track_relation_access
            AFTER INSERT OR UPDATE ON wikidata_relations
            FOR EACH ROW EXECUTE FUNCTION track_statement_access();
        """)

        conn.commit()


def setup_test_database(engine: Engine):
    """Setup all required triggers for test database."""
    create_timestamp_triggers(engine)
    create_import_tracking_triggers(engine)
