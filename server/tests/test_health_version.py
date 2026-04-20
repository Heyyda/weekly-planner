"""
Тесты health и version endpoints — public, без auth.

GET /api/health  → 200 {"status": "ok"}
GET /api/version → 200 {"version": "0.1.0", "download_url": ..., "sha256": ...}

Оба endpoint не требуют Bearer — используются для monitoring и авто-обновления.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    """Настроить env vars и очистить кеш settings."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'hv.db'}")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:test_token_for_tests")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita")
    from server.config import get_settings
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_health_returns_ok():
    """GET /api/health → 200 {"status": "ok"}."""
    from server.api.app import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_version_returns_schema():
    """GET /api/version → 200 с version, download_url, sha256."""
    from server.api.app import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/version")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "0.1.0"
    # download_url может быть пустым пока manifest /opt/planner/releases/latest.json не создан
    assert "download_url" in data
    assert "sha256" in data


@pytest.mark.asyncio
async def test_health_no_auth_required():
    """Health endpoint не требует Bearer — для reverse-proxy и systemd healthcheck."""
    from server.api.app import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Запрос без Authorization header
        r = await ac.get("/api/health")
    assert r.status_code == 200  # НЕ 401
