"""Integration тесты AuthCodeService — реальная БД, реальный bcrypt (медленнее)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.db.base import Base
from server.db import models


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'codes.db'}")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "test-token-12345")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita")
    from server.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db():
    from server.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    from server.db.engine import _attach_pragma_listener
    _attach_pragma_listener(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_request_code_generates_6_digits(db):
    from server.auth.codes import AuthCodeService
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")
    assert len(result.code) == 6
    assert result.code.isdigit()
    assert result.request_id  # UUID строка


@pytest.mark.asyncio
async def test_request_code_stores_hash_not_plaintext(db):
    from server.auth.codes import AuthCodeService
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")

    stmt = select(models.AuthCode).where(models.AuthCode.id == result.request_id)
    record = (await db.execute(stmt)).scalar_one()
    assert record.code_hash != result.code
    assert result.code not in record.code_hash
    # bcrypt префикс $2b$ или $2a$
    assert record.code_hash.startswith("$2")


@pytest.mark.asyncio
async def test_request_code_sets_5min_expiry(db):
    from server.auth.codes import AuthCodeService
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")
    stmt = select(models.AuthCode).where(models.AuthCode.id == result.request_id)
    record = (await db.execute(stmt)).scalar_one()

    delta = (record.expires_at - record.created_at).total_seconds()
    assert 298 <= delta <= 302  # 5 min ± 2 sec


@pytest.mark.asyncio
async def test_verify_correct_code_ok(db):
    from server.auth.codes import AuthCodeService, VerifyResult
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")
    verdict = await svc.verify_code("nikita", result.code)
    assert verdict == VerifyResult.OK


@pytest.mark.asyncio
async def test_verify_sets_used_at(db):
    from server.auth.codes import AuthCodeService
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")
    await svc.verify_code("nikita", result.code)

    stmt = select(models.AuthCode).where(models.AuthCode.id == result.request_id)
    record = (await db.execute(stmt)).scalar_one()
    assert record.used_at is not None


@pytest.mark.asyncio
async def test_verify_same_code_twice_returns_already_used(db):
    from server.auth.codes import AuthCodeService, VerifyResult
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")
    first = await svc.verify_code("nikita", result.code)
    second = await svc.verify_code("nikita", result.code)
    assert first == VerifyResult.OK
    assert second == VerifyResult.ALREADY_USED


@pytest.mark.asyncio
async def test_verify_wrong_code_returns_invalid(db):
    from server.auth.codes import AuthCodeService, VerifyResult
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")
    # Генерируем код, гарантированно отличающийся
    wrong = "000000" if result.code != "000000" else "111111"
    verdict = await svc.verify_code("nikita", wrong)
    assert verdict == VerifyResult.INVALID
    # used_at НЕ установлен
    stmt = select(models.AuthCode).where(models.AuthCode.id == result.request_id)
    record = (await db.execute(stmt)).scalar_one()
    assert record.used_at is None


@pytest.mark.asyncio
async def test_verify_expired_code_returns_expired(db):
    from server.auth.codes import AuthCodeService, VerifyResult
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")
    # Подправим expires_at в БД
    stmt = select(models.AuthCode).where(models.AuthCode.id == result.request_id)
    record = (await db.execute(stmt)).scalar_one()
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()

    verdict = await svc.verify_code("nikita", result.code)
    assert verdict == VerifyResult.EXPIRED


@pytest.mark.asyncio
async def test_verify_different_username_returns_invalid(db):
    from server.auth.codes import AuthCodeService, VerifyResult
    svc = AuthCodeService(db)
    result = await svc.request_code("nikita")
    verdict = await svc.verify_code("not_nikita", result.code)
    assert verdict == VerifyResult.INVALID


@pytest.mark.asyncio
async def test_verify_uses_most_recent_code(db):
    """Если user запросил 2 кода подряд, самый свежий выигрывает."""
    from server.auth.codes import AuthCodeService, VerifyResult
    svc = AuthCodeService(db)
    first = await svc.request_code("nikita")
    second = await svc.request_code("nikita")
    # Старый код должен стать unusable (самый свежий — second)
    # Первый verify через first.code → самый свежий (second) не match → INVALID
    verdict = await svc.verify_code("nikita", first.code)
    assert verdict == VerifyResult.INVALID
    # second.code работает
    verdict2 = await svc.verify_code("nikita", second.code)
    assert verdict2 == VerifyResult.OK


@pytest.mark.asyncio
async def test_cleanup_expired_deletes_old(db):
    from server.auth.codes import AuthCodeService
    svc = AuthCodeService(db)
    # Создать 2 кода, у одного подкрутить expires_at в прошлое
    r1 = await svc.request_code("nikita")
    r2 = await svc.request_code("nikita")
    stmt = select(models.AuthCode).where(models.AuthCode.id == r1.request_id)
    rec1 = (await db.execute(stmt)).scalar_one()
    rec1.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    await db.commit()

    count = await svc.cleanup_expired()
    assert count == 1

    # Убедиться что осталась только вторая
    all_stmt = select(models.AuthCode)
    all_records = (await db.execute(all_stmt)).scalars().all()
    assert len(all_records) == 1
    assert all_records[0].id == r2.request_id
