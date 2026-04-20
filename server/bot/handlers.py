"""
Bot handlers — Phase 1 (/start) + Phase 5 (/add, /today, /week + callbacks).

/start: chat_id для auth-flow (Фаза 1).
/add <text>: BOT-03 — smart-parse и создать задачу.
/today: BOT-04 — задачи на сегодня с inline-кнопками на каждой.
/week: BOT-04 — компактный обзор недели (одно сообщение).
callback 'tk:toggle' / 'tk:tomorrow': BOT-05 — inline действия.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from server.bot import tasks_service
from server.bot.formatters import (
    format_task_line,
    format_today,
    format_week,
    parse_callback,
    task_keyboard,
)
from server.config import get_settings
from server.db.engine import AsyncSessionLocal
from server.db.models import User
from shared.parse_input import parse_quick_input

logger = logging.getLogger(__name__)

router = Router(name="planner-bot")


ACCESS_DENIED_TEXT = (
    "Доступ к Личному Еженедельнику ограничен.\n\n"
    "Этот бот обслуживает приватный проект. Если вы получили его ссылку по ошибке — "
    "просто игнорируйте это сообщение."
)

START_SUCCESS_TEXT = (
    "Привет! Я бот Личного Еженедельника.\n\n"
    "Теперь я могу присылать тебе коды для входа в приложение.\n"
    "Чтобы войти — открой приложение и введи свой Telegram username.\n\n"
    "Команды:\n"
    "/add <текст> — добавить задачу (можно писать 'завтра 14:00')\n"
    "/today — задачи на сегодня\n"
    "/week — вся неделя"
)


async def _resolve_user(session, username: str | None) -> User | None:
    """Поиск User по нормализованному telegram_username."""
    if not username:
        return None
    stmt = select(User).where(User.telegram_username == username.lower())
    return (await session.execute(stmt)).scalar_one_or_none()


def _is_allowed(username: str | None) -> bool:
    if not username:
        return False
    return username.lower() in get_settings().allowed_usernames


# ---------- /start ----------

@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """/start: привязать chat_id к user. Идемпотентно."""
    logger.info(
        "/start received: chat_id=%s username=%s",
        getattr(message.chat, "id", None),
        (message.from_user.username if message.from_user else None),
    )
    tg_user = message.from_user
    if tg_user is None:
        return

    tg_username = (tg_user.username or "").lower()
    if not tg_username:
        await message.answer(
            "У вашего Telegram-аккаунта не установлен username. "
            "Зайдите в настройки Telegram, задайте username и отправьте /start снова."
        )
        return

    if not _is_allowed(tg_username):
        await message.answer(ACCESS_DENIED_TEXT)
        return

    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        user = await _resolve_user(session, tg_username)
        if user is None:
            user = User(telegram_username=tg_username, telegram_chat_id=chat_id)
            session.add(user)
        else:
            user.telegram_chat_id = chat_id
        await session.commit()

    await message.answer(START_SUCCESS_TEXT)


# ---------- /add ----------

@router.message(Command("add"))
async def handle_add(message: Message) -> None:
    """BOT-03: /add <текст> — создать задачу через smart parse."""
    if message.from_user is None or not _is_allowed(message.from_user.username):
        return

    raw = message.text or ""
    # Убрать "/add" префикс
    parts = raw.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Пример: `/add купить молоко завтра 14:00`\n"
            "Поддерживаются: сегодня / завтра / послезавтра / пн-вс + HH:MM",
            parse_mode="Markdown",
        )
        return

    parsed = parse_quick_input(parts[1])

    async with AsyncSessionLocal() as session:
        user = await _resolve_user(session, message.from_user.username)
        if user is None:
            await message.answer("Сначала выполни /start для привязки аккаунта.")
            return

        task = await tasks_service.create_task(
            session, user.id, parsed["text"], parsed["day"], parsed["time"],
        )

    time_suffix = f" {parsed['time']}" if parsed["time"] else ""
    day_fmt = date.fromisoformat(parsed["day"]).strftime("%d.%m")
    await message.answer(
        f"✅ Добавлено: *{_md_escape(parsed['text'])}* — {day_fmt}{time_suffix}",
        parse_mode="MarkdownV2",
    )
    logger.info("Task created via bot: user=%s id=%s", user.id, task.id)


# ---------- /today ----------

@router.message(Command("today"))
async def handle_today(message: Message) -> None:
    """BOT-04: задачи на сегодня + inline-кнопки на каждой."""
    if message.from_user is None or not _is_allowed(message.from_user.username):
        return

    today = date.today()
    async with AsyncSessionLocal() as session:
        user = await _resolve_user(session, message.from_user.username)
        if user is None:
            await message.answer("Сначала выполни /start.")
            return
        tasks = await tasks_service.get_today_tasks(session, user.id, today)

    if not tasks:
        await message.answer(format_today([], today), parse_mode="MarkdownV2")
        return

    # Summary header
    await message.answer(format_today(tasks, today), parse_mode="MarkdownV2")
    # Per-task messages с inline keyboards (для action'ов)
    for t in tasks:
        await message.answer(
            format_task_line(t),
            parse_mode="MarkdownV2",
            reply_markup=task_keyboard(t),
        )


# ---------- /week ----------

@router.message(Command("week"))
async def handle_week(message: Message) -> None:
    """BOT-04: обзор недели — одно сообщение с 7 днями."""
    if message.from_user is None or not _is_allowed(message.from_user.username):
        return

    today = date.today()
    week_monday = today - timedelta(days=today.weekday())

    async with AsyncSessionLocal() as session:
        user = await _resolve_user(session, message.from_user.username)
        if user is None:
            await message.answer("Сначала выполни /start.")
            return
        by_day = await tasks_service.get_week_tasks(session, user.id, week_monday)

    await message.answer(format_week(by_day, week_monday), parse_mode="MarkdownV2")


# ---------- Inline callbacks ----------

@router.callback_query(F.data.startswith("tk:"))
async def handle_task_callback(cb: CallbackQuery) -> None:
    """BOT-05: inline-кнопки на задаче: tk:toggle / tk:tomorrow."""
    if cb.from_user is None or not _is_allowed(cb.from_user.username):
        await cb.answer("Доступ запрещён", show_alert=False)
        return

    parsed = parse_callback(cb.data or "")
    if parsed is None:
        await cb.answer("Некорректная команда")
        return
    action, task_id = parsed

    async with AsyncSessionLocal() as session:
        user = await _resolve_user(session, cb.from_user.username)
        if user is None:
            await cb.answer("Выполни /start")
            return

        if action == "toggle":
            new_done = await tasks_service.toggle_done(session, user.id, task_id)
            if new_done is None:
                await cb.answer("Задача не найдена")
                return
            await cb.answer("Выполнено ✅" if new_done else "Возвращено ⬜")
        elif action == "tomorrow":
            tomorrow_iso = (date.today() + timedelta(days=1)).isoformat()
            ok = await tasks_service.move_to_day(session, user.id, task_id, tomorrow_iso)
            if not ok:
                await cb.answer("Задача не найдена")
                return
            await cb.answer("Перенесено на завтра ⏩")
        else:
            await cb.answer("Неизвестное действие")
            return

        # Перечитать задачу чтобы обновить сообщение
        task = await tasks_service.get_by_id(session, user.id, task_id)
    if task is not None and cb.message is not None:
        try:
            await cb.message.edit_text(
                format_task_line(task),
                parse_mode="MarkdownV2",
                reply_markup=task_keyboard(task),
            )
        except Exception as exc:
            logger.debug("edit_text after callback failed: %s", exc)


# ---------- Internal helpers ----------

_MD_V2_SPECIAL = r"_*[]()~`>#+-=|{}.!\\"


def _md_escape(text: str) -> str:
    out = []
    for ch in text:
        if ch in _MD_V2_SPECIAL:
            out.append("\\")
        out.append(ch)
    return "".join(out)
