"""
/start handler — регистрирует chat_id для user.

Проверяем:
1. Telegram username пользователя есть в settings.allowed_usernames
2. Сохраняем/обновляем users.telegram_chat_id = message.chat.id
3. Отвечаем инструкцией "Бот готов; возвращайтесь в приложение"

Если username не в allow-list — бот отвечает "доступ ограничен" и ничего не пишет в БД.

Фаза 1: только /start (chat_id для auth-flow).
Фаза 5: добавятся /add, /week, /today в этот же router.
"""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select

from server.config import get_settings
from server.db.engine import AsyncSessionLocal
from server.db.models import User

logger = logging.getLogger(__name__)

router = Router(name="planner-bot-start")


ACCESS_DENIED_TEXT = (
    "Доступ к Личному Еженедельнику ограничен.\n\n"
    "Этот бот обслуживает приватный проект. Если вы получили его ссылку по ошибке — "
    "просто игнорируйте это сообщение."
)

START_SUCCESS_TEXT = (
    "Привет! Я бот Личного Еженедельника.\n\n"
    "Теперь я могу присылать тебе коды для входа в приложение.\n"
    "Чтобы войти — открой приложение и введи свой Telegram username.\n\n"
    "Коды действуют 5 минут и одноразовые."
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """
    /start: привязать chat_id к user.

    Алгоритм:
    1. Получаем telegram username из from_user
    2. Проверяем allow-list (ALLOWED_USERNAMES из settings)
    3. Если разрешён — находим или создаём User в БД, пишем telegram_chat_id
    4. Отвечаем

    Идемпотентно — повторный /start просто обновляет chat_id (на случай
    смены Telegram-клиента или restore с другого устройства).
    """
    tg_user = message.from_user
    if tg_user is None:
        logger.warning("Получен /start без from_user — игнорируем")
        return

    tg_username = (tg_user.username or "").lower()
    if not tg_username:
        await message.answer(
            "У вашего Telegram-аккаунта не установлен username. "
            "Зайдите в настройки Telegram, задайте username и отправьте /start снова."
        )
        return

    settings = get_settings()
    if tg_username not in settings.allowed_usernames:
        logger.info("Попытка /start от неизвестного пользователя: %s", tg_username)
        await message.answer(ACCESS_DENIED_TEXT)
        return

    chat_id = message.chat.id

    async with AsyncSessionLocal() as session:
        # Найти или создать user
        stmt = select(User).where(User.telegram_username == tg_username)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(telegram_username=tg_username, telegram_chat_id=chat_id)
            session.add(user)
            logger.info("Создан новый пользователь: %s с chat_id=%d", tg_username, chat_id)
        else:
            user.telegram_chat_id = chat_id
            logger.info("Обновлён chat_id для %s: %d", tg_username, chat_id)

        await session.commit()

    await message.answer(START_SUCCESS_TEXT)
