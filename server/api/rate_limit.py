"""
Rate limiter через slowapi (CONTEXT.md D-09).

Ключ — IP address (get_remote_address), не username — RESEARCH.md Pitfall 6:
slowapi's key_func вызывается синхронно, не может читать async request.body().

Для personal VPS single-user кейса IP-based rate limit достаточен — защищает от
тривиальных ботов и случайных повторных кликов.

Лимиты (D-09): 1 запрос/минуту, 5 запросов/час на один IP.
"""
from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


# Default limits применяются ТОЛЬКО к endpoints с @limiter.limit декоратором —
# не ко всем. Объявляем пустыми; per-endpoint лимиты в auth_routes.py.
limiter = Limiter(key_func=get_remote_address, default_limits=[])


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Кастомный handler для rate-limit — формат D-18 вместо дефолтного текста slowapi.
    """
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Слишком много запросов. Попробуйте через минуту.",
            }
        },
        headers={"Retry-After": "60"},
    )
