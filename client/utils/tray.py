"""
System Tray — иконка в системном трее.

Показывает:
- Иконку приложения рядом с часами
- Badge с количеством задач на сегодня (если есть)
- Контекстное меню: Показать/Скрыть, Настройки, Выход

Использует pystray для кроссплатформенности.
"""

import threading
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False


class TrayManager:
    """Управление иконкой в system tray."""

    def __init__(self, icon_path: str, on_show: Callable, on_quit: Callable):
        self.icon_path = icon_path
        self.on_show = on_show
        self.on_quit = on_quit
        self._icon: Optional[object] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Запустить иконку в отдельном потоке."""
        if not HAS_PYSTRAY:
            return

        image = Image.open(self.icon_path) if self.icon_path else self._create_default_icon()

        menu = pystray.Menu(
            pystray.MenuItem("Показать", self.on_show, default=True),
            pystray.MenuItem("Выход", self._quit),
        )

        self._icon = pystray.Icon("weekly_planner", image, "Личный Еженедельник", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        """Убрать иконку из трея."""
        if self._icon:
            self._icon.stop()

    def update_tooltip(self, text: str):
        """Обновить tooltip (например: '3 задачи на сегодня')."""
        if self._icon:
            self._icon.title = text

    def _quit(self, icon, item):
        """Выход из приложения через трей."""
        icon.stop()
        self.on_quit()

    @staticmethod
    def _create_default_icon() -> "Image":
        """Простая иконка-заглушка если нет icon.ico."""
        img = Image.new("RGB", (64, 64), color=(74, 158, 255))
        return img
