"""
Pydantic v2 request/response схемы для auth endpoints.

Формат ошибок — CONTEXT.md D-18:
    {"error": {"code": "INVALID_CODE", "message": "Код истёк или неверен"}}

Все user-facing строки — на русском (CLAUDE.md project instructions).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RequestCodeIn(BaseModel):
    """POST /api/auth/request-code — шаг 1 авторизации."""

    username: str = Field(..., description="Telegram username (с @ или без)")
    hostname: str = Field(default="неизвестно", max_length=100, description="Имя устройства для сообщения в Telegram")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        """Убираем @, lowercase, strip — чтобы "@Nikita" == "nikita" == "NIKITA"."""
        if not isinstance(v, str):
            raise ValueError("username должен быть строкой")
        normalized = v.strip().lstrip("@").lower()
        if not normalized:
            raise ValueError("username не может быть пустым")
        if len(normalized) > 100:
            raise ValueError("username слишком длинный (максимум 100 символов)")
        return normalized

    @field_validator("hostname", mode="before")
    @classmethod
    def normalize_hostname(cls, v: str) -> str:
        """Trim пробелы, fallback к дефолту если пустой."""
        if not isinstance(v, str):
            return "неизвестно"
        stripped = v.strip()
        return stripped if stripped else "неизвестно"


class VerifyCodeIn(BaseModel):
    """POST /api/auth/verify — ввод 6-значного кода."""

    request_id: str = Field(..., description="UUID из ответа /auth/request-code")
    code: str = Field(..., description="6-значный код из Telegram")
    device_name: Optional[str] = Field(default=None, max_length=100, description="Название устройства для сессии")

    @field_validator("code", mode="before")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Код — строго 6 десятичных цифр."""
        if not isinstance(v, str):
            raise ValueError("Код должен быть 6 цифр")
        stripped = v.strip()
        if not stripped.isdigit() or len(stripped) != 6:
            raise ValueError("Код должен быть 6 цифр")
        return stripped


class RefreshTokenIn(BaseModel):
    """POST /api/auth/refresh — обновление access token."""

    refresh_token: str = Field(..., description="Refresh-токен из /auth/verify или предыдущего /auth/refresh")


class LogoutIn(BaseModel):
    """POST /api/auth/logout — опциональный body."""

    refresh_token: Optional[str] = Field(
        default=None,
        description="Если передан — revoke только эту сессию; иначе revoke все сессии пользователя",
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class RequestCodeOut(BaseModel):
    """Ответ /api/auth/request-code."""

    request_id: str = Field(..., description="UUID для следующего шага /auth/verify")
    expires_in: int = Field(..., description="Срок действия кода в секундах (300 = 5 минут)")


class TokenPairOut(BaseModel):
    """Ответ /api/auth/verify — полная пара токенов."""

    access_token: str
    refresh_token: str
    expires_in: int = Field(..., description="TTL access token в секундах (900 = 15 минут)")
    token_type: str = Field(default="bearer")
    user_id: str


class AccessTokenOut(BaseModel):
    """Ответ /api/auth/refresh — обновлённые токены (rolling refresh)."""

    access_token: str
    refresh_token: Optional[str] = Field(default=None, description="Новый refresh (rolling rotation)")
    expires_in: int = Field(..., description="TTL access token в секундах")
    token_type: str = Field(default="bearer")


class UserMeOut(BaseModel):
    """Ответ /api/auth/me."""

    user_id: str
    username: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Error models (D-18)
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    """Детали ошибки."""

    code: str = Field(..., description="Машиночитаемый код ошибки (SNAKE_UPPER_CASE)")
    message: str = Field(..., description="Описание ошибки для пользователя (на русском)")


class ErrorOut(BaseModel):
    """Стандартный формат ошибки D-18: {\"error\": {\"code\": \"...\", \"message\": \"...\"}}."""

    error: ErrorDetail
