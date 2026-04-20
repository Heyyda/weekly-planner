"""
End-to-end integration тест Фазы 1.

Два теста вместе гарантируют что все Plans 02-10 работают корректно:

test_phase_1_full_flow — полный flow Фазы 1:
  1.  Симулируем handle_start: user пишет /start → chat_id в БД
  2.  POST /api/auth/request-code → fake_send перехватывает код
  3.  POST /api/auth/verify с кодом → получаем access + refresh
  4.  GET /api/auth/me → подтверждаем что auth работает
  5.  POST /api/sync: CREATE task
  6.  POST /api/sync: UPDATE task (done=true)
  7.  POST /api/sync: DELETE task (tombstone)
  8.  POST /api/sync delta (since=None) → видим changes
  9.  POST /api/auth/refresh → новые токены, старый refresh revoked
  10. POST /api/auth/logout → sessions revoked
  11. POST /api/auth/refresh с revoked → 401

test_phase_1_wal_and_concurrent_writes — ROADMAP Success Criterion #4:
  - 5 параллельных async записей в SQLite с WAL
  - Все проходят без OperationalError: database is locked
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock

from server.db.base import Base


# ---------------------------------------------------------------------------
# Общий fixture окружения — autouse для всего модуля
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """Установить env vars + очистить кеш settings перед каждым тестом."""
    # DATABASE_URL не задаём здесь — каждый тест создаёт свой engine с tmp_path
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:test_token_e2e")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita_heyyda")
    from server.config import get_settings
    get_settings.cache_clear()


def _make_bot_message(*, chat_id: int, tg_username: str):
    """
    Создать aiogram Message через pydantic.model_validate (без реального API).

    Аналог вспомогательной функции из test_bot_handlers.py.
    object.__setattr__ нужен из-за frozen pydantic модели aiogram.
    """
    from aiogram.types import Message
    data = {
        "message_id": 1,
        "date": 1234567890,
        "chat": {"id": chat_id, "type": "private"},
        "from": {
            "id": 111,
            "is_bot": False,
            "first_name": "Nikita",
            "username": tg_username,
        },
        "text": "/start",
    }
    msg = Message.model_validate(data)
    object.__setattr__(msg, "answer", AsyncMock())
    return msg


# ---------------------------------------------------------------------------
# Task 1: test_phase_1_full_flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase_1_full_flow(monkeypatch, tmp_path):
    """
    Полный e2e flow: bot /start → auth → sync CRUD → refresh rotation → logout → revoke verify.

    Этот тест — финальная гарантия что Фаза 1 (Plans 02-10) собрана корректно
    и все компоненты работают вместе.
    """
    from server.config import get_settings
    from server.db.engine import _attach_pragma_listener, get_db
    from server.db import models as _models  # noqa: F401 — регистрируем модели в Base.metadata

    db_path = tmp_path / "e2e_flow.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    _attach_pragma_listener(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    # Подменить AsyncSessionLocal в bot.handlers на тестовую фабрику
    monkeypatch.setattr("server.bot.handlers.AsyncSessionLocal", factory)

    # Перехват send_auth_code — сохраняем отправленные коды, не ходим в Telegram
    sent_codes: list[dict] = []

    async def fake_send(chat_id, code, hostname, msk_time_str, **kwargs):
        from server.auth.telegram import TelegramSendError
        sent_codes.append({"chat_id": chat_id, "code": code, "hostname": hostname})
        return TelegramSendError.OK

    monkeypatch.setattr("server.api.auth_routes.send_auth_code", fake_send)

    # Сбросить состояние rate-limiter между тестами
    from server.api.rate_limit import limiter
    limiter.reset()

    from server.api.app import app
    app.dependency_overrides[get_db] = override_get_db

    try:
        # ---------------------------------------------------------------
        # STEP 1: Bot /start → chat_id записан в БД
        # ---------------------------------------------------------------
        from server.bot.handlers import handle_start

        msg = _make_bot_message(chat_id=99999, tg_username="nikita_heyyda")
        await handle_start(msg)
        msg.answer.assert_called_once()  # бот ответил пользователю

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

            # ---------------------------------------------------------------
            # STEP 2: POST /api/auth/request-code
            # ---------------------------------------------------------------
            r1 = await ac.post(
                "/api/auth/request-code",
                json={"username": "nikita_heyyda", "hostname": "e2e-test-pc"},
            )
            assert r1.status_code == 200, f"request-code failed: {r1.text}"
            request_id = r1.json()["request_id"]
            assert r1.json()["expires_in"] == 300  # D-07: 5 минут

            # fake_send перехватил вызов — берём код из захваченных данных
            assert len(sent_codes) == 1
            assert sent_codes[0]["chat_id"] == 99999  # chat_id из /start
            assert sent_codes[0]["hostname"] == "e2e-test-pc"
            code = sent_codes[0]["code"]
            assert len(code) == 6 and code.isdigit()  # D-06: 6 цифр

            # ---------------------------------------------------------------
            # STEP 3: POST /api/auth/verify → access + refresh
            # ---------------------------------------------------------------
            r2 = await ac.post(
                "/api/auth/verify",
                json={"request_id": request_id, "code": code, "device_name": "e2e-device"},
            )
            assert r2.status_code == 200, f"verify failed: {r2.text}"
            tokens = r2.json()
            access = tokens["access_token"]
            refresh = tokens["refresh_token"]
            user_id = tokens["user_id"]
            assert tokens["expires_in"] == 900  # D-12: 15 минут
            assert tokens["token_type"] == "bearer"
            assert user_id

            # ---------------------------------------------------------------
            # STEP 4: GET /api/auth/me → подтверждаем username
            # ---------------------------------------------------------------
            r3 = await ac.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access}"},
            )
            assert r3.status_code == 200
            me_data = r3.json()
            assert me_data["username"] == "nikita_heyyda"
            assert me_data["user_id"] == user_id

            # ---------------------------------------------------------------
            # STEP 5: POST /api/sync — CREATE task
            # ---------------------------------------------------------------
            r4 = await ac.post(
                "/api/sync",
                headers={"Authorization": f"Bearer {access}"},
                json={
                    "since": None,
                    "changes": [
                        {
                            "op": "create",
                            "task_id": "task-e2e-alpha",
                            "text": "e2e test task",
                            "day": "2026-04-14",
                            "done": False,
                            "position": 0,
                        }
                    ],
                },
            )
            assert r4.status_code == 200, f"sync CREATE failed: {r4.text}"
            sync_data = r4.json()
            assert "server_timestamp" in sync_data
            task = next(t for t in sync_data["changes"] if t["task_id"] == "task-e2e-alpha")
            assert task["text"] == "e2e test task"
            assert task["done"] is False
            assert task["deleted_at"] is None
            assert task["updated_at"] is not None  # SRV-06: server-side timestamp

            # ---------------------------------------------------------------
            # STEP 6: POST /api/sync — UPDATE task (done=True)
            # ---------------------------------------------------------------
            r5 = await ac.post(
                "/api/sync",
                headers={"Authorization": f"Bearer {access}"},
                json={
                    "since": None,
                    "changes": [
                        {"op": "update", "task_id": "task-e2e-alpha", "done": True}
                    ],
                },
            )
            assert r5.status_code == 200, f"sync UPDATE failed: {r5.text}"
            updated_task = next(
                t for t in r5.json()["changes"] if t["task_id"] == "task-e2e-alpha"
            )
            assert updated_task["done"] is True
            assert updated_task["text"] == "e2e test task"  # text не затёрт частичным update

            # ---------------------------------------------------------------
            # STEP 7: POST /api/sync — DELETE task (tombstone)
            # ---------------------------------------------------------------
            r6 = await ac.post(
                "/api/sync",
                headers={"Authorization": f"Bearer {access}"},
                json={
                    "since": None,
                    "changes": [
                        {"op": "delete", "task_id": "task-e2e-alpha"}
                    ],
                },
            )
            assert r6.status_code == 200, f"sync DELETE failed: {r6.text}"
            deleted_task = next(
                t for t in r6.json()["changes"] if t["task_id"] == "task-e2e-alpha"
            )
            # Tombstone: deleted_at выставлен, запись не удалена физически
            assert deleted_task["deleted_at"] is not None, "SRV-02: tombstone должен иметь deleted_at"

            # ---------------------------------------------------------------
            # STEP 8: POST /api/sync delta (since=None) → видим task-e2e-alpha c tombstone
            # ---------------------------------------------------------------
            r7 = await ac.post(
                "/api/sync",
                headers={"Authorization": f"Bearer {access}"},
                json={"since": None, "changes": []},
            )
            assert r7.status_code == 200
            delta_changes = r7.json()["changes"]
            tombstone = next(
                (t for t in delta_changes if t["task_id"] == "task-e2e-alpha"), None
            )
            assert tombstone is not None, "Удалённая task должна присутствовать в delta"
            assert tombstone["deleted_at"] is not None

            # ---------------------------------------------------------------
            # STEP 9: POST /api/auth/refresh → rotating refresh (AUTH-04, D-13)
            # ---------------------------------------------------------------
            r8 = await ac.post("/api/auth/refresh", json={"refresh_token": refresh})
            assert r8.status_code == 200, f"refresh failed: {r8.text}"
            new_tokens = r8.json()
            new_access = new_tokens["access_token"]
            new_refresh = new_tokens["refresh_token"]
            assert new_refresh != refresh  # rolling: выдан новый refresh

            # Старый refresh больше не работает (revoked при rotation)
            r9 = await ac.post("/api/auth/refresh", json={"refresh_token": refresh})
            assert r9.status_code == 401
            assert r9.json()["detail"]["error"]["code"] == "INVALID_REFRESH"

            # ---------------------------------------------------------------
            # STEP 10: POST /api/auth/logout → все сессии revoked (AUTH-05)
            # ---------------------------------------------------------------
            r10 = await ac.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {new_access}"},
            )
            assert r10.status_code == 204

            # ---------------------------------------------------------------
            # STEP 11: Новый refresh тоже не работает (session revoked после logout)
            # ---------------------------------------------------------------
            r11 = await ac.post("/api/auth/refresh", json={"refresh_token": new_refresh})
            assert r11.status_code == 401, "Refresh после logout должен возвращать 401"

            # ---------------------------------------------------------------
            # STEP 12: /api/health и /api/version — публичные, не требуют auth
            # ---------------------------------------------------------------
            r12 = await ac.get("/api/health")
            assert r12.status_code == 200
            assert r12.json()["status"] == "ok"  # ROADMAP Success Criterion #2

            r13 = await ac.get("/api/version")
            assert r13.status_code == 200
            assert "version" in r13.json()  # ROADMAP Success Criterion #2

    finally:
        app.dependency_overrides.clear()
        limiter.reset()
        await engine.dispose()


# ---------------------------------------------------------------------------
# Task 2: test_phase_1_wal_and_concurrent_writes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase_1_wal_and_concurrent_writes(monkeypatch, tmp_path):
    """
    ROADMAP Success Criterion #4: два одновременных запроса не вызывают
    OperationalError: database is locked.

    5 параллельных async писателей → все проходят благодаря WAL + busy_timeout=5000.
    Этот тест дублирует test_engine.py::test_concurrent_writes_no_lock, но явно
    привязан к Phase 1 success criterion и использует реальный файл (не in-memory)
    для честной проверки WAL.
    """
    from sqlalchemy import select
    from server.db.engine import _attach_pragma_listener
    from server.db import models

    db_path = tmp_path / "wal_concurrent.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    from server.config import get_settings
    get_settings.cache_clear()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    _attach_pragma_listener(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async def write_user(username: str) -> None:
            """Записать одного пользователя в БД — один конкурентный писатель."""
            async with factory() as sess:
                sess.add(models.User(telegram_username=username))
                await sess.commit()

        # 5 параллельных писателей — без WAL хотя бы один упал бы с database is locked
        await asyncio.gather(*[write_user(f"concurrent_user_{i}") for i in range(5)])

        # Проверяем что все 5 успешно записаны
        async with factory() as sess:
            result = await sess.execute(select(models.User))
            users = result.scalars().all()
            assert len(users) == 5, (
                f"Ожидалось 5 пользователей, получили {len(users)} — "
                "возможно WAL не включён или busy_timeout не работает"
            )

        # Дополнительно: убедиться что journal_mode=wal
        from sqlalchemy import text
        async with factory() as sess:
            result = await sess.execute(text("PRAGMA journal_mode"))
            journal_mode = result.scalar()
            assert journal_mode == "wal", (
                f"PRAGMA journal_mode должен быть 'wal', получили '{journal_mode}'"
            )

    finally:
        await engine.dispose()
