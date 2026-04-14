"""
Стандартизированные error helpers для auth endpoints.

Формат D-18: {"error": {"code": "INVALID_CODE", "message": "..."}}

Все сообщения на русском (D-05 user-facing + CLAUDE.md project instructions).
Коды ошибок — SNAKE_UPPER_CASE (машиночитаемые, для клиентского кода).

Принцип: каждый err_xxx() создаёт HTTPException с detail в формате D-18.
FastAPI сериализует detail как JSON, клиент видит {"error": {...}}.
"""
from __future__ import annotations

from fastapi import HTTPException


def api_error(
    code: str,
    message: str,
    status_code: int = 400,
    headers: dict | None = None,
) -> HTTPException:
    """
    Базовый конструктор ошибки в формате D-18.

    Usage:
        raise api_error("INVALID_CODE", "Код неверный", 400)
        raise api_error("INVALID_REFRESH", "...", 401, {"WWW-Authenticate": "Bearer"})
    """
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Предопределённые error helpers — для консистентности между endpoints
# ---------------------------------------------------------------------------

def err_user_not_allowed() -> HTTPException:
    """Username не в ALLOWED_USERNAMES — доступ запрещён."""
    return api_error(
        "USER_NOT_ALLOWED",
        "Пользователь не в списке разрешённых. Обратитесь к администратору.",
        403,
    )


def err_bot_not_started() -> HTTPException:
    """User ещё не написал /start боту — chat_id неизвестен (RESEARCH.md Pattern 5)."""
    return api_error(
        "BOT_NOT_STARTED",
        "Напишите /start боту @Jazzways_bot в Telegram, затем попробуйте снова",
        400,
    )


def err_telegram_send() -> HTTPException:
    """Telegram API не ответил или вернул ошибку."""
    return api_error(
        "TELEGRAM_ERROR",
        "Не удалось отправить код — попробуйте через минуту",
        502,
    )


def err_invalid_code() -> HTTPException:
    """Код не совпал с ожидаемым."""
    return api_error("INVALID_CODE", "Код неверный", 400)


def err_code_expired() -> HTTPException:
    """TTL кода истёк (D-07: 5 минут)."""
    return api_error("CODE_EXPIRED", "Срок действия кода истёк — запросите новый", 400)


def err_already_used() -> HTTPException:
    """Код уже был использован (D-08: single-use)."""
    return api_error("ALREADY_USED", "Код уже был использован — запросите новый", 400)


def err_invalid_refresh() -> HTTPException:
    """Refresh-токен недействителен, истёк или revoked."""
    return api_error(
        "INVALID_REFRESH",
        "Refresh-токен недействителен или истёк",
        401,
        {"WWW-Authenticate": "Bearer"},
    )


def err_request_not_found() -> HTTPException:
    """request_id не найден в auth_codes — неверный или устаревший."""
    return api_error("INVALID_CODE", "request_id не найден", 400)
