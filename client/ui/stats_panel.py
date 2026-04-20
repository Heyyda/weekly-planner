"""
Stats Panel — итоги недели.

Отображается внизу панели:
  📊 Выполнено: 5/8 (62%)  |  Просрочено: 2

Опционально: мини-прогрессбар или визуальная полоска.
"""


class StatsPanel:
    """
    Мини-статистика по текущей неделе.

    Метрики:
    - total: общее кол-во задач
    - done: выполненные
    - overdue: просроченные (не выполнены, день прошёл)
    - completion_pct: процент выполнения
    """

    def __init__(self, parent_frame):
        self.parent = parent_frame

    def update(self, total: int, done: int, overdue: int):
        """Обновить статистику."""
        # TODO: пересчитать и перерисовать
        pass
