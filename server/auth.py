"""
Серверная авторизация — JWT + Telegram.

Поток:
1. POST /auth/request → генерирует 6-значный код, отправляет в Telegram
2. POST /auth/verify → проверяет код, выдаёт JWT пару
3. POST /auth/refresh → обновляет access token
4. GET  /auth/me → информация о текущем пользователе
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from server.config import JWT_SECRET, JWT_ALGORITHM, JWT_ACCESS_EXPIRE_DAYS, JWT_REFRESH_EXPIRE_DAYS


# Временное хранилище кодов подтверждения (в проде — Redis/DB)
_pending_codes: dict[str, dict] = {}


def generate_verification_code(username: str) -> str:
    """Сгенерировать 6-значный код для пользователя."""
    code = f"{secrets.randbelow(1000000):06d}"
    _pending_codes[username] = {
        "code": code,
        "expires": datetime.utcnow() + timedelta(minutes=10),
    }
    return code


def verify_code(username: str, code: str) -> bool:
    """Проверить код подтверждения."""
    pending = _pending_codes.get(username)
    if not pending:
        return False
    if datetime.utcnow() > pending["expires"]:
        del _pending_codes[username]
        return False
    if pending["code"] != code:
        return False
    del _pending_codes[username]
    return True


def create_access_token(user_id: str) -> str:
    """Создать JWT access token."""
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=JWT_ACCESS_EXPIRE_DAYS),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Создать JWT refresh token."""
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=JWT_REFRESH_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Декодировать и проверить JWT."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
