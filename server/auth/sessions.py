"""
SessionService — CRUD для sessions table.

Поток (CONTEXT.md D-14, D-15):
1. Verify-code успешен → SessionService.create(user_id) → (session, refresh_plaintext)
2. Endpoint /auth/verify возвращает клиенту access + refresh
3. Клиент сохраняет refresh в keyring (plaintext), использует для /auth/refresh
4. При refresh: rotate_refresh(old_plaintext) → (new_session, new_plaintext)
   — старая session revoked, новая создана (rolling refresh — D-13)
5. При logout: revoke(session_id) → revoked_at установлен, refresh больше не работает (D-15)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as AsyncDBSession

from server.auth.jwt import (
    create_refresh_token,
    decode_refresh_token,
    hash_refresh_token,
)
from server.config import get_settings
from server.db.models import Session as SessionRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionService:
    """Все DB-операции над sessions table — async."""

    def __init__(self, db: AsyncDBSession):
        self.db = db

    async def create(
        self, user_id: str, device_name: Optional[str] = None
    ) -> tuple[SessionRecord, str]:
        """
        Создать новую серверную session и сгенерировать refresh-токен.

        Возвращает (session, plaintext_refresh_token). Plaintext — единственный раз
        возвращается наружу; в БД хранится только hash.
        """
        settings = get_settings()

        # session_id сначала, потому что refresh_token ссылается на него (sid claim)
        new_session = SessionRecord(
            user_id=user_id,
            device_name=device_name,
            expires_at=_utcnow() + timedelta(seconds=settings.refresh_token_ttl_seconds),
            refresh_token_hash="",  # будет заполнен ниже (нужен session.id сначала)
        )
        self.db.add(new_session)
        await self.db.flush()  # получаем сгенерированный id (UUID default)

        plaintext_refresh = create_refresh_token(user_id=user_id, session_id=new_session.id)
        new_session.refresh_token_hash = hash_refresh_token(plaintext_refresh)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(new_session)
        return new_session, plaintext_refresh

    async def rotate_refresh(
        self, old_refresh_token: str
    ) -> Optional[tuple[SessionRecord, str]]:
        """
        Rolling refresh (CONTEXT.md D-13):
        - Проверить что JWT валиден и не expired
        - Найти session по session_id из claims
        - Проверить hash совпадает (защита от "interesting" claims)
        - Проверить не revoked
        - Revoke старую, создать новую, вернуть (new_session, new_plaintext)

        Возвращает None если что-то не сошлось.
        """
        payload = decode_refresh_token(old_refresh_token)
        if payload is None:
            return None

        session_id = payload.get("sid")
        user_id = payload.get("sub")
        if not session_id or not user_id:
            return None

        # Ищем session в БД
        stmt = select(SessionRecord).where(SessionRecord.id == session_id)
        result = await self.db.execute(stmt)
        session: Optional[SessionRecord] = result.scalar_one_or_none()
        if session is None:
            return None
        if session.revoked_at is not None:
            return None
        if session.user_id != user_id:
            return None  # claims tampered
        if session.expires_at.replace(tzinfo=timezone.utc) <= _utcnow():
            return None  # DB expired

        # Защита от подмены: hash должен совпасть
        expected_hash = hash_refresh_token(old_refresh_token)
        if session.refresh_token_hash != expected_hash:
            return None

        # Revoke старую
        session.revoked_at = _utcnow()

        # Создать новую (переиспользуем create — он сам flush+commit)
        new_session, new_plaintext = await self.create(
            user_id=user_id, device_name=session.device_name
        )
        return new_session, new_plaintext

    async def revoke(self, session_id: str) -> bool:
        """
        Установить revoked_at для session. Используется при logout (D-15).
        Возвращает True если session найдена и revoked, False если не найдена.
        """
        stmt = select(SessionRecord).where(SessionRecord.id == session_id)
        result = await self.db.execute(stmt)
        session: Optional[SessionRecord] = result.scalar_one_or_none()
        if session is None:
            return False
        if session.revoked_at is None:
            session.revoked_at = _utcnow()
            await self.db.commit()
        return True

    async def get_by_refresh_hash(self, refresh_hash: str) -> Optional[SessionRecord]:
        """Найти session по refresh_token_hash — для internal проверок."""
        stmt = select(SessionRecord).where(SessionRecord.refresh_token_hash == refresh_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
