"""
Health + Version endpoints.

Health — liveness check для systemd и reverse-proxy.
Version — для авто-обновления клиента (DIST-04/05). Читает манифест
`/opt/planner/releases/latest.json` — обновляется деплой-скриптом без
пересборки сервера.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter

from server.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["misc"])


_DEFAULT_MANIFEST_PATH = "/opt/planner/releases/latest.json"


def _read_manifest() -> dict:
    """Читать manifest JSON. Если нет или сломан — fallback к дефолту из config."""
    path = os.environ.get("PLANNER_RELEASE_MANIFEST", _DEFAULT_MANIFEST_PATH)
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "version": str(data.get("version", "")),
            "download_url": str(data.get("download_url", "")),
            "sha256": str(data.get("sha256", "")),
        }
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.debug("release manifest fallback: %s", exc)
        return {}


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/version")
async def version():
    """Версия последнего .exe релиза для автообновления клиента."""
    settings = get_settings()
    manifest = _read_manifest()
    return {
        "version": manifest.get("version") or settings.app_version,
        "download_url": manifest.get("download_url") or "",
        "sha256": manifest.get("sha256") or "",
    }
