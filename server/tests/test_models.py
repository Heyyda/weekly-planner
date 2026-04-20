"""
Unit-тесты моделей Фазы 1 — структурные проверки (не интеграционные).
Интеграционные тесты с реальной БД — в Plan 03 (engine + WAL).
"""
import pytest
from server.db.base import Base
from server.db import models


def test_base_is_declarative():
    """Base — SQLAlchemy 2.x DeclarativeBase."""
    from sqlalchemy.orm import DeclarativeBase
    assert issubclass(Base, DeclarativeBase)
    assert hasattr(Base, "metadata")


def test_all_four_tables_registered():
    """SRV-04: users, auth_codes, sessions, tasks все есть в metadata."""
    tables = set(Base.metadata.tables.keys())
    assert "users" in tables
    assert "auth_codes" in tables
    assert "sessions" in tables
    assert "tasks" in tables


def test_user_fields():
    """User имеет правильные поля с правильными constraints."""
    cols = models.User.__table__.columns
    assert {"id", "telegram_username", "telegram_chat_id", "created_at", "updated_at"} <= set(cols.keys())
    assert cols["id"].primary_key is True
    assert cols["telegram_username"].unique is True
    assert cols["telegram_chat_id"].nullable is True


def test_authcode_fields():
    """AuthCode имеет code_hash (не plain), used_at nullable, expires_at."""
    cols = models.AuthCode.__table__.columns
    assert "code_hash" in cols
    assert "plain_code" not in cols  # не храним plaintext!
    assert cols["used_at"].nullable is True
    assert cols["expires_at"].nullable is False


def test_session_fields():
    """Session имеет refresh_token_hash unique, revoked_at nullable."""
    cols = models.Session.__table__.columns
    assert cols["refresh_token_hash"].unique is True
    assert cols["revoked_at"].nullable is True
    assert cols["last_used_at"].nullable is False


def test_task_has_tombstone_and_server_updated_at():
    """SRV-06: Task.updated_at.onupdate должен быть не None; deleted_at — tombstone (nullable)."""
    cols = models.Task.__table__.columns
    assert cols["deleted_at"].nullable is True, "deleted_at должен быть nullable (tombstone)"
    assert cols["updated_at"].onupdate is not None, "updated_at должен иметь onupdate (SRV-06 server-side timestamp)"
    # Task.id НЕ имеет default — UUID приходит от клиента
    assert cols["id"].default is None, "Task.id — client-generated UUID, без server default"


@pytest.mark.asyncio
async def test_create_all_works(test_engine):
    """Base.metadata.create_all должен работать на async SQLite in-memory."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Если не упало — таблицы созданы. Проверку что таблицы реально в БД можно
    # добавить в Plan 03 через inspect(), но для Wave 1 достаточно что create_all не падает.
