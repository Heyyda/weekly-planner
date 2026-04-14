"""
FastAPI dependencies для защищённых endpoints.

get_current_user — извлекает Bearer из Authorization header, декодирует access JWT,
загружает User из БД. При любой проблеме — 401 в формате CONTEXT.md D-18.

Usage в endpoints:
    @router.get("/api/me")
    async def me(user: User = Depends(get_current_user)):
        return {"user_id": user.id, "username": user.telegram_username}
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.jwt import decode_access_token
from server.db.engine import get_db
from server.db.models import User


# auto_error=False чтобы сами контролировали формат ошибки (D-18)
security = HTTPBearer(auto_error=False)


def _error(code: str, message: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Извлечь текущего user из Bearer token.

    При любой ошибке — 401 с {"error": {"code": ..., "message": ...}} (D-18).
    """
    if credentials is None or not credentials.credentials:
        raise _error("MISSING_TOKEN", "Отсутствует Authorization header")

    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise _error("INVALID_TOKEN", "Токен недействителен или истёк")

    user_id = payload.get("sub")
    if not user_id:
        raise _error("INVALID_TOKEN", "Токен не содержит user_id")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user: Optional[User] = result.scalar_one_or_none()
    if user is None:
        raise _error("USER_NOT_FOUND", "Пользователь не найден")

    return user
