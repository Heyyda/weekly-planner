"""
LocalStorage — потокобезопасный JSON-кеш задач + очередь pending_changes.

Структура cache.json (D-10):
    {
      "meta": {"cache_version": 1, "last_sync_at": "ISO" | null},
      "tasks": [Task, ...],
      "pending_changes": [TaskChange.to_dict(), ...]
    }

Thread safety (D-12):
    Один threading.Lock защищает весь _data. ВСЕ публичные мутации делают
    self._lock + _save_locked() в одном критическом участке. Никаких RLock,
    никаких nested acquire. UI thread читает get_visible_tasks() (с lock),
    sync thread вызывает drain_pending_changes() / merge_from_server() (с lock).

Atomic persistence (RESEARCH Pitfall 3):
    _save_locked пишет в .tmp файл, потом os.replace(tmp, cache_file).
    os.replace атомарен на одном томе (Windows + POSIX).
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from client.core import config
from client.core.models import Task, TaskChange, utcnow_iso
from client.core.paths import AppPaths

logger = logging.getLogger(__name__)


def _empty_data() -> dict:
    return {
        "meta": {"cache_version": config.CACHE_VERSION, "last_sync_at": None},
        "tasks": [],
        "pending_changes": [],
    }


class LocalStorage:
    """JSON-кеш с thread-safe pending queue. См. CONTEXT.md D-01..D-12, D-22..D-24."""

    def __init__(self, paths: Optional[AppPaths] = None) -> None:
        self.paths: AppPaths = paths or AppPaths()
        self._lock = threading.Lock()
        self._data: dict = _empty_data()

    # ---- lifecycle ----

    def init(self) -> None:
        """Создать директории и загрузить cache.json (no-op если уже инициализировано)."""
        self.paths.ensure()
        self._load()

    def _load(self) -> None:
        """Загрузить cache.json. При отсутствии/коррупции — пустая структура."""
        cache_file = self.paths.cache_file
        if not cache_file.exists():
            self._data = _empty_data()
            return
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Минимальная нормализация — ensure all keys present
            if not isinstance(loaded, dict):
                raise ValueError("cache.json не dict")
            normalized = _empty_data()
            normalized["meta"].update(loaded.get("meta", {}) or {})
            normalized["tasks"] = list(loaded.get("tasks", []) or [])
            normalized["pending_changes"] = list(loaded.get("pending_changes", []) or [])
            self._data = normalized
            if normalized["meta"].get("cache_version") != config.CACHE_VERSION:
                logger.warning(
                    "Версия кеша %s != текущая %s — рекомендован full resync",
                    normalized["meta"].get("cache_version"), config.CACHE_VERSION,
                )
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.error("Не удалось загрузить cache.json: %s. Начинаю с пустого.", exc)
            self._data = _empty_data()

    def _save_locked(self) -> None:
        """Atomic write через tmp + os.replace. ВЫЗЫВАТЬ ТОЛЬКО ПОД self._lock."""
        cache_file = self.paths.cache_file
        tmp = cache_file.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, cache_file)
        except OSError as exc:
            logger.error("Не удалось сохранить cache.json: %s", exc)
            try:
                tmp.unlink()
            except OSError:
                pass

    # ---- task accessors ----

    def get_visible_tasks(self) -> list[Task]:
        """Все живые задачи (deleted_at is None). Возвращает копии (Task dataclasses)."""
        with self._lock:
            return [Task(**t) for t in self._data["tasks"] if t.get("deleted_at") is None]

    def get_all_tasks(self) -> list[Task]:
        """Все задачи включая tombstones (для sync push/merge)."""
        with self._lock:
            return [Task(**t) for t in self._data["tasks"]]

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            for t in self._data["tasks"]:
                if t.get("id") == task_id:
                    return Task(**t)
        return None

    # ---- task mutations (SYNC-02 optimistic) ----

    def add_task(self, task: Task) -> None:
        """Добавить задачу + поставить CREATE в очередь (optimistic UI)."""
        change = TaskChange(
            op="create",
            task_id=task.id,
            text=task.text,
            day=task.day,
            time_deadline=task.time_deadline,
            done=task.done,
            position=task.position,
        )
        with self._lock:
            self._data["tasks"].append(task.to_dict())
            self._data["pending_changes"].append(change.to_dict())
            self._save_locked()

    def update_task(self, task_id: str, **fields) -> bool:
        """Изменить поля задачи + поставить partial UPDATE в очередь."""
        allowed = {"text", "day", "time_deadline", "done", "position"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Неизвестные поля: {unknown}")

        with self._lock:
            target = None
            for t in self._data["tasks"]:
                if t.get("id") == task_id:
                    target = t
                    break
            if target is None or target.get("deleted_at") is not None:
                return False
            for k, v in fields.items():
                target[k] = v
            target["updated_at"] = utcnow_iso()  # локальный optimistic — сервер всё равно перепишет
            change = TaskChange(op="update", task_id=task_id, **fields)
            self._data["pending_changes"].append(change.to_dict())
            self._save_locked()
        return True

    def soft_delete_task(self, task_id: str) -> bool:
        """SYNC-08: пометить tombstone (deleted_at) + поставить DELETE в очередь (D-22)."""
        with self._lock:
            target = None
            for t in self._data["tasks"]:
                if t.get("id") == task_id:
                    target = t
                    break
            if target is None or target.get("deleted_at") is not None:
                return False
            now = utcnow_iso()
            target["deleted_at"] = now
            target["updated_at"] = now
            change = TaskChange(op="delete", task_id=task_id)
            self._data["pending_changes"].append(change.to_dict())
            self._save_locked()
        return True

    # ---- pending queue (SYNC-04 thread-safe) ----

    def add_pending_change(self, change: TaskChange) -> None:
        """Прямое добавление в очередь (для миграций / прямых API вызовов)."""
        with self._lock:
            self._data["pending_changes"].append(change.to_dict())
            self._save_locked()

    def drain_pending_changes(self) -> list[TaskChange]:
        """
        Атомарно изъять всю очередь (SYNC-04). Sync thread берёт snapshot;
        UI thread может продолжать добавлять новые операции.

        ВАЖНО: НЕ сохраняем cache.json здесь — иначе при failed push изменения
        теряются на диске. Restore через restore_pending_changes() при ошибке.
        """
        with self._lock:
            serialized = list(self._data["pending_changes"])
            self._data["pending_changes"] = []
            # ВНИМАНИЕ: НЕ вызываем _save_locked здесь
        return [TaskChange.from_dict(d) for d in serialized]

    def restore_pending_changes(self, changes: list[TaskChange]) -> None:
        """Вернуть changes в начало очереди (при failed push)."""
        if not changes:
            return
        with self._lock:
            existing = self._data["pending_changes"]
            self._data["pending_changes"] = [c.to_dict() for c in changes] + existing
            self._save_locked()

    def commit_drained(self, drained: list[TaskChange]) -> None:
        """
        Сохранить cache.json после успешного push (изменения уже изъяты drain'ом).
        Просто триггерит _save_locked для персистенции пустой очереди.
        """
        with self._lock:
            self._save_locked()

    def pending_count(self) -> int:
        """Сколько изменений в очереди (для диагностики)."""
        with self._lock:
            return len(self._data["pending_changes"])

    # ---- merge from server (SYNC-05 server-wins) ----

    def merge_from_server(
        self, server_changes: list[dict], server_timestamp: str
    ) -> dict:
        """
        Применить delta от сервера (D-16, D-17, SYNC-05).

        server_changes: список TaskState dicts (server/api/sync_schemas.py).
            Каждый dict имеет ключ "task_id" — мы маппим в локальный "id".
        server_timestamp: ISO-строка, сохраняется как meta.last_sync_at.

        Возвращает: {"applied": int, "conflicts": int, "tombstones_received": int}
        """
        applied = 0
        conflicts = 0
        tombstones_received = 0

        with self._lock:
            tasks_by_id: dict[str, dict] = {
                t["id"]: t for t in self._data["tasks"]
            }
            pending_ids: set[str] = {
                c.get("task_id") for c in self._data["pending_changes"]
                if c.get("task_id")
            }

            for server_task in server_changes:
                tid = server_task.get("task_id")
                if not tid:
                    continue
                # Маппинг task_id → id для локального формата
                local_format = dict(server_task)
                local_format["id"] = tid
                local_format.pop("task_id", None)
                # user_id может отсутствовать в TaskState — заполняем из существующей записи или пусто
                if "user_id" not in local_format:
                    existing = tasks_by_id.get(tid, {})
                    local_format["user_id"] = existing.get("user_id", "")
                # Конвертируем datetime поля → ISO строки (если pydantic вернул datetime)
                for dt_key in ("created_at", "updated_at", "deleted_at", "time_deadline"):
                    v = local_format.get(dt_key)
                    if isinstance(v, datetime):
                        local_format[dt_key] = v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

                if tid in pending_ids:
                    logger.warning(
                        "Конфликт: task %s в pending_changes перезаписана сервером (D-17)", tid
                    )
                    conflicts += 1

                if local_format.get("deleted_at") is not None:
                    tombstones_received += 1

                existing = tasks_by_id.get(tid)
                if existing is None:
                    tasks_by_id[tid] = local_format
                    applied += 1
                else:
                    server_ts = local_format.get("updated_at", "") or ""
                    local_ts = existing.get("updated_at", "") or ""
                    if server_ts >= local_ts:
                        tasks_by_id[tid] = local_format
                        applied += 1

            self._data["tasks"] = list(tasks_by_id.values())
            self._data["meta"]["last_sync_at"] = server_timestamp
            self._save_locked()

        logger.info(
            "merge_from_server: applied=%d, conflicts=%d, tombstones=%d, since=%s",
            applied, conflicts, tombstones_received, server_timestamp,
        )
        return {
            "applied": applied,
            "conflicts": conflicts,
            "tombstones_received": tombstones_received,
        }

    # ---- tombstone cleanup (D-23, D-24) ----

    def cleanup_tombstones(self, min_age_seconds: int = config.TOMBSTONE_CLEANUP_SECONDS) -> int:
        """
        Физически удалить tombstone-задачи старше min_age_seconds, если для них
        нет pending op (D-23: ждём подтверждения push). Возвращает количество удалённых.
        """
        removed = 0
        cutoff = datetime.now(timezone.utc).timestamp() - min_age_seconds

        with self._lock:
            pending_ids = {
                c.get("task_id") for c in self._data["pending_changes"]
                if c.get("task_id")
            }
            kept: list[dict] = []
            for t in self._data["tasks"]:
                deleted_at_str = t.get("deleted_at")
                if deleted_at_str is None:
                    kept.append(t)
                    continue
                if t.get("id") in pending_ids:
                    kept.append(t)  # ждём подтверждения push
                    continue
                try:
                    ts = datetime.fromisoformat(deleted_at_str.replace("Z", "+00:00")).timestamp()
                except (ValueError, AttributeError):
                    kept.append(t)
                    continue
                if ts < cutoff:
                    removed += 1
                else:
                    kept.append(t)
            if removed > 0:
                self._data["tasks"] = kept
                self._save_locked()
        if removed:
            logger.info("cleanup_tombstones: удалено %d", removed)
        return removed

    # ---- meta ----

    def get_meta(self, key: str) -> Any:
        with self._lock:
            return self._data["meta"].get(key)

    def set_meta(self, key: str, value: Any) -> None:
        with self._lock:
            self._data["meta"][key] = value
            self._save_locked()

    # ---- settings (отдельный файл) ----

    def load_settings(self) -> dict:
        settings_file = self.paths.settings_file
        if not settings_file.exists():
            return {}
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Не удалось загрузить settings.json: %s", exc)
            return {}

    def save_settings(self, settings: dict) -> None:
        settings_file = self.paths.settings_file
        tmp = settings_file.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            os.replace(tmp, settings_file)
        except OSError as exc:
            logger.error("Не удалось сохранить settings.json: %s", exc)
            try:
                tmp.unlink()
            except OSError:
                pass
