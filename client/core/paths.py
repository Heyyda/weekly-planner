"""
AppPaths — резолюция путей к AppData-директории клиента.

Порядок fallback (D-02):
  1. %APPDATA% (основной — Windows Roaming AppData)
  2. %LOCALAPPDATA% (если APPDATA пусто — редкий edge case)
  3. Текущая рабочая директория "." (последний fallback — не блокировать запуск)

Директория автосоздаётся через ensure(). Файлы (cache.json, settings.json) НЕ
создаются здесь — только пути вычисляются. Создание — забота LocalStorage.
"""
from __future__ import annotations

import os
from pathlib import Path

from client.core.config import (
    APP_DIR_NAME,
    CACHE_FILE_NAME,
    LOGS_SUBDIR,
    SETTINGS_FILE_NAME,
)


def _resolve_appdata_root() -> Path:
    """
    APPDATA → LOCALAPPDATA → cwd fallback.
    Пустая строка трактуется как отсутствие переменной (важно для tests).
    """
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local)
    return Path(".").resolve()


class AppPaths:
    """
    Пути к файлам клиента. Лёгкий immutable wrapper — можно создавать много раз.
    Все поля read-only после __init__.

    Использование:
        paths = AppPaths()
        paths.ensure()           # создать директории
        data = paths.cache_file  # Path(.../cache.json)
    """

    def __init__(self) -> None:
        root = _resolve_appdata_root()
        self.base_dir: Path = root / APP_DIR_NAME
        self.cache_file: Path = self.base_dir / CACHE_FILE_NAME
        self.settings_file: Path = self.base_dir / SETTINGS_FILE_NAME
        self.logs_dir: Path = self.base_dir / LOGS_SUBDIR

    def ensure(self) -> None:
        """Создать base_dir и logs_dir (идемпотентно)."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return f"AppPaths(base_dir={self.base_dir!r})"
