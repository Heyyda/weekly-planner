"""
Центральные константы клиента. Никаких секретов (keyring — для refresh_token).

Все значения — из CONTEXT.md D-07..D-28. Не дублировать в других модулях:
импортировать `from client.core.config import API_BASE, SYNC_INTERVAL_SECONDS, ...`.
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
# Production endpoint. Для dev-окружения override через env var.
_DEFAULT_API_BASE = "https://planner.heyda.ru/api"
API_BASE: str = os.environ.get("PLANNER_API_URL", _DEFAULT_API_BASE).rstrip("/")

# HTTP timeout для sync/auth запросов (секунды)
HTTP_TIMEOUT_SECONDS: float = 10.0

# ---------------------------------------------------------------------------
# Sync cadence (D-07, D-08, D-13, D-19)
# ---------------------------------------------------------------------------
SYNC_INTERVAL_SECONDS: float = 30.0           # D-07 штатный интервал опроса
STALE_THRESHOLD_SECONDS: int = 300            # D-19 > 5 минут → full resync (since=None)
BACKOFF_BASE: float = 1.0                     # D-13 начальная задержка
BACKOFF_CAP: float = 60.0                     # D-13 cap 60s
TOMBSTONE_CLEANUP_SECONDS: int = 3600         # D-24 opportunistic cleanup после 1 часа

# ---------------------------------------------------------------------------
# Keyring (D-25, D-26)
# ---------------------------------------------------------------------------
# ASCII service name — избегаем проблему Cyrillic в frozen exe (PITFALLS Pitfall 4).
KEYRING_SERVICE: str = "WeeklyPlanner"
KEYRING_REFRESH_KEY: str = "refresh_token"
KEYRING_USERNAME_KEY: str = "telegram_username"

# ---------------------------------------------------------------------------
# Logging (D-27)
# ---------------------------------------------------------------------------
LOG_FILE_NAME: str = "client.log"
LOG_ROTATION_MAX_BYTES: int = 1_000_000        # 1 MB
LOG_ROTATION_BACKUP_COUNT: int = 5

# ---------------------------------------------------------------------------
# Paths (используется client/core/paths.py)
# ---------------------------------------------------------------------------
# Русское название папки — совпадает со скелетом (LocalStorage.APP_DIR).
APP_DIR_NAME: str = "ЛичныйЕженедельник"
CACHE_FILE_NAME: str = "cache.json"
SETTINGS_FILE_NAME: str = "settings.json"
LOGS_SUBDIR: str = "logs"

# Версия кеша (для будущих миграций)
CACHE_VERSION: int = 1
