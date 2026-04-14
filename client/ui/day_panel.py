"""
Day Panel — сворачиваемая секция одного дня.

Содержит:
- Заголовок (название дня + дата, кликабельный для сворачивания)
- Индикатор просроченных задач (красная точка)
- Список задач (TaskWidget для каждой)
- Кнопка "+ Добавить задачу"
- Секция заметок (опционально)
"""

from datetime import date


class DayPanel:
    """
    Один день в недельном виде.

    Состояния:
    - Свёрнутый: только заголовок "▶ Понедельник, 7 апреля"
    - Развёрнутый: заголовок + задачи + кнопка добавления

    Сегодняшний день выделяется цветом заголовка.
    Дни с просроченными задачами показывают красный индикатор.
    """

    def __init__(self, parent_frame, day_date: date, is_today: bool = False):
        self.parent = parent_frame
        self.day_date = day_date
        self.is_today = is_today
        self.expanded = is_today  # сегодня развёрнут по умолчанию
        self.tasks = []

    def toggle(self):
        """Свернуть/развернуть секцию дня."""
        self.expanded = not self.expanded
        self._refresh()

    def add_task(self, text: str, priority: int = 2):
        """Добавить новую задачу в этот день."""
        # TODO: создать Task, сохранить, обновить UI
        pass

    def has_overdue(self) -> bool:
        """Есть ли невыполненные задачи в прошедшем дне."""
        return (
            self.day_date < date.today()
            and any(not t.done for t in self.tasks)
        )

    def _refresh(self):
        """Перерисовать секцию."""
        # TODO: Реализовать
        pass
