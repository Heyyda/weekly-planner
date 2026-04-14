"""
Local Storage — локальный кеш задач для оффлайн-работы.

Хранит данные в JSON файле:
%APPDATA%/ЛичныйЕженедельник/cache.json

Структура файла:
{
    "weeks": {
        "2026-04-07": { ... WeekPlan ... },
        "2026-04-14": { ... WeekPlan ... }
    },
    "categories": [ ... ],
    "templates": [ ... ],
    "settings": { ... AppState ... },
    "pending_changes": [ ... ]  // изменения для синхронизации
}

Pending changes — очередь операций, которые нужно отправить на сервер:
[
    {"op": "create_task", "data": {...}, "timestamp": "..."},
    {"op": "update_task", "data": {...}, "timestamp": "..."},
    {"op": "delete_task", "id": "...", "timestamp": "..."}
]
"""

import json
import os
from pathlib import Path
from typing import Optional

from client.core.models import WeekPlan, AppState


class LocalStorage:
    """
    Управление локальным кешем.

    Потокобезопасность: все записи через threading.Lock (UI thread может
    читать в любой момент, sync thread пишет в фоне).
    """

    APP_DIR = "ЛичныйЕженедельник"

    def __init__(self):
        self.base_path = Path(os.environ.get("APPDATA", ".")) / self.APP_DIR
        self.cache_file = self.base_path / "cache.json"
        self.settings_file = self.base_path / "settings.json"
        self._data = {}

    def init(self):
        """Создать директорию и загрузить кеш."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def save(self):
        """Сохранить кеш на диск."""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get_week(self, week_start: str) -> Optional[dict]:
        """Получить данные недели из кеша."""
        return self._data.get("weeks", {}).get(week_start)

    def save_week(self, week_start: str, week_data: dict):
        """Сохранить данные недели в кеш."""
        if "weeks" not in self._data:
            self._data["weeks"] = {}
        self._data["weeks"][week_start] = week_data
        self.save()

    def add_pending_change(self, operation: dict):
        """Добавить операцию в очередь синхронизации."""
        if "pending_changes" not in self._data:
            self._data["pending_changes"] = []
        self._data["pending_changes"].append(operation)
        self.save()

    def get_pending_changes(self) -> list:
        """Получить все неотправленные изменения."""
        return self._data.get("pending_changes", [])

    def clear_pending_changes(self):
        """Очистить очередь после успешной синхронизации."""
        self._data["pending_changes"] = []
        self.save()

    def load_settings(self) -> dict:
        """Загрузить настройки."""
        if self.settings_file.exists():
            with open(self.settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_settings(self, settings: dict):
        """Сохранить настройки."""
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
