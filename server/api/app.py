"""
FastAPI приложение — entry point для uvicorn.

Запуск локально (для разработки):
    cd s:/Проекты/ежедневник
    uvicorn server.api.app:app --reload --port 8100

На VPS (через systemd, Plan 10):
    ExecStart=/opt/planner/venv/bin/uvicorn server.api.app:app \
        --host 127.0.0.1 --port 8100 --workers 1

Архитектура: Plan 07 добавляет sync_router, Plan 08 добавляет health_router + slowapi.
Все роутеры подключаются здесь через app.include_router().
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.api.auth_routes import router as auth_router
from server.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown hooks.

    Startup:
    - Логируем запуск (версия, хост, порт)
    - Alembic миграции запускаются отдельно (Plan 10 deploy script),
      не при каждом старте сервера

    Shutdown:
    - engine.dispose() — корректно закрываем все aiosqlite connections
    """
    settings = get_settings()
    logger.info(
        "Starting Личный Еженедельник API v%s (host=%s, port=%d)",
        settings.app_version,
        settings.host,
        settings.port,
    )

    yield

    # Shutdown: освобождаем connection pool
    from server.db.engine import _get_engine  # type: ignore[attr-defined]
    try:
        await _get_engine().dispose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Engine dispose error on shutdown: %s", exc)

    logger.info("Личный Еженедельник API остановлен")


app = FastAPI(
    title="Личный Еженедельник API",
    description=(
        "REST API для десктопного планировщика задач. "
        "Telegram JWT авторизация, синхронизация задач."
    ),
    version=get_settings().app_version,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Auth endpoints (Фаза 1, Plan 06)
app.include_router(auth_router)

# Sync endpoint подключается в Plan 07: app.include_router(sync_router)
# Health + version + rate-limit подключаются в Plan 08: app.include_router(health_router)
