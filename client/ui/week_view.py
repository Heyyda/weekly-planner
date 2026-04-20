"""
Week View — навигация по неделям и отображение дней.

Структура:
┌─────────────────────────────┐
│  ◀  Неделя 15 (7-11 апр)  ▶ │  ← навигация
├─────────────────────────────┤
│ ▼ Понедельник, 7 апреля  ●  │  ← заголовок дня (● = есть просроченные)
│   ☑ Проверить остатки       │
│   ☐ Позвонить поставщику    │
│   + Добавить задачу...      │
├─────────────────────────────┤
│ ▶ Вторник, 8 апреля         │  ← свёрнутый день
├─────────────────────────────┤
│ ▼ Среда, 9 апреля           │  ← развёрнутый день
│   ☐ Сделать отчёт           │
│   📝 Заметки...             │
│   + Добавить задачу...      │
├─────────────────────────────┤
│ ...                         │
├─────────────────────────────┤
│ 📊 Итоги: 5/8 (62%)        │  ← мини-статистика
└─────────────────────────────┘
"""

from datetime import date, timedelta
from typing import Optional

from client.core.models import WeekPlan


# Русские названия дней
DAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
DAY_NAMES_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт"]
MONTH_NAMES = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]


class WeekView:
    """
    Виджет навигации по неделям.

    Отвечает за:
    - Определение текущей недели (ISO week)
    - Навигация стрелками влево/вправо
    - Отображение заголовка "Неделя N (дата-дата месяц)"
    - Создание DayPanel для каждого рабочего дня
    - Подсветка сегодняшнего дня
    - Мини-статистика внизу
    """

    def __init__(self, parent_frame):
        self.parent = parent_frame
        self.current_week_start: date = self._get_week_start(date.today())
        self.week_plan: Optional[WeekPlan] = None

    @staticmethod
    def _get_week_start(d: date) -> date:
        """Понедельник текущей недели."""
        return d - timedelta(days=d.weekday())

    def navigate(self, delta: int):
        """Перейти на delta недель вперёд/назад."""
        self.current_week_start += timedelta(weeks=delta)
        self._refresh()

    def go_to_today(self):
        """Вернуться к текущей неделе."""
        self.current_week_start = self._get_week_start(date.today())
        self._refresh()

    def _refresh(self):
        """Перерисовать неделю."""
        # TODO: Реализовать
        # 1. Загрузить WeekPlan из storage/sync
        # 2. Очистить parent frame
        # 3. Нарисовать заголовок с навигацией
        # 4. Нарисовать DayPanel для каждого дня (Пн-Пт)
        # 5. Подсветить сегодняшний день
        # 6. Нарисовать итоги недели
        pass

    def get_week_title(self) -> str:
        """Форматирование заголовка: 'Неделя 15 (7-11 апреля)'."""
        week_num = self.current_week_start.isocalendar()[1]
        end = self.current_week_start + timedelta(days=4)
        start_day = self.current_week_start.day
        end_day = end.day
        month = MONTH_NAMES[end.month]
        return f"Неделя {week_num} ({start_day}–{end_day} {month})"
