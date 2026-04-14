"""
AuthCodeService — генерация, хранение, верификация 6-значных auth-кодов.

CONTEXT.md constraints:
- D-06: 6 цифр
- D-07: TTL 5 минут
- D-08: single-use (used_at после verify)
- D-09: rate-limit 1/min, 5/hour — реализуется в endpoint (Plan 08 через slowapi),
  здесь только базовая DB-логика.

Безопасность:
- bcrypt-hash для кодов через bcrypt.hashpw/checkpw напрямую (passlib 1.7.4
  несовместима с bcrypt 5.x из-за удаления __about__; RESEARCH.md §Don't Hand-Roll
  — защита от брутфорса 10^6 при leak БД)
- Plaintext код возвращается один раз из request_code — чтобы endpoint передал
  его в send_auth_code. Никогда не логируется.
"""
from __future__ import annotations

import enum
import secrets
from datetime import datetime, timedelta, timezone
from typing import NamedTuple, Optional

import bcrypt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import get_settings
from server.db.models import AuthCode


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VerifyResult(enum.Enum):
    """Результат verify_code — для endpoint'а чтобы вернуть правильный error.code (D-18)."""
    OK = "ok"
    INVALID = "invalid"            # код не совпал или username не найден
    EXPIRED = "expired"            # TTL истёк
    ALREADY_USED = "already_used"  # D-08: single-use


class CodeRequestResult(NamedTuple):
    """Результат request_code — request_id для клиента, plaintext code для Telegram."""
    request_id: str
    code: str  # plaintext — НЕ ЛОГИРОВАТЬ, сразу передать в Telegram


class AuthCodeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_code(self) -> str:
        """Криптографически случайный код настроенной длины (по умолчанию 6 цифр)."""
        settings = get_settings()
        length = settings.auth_code_length
        # secrets.randbelow(10**length) — равномерно в [0, 10^length)
        return f"{secrets.randbelow(10 ** length):0{length}d}"

    async def request_code(self, username: str) -> CodeRequestResult:
        """
        Сгенерировать код для username, сохранить bcrypt-hash в auth_codes.

        Возвращает (request_id, plaintext) — request_id для UI (client увидит
        в ответе /auth/request-code), plaintext отправляется в Telegram.

        Не проверяет ALLOWED_USERNAMES (endpoint делает это до вызова).
        """
        settings = get_settings()
        code = self._generate_code()
        code_hash = bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
        now = _utcnow()

        record = AuthCode(
            username=username.lower().lstrip("@"),  # нормализация — на случай ручного вызова
            code_hash=code_hash,
            expires_at=now + timedelta(seconds=settings.auth_code_ttl_seconds),
            created_at=now,  # явно передаём Python UTC datetime — гарантирует уникальность при конкурентных запросах
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(record)
        return CodeRequestResult(request_id=record.id, code=code)

    async def verify_code(self, username: str, code: str) -> VerifyResult:
        """
        Проверить код: ищем самый свежий НЕиспользованный код для username,
        сверяем через passlib, при успехе ставим used_at.

        Алгоритм:
        1. Найти самый свежий AuthCode по username, где used_at IS NULL
        2. Если нет → проверяем использованные (ALREADY_USED или INVALID)
        3. Если expires_at < now → EXPIRED (но не трогаем used_at)
        4. Если bcrypt.verify(code, hash) не прошла → INVALID
        5. Иначе установить used_at = now, commit → OK

        D-08 single-use: used_at гарантирует, что следующий verify той же записи
        не пройдёт (хотя вызов и не падает — просто вернёт INVALID т.к. запись
        отфильтрована условием used_at IS NULL).
        """
        uname = username.lower().lstrip("@")
        stmt = (
            select(AuthCode)
            .where(AuthCode.username == uname)
            .where(AuthCode.used_at.is_(None))
            .order_by(AuthCode.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        record: Optional[AuthCode] = result.scalar_one_or_none()

        if record is None:
            # Проверим — был ли недавно used code (чтобы различать INVALID vs ALREADY_USED)
            stmt_used = (
                select(AuthCode)
                .where(AuthCode.username == uname)
                .where(AuthCode.used_at.is_not(None))
                .order_by(AuthCode.used_at.desc())
                .limit(1)
            )
            used_result = await self.db.execute(stmt_used)
            used_record = used_result.scalar_one_or_none()
            if used_record and bcrypt.checkpw(code.encode(), used_record.code_hash.encode()):
                return VerifyResult.ALREADY_USED
            return VerifyResult.INVALID

        # Проверить expired
        # SQLite возвращает naive datetime — приводим к aware UTC для сравнения
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= _utcnow():
            return VerifyResult.EXPIRED

        # Проверить hash
        try:
            if not bcrypt.checkpw(code.encode(), record.code_hash.encode()):
                return VerifyResult.INVALID
        except Exception:
            return VerifyResult.INVALID

        # Success — single-use: ставим used_at
        record.used_at = _utcnow()
        await self.db.commit()
        return VerifyResult.OK

    async def cleanup_expired(self) -> int:
        """
        Удалить истёкшие коды из auth_codes (housekeeping).

        Вызывается периодически — для Фазы 1 не критично (можно не вызывать вовсе).
        """
        now = _utcnow()
        stmt = delete(AuthCode).where(AuthCode.expires_at < now)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount or 0
