"""
Sync Manager — синхронизация с сервером.

Стратегия: optimistic UI + background sync.
1. Все действия пользователя применяются к локальному кешу мгновенно
2. Изменения добавляются в pending_changes
3. Фоновый поток каждые 30 сек отправляет pending_changes на сервер
4. При получении ответа — обновляет локальный кеш серверными данными
5. Конфликты: server wins (серверная версия перезаписывает локальную)

API endpoints:
- POST /api/sync — отправить pending_changes, получить актуальные данные
- GET  /api/weeks/{week_start} — получить неделю
- GET  /api/overdue — получить все просроченные задачи
"""

import threading
import time
import requests
from typing import Optional

from client.core.storage import LocalStorage


# Сервер
API_BASE = "https://heyda.ru/planner/api"  # TODO: финализировать URL
SYNC_INTERVAL = 30  # секунд


class SyncManager:
    """
    Фоновая синхронизация.

    Запускается в отдельном потоке.
    При ошибке сети — молча ждёт следующего цикла (оффлайн-режим).
    """

    def __init__(self, storage: LocalStorage, jwt_token: Optional[str] = None):
        self.storage = storage
        self.jwt_token = jwt_token
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Запустить фоновую синхронизацию."""
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Остановить синхронизацию."""
        self._running = False

    def force_sync(self):
        """Принудительная синхронизация (вызывается при важных действиях)."""
        threading.Thread(target=self._do_sync, daemon=True).start()

    def _sync_loop(self):
        """Основной цикл синхронизации."""
        while self._running:
            self._do_sync()
            time.sleep(SYNC_INTERVAL)

    def _do_sync(self):
        """Одна итерация синхронизации."""
        if not self.jwt_token:
            return

        pending = self.storage.get_pending_changes()
        if not pending:
            return

        try:
            resp = requests.post(
                f"{API_BASE}/sync",
                json={"changes": pending},
                headers={"Authorization": f"Bearer {self.jwt_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Обновить локальный кеш серверными данными
                for week_start, week_data in data.get("weeks", {}).items():
                    self.storage.save_week(week_start, week_data)
                self.storage.clear_pending_changes()
        except requests.RequestException:
            pass  # оффлайн — повторим на следующем цикле

    def pull_week(self, week_start: str) -> Optional[dict]:
        """Загрузить неделю с сервера."""
        if not self.jwt_token:
            return None
        try:
            resp = requests.get(
                f"{API_BASE}/weeks/{week_start}",
                headers={"Authorization": f"Bearer {self.jwt_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except requests.RequestException:
            pass
        return None
