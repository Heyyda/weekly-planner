"""
Тесты rate-limit на /api/auth/request-code (CONTEXT.md D-09).

slowapi ключ = IP address (get_remote_address). В httpx AsyncClient все запросы
идут от одного "IP" (127.0.0.1), поэтому лимит 1/minute срабатывает на втором запросе.

Для изоляции тестов limiter.reset() вызывается в setUp/tearDown fixture.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.db.base import Base


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    """Настроить env vars и очистить кеш settings."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'rl.db'}")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:test_token_for_tests")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita")
    from server.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client_with_user(monkeypatch):
    """App client + предсозданный user + мокнутый Telegram + сброшенный limiter."""
    from server.config import get_settings
    from server.db.models import User  # noqa: F401 — нужен до create_all чтобы модели попали в Base.metadata
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    from server.db.engine import _attach_pragma_listener, get_db
    _attach_pragma_listener(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    async def fake_send(chat_id, code, hostname, msk_time_str, **kwargs):
        from server.auth.telegram import TelegramSendError
        return TelegramSendError.OK

    monkeypatch.setattr("server.api.auth_routes.send_auth_code", fake_send)

    async with factory() as session:
        session.add(User(telegram_username="nikita", telegram_chat_id=12345))
        await session.commit()

    from server.api.app import app
    from server.api.rate_limit import limiter

    # КРИТИЧНО: limiter состояние глобальное — сбрасываем перед каждым тестом
    limiter.reset()

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    limiter.reset()
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Первый запрос — 200; второй в той же минуте — 429
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_code_rate_limited_on_second_call(client_with_user):
    """CONTEXT.md D-09: лимит 1/минуту на POST /api/auth/request-code по IP."""
    ac = client_with_user

    # Первый запрос — OK
    r1 = await ac.post("/api/auth/request-code", json={"username": "nikita", "hostname": "pc"})
    assert r1.status_code == 200, f"Первый запрос должен пройти: {r1.text}"

    # Второй запрос в той же минуте — Rate Limited
    r2 = await ac.post("/api/auth/request-code", json={"username": "nikita", "hostname": "pc"})
    assert r2.status_code == 429, f"Второй запрос должен быть отклонён rate-limit: {r2.text}"

    # Проверяем формат D-18: {"error": {"code": "RATE_LIMIT_EXCEEDED", ...}}
    data = r2.json()
    assert "error" in data, f"Ответ должен содержать ключ 'error': {data}"
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    # Retry-After header присутствует
    headers_lower = {k.lower(): v for k, v in r2.headers.items()}
    assert "retry-after" in headers_lower, "Retry-After header должен присутствовать"


# ---------------------------------------------------------------------------
# 2. Rate-limit не распространяется на другие endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_does_not_affect_other_endpoints(client_with_user):
    """Rate-limit только на /request-code — health и version не ограничены."""
    ac = client_with_user

    # Hit request-code чтобы лимит засчитался
    await ac.post("/api/auth/request-code", json={"username": "nikita", "hostname": "pc"})

    # Health доступен без ограничений (несколько запросов подряд)
    r1 = await ac.get("/api/health")
    assert r1.status_code == 200
    r2 = await ac.get("/api/health")
    assert r2.status_code == 200

    # Version тоже не ограничен
    r3 = await ac.get("/api/version")
    assert r3.status_code == 200


# ---------------------------------------------------------------------------
# 3. 429 содержит Retry-After header (проверяем структуру ответа)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_response_contains_retry_after(client_with_user):
    """429 ответ содержит Retry-After header для клиента."""
    ac = client_with_user

    # Исчерпать лимит
    await ac.post("/api/auth/request-code", json={"username": "nikita", "hostname": "pc"})
    r = await ac.post("/api/auth/request-code", json={"username": "nikita", "hostname": "pc"})

    assert r.status_code == 429
    headers_lower = {k.lower(): v for k, v in r.headers.items()}
    assert "retry-after" in headers_lower
    # Значение должно быть числом (секунды)
    retry_after = headers_lower["retry-after"]
    assert retry_after.isdigit(), f"Retry-After должен быть числом: {retry_after}"
