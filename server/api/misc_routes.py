"""
Health + Version endpoints.

Health — для systemd liveness check и reverse-proxy healthcheck.
Version — для авто-обновления клиента (Фаза 6) — возвращает текущую версию
и SHA256 файла для проверки интегрии после скачивания.

Оба endpoint — БЕЗ auth (public), но они находятся под /api/ префиксом.
"""
from __future__ import annotations

from fastapi import APIRouter

from server.config import get_settings

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health")
async def health():
    """
    Liveness check. Используется systemd WatchdogSec/ExecStartPost и Caddy/nginx healthchecks.

    Return 200 всегда — если процесс живой, health OK. Для readiness (DB доступна)
    можно добавить ping БД, но для Фазы 1 избыточно.
    """
    return {"status": "ok"}


@router.get("/version")
async def version():
    """
    Версия сервера и download URL для авто-обновления клиента (Фаза 6 — DIST-05).

    sha256 пока пустая — заполнится при билд-процессе клиента, когда появится
    реальный .exe артефакт для публикации.
    """
    settings = get_settings()
    return {
        "version": settings.app_version,
        "download_url": "https://heyda.ru/planner/download",
        "sha256": "",
    }
