"""
Отправка auth-кода через Telegram Bot API.

Использует httpx напрямую (без aiogram) — RESEARCH.md Pattern 4 рекомендует это
для Фазы 1. aiogram появится в Plan 09 только для /start handler (получение chat_id).

Формат сообщения — CONTEXT.md D-05 (расширенный контекст с hostname, временем, TTL).
"""
from __future__ import annotations

import enum
import logging
from typing import Optional

import httpx

from server.config import get_settings

logger = logging.getLogger(__name__)


class TelegramSendError(enum.Enum):
    OK = "ok"
    BOT_NOT_STARTED = "bot_not_started"  # user.telegram_chat_id is None
    API_ERROR = "api_error"              # Telegram API ответил не-200
    NETWORK_ERROR = "network_error"      # connection / timeout


def _format_message(code: str, hostname: str, msk_time_str: str) -> str:
    """
    Формат из CONTEXT.md D-05.

    🔐 Запрошен вход в Личный Еженедельник

    Код: <b>123456</b>
    Устройство: <hostname>
    Время: <msk_time> MSK
    Срок: 5 минут

    Если это не ты — игнорируй это сообщение.
    """
    return (
        "🔐 Запрошен вход в Личный Еженедельник\n"
        "\n"
        f"Код: <b>{code}</b>\n"
        f"Устройство: {hostname}\n"
        f"Время: {msk_time_str} MSK\n"
        "Срок: 5 минут\n"
        "\n"
        "Если это не ты — игнорируй это сообщение."
    )


async def send_auth_code(
    chat_id: Optional[int],
    code: str,
    hostname: str,
    msk_time_str: str,
    *,
    timeout_sec: float = 5.0,
    client: Optional[httpx.AsyncClient] = None,
) -> TelegramSendError:
    """
    Отправить код в Telegram DM.

    Pattern 5 RESEARCH.md: если chat_id is None — значит user ещё не написал /start
    боту. Возвращаем BOT_NOT_STARTED чтобы endpoint показал пользователю
    инструкцию "напишите /start @Jazzways_bot".

    Args:
        chat_id: Telegram chat_id (из users.telegram_chat_id — заполнится в Plan 09)
        code: plaintext 6-digit code
        hostname: устройство, с которого запросили (D-05)
        msk_time_str: время запроса в MSK-формате "2026-04-14 14:23"
        client: Опциональный httpx.AsyncClient для DI в тестах
    """
    if chat_id is None:
        return TelegramSendError.BOT_NOT_STARTED

    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": _format_message(code, hostname, msk_time_str),
        "parse_mode": "HTML",
    }

    _owned_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout_sec)

    try:
        try:
            resp = await client.post(url, json=payload, timeout=timeout_sec)
        except httpx.RequestError as e:
            logger.warning("Telegram send_message network error: %s", e)
            return TelegramSendError.NETWORK_ERROR

        if resp.status_code != 200:
            logger.warning(
                "Telegram API returned %d: %s", resp.status_code, resp.text[:200]
            )
            return TelegramSendError.API_ERROR

        try:
            body = resp.json()
        except Exception:
            return TelegramSendError.API_ERROR

        if not body.get("ok"):
            logger.warning("Telegram API response not ok: %s", body)
            return TelegramSendError.API_ERROR

        return TelegramSendError.OK
    finally:
        if _owned_client:
            await client.aclose()
