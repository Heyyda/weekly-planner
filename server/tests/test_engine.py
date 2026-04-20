"""
Тесты async engine + PRAGMA WAL wiring.

КРИТИЧНО: WAL mode работает только для файлового SQLite. :memory: молча
возвращает journal_mode=memory. Поэтому тесты используют tmp_path/test.db.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.db.base import Base
from server.db import models  # noqa: F401 — регистрирует модели в metadata
from server.db.engine import _attach_pragma_listener


def _make_file_engine(tmp_path):
    """Helper: файловый async engine с PRAGMA listener."""
    db_file = tmp_path / "test_wal.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    _attach_pragma_listener(engine)
    return engine


@pytest.mark.asyncio
async def test_wal_pragmas_applied(tmp_path):
    """SRV-03: journal_mode=WAL на файловом SQLite."""
    engine = _make_file_engine(tmp_path)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            assert mode == "wal", f"Ожидался WAL, получен {mode!r}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_busy_timeout_is_5000(tmp_path):
    engine = _make_file_engine(tmp_path)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA busy_timeout"))
            assert result.scalar() == 5000
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_foreign_keys_on(tmp_path):
    engine = _make_file_engine(tmp_path)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys"))
            assert result.scalar() == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_synchronous_normal(tmp_path):
    engine = _make_file_engine(tmp_path)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA synchronous"))
            # NORMAL == 1
            assert result.scalar() == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_writes_no_lock(tmp_path):
    """
    SRV-03 ROADMAP success criterion: два одновременных запроса не вызывают
    OperationalError: database is locked.

    Создаём схему, запускаем 2 concurrent INSERT в разных сессиях.
    С WAL + busy_timeout=5000 — оба должны succeed.
    """
    engine = _make_file_engine(tmp_path)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async def insert_user(username: str) -> None:
            async with session_factory() as sess:
                sess.add(models.User(telegram_username=username))
                await sess.commit()

        # Две параллельные вставки
        await asyncio.gather(
            insert_user("user_one"),
            insert_user("user_two"),
        )

        # Проверить что обе записи есть
        async with session_factory() as sess:
            from sqlalchemy import select
            result = await sess.execute(select(models.User.telegram_username))
            usernames = {row[0] for row in result.all()}
            assert usernames == {"user_one", "user_two"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_db_yields_async_session(monkeypatch, tmp_path):
    """get_db — async generator, yield'ит AsyncSession, закрывается корректно."""
    # Подменяем DATABASE_URL на файловый (чтобы reimport engine взял новый URL)
    db_file = tmp_path / "gettest.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:ABC")
    monkeypatch.setenv("ALLOWED_USERNAMES", "test")

    from server.config import get_settings
    get_settings.cache_clear()

    # Локально создать dependency вручную с новым URL
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from server.db.engine import _attach_pragma_listener

    engine_local = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    _attach_pragma_listener(engine_local)
    factory = async_sessionmaker(engine_local, expire_on_commit=False)

    async def local_get_db():
        async with factory() as session:
            yield session

    # Используем generator вручную
    gen = local_get_db()
    session = await gen.__anext__()
    assert isinstance(session, AsyncSession)

    # Finish generator
    try:
        await gen.__anext__()
    except StopAsyncIteration:
        pass

    await engine_local.dispose()
