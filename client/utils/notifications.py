"""
Notifications — всплывающие напоминания.

Типы уведомлений:
1. Просроченные задачи — при открытии приложения, если есть незакрытые за прошлые дни
2. Напоминание о текущих задачах — по таймеру (если настроено)

В режиме "Не беспокоить" все уведомления подавляются.

Использует win10toast или встроенные средства Windows для toast-уведомлений.
"""

from typing import List
from client.core.models import Task


class NotificationManager:
    """Управление уведомлениями."""

    def __init__(self, do_not_disturb: bool = False):
        self.do_not_disturb = do_not_disturb

    def check_overdue(self, tasks: List[Task]):
        """
        Проверить просроченные задачи и показать уведомление.
        Вызывается при запуске и при возврате к панели.
        """
        if self.do_not_disturb:
            return

        overdue = [t for t in tasks if t.is_overdue()]
        if not overdue:
            return

        count = len(overdue)
        # TODO: показать toast или внутреннее уведомление
        # "У вас 3 просроченных задачи. Перенести на сегодня?"
        pass

    def show_toast(self, title: str, message: str):
        """Показать Windows toast-уведомление."""
        if self.do_not_disturb:
            return
        # TODO: win10toast или ctypes MessageBox как fallback
        pass
