"""
Unit тесты handle_start — создаём aiogram Message вручную через pydantic.model_validate,
не гоняем long-polling.

Покрываемые сценарии:
1. Allowed user с username → chat_id записан в БД, ответ START_SUCCESS_TEXT
2. Allowed user без username → инструкция "задайте username"
3. Not-allowed user → ACCESS_DENIED_TEXT, НЕТ записи в users
4. Повторный /start (идемпотентность) → chat_id обновлён
5. Case-insensitive username (Nikita_Heyyda == nikita_heyyda)

Ни один тест не делает реальный HTTP-запрос в Telegram API.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.db.base import Base
from server.db import models


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """Установить все обязательные env vars перед каждым тестом."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:abcdefghijklmnopqrstuvwxyz12345")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita_heyyda")
    from server.config import get_settings
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_ready(tmp_path, monkeypatch):
    """
    Инициализировать тестовую async SQLite БД и замонкипатчить AsyncSessionLocal в handlers.

    Возвращает async_sessionmaker чтобы тесты могли проверить состояние БД напрямую.
    """
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'bot_test.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    from server.config import get_settings
    get_settings.cache_clear()

    engine = create_async_engine(db_url, echo=False)
    from server.db.engine import _attach_pragma_listener
    _attach_pragma_listener(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Подменить AsyncSessionLocal в server.bot.handlers на нашу тестовую фабрику
    monkeypatch.setattr("server.bot.handlers.AsyncSessionLocal", factory)

    yield factory

    await engine.dispose()


def _make_message(*, chat_id: int, tg_username: str | None, user_id: int = 111):
    """
    Создать aiogram Message через pydantic.model_validate (без реального API call).

    message.answer патчим как AsyncMock — handler вызывает message.answer(text).

    aiogram Message — замороженная pydantic-модель, поэтому прямое присваивание
    атрибута запрещено. Используем object.__setattr__ для обхода заморозки.
    """
    from aiogram.types import Message
    data = {
        "message_id": 1,
        "date": 1234567890,
        "chat": {"id": chat_id, "type": "private"},
        "from": {
            "id": user_id,
            "is_bot": False,
            "first_name": "Test",
            "username": tg_username,
        } if tg_username is not None else {
            "id": user_id,
            "is_bot": False,
            "first_name": "Test",
        },
        "text": "/start",
    }
    msg = Message.model_validate(data)
    # aiogram Message заморожен (frozen pydantic model), поэтому используем
    # object.__setattr__ для подмены метода .answer на AsyncMock
    object.__setattr__(msg, "answer", AsyncMock())
    return msg


@pytest.mark.asyncio
async def test_start_allowed_user_registers_chat_id(db_ready):
    """Allowed user отправил /start → chat_id сохранён в БД, ответ START_SUCCESS_TEXT."""
    from server.bot.handlers import handle_start, START_SUCCESS_TEXT
    factory = db_ready

    msg = _make_message(chat_id=12345, tg_username="nikita_heyyda")
    await handle_start(msg)

    msg.answer.assert_called_once_with(START_SUCCESS_TEXT)

    # Проверка БД: user создан с правильным chat_id
    async with factory() as session:
        result = await session.execute(
            select(models.User).where(models.User.telegram_username == "nikita_heyyda")
        )
        user = result.scalar_one()
        assert user.telegram_chat_id == 12345


@pytest.mark.asyncio
async def test_start_no_username(db_ready):
    """User без Telegram username → ответ с инструкцией про username, НЕТ записи в БД."""
    from server.bot.handlers import handle_start
    factory = db_ready

    msg = _make_message(chat_id=12345, tg_username=None)
    await handle_start(msg)

    # Ответ содержит инструкцию про username
    msg.answer.assert_called_once()
    args, _ = msg.answer.call_args
    assert "username" in args[0].lower()

    # Ничего не записано в БД
    async with factory() as session:
        result = await session.execute(select(models.User))
        users = result.scalars().all()
        assert len(users) == 0


@pytest.mark.asyncio
async def test_start_not_allowed_user(db_ready):
    """Not-allowed user → ACCESS_DENIED_TEXT, НЕТ записи в users."""
    from server.bot.handlers import handle_start, ACCESS_DENIED_TEXT
    factory = db_ready

    msg = _make_message(chat_id=99999, tg_username="stranger")
    await handle_start(msg)

    msg.answer.assert_called_once_with(ACCESS_DENIED_TEXT)

    # Проверка: в users таблице пусто
    async with factory() as session:
        result = await session.execute(select(models.User))
        users = result.scalars().all()
        assert all(u.telegram_username != "stranger" for u in users)
        assert len(users) == 0


@pytest.mark.asyncio
async def test_start_idempotent_updates_chat_id(db_ready):
    """Повторный /start обновляет chat_id (user перешёл на другое устройство / другой аккаунт)."""
    from server.bot.handlers import handle_start
    factory = db_ready

    # Первый /start — chat_id=12345
    msg1 = _make_message(chat_id=12345, tg_username="nikita_heyyda")
    await handle_start(msg1)

    # Второй /start — chat_id=67890 (новое устройство)
    msg2 = _make_message(chat_id=67890, tg_username="nikita_heyyda")
    await handle_start(msg2)

    # В БД один user с последним chat_id
    async with factory() as session:
        result = await session.execute(
            select(models.User).where(models.User.telegram_username == "nikita_heyyda")
        )
        users = result.scalars().all()
        assert len(users) == 1
        assert users[0].telegram_chat_id == 67890


@pytest.mark.asyncio
async def test_start_allowed_user_case_insensitive(db_ready):
    """Telegram username может приходить в любом регистре — сравнение нечувствительно к регистру."""
    from server.bot.handlers import handle_start, START_SUCCESS_TEXT
    factory = db_ready

    # Отправляем с uppercase username — должен совпасть с "nikita_heyyda" в allowed list
    msg = _make_message(chat_id=12345, tg_username="Nikita_Heyyda")
    await handle_start(msg)

    msg.answer.assert_called_once_with(START_SUCCESS_TEXT)

    # User записан в lowercase
    async with factory() as session:
        result = await session.execute(
            select(models.User).where(models.User.telegram_username == "nikita_heyyda")
        )
        user = result.scalar_one()
        assert user.telegram_chat_id == 12345


# ============ Phase 5 tests (/add, /today, /week, callbacks) ============

from datetime import date, timedelta  # noqa: E402


def _make_command_message(
    *, text: str, chat_id: int = 12345, tg_username: str = "nikita_heyyda",
):
    """Создать Message с произвольным text (для /add, /today, /week)."""
    from aiogram.types import Message
    data = {
        "message_id": 1,
        "date": 1234567890,
        "chat": {"id": chat_id, "type": "private"},
        "from": {
            "id": 111, "is_bot": False, "first_name": "Test",
            "username": tg_username,
        },
        "text": text,
    }
    msg = Message.model_validate(data)
    object.__setattr__(msg, "answer", AsyncMock())
    return msg


async def _ensure_user(factory, tg_username: str = "nikita_heyyda", chat_id: int = 12345):
    from server.bot.handlers import handle_start
    msg = _make_message(chat_id=chat_id, tg_username=tg_username)
    await handle_start(msg)
    async with factory() as session:
        user = (await session.execute(
            select(models.User).where(models.User.telegram_username == tg_username)
        )).scalar_one()
    return user


@pytest.mark.asyncio
async def test_add_creates_task(db_ready):
    from server.bot.handlers import handle_add
    factory = db_ready
    await _ensure_user(factory)

    msg = _make_command_message(text="/add купить молоко завтра 14:00")
    await handle_add(msg)

    msg.answer.assert_called_once()
    args, _ = msg.answer.call_args
    assert "купить молоко" in args[0]

    async with factory() as session:
        tasks = (await session.execute(select(models.Task))).scalars().all()
        assert len(tasks) == 1
        assert "купить молоко" in tasks[0].text
        tomorrow_iso = (date.today() + timedelta(days=1)).isoformat()
        assert tasks[0].day == tomorrow_iso


@pytest.mark.asyncio
async def test_add_without_text_shows_example(db_ready):
    from server.bot.handlers import handle_add
    await _ensure_user(db_ready)
    msg = _make_command_message(text="/add")
    await handle_add(msg)
    msg.answer.assert_called_once()


@pytest.mark.asyncio
async def test_add_denied_for_stranger(db_ready):
    from server.bot.handlers import handle_add
    msg = _make_command_message(text="/add foo", tg_username="stranger")
    await handle_add(msg)
    msg.answer.assert_not_called()


@pytest.mark.asyncio
async def test_today_empty(db_ready):
    from server.bot.handlers import handle_today
    await _ensure_user(db_ready)
    msg = _make_command_message(text="/today")
    await handle_today(msg)
    msg.answer.assert_called_once()
    args, _ = msg.answer.call_args
    assert "Задач нет" in args[0]


@pytest.mark.asyncio
async def test_today_lists_tasks(db_ready):
    from server.bot.handlers import handle_add, handle_today
    await _ensure_user(db_ready)

    for text in ("задача 1", "задача 2"):
        m = _make_command_message(text=f"/add {text} сегодня")
        await handle_add(m)

    msg = _make_command_message(text="/today")
    await handle_today(msg)
    assert msg.answer.call_count >= 3


@pytest.mark.asyncio
async def test_week_shows_seven_days(db_ready):
    from server.bot.handlers import handle_week
    await _ensure_user(db_ready)
    msg = _make_command_message(text="/week")
    await handle_week(msg)
    msg.answer.assert_called_once()
    args, _ = msg.answer.call_args
    text = args[0]
    from server.bot.formatters import DAY_NAMES_RU_FULL
    for d in DAY_NAMES_RU_FULL:
        assert d in text


@pytest.mark.asyncio
async def test_callback_toggle_marks_done(db_ready):
    from server.bot.handlers import handle_add, handle_task_callback
    factory = db_ready
    await _ensure_user(factory)

    m = _make_command_message(text="/add проверка")
    await handle_add(m)
    async with factory() as session:
        task = (await session.execute(select(models.Task))).scalar_one()

    from aiogram.types import CallbackQuery
    cb = CallbackQuery.model_validate({
        "id": "cbq1",
        "from": {"id": 111, "is_bot": False, "first_name": "Test", "username": "nikita_heyyda"},
        "chat_instance": "inst-1",
        "data": f"tk:toggle:{task.id}",
    })
    object.__setattr__(cb, "answer", AsyncMock())
    object.__setattr__(cb, "message", None)

    await handle_task_callback(cb)

    cb.answer.assert_called_once()
    async with factory() as session:
        t2 = (await session.execute(
            select(models.Task).where(models.Task.id == task.id)
        )).scalar_one()
        assert t2.done is True


@pytest.mark.asyncio
async def test_callback_tomorrow_moves_day(db_ready):
    from server.bot.handlers import handle_add, handle_task_callback
    factory = db_ready
    await _ensure_user(factory)

    m = _make_command_message(text="/add для переноса сегодня")
    await handle_add(m)
    async with factory() as session:
        task = (await session.execute(select(models.Task))).scalar_one()
    original_day = task.day

    from aiogram.types import CallbackQuery
    cb = CallbackQuery.model_validate({
        "id": "cbq2",
        "from": {"id": 111, "is_bot": False, "first_name": "Test", "username": "nikita_heyyda"},
        "chat_instance": "inst-1",
        "data": f"tk:tomorrow:{task.id}",
    })
    object.__setattr__(cb, "answer", AsyncMock())
    object.__setattr__(cb, "message", None)

    await handle_task_callback(cb)

    async with factory() as session:
        t2 = (await session.execute(
            select(models.Task).where(models.Task.id == task.id)
        )).scalar_one()
        assert t2.day != original_day
        tomorrow_iso = (date.today() + timedelta(days=1)).isoformat()
        assert t2.day == tomorrow_iso


@pytest.mark.asyncio
async def test_callback_invalid_data_gracefully(db_ready):
    from server.bot.handlers import handle_task_callback
    await _ensure_user(db_ready)

    from aiogram.types import CallbackQuery
    cb = CallbackQuery.model_validate({
        "id": "cbq3",
        "from": {"id": 111, "is_bot": False, "first_name": "Test", "username": "nikita_heyyda"},
        "chat_instance": "inst-1",
        "data": "garbage",
    })
    object.__setattr__(cb, "answer", AsyncMock())
    object.__setattr__(cb, "message", None)
    await handle_task_callback(cb)
    cb.answer.assert_called_once()
