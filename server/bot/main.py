"""
Запуск Telegram-бота как отдельного процесса.

Запуск локально:     python -m server.bot.main
Запуск на VPS:       через systemd unit planner-bot.service (Plan 10)

Почему отдельный процесс (не часть FastAPI uvicorn):
- aiogram long-polling занимает event loop — несовместимо с uvicorn worker
- Простая изоляция: если FastAPI падает, бот остаётся; и наоборот
- Отдельные systemd units → независимый Restart=always → независимые перезапуски
- В Фазе 5 бот получит новые handlers (/add, /week, /today) без изменения main.py
  (просто добавятся router'ы в create_dispatcher)

Архитектура:
    create_dispatcher() → Dispatcher с зарегистрированными handlers
    create_bot()        → Bot с токеном из settings
    main()              → long-polling entry point (блокирующий)

См. CONTEXT.md D-24 (плоскость deployment), D-04 (токен только на сервере).
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from server.config import get_settings


def create_dispatcher() -> Dispatcher:
    """
    Создать Dispatcher с подключёнными handlers.

    Вынесено отдельно чтобы тесты могли вызвать create_dispatcher()
    без запуска long-polling.

    Фаза 1: только /start handler.
    Фаза 5: добавятся router'ы для задач (/add, /week, /today).
    """
    dp = Dispatcher()
    from server.bot.handlers import router as start_router
    dp.include_router(start_router)
    return dp


def create_bot() -> Bot:
    """Создать Bot с токеном из settings и HTML parse_mode по умолчанию."""
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def main() -> None:
    """
    Long-polling entry point. Вызывается как `python -m server.bot.main`.

    drop_pending_updates=True — игнорируем старые сообщения при рестарте бота,
    иначе бот обработает накопившиеся /start-команды за время простоя,
    что может создать race condition при деплое новой версии.
    """
    logging.basicConfig(
        level=get_settings().log_level,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("server.bot")
    logger.info("Запуск Telegram-бота (Фаза 1: только /start handler)")

    bot = create_bot()
    dp = create_dispatcher()

    try:
        # drop_pending_updates=True — игнорируем старые updates при рестарте
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
