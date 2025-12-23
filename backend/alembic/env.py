from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.settings import settings
from app.db.models import Base  # IMPORTANT: imports all ORM models via Base


# Alembic Config object (from alembic.ini)
config = context.config

# Configure Python logging using alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Enable autogenerate
target_metadata = Base.metadata


def _sync_url(url: str) -> str:
    """
    Alembic traditionally runs migrations with a synchronous SQLAlchemy engine.
    If app uses async drivers (aiosqlite, asyncpg), convert to sync form for migrations.
    """
    if "+aiosqlite" in url:
        return url.replace("+aiosqlite", "")
    if "+asyncpg" in url:
        # we can choose psycopg2 or psycopg depending on our preference/installed driver
        return url.replace("+asyncpg", "+psycopg2")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _sync_url(settings.database_url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # detects column type changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Override sqlalchemy.url from settings (single source of truth)
    cfg_section = config.get_section(config.config_ini_section, {})
    cfg_section["sqlalchemy.url"] = _sync_url(settings.database_url)

    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detects column type changes
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
