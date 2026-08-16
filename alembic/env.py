from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import all models so they are registered with Base.metadata
from app.models import Base  # noqa: F401
from app.models import *  # noqa: F401, F403

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Read the database URL from the .env-driven app settings rather than the
# hard-coded sqlalchemy.url in alembic.ini.
#
# Alembic runs migrations through a *synchronous* connection, so the async
# asyncpg driver must be swapped for the sync psycopg2 driver.
from app.config.settings import settings as app_settings

_db_url = app_settings.DATABASE_URL
if _db_url.startswith("postgresql+asyncpg://"):
    _db_url = "postgresql+psycopg2://" + _db_url.split("://", 1)[1]

config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()