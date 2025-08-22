from logging.config import fileConfig

from alembic import context
from poliloom.models import Base
from poliloom.database import get_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Uses the centralized database engine from poliloom.database
    which handles both local and Cloud SQL connections properly.
    """
    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


# Only support online mode - no offline SQL generation
if context.is_offline_mode():
    raise ValueError("Offline mode is not supported. Use online mode only.")
else:
    run_migrations_online()
