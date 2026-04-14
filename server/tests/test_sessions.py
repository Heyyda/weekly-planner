"""
Integration тесты SessionService — использует реальную файловую SQLite.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.db.base import Base
from server.db import models


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:ABC")
    monkeypatch.setenv("ALLOWED_USERNAMES", "test")
    from server.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db():
    """Свежая БД с применённой schema на каждый тест."""
    from server.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    from server.db.engine import _attach_pragma_listener
    _attach_pragma_listener(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Создадим юзера для FK
        user = models.User(telegram_username="testuser")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.user_id = user.id  # type: ignore
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_session_returns_plaintext_and_stores_hash(db):
    from server.auth.sessions import SessionService
    from server.auth.jwt import hash_refresh_token
    svc = SessionService(db)
    session_obj, plaintext = await svc.create(user_id=db.user_id, device_name="PC-Work")
    assert session_obj.refresh_token_hash == hash_refresh_token(plaintext)
    assert session_obj.user_id == db.user_id
    assert session_obj.device_name == "PC-Work"
    assert session_obj.revoked_at is None
    # В БД не хранится plaintext
    assert plaintext != session_obj.refresh_token_hash


@pytest.mark.asyncio
async def test_rotate_refresh_creates_new_revokes_old(db):
    from server.auth.sessions import SessionService
    svc = SessionService(db)
    old_session, old_plaintext = await svc.create(user_id=db.user_id)
    old_id = old_session.id

    result = await svc.rotate_refresh(old_plaintext)
    assert result is not None
    new_session, new_plaintext = result
    assert new_session.id != old_id
    assert new_plaintext != old_plaintext

    # Старая revoked
    stmt = select(models.Session).where(models.Session.id == old_id)
    res = await db.execute(stmt)
    refreshed_old = res.scalar_one()
    assert refreshed_old.revoked_at is not None


@pytest.mark.asyncio
async def test_rotate_invalid_token_returns_none(db):
    from server.auth.sessions import SessionService
    svc = SessionService(db)
    assert await svc.rotate_refresh("total.garbage.token") is None
    assert await svc.rotate_refresh("") is None


@pytest.mark.asyncio
async def test_rotate_revoked_session_returns_none(db):
    from server.auth.sessions import SessionService
    svc = SessionService(db)
    sess, plaintext = await svc.create(user_id=db.user_id)
    await svc.revoke(sess.id)
    assert await svc.rotate_refresh(plaintext) is None


@pytest.mark.asyncio
async def test_revoke_sets_revoked_at(db):
    from server.auth.sessions import SessionService
    svc = SessionService(db)
    sess, _ = await svc.create(user_id=db.user_id)
    assert sess.revoked_at is None
    ok = await svc.revoke(sess.id)
    assert ok is True

    await db.refresh(sess)
    assert sess.revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_unknown_session_returns_false(db):
    from server.auth.sessions import SessionService
    svc = SessionService(db)
    assert await svc.revoke("does-not-exist-uuid") is False


@pytest.mark.asyncio
async def test_get_by_refresh_hash(db):
    from server.auth.sessions import SessionService
    from server.auth.jwt import hash_refresh_token
    svc = SessionService(db)
    sess, plaintext = await svc.create(user_id=db.user_id)

    found = await svc.get_by_refresh_hash(hash_refresh_token(plaintext))
    assert found is not None
    assert found.id == sess.id

    assert await svc.get_by_refresh_hash("nonexistent-hash") is None
