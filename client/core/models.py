"""
Модели данных клиента — зеркалят серверные схемы (server/api/sync_schemas.py).

Task: dataclass, в памяти + сериализуется в JSON (cache.json).
TaskChange: одна операция в pending_changes queue, отправляется в /api/sync.
DayPlan/WeekPlan: computed aggregations (не хранятся в cache.json, строятся на лету).
AppState: глобальное состояние (сохраняется в settings.json).

Wire-format compatibility: см. server/api/sync_schemas.py — любое расхождение
→ 422 Unprocessable Entity на /api/sync.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Literal, Optional


def utcnow_iso() -> str:
    """UTC timestamp в ISO-8601 формате с суффиксом Z (совместимо с server_timestamp)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Task:
    """
    Одна задача. Зеркалит server TaskState (sync_schemas.py).

    id — UUID string, сгенерирован КЛИЕНТОМ (SYNC-06, идемпотентный CREATE).
    deleted_at is None → задача жива; str → tombstone (не создавать заново, SYNC-08).
    updated_at — source of truth: СЕРВЕР всегда ставит свой (SRV-06). Локально
    обновляем только после успешного merge_from_server().
    """
    id: str
    user_id: str
    text: str
    day: str                                    # ISO date: "2026-04-14"
    time_deadline: Optional[str] = None         # ISO datetime или None
    done: bool = False
    position: int = 0
    created_at: str = ""                        # ISO datetime UTC
    updated_at: str = ""                        # ISO datetime UTC (server-side)
    deleted_at: Optional[str] = None            # None = жива, ISO str = tombstone

    @classmethod
    def new(cls, user_id: str, text: str, day: str,
            time_deadline: Optional[str] = None, position: int = 0) -> "Task":
        """Создать новую задачу с client-generated UUID (SYNC-06)."""
        now = utcnow_iso()
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            text=text,
            day=day,
            time_deadline=time_deadline,
            done=False,
            position=position,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )

    def is_alive(self) -> bool:
        """True если задача не удалена (tombstone отсутствует)."""
        return self.deleted_at is None

    def is_overdue(self) -> bool:
        """Просроченная = не выполнена и дата прошла."""
        if self.done or not self.day or self.deleted_at is not None:
            return False
        try:
            return date.fromisoformat(self.day) < date.today()
        except ValueError:
            return False

    def to_dict(self) -> dict:
        """Сериализация для cache.json."""
        return asdict(self)


@dataclass
class TaskChange:
    """
    Операция в pending_changes queue. Сериализуется в server TaskChange через to_wire().

    Поля text/day/time_deadline/done/position — опциональные:
      CREATE: все обязательные (text, day заполнены; done/position/time_deadline могут быть None → дефолты)
      UPDATE: partial (только изменённые != None)
      DELETE: только op + task_id
    """
    op: Literal["create", "update", "delete"]
    task_id: str                                       # UUID string (Task.id)
    text: Optional[str] = None
    day: Optional[str] = None
    time_deadline: Optional[str] = None
    done: Optional[bool] = None
    position: Optional[int] = None
    # Internal metadata (НЕ отправляется на сервер)
    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=utcnow_iso)

    def to_wire(self) -> dict:
        """
        Сериализация в dict для отправки в POST /api/sync.
        Не включает change_id/ts (internal metadata).
        Для DELETE возвращает только {op, task_id}.
        Для UPDATE возвращает только не-None поля (partial update).
        """
        payload: dict = {"op": self.op, "task_id": self.task_id}
        if self.op == "delete":
            return payload
        for key in ("text", "day", "time_deadline", "done", "position"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload

    def to_dict(self) -> dict:
        """Сериализация ДЛЯ cache.json (включает change_id/ts для восстановления после крэша)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TaskChange":
        """Десериализация из cache.json."""
        return cls(**data)


@dataclass
class DayPlan:
    """Один день — задачи + опционально заметки (заметки — Phase 4). Computed."""
    day: str = ""
    tasks: list[Task] = field(default_factory=list)
    notes: str = ""

    @property
    def total(self) -> int:
        return sum(1 for t in self.tasks if t.is_alive())

    @property
    def done_count(self) -> int:
        return sum(1 for t in self.tasks if t.is_alive() and t.done)

    @property
    def overdue_count(self) -> int:
        return sum(1 for t in self.tasks if t.is_overdue())


@dataclass
class WeekPlan:
    """Неделя — 7 дней (Пн-Вс). Computed aggregation, не хранится в cache.json."""
    week_start: str = ""
    days: list[DayPlan] = field(default_factory=list)

    @property
    def total_tasks(self) -> int:
        return sum(d.total for d in self.days)

    @property
    def total_done(self) -> int:
        return sum(d.done_count for d in self.days)

    @property
    def total_overdue(self) -> int:
        return sum(d.overdue_count for d in self.days)

    @property
    def completion_pct(self) -> int:
        if self.total_tasks == 0:
            return 100
        return round(self.total_done / self.total_tasks * 100)


@dataclass
class AppState:
    """Глобальное состояние — сохраняется в settings.json."""
    user_id: Optional[str] = None
    username: Optional[str] = None
    theme: str = "dark"
    sidebar_side: str = "right"
    hotkey: str = "win+q"
    autostart: bool = False
    do_not_disturb: bool = False
    last_sync: Optional[str] = None
