"""
Integration тесты /api/sync — auth required, CRUD через op, tombstone, delta.

Использует паттерн из test_auth_routes.py: логинимся через /verify, получаем
access, дальше все sync вызовы с Bearer.

Покрывает SRV-02 (delta-синхронизация) и SRV-06 (server-side updated_at).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.db.base import Base


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    """Настроить env vars и очистить кеш settings."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'sync.db'}")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:test_token_for_tests")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita")
    from server.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def authed_client(monkeypatch):
    """App + client + логин → возвращает (client, access_token, user_id, factory)."""
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

    # Мок Telegram — не ходим в реальный API
    sent_codes: list[dict] = []

    async def fake_send(chat_id, code, hostname, msk_time_str, **kwargs):
        from server.auth.telegram import TelegramSendError
        sent_codes.append({"chat_id": chat_id, "code": code})
        return TelegramSendError.OK

    monkeypatch.setattr("server.api.auth_routes.send_auth_code", fake_send)

    # Предсоздать user с chat_id чтобы Telegram отправил код
    async with factory() as session:
        session.add(User(telegram_username="nikita", telegram_chat_id=12345))
        await session.commit()

    from server.api.app import app
    from server.api.rate_limit import limiter
    limiter.reset()  # Сброс лимитов между тестами
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login flow
        r1 = await ac.post("/api/auth/request-code", json={"username": "nikita", "hostname": "pc"})
        assert r1.status_code == 200, f"request-code failed: {r1.text}"
        r2 = await ac.post(
            "/api/auth/verify",
            json={"request_id": r1.json()["request_id"], "code": sent_codes[-1]["code"]},
        )
        assert r2.status_code == 200, f"verify failed: {r2.text}"
        access = r2.json()["access_token"]
        user_id = r2.json()["user_id"]
        yield ac, access, user_id, factory

    app.dependency_overrides.clear()
    limiter.reset()
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Auth guard: POST /api/sync без Bearer → 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_requires_auth(authed_client):
    """Sync endpoint защищён Bearer auth — без токена 401."""
    ac, access, user_id, _ = authed_client
    r = await ac.post("/api/sync", json={"since": None, "changes": []})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 2. Пустой sync: нет changes → server_timestamp + пустой список
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_empty_returns_server_timestamp(authed_client):
    ac, access, user_id, _ = authed_client
    r = await ac.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {access}"},
        json={"since": None, "changes": []},
    )
    assert r.status_code == 200
    data = r.json()
    assert "server_timestamp" in data
    assert data["changes"] == []


# ---------------------------------------------------------------------------
# 3. CREATE task через op=create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_create_task(authed_client):
    """CREATE task: task_id, text, day, done=False; updated_at server-side (SRV-06)."""
    ac, access, user_id, _ = authed_client
    body = {
        "since": None,
        "changes": [
            {
                "op": "create",
                "task_id": "task-uuid-1",
                "text": "купить молоко",
                "day": "2026-04-14",
                "done": False,
                "position": 0,
            }
        ],
    }
    r = await ac.post("/api/sync", headers={"Authorization": f"Bearer {access}"}, json=body)
    assert r.status_code == 200
    data = r.json()
    assert len(data["changes"]) == 1
    t = data["changes"][0]
    assert t["task_id"] == "task-uuid-1"
    assert t["text"] == "купить молоко"
    assert t["day"] == "2026-04-14"
    assert t["done"] is False
    assert t["deleted_at"] is None
    # SRV-06: updated_at выставляется сервером — он должен быть в ответе
    assert t["updated_at"] is not None, "SRV-06: updated_at должен быть server-side"


# ---------------------------------------------------------------------------
# 4. UPDATE task (частичный): меняем только done
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_update_task_partial(authed_client):
    """UPDATE с одним полем (done=True) не затирает остальные поля."""
    ac, access, user_id, _ = authed_client
    # Сначала create
    await ac.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "since": None,
            "changes": [
                {
                    "op": "create",
                    "task_id": "t1",
                    "text": "оригинал",
                    "day": "2026-04-14",
                    "done": False,
                    "position": 0,
                }
            ],
        },
    )
    # Update только done
    r = await ac.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "since": None,
            "changes": [{"op": "update", "task_id": "t1", "done": True}],
        },
    )
    data = r.json()
    t1 = next(t for t in data["changes"] if t["task_id"] == "t1")
    assert t1["done"] is True
    assert t1["text"] == "оригинал"  # не затёрто частичным update


# ---------------------------------------------------------------------------
# 5. DELETE через op=delete → tombstone (SRV-02 + SYNC-08)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_delete_task_creates_tombstone(authed_client):
    """op=delete ставит deleted_at (tombstone), не hard-delete."""
    ac, access, user_id, _ = authed_client
    # Создать task
    await ac.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "since": None,
            "changes": [
                {
                    "op": "create",
                    "task_id": "t-del",
                    "text": "к удалению",
                    "day": "2026-04-14",
                    "done": False,
                    "position": 0,
                }
            ],
        },
    )
    # Удалить
    r = await ac.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "since": None,
            "changes": [{"op": "delete", "task_id": "t-del"}],
        },
    )
    data = r.json()
    t_del = next(t for t in data["changes"] if t["task_id"] == "t-del")
    # Tombstone: deleted_at не None
    assert t_del["deleted_at"] is not None, "Tombstone: deleted_at должен быть выставлен"


# ---------------------------------------------------------------------------
# 6. Delta-query по since: фильтрует старые tasks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_delta_query_filters_by_since(authed_client):
    """Since-timestamp: возвращаются только tasks с updated_at > since."""
    ac, access, user_id, _ = authed_client
    headers = {"Authorization": f"Bearer {access}"}

    # Создать 2 tasks
    await ac.post(
        "/api/sync",
        headers=headers,
        json={
            "since": None,
            "changes": [
                {"op": "create", "task_id": "a", "text": "старая1", "day": "2026-04-14", "done": False, "position": 0},
                {"op": "create", "task_id": "b", "text": "старая2", "day": "2026-04-14", "done": False, "position": 1},
            ],
        },
    )

    # Получить текущий server_timestamp как since
    r_ts = await ac.post("/api/sync", headers=headers, json={"since": None, "changes": []})
    mid_ts = r_ts.json()["server_timestamp"]

    # Небольшая пауза чтобы updated_at новой task был строго > mid_ts
    await asyncio.sleep(1.1)

    # Создать новую task
    await ac.post(
        "/api/sync",
        headers=headers,
        json={
            "since": None,
            "changes": [
                {"op": "create", "task_id": "c", "text": "новая", "day": "2026-04-14", "done": False, "position": 2}
            ],
        },
    )

    # Delta с since=mid_ts — должна вернуться только "c"
    r = await ac.post("/api/sync", headers=headers, json={"since": mid_ts, "changes": []})
    data = r.json()
    returned_ids = {t["task_id"] for t in data["changes"]}
    assert "c" in returned_ids, "Новая task должна быть в delta"
    # a и b создавались до mid_ts — их не должно быть
    assert "a" not in returned_ids, "Старая task 'a' не должна быть в delta"
    assert "b" not in returned_ids, "Старая task 'b' не должна быть в delta"


# ---------------------------------------------------------------------------
# 7. Server-wins: updated_at всегда из БД, не из клиента (SRV-06)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_server_sets_updated_at_not_client(authed_client):
    """SRV-06: клиент не может подменить updated_at — сервер всегда выставляет своё."""
    ac, access, user_id, _ = authed_client
    # Создать task — клиент не передаёт updated_at
    r = await ac.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "since": None,
            "changes": [
                {
                    "op": "create",
                    "task_id": "srv-time-test",
                    "text": "test",
                    "day": "2026-04-14",
                    "done": False,
                    "position": 0,
                }
            ],
        },
    )
    assert r.status_code == 200
    t = r.json()["changes"][0]
    # updated_at должен быть близко к текущему времени (в пределах 5 секунд)
    updated_at_str = t["updated_at"]
    # Нормализуем "Z" → "+00:00" для Python < 3.11 совместимости
    updated_at_str = updated_at_str.rstrip("Z") + "+00:00" if updated_at_str.endswith("Z") else updated_at_str
    updated_at = datetime.fromisoformat(updated_at_str)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff_seconds = abs((now - updated_at).total_seconds())
    assert diff_seconds < 5, f"updated_at слишком далеко от server now: {diff_seconds}s"


# ---------------------------------------------------------------------------
# 8. Row-level isolation: user A не может трогать task user B
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_user_id_set_from_jwt_not_body(authed_client):
    """user_id всегда берётся из JWT, не из тела запроса — cross-user isolation."""
    ac, access, user_id, factory = authed_client

    # Создать "чужого" user и его task напрямую в БД
    from server.db.models import Task, User as UserModel
    async with factory() as session:
        other = UserModel(telegram_username="other")
        session.add(other)
        await session.commit()
        await session.refresh(other)
        other_id = other.id
        other_task = Task(
            id="other-task",
            user_id=other_id,
            text="секрет",
            day="2026-04-14",
            done=False,
            position=0,
        )
        session.add(other_task)
        await session.commit()

    # Nikita пытается обновить чужую task через op=update
    r = await ac.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "since": None,
            "changes": [{"op": "update", "task_id": "other-task", "text": "взломано"}],
        },
    )
    assert r.status_code == 200

    # Проверяем что task other пользователя НЕ изменилась
    from sqlalchemy import select
    async with factory() as session:
        result = await session.execute(
            select(Task).where(Task.id == "other-task")
        )
        t = result.scalar_one()
        assert t.text == "секрет", "Текст чужой task не должен измениться"
        assert t.user_id == other_id, "user_id чужой task не должен измениться"
