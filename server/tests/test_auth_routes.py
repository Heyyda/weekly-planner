"""
Integration тесты auth endpoints — Plan 06.

Паттерн:
- fixture `_setup_env` — monkeypatch env vars (autouse, scope=function)
  + get_settings.cache_clear() чтобы не было кеша из предыдущих тестов
- fixture `app_client` — FastAPI app с in-file SQLite (tmp_path),
  override_get_db на тестовую БД, мокнутый send_auth_code
- httpx.AsyncClient привязан к app через ASGITransport

Покрыты сценарии (AUTH-01..05, SRV-01, D-17, D-18):
1. request-code: user_not_allowed → 403 USER_NOT_ALLOWED
2. request-code: успех → 200 + request_id + sends telegram
3. request-code: chat_id is None → 400 BOT_NOT_STARTED
4. full flow: request-code → verify → /me (end-to-end AUTH-01 + AUTH-02)
5. verify: неверный код → 400 INVALID_CODE
6. verify: malformed код (5 цифр) → 422 Pydantic validation
7. refresh: rotation работает, старый токен инвалидируется (AUTH-04)
8. refresh: garbage refresh → 401 INVALID_REFRESH
9. logout: revoke all → последующий refresh 401 (AUTH-05)
10. /me без токена → 401 MISSING_TOKEN
11. logout: revoke конкретной сессии, остальные живут
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.db.base import Base


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    """Настроить env vars для тестов и очистить кеш settings."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'e2e.db'}")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "test_token_1234567890")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita")
    from server.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def app_client(monkeypatch, tmp_path):
    """
    FastAPI app + httpx AsyncClient + перехваченный send_auth_code.

    Возвращает тройку (ac, sent_codes, factory) для доступа к БД в тестах.
    sent_codes — список dict с {chat_id, code, hostname} из перехваченных вызовов.
    """
    from server.config import get_settings
    from server.db.engine import _attach_pragma_listener, get_db
    from server.db.models import User

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    _attach_pragma_listener(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    # Мок send_auth_code — сохраняем вызовы в список, не ходим в реальный Telegram
    sent_codes: list[dict] = []

    async def fake_send_auth_code(chat_id, code, hostname, msk_time_str, **kwargs):
        from server.auth.telegram import TelegramSendError
        sent_codes.append({"chat_id": chat_id, "code": code, "hostname": hostname})
        # Если chat_id не задан — user не написал /start боту
        if chat_id is None:
            return TelegramSendError.BOT_NOT_STARTED
        return TelegramSendError.OK

    monkeypatch.setattr("server.api.auth_routes.send_auth_code", fake_send_auth_code)

    # Импортируем app после override env vars
    from server.api.app import app
    app.dependency_overrides[get_db] = override_get_db

    # Предзаполнить пользователя nikita с chat_id (чтобы Telegram мог отправить код)
    async with factory() as session:
        user = User(telegram_username="nikita", telegram_chat_id=12345)
        session.add(user)
        await session.commit()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac, sent_codes, factory
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


# ---------------------------------------------------------------------------
# 1. request-code: unknown user → 403 USER_NOT_ALLOWED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_code_user_not_allowed(app_client):
    ac, _, _ = app_client
    resp = await ac.post(
        "/api/auth/request-code",
        json={"username": "stranger", "hostname": "pc"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"]["code"] == "USER_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# 2. request-code: успешный запрос → request_id + Telegram отправлен
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_code_success_sends_telegram(app_client):
    ac, sent, _ = app_client
    resp = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "work-pc"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "request_id" in data
    assert data["expires_in"] == 300  # 5 минут (D-07)

    # Telegram был вызван с правильными параметрами
    assert len(sent) == 1
    assert sent[0]["chat_id"] == 12345
    assert sent[0]["hostname"] == "work-pc"
    assert len(sent[0]["code"]) == 6
    assert sent[0]["code"].isdigit()


# ---------------------------------------------------------------------------
# 3. request-code: chat_id is None → 400 BOT_NOT_STARTED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_code_bot_not_started(app_client):
    """Пользователь ещё не написал /start боту — chat_id = NULL."""
    ac, _, factory = app_client
    # Сбрасываем chat_id для nikita
    async with factory() as session:
        await session.execute(
            update(__import__("server.db.models", fromlist=["User"]).User)
            .where(__import__("server.db.models", fromlist=["User"]).User.telegram_username == "nikita")
            .values(telegram_chat_id=None)
        )
        await session.commit()

    resp = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "pc"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "BOT_NOT_STARTED"


# ---------------------------------------------------------------------------
# 4. Full flow: request-code → verify → /me  (AUTH-01 + AUTH-02 + SRV-01)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_auth_flow_request_verify_me(app_client):
    """End-to-end: username → код в Telegram → JWT → /me."""
    ac, sent, _ = app_client

    # Шаг 1: запросить код
    r1 = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "pc"},
    )
    assert r1.status_code == 200
    request_id = r1.json()["request_id"]
    code = sent[-1]["code"]

    # Шаг 2: верифицировать код → получить токены
    r2 = await ac.post(
        "/api/auth/verify",
        json={"request_id": request_id, "code": code, "device_name": "test-pc"},
    )
    assert r2.status_code == 200
    tokens = r2.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["expires_in"] == 900  # 15 минут (D-12)
    assert tokens["token_type"] == "bearer"
    assert tokens["user_id"]

    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # Шаг 3: /me с access token
    r3 = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r3.status_code == 200
    me_data = r3.json()
    assert me_data["username"] == "nikita"
    assert me_data["user_id"] == tokens["user_id"]
    assert "created_at" in me_data


# ---------------------------------------------------------------------------
# 5. verify: неверный код → 400 INVALID_CODE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_invalid_code(app_client):
    ac, _, _ = app_client
    r1 = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "pc"},
    )
    request_id = r1.json()["request_id"]

    # 000000 почти наверняка не равен реальному коду (шанс 1/1000000)
    r2 = await ac.post(
        "/api/auth/verify",
        json={"request_id": request_id, "code": "000000"},
    )
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"]["code"] == "INVALID_CODE"


# ---------------------------------------------------------------------------
# 6. verify: malformed код (5 цифр) → 422 Pydantic validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_malformed_code_rejected_by_pydantic(app_client):
    ac, _, _ = app_client
    r1 = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "pc"},
    )
    request_id = r1.json()["request_id"]

    # 5 цифр — Pydantic validator должен отклонить
    r2 = await ac.post(
        "/api/auth/verify",
        json={"request_id": request_id, "code": "12345"},
    )
    assert r2.status_code == 422  # Pydantic ValidationError


# ---------------------------------------------------------------------------
# 7. refresh: rotation (AUTH-04 rolling refresh)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_rotates_tokens(app_client):
    """Старый refresh → новый access + новый refresh. Старый больше не работает."""
    ac, sent, _ = app_client

    r1 = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "pc"},
    )
    code = sent[-1]["code"]
    r2 = await ac.post(
        "/api/auth/verify",
        json={"request_id": r1.json()["request_id"], "code": code},
    )
    old_refresh = r2.json()["refresh_token"]

    # Rotation
    r3 = await ac.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert r3.status_code == 200
    new_tokens = r3.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]
    assert new_tokens["refresh_token"] != old_refresh  # rolling: новый токен

    # Старый refresh больше не работает (revoked)
    r4 = await ac.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert r4.status_code == 401
    assert r4.json()["detail"]["error"]["code"] == "INVALID_REFRESH"


# ---------------------------------------------------------------------------
# 8. refresh: garbage token → 401 INVALID_REFRESH
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_invalid_returns_401(app_client):
    ac, _, _ = app_client
    r = await ac.post(
        "/api/auth/refresh",
        json={"refresh_token": "garbage.token.here"},
    )
    assert r.status_code == 401
    assert r.json()["detail"]["error"]["code"] == "INVALID_REFRESH"


# ---------------------------------------------------------------------------
# 9. logout: revoke all → refresh больше не работает (AUTH-05)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_revokes_session(app_client):
    ac, sent, _ = app_client

    # Login
    r1 = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "pc"},
    )
    code = sent[-1]["code"]
    r2 = await ac.post(
        "/api/auth/verify",
        json={"request_id": r1.json()["request_id"], "code": code},
    )
    access = r2.json()["access_token"]
    refresh = r2.json()["refresh_token"]

    # Logout (без body → revoke все)
    r3 = await ac.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r3.status_code == 204

    # Refresh не работает (session revoked)
    r4 = await ac.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r4.status_code == 401
    assert r4.json()["detail"]["error"]["code"] == "INVALID_REFRESH"


# ---------------------------------------------------------------------------
# 10. /me без токена → 401 MISSING_TOKEN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_without_auth_returns_401(app_client):
    ac, _, _ = app_client
    r = await ac.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["detail"]["error"]["code"] == "MISSING_TOKEN"


# ---------------------------------------------------------------------------
# 11. logout: revoke конкретной сессии, остальные живут
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_with_specific_refresh_token(app_client):
    """
    Logout с body {refresh_token} → revoke только эту сессию.
    Второй refresh (другого устройства) остаётся рабочим.
    """
    ac, sent, _ = app_client

    # Первая сессия (устройство 1)
    r1 = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "pc"},
    )
    code1 = sent[-1]["code"]
    r2 = await ac.post(
        "/api/auth/verify",
        json={"request_id": r1.json()["request_id"], "code": code1},
    )
    access1 = r2.json()["access_token"]
    refresh1 = r2.json()["refresh_token"]

    # Вторая сессия (устройство 2 — тот же user, новый код)
    r3 = await ac.post(
        "/api/auth/request-code",
        json={"username": "nikita", "hostname": "phone"},
    )
    code2 = sent[-1]["code"]
    r4 = await ac.post(
        "/api/auth/verify",
        json={"request_id": r3.json()["request_id"], "code": code2},
    )
    refresh2 = r4.json()["refresh_token"]

    # Logout первой сессии (передаём её refresh_token)
    r5 = await ac.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access1}"},
        json={"refresh_token": refresh1},
    )
    assert r5.status_code == 204

    # refresh1 не работает (revoked)
    r6 = await ac.post("/api/auth/refresh", json={"refresh_token": refresh1})
    assert r6.status_code == 401

    # refresh2 всё ещё работает (другая сессия)
    r7 = await ac.post("/api/auth/refresh", json={"refresh_token": refresh2})
    assert r7.status_code == 200
