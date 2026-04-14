"""
Модели данных приложения.

Все модели — dataclass для простоты сериализации в JSON.
Используются и на клиенте, и при обмене с сервером.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from enum import IntEnum


class Priority(IntEnum):
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Task:
    """Одна задача."""
    id: str = ""                          # UUID, генерируется при создании
    text: str = ""                        # текст задачи
    done: bool = False                    # выполнена
    priority: Priority = Priority.NORMAL  # приоритет
    day: str = ""                         # дата (ISO: "2026-04-14")
    position: int = 0                     # порядок внутри дня
    category_id: Optional[str] = None     # ID категории (опционально)
    created_at: str = ""                  # ISO datetime
    updated_at: str = ""                  # ISO datetime

    def is_overdue(self) -> bool:
        """Задача просрочена если не выполнена и день прошёл."""
        if self.done or not self.day:
            return False
        return date.fromisoformat(self.day) < date.today()


@dataclass
class DayPlan:
    """Один день — задачи + заметки."""
    day: str = ""           # дата (ISO)
    tasks: list[Task] = field(default_factory=list)
    notes: str = ""         # свободные заметки

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def done_count(self) -> int:
        return sum(1 for t in self.tasks if t.done)

    @property
    def overdue_count(self) -> int:
        return sum(1 for t in self.tasks if t.is_overdue())


@dataclass
class WeekPlan:
    """Неделя — 5 рабочих дней."""
    week_start: str = ""    # понедельник (ISO date)
    days: list[DayPlan] = field(default_factory=list)  # Пн-Пт

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
class Category:
    """Категория/тег для группировки задач."""
    id: str = ""
    name: str = ""          # "Закупки", "Клиенты", "Внутреннее"
    color: str = "#4a9eff"  # hex цвет метки


@dataclass
class RecurringTemplate:
    """Шаблон повторяющейся задачи."""
    id: str = ""
    text: str = ""
    priority: Priority = Priority.NORMAL
    category_id: Optional[str] = None
    weekdays: list[int] = field(default_factory=list)  # 0=Пн, 1=Вт, ..., 4=Пт


@dataclass
class AppState:
    """Глобальное состояние приложения."""
    user_id: Optional[str] = None
    username: Optional[str] = None
    jwt_token: Optional[str] = None
    theme: str = "dark"
    sidebar_side: str = "right"       # "left" или "right"
    hotkey: str = "win+q"
    autostart: bool = False
    do_not_disturb: bool = False
    last_sync: Optional[str] = None   # ISO datetime последней синхронизации
