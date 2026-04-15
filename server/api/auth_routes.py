"""
Auth endpoints Фазы 1.

Тонкий слой над server.auth.{codes, sessions, jwt, telegram} — парсит request,
вызывает сервис, формирует response. Никакой бизнес-логики здесь — только routing.

Endpoints (CONTEXT.md D-17):
- POST /api/auth/request-code  → {request_id, expires_in}
- POST /api/auth/verify        → {access_token, refresh_token, expires_in, user_id, token_type}
- POST /api/auth/refresh       → {access_token, refresh_token, expires_in, token_type}
- POST /api/auth/logout        → 204 No Content
- GET  /api/auth/me            → {user_id, username, created_at}

Ошибки в формате D-18: {"error": {"code": "...", "message": "..."}}
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from server.api import errors as err
from server.api.rate_limit import limiter
from server.api.schemas import (
    AccessTokenOut,
    LogoutIn,
    RefreshTokenIn,
    RequestCodeIn,
    RequestCodeOut,
    TokenPairOut,
    UserMeOut,
    VerifyCodeIn,
)
from server.auth.codes import AuthCodeService, VerifyResult
from server.auth.dependencies import get_current_user
from server.auth.jwt import create_access_token, hash_refresh_token
from server.auth.sessions import SessionService
from server.auth.telegram import TelegramSendError, send_auth_code
from server.config import get_settings
from server.db.engine import get_db
from server.db.models import AuthCode, Session as SessionRecord, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

MSK = ZoneInfo("Europe/Moscow")


def _now_msk_str() -> str:
    """Текущее время в московском часовом поясе для сообщения Telegram (D-05)."""
    return datetime.now(MSK).strftime("%Y-%m-%d %H:%M")


@router.post("/request-code", response_model=RequestCodeOut)
@limiter.limit("1/minute;5/hour")  # CONTEXT.md D-09
async def request_code(
    request: Request,  # нужен slowapi для получения IP адреса
    body: RequestCodeIn,
    db: AsyncSession = Depends(get_db),
):
    """
    Шаг 1: пользователь ввёл username → мы шлём 6-значный код в Telegram.

    Поток:
    1. Проверить allow-list (CONTEXT.md D-27 ALLOWED_USERNAMES)
    2. Найти или создать User (chat_id может быть NULL — заполнит /start handler Plan 09)
    3. Сгенерировать код через AuthCodeService (D-06: 6 цифр, D-07: TTL 5 мин)
    4. Отправить через send_auth_code (D-05: расширенный контекст с hostname, временем)
    5. Вернуть request_id для UI (клиент передаёт его в /auth/verify)
    """
    settings = get_settings()
    username = body.username  # уже нормализован Pydantic validator'ом

    # 1. Allow-list check (D-27)
    if username not in settings.allowed_usernames:
        raise err.err_user_not_allowed()

    # 2. Найти или создать user
    stmt = select(User).where(User.telegram_username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_username=username)
        db.add(user)
        await db.flush()
        await db.commit()
        await db.refresh(user)

    # 3. Сгенерировать код
    svc = AuthCodeService(db)
    code_result = await svc.request_code(username)

    # 4. Отправить через Telegram (RESEARCH.md Pattern 5: chat_id может быть None)
    send_result = await send_auth_code(
        chat_id=user.telegram_chat_id,
        code=code_result.code,
        hostname=body.hostname,
        msk_time_str=_now_msk_str(),
    )

    if send_result == TelegramSendError.BOT_NOT_STARTED:
        raise err.err_bot_not_started()
    if send_result != TelegramSendError.OK:
        raise err.err_telegram_send()

    # 5. Вернуть request_id
    return RequestCodeOut(
        request_id=code_result.request_id,
        expires_in=settings.auth_code_ttl_seconds,
    )


@router.post("/verify", response_model=TokenPairOut)
async def verify_code(body: VerifyCodeIn, db: AsyncSession = Depends(get_db)):
    """
    Шаг 2: пользователь ввёл код → выдаём access+refresh пару (AUTH-01 + AUTH-02).

    Поток:
    1. Найти AuthCode по request_id, взять username
    2. Verify через AuthCodeService (D-08 single-use, D-07 TTL)
    3. Найти User по username
    4. SessionService.create → (session, refresh_plaintext) (D-14)
    5. Сгенерировать access через create_access_token (D-12: TTL 15 мин)
    6. Вернуть TokenPairOut
    """
    settings = get_settings()

    # 1. Найти AuthCode по request_id — узнать username
    stmt = select(AuthCode).where(AuthCode.id == body.request_id)
    res = await db.execute(stmt)
    auth_code_record = res.scalar_one_or_none()
    if auth_code_record is None:
        raise err.err_request_not_found()

    username = auth_code_record.username

    # 2. Verify (AuthCodeService проверяет TTL, single-use, hash)
    svc = AuthCodeService(db)
    verdict = await svc.verify_code(username, body.code)
    if verdict == VerifyResult.INVALID:
        raise err.err_invalid_code()
    if verdict == VerifyResult.EXPIRED:
        raise err.err_code_expired()
    if verdict == VerifyResult.ALREADY_USED:
        raise err.err_already_used()

    # 3. Найти user
    stmt_user = select(User).where(User.telegram_username == username)
    user_res = await db.execute(stmt_user)
    user = user_res.scalar_one_or_none()
    if user is None:
        raise err.api_error("USER_NOT_FOUND", "Пользователь не найден в БД", 500)

    # 4. Создать session + refresh (D-14: refresh только в keyring + БД)
    sess_svc = SessionService(db)
    session_obj, refresh_plaintext = await sess_svc.create(
        user_id=user.id, device_name=body.device_name
    )

    # 5. Access token (D-12: 15 мин, хранится только в памяти)
    access = create_access_token(user.id)

    return TokenPairOut(
        access_token=access,
        refresh_token=refresh_plaintext,
        expires_in=settings.access_token_ttl_seconds,
        user_id=user.id,
    )


@router.post("/refresh", response_model=AccessTokenOut)
async def refresh_access(body: RefreshTokenIn, db: AsyncSession = Depends(get_db)):
    """
    Обновить access через refresh (AUTH-04, rolling refresh D-13).

    SessionService.rotate_refresh:
    - Проверяет JWT подпись + expiry
    - Ищет session в БД
    - Revoke'ит старую → создаёт новую (rolling)
    - Возвращает (new_session, new_refresh_plaintext)
    """
    settings = get_settings()
    sess_svc = SessionService(db)
    rot_result = await sess_svc.rotate_refresh(body.refresh_token)
    if rot_result is None:
        raise err.err_invalid_refresh()

    new_session, new_refresh_plaintext = rot_result
    access = create_access_token(new_session.user_id)

    return AccessTokenOut(
        access_token=access,
        refresh_token=new_refresh_plaintext,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutIn | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Разлогинить текущий device (AUTH-05 + D-15).

    Если передан refresh_token в body — revoke именно эту сессию (logout одного устройства).
    Если не передан — revoke все активные сессии этого user (full logout).
    """
    sess_svc = SessionService(db)

    if body is not None and body.refresh_token:
        # Revoke конкретную session по hash lookup
        target_hash = hash_refresh_token(body.refresh_token)
        session = await sess_svc.get_by_refresh_hash(target_hash)
        if session is not None and session.user_id == current_user.id:
            await sess_svc.revoke(session.id)
    else:
        # Revoke все активные sessions этого user (D-15: full device logout)
        stmt = select(SessionRecord).where(
            SessionRecord.user_id == current_user.id,
            SessionRecord.revoked_at.is_(None),
        )
        result = await db.execute(stmt)
        now = datetime.now(timezone.utc)
        for session in result.scalars().all():
            session.revoked_at = now
        await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserMeOut)
async def me(current_user: User = Depends(get_current_user)):
    """
    Информация о текущем пользователе (требует Bearer access token).

    Используется клиентом для проверки что авторизация работает
    и для отображения имени пользователя в UI.
    """
    return UserMeOut(
        user_id=current_user.id,
        username=current_user.telegram_username,
        created_at=current_user.created_at,
    )
