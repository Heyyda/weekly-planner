"""
Alembic environment.

КРИТИЧНО (RESEARCH.md Pitfall 5): Alembic использует sync connections,
а приложение — async engine (aiosqlite). Здесь URL должен быть sqlite:///,
а не sqlite+aiosqlite:///. Фикс: срезаем `+aiosqlite` если он есть в DATABASE_URL.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Добавить корень проекта (родитель server/) в sys.path — чтобы `from server.db.base import Base` работало
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.db.base import Base  # noqa: E402
from server.db import models  # noqa: E402, F401  — импорт для регистрации в metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Переопределить URL из env var, конвертировав в sync форму
database_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
if database_url and "+aiosqlite" in database_url:
    database_url = database_url.replace("+aiosqlite", "")
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline mode — генерирует SQL без подключения к БД."""
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
    """Online mode — подключается к БД и выполняет миграции."""
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
