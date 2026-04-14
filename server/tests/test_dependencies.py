"""Тесты get_current_user — через мини-FastAPI app с одной защищённой route."""
from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.db.base import Base
from server.db import models


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'deps.db'}")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:ABC")
    monkeypatch.setenv("ALLOWED_USERNAMES", "test")
    from server.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def app_and_user():
    """Мини FastAPI app с /whoami защищённой через get_current_user."""
    from server.auth.dependencies import get_current_user
    from server.db.engine import get_db, _attach_pragma_listener
    from server.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    _attach_pragma_listener(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Создать user для тестов
    async with factory() as session:
        user = models.User(telegram_username="testuser")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    async def override_get_db():
        async with factory() as session:
            yield session

    app = FastAPI()
    app.dependency_overrides[get_db] = override_get_db

    @app.get("/whoami")
    async def whoami(current_user: models.User = Depends(get_current_user)):
        return {"id": current_user.id, "username": current_user.telegram_username}

    yield app, user_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_valid_token_returns_user(app_and_user):
    app, user_id = app_and_user
    from server.auth.jwt import create_access_token
    token = create_access_token(user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == user_id
    assert data["username"] == "testuser"


@pytest.mark.asyncio
async def test_missing_bearer_returns_401(app_and_user):
    app, _ = app_and_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/whoami")
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"]["error"]["code"] == "MISSING_TOKEN"


@pytest.mark.asyncio
async def test_invalid_token_returns_401(app_and_user):
    app, _ = app_and_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/whoami", headers={"Authorization": "Bearer garbage.jwt.token"})
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"]["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_user_not_in_db_returns_401(app_and_user):
    app, _ = app_and_user
    from server.auth.jwt import create_access_token
    token = create_access_token("nonexistent-user-id")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"]["error"]["code"] == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_expired_token_returns_401(app_and_user):
    app, user_id = app_and_user
    from datetime import datetime, timezone, timedelta
    import jwt as pyjwt
    from server.config import get_settings
    settings = get_settings()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    expired = pyjwt.encode(
        {"sub": user_id, "type": "access", "iat": past, "exp": past},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/whoami", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "INVALID_TOKEN"
