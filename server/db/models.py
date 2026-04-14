"""
SQLAlchemy ORM модели Личного Еженедельника — Фаза 1.

Таблицы (из CONTEXT.md D-21):
- users: пользователь приложения, привязан к Telegram username и chat_id
- auth_codes: 6-значные коды подтверждения (hash через bcrypt), TTL 5 минут, single-use
- sessions: refresh-токены для активных сессий (revokable через logout)
- tasks: задачи с tombstone (deleted_at) для SYNC — client-generated UUID PK

SRV-04: все 4 модели определены.
SRV-06: updated_at — server-side через onupdate=func.now().
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db.base import Base


def _gen_uuid() -> str:
    """UUID4 как строку — PK для server-generated id'шников."""
    return str(uuid.uuid4())


class User(Base):
    """
    Пользователь. В v1 — один владелец (Никита), но модель готова к множеству users
    (см. REQUIREMENTS.md SOC-01 v2 и CONTEXT.md "Allow-list переходит в многопользователь").

    telegram_chat_id NULL пока пользователь не написал боту /start (см. RESEARCH.md Pattern 5).
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_gen_uuid)
    telegram_username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # relationships (не обязательны для Фазы 1, но полезны для тестов)
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="user", cascade="all, delete-orphan"
    )


class AuthCode(Base):
    """
    6-значный код подтверждения для Telegram-авторизации.

    Храним bcrypt-хеш, не plaintext (см. RESEARCH.md §Don't Hand-Roll — 6-цифровой код
    тривиально брутфорсится без хеширования).

    single-use: после успешной проверки устанавливается used_at (CONTEXT.md D-08).
    TTL: expires_at = created_at + 5min (CONTEXT.md D-07).
    """
    __tablename__ = "auth_codes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_gen_uuid)
    username: Mapped[str] = mapped_column(String, nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Session(Base):
    """
    Серверная сессия (refresh-токен device'а).

    Храним SHA256(refresh_token), не сам токен (CONTEXT.md D-14).
    revoked_at устанавливается при /api/auth/logout (CONTEXT.md D-15).
    last_used_at обновляется при каждом refresh (для rolling refresh логики, CONTEXT.md D-13).
    """
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_gen_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    device_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")


class Task(Base):
    """
    Задача в планировщике.

    id = UUID, сгенерированный КЛИЕНТОМ (CONTEXT.md SYNC-06 + ARCHITECTURE.md Pattern 4).
    day = ISO date string "2026-04-14" (не DateTime — day-level гранулярность).
    time_deadline — опциональное время дедлайна внутри дня.
    deleted_at — tombstone для SYNC (NULL = жива, timestamp = удалена).
    updated_at — SERVER-SIDE через onupdate=func.now() (SRV-06: клиент никогда не присылает updated_at).
    """
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID от клиента — без default
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # "2026-04-14"
    time_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # SRV-06: сервер — source of truth для updated_at
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="tasks")


# Экспорт для Alembic env.py и тестов
__all__ = ["Base", "User", "AuthCode", "Session", "Task"]
