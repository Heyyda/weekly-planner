"""
JWT encode/decode — access + refresh токены с раздельными секретами.

Использует PyJWT (не python-jose — abandoned, см. RESEARCH.md §Anti-Patterns).
Access TTL = 15 мин (CONTEXT.md D-12), refresh TTL = 30 дней (D-13).
Раздельные секреты (D-14): даже если access утечёт, refresh не скомпрометирован.

Hash refresh-токена для хранения в sessions.refresh_token_hash — SHA256 (быстрый,
достаточно для обфускации; bcrypt излишен т.к. токен сам имеет высокую энтропию).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as pyjwt  # PyJWT — не python-jose!

from server.config import get_settings


# Type-теги для JWT payloads — предотвращает использование refresh как access и наоборот
ACCESS_TYPE = "access"
REFRESH_TYPE = "refresh"


def _utcnow() -> datetime:
    """timezone-aware UTC — не deprecated utcnow()."""
    return datetime.now(timezone.utc)


def create_access_token(user_id: str) -> str:
    """
    Создать access token (TTL = settings.access_token_ttl_seconds).

    Payload: {sub: user_id, type: "access", iat: ..., exp: ...}
    Алгоритм: HS256 (CONTEXT.md Deferred: RS256 только в v2).
    Секрет: JWT_SECRET (отдельный от refresh).
    """
    settings = get_settings()
    now = _utcnow()
    payload = {
        "sub": user_id,
        "type": ACCESS_TYPE,
        "iat": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, session_id: str) -> str:
    """
    Создать refresh token (TTL = settings.refresh_token_ttl_seconds).

    Payload: {sub: user_id, sid: session_id, type: "refresh", iat, exp}
    session_id нужен чтобы при rotate_refresh мы знали какую запись в БД обновить.
    Секрет: JWT_REFRESH_SECRET (отдельный — D-14).
    """
    settings = get_settings()
    now = _utcnow()
    payload = {
        "sub": user_id,
        "sid": session_id,
        "type": REFRESH_TYPE,
        "iat": now,
        "exp": now + timedelta(seconds=settings.refresh_token_ttl_seconds),
    }
    return pyjwt.encode(payload, settings.jwt_refresh_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Декодировать access token.

    Возвращает dict с payload ИЛИ None если:
    - Подпись невалидна
    - Срок истёк
    - type != "access" (например, передали refresh-токен как access)
    """
    return _decode(token, expected_type=ACCESS_TYPE, is_refresh=False)


def decode_refresh_token(token: str) -> Optional[dict]:
    """Декодировать refresh token. Возвращает None если невалиден/истёк/wrong-type."""
    return _decode(token, expected_type=REFRESH_TYPE, is_refresh=True)


def _decode(token: str, *, expected_type: str, is_refresh: bool) -> Optional[dict]:
    settings = get_settings()
    secret = settings.jwt_refresh_secret if is_refresh else settings.jwt_secret
    try:
        payload = pyjwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
    except pyjwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def hash_refresh_token(token: str) -> str:
    """
    SHA256 hex-digest для хранения в sessions.refresh_token_hash.

    Мы не используем bcrypt т.к. (1) refresh-токен сам имеет ~256 бит энтропии
    (UUID в sid + секрет), брутфорс бессмысленен; (2) lookup по hash в БД — частая операция
    (каждый refresh), bcrypt.verify × N записей медленный.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
