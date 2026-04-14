"""
Sidebar Manager — управление боковой панелью.

Отвечает за:
- Позиционирование окна у правого края экрана
- Анимацию выезда/скрытия (slide in/out)
- Отслеживание курсора для авто-показа
- Видимая полоска (4-6px) когда панель скрыта
- Иконка-триггер для раскрытия
"""

import ctypes
from enum import Enum


class SidebarState(Enum):
    COLLAPSED = "collapsed"   # скрыта, видна полоска
    EXPANDING = "expanding"   # анимация выезда
    EXPANDED = "expanded"     # полностью видна
    COLLAPSING = "collapsing" # анимация скрытия


class SidebarManager:
    """
    Управление sidebar-поведением окна.

    Принцип работы:
    - Окно всегда полного размера (PANEL_WIDTH x screen_height)
    - В collapsed: окно сдвинуто вправо, видна полоска COLLAPSED_WIDTH
    - При hover на полоску: анимация slide-in (x уменьшается на STEP каждые DELAY мс)
    - При уходе курсора: задержка 500мс → анимация slide-out

    Использует Win32 API:
    - GetCursorPos — позиция мыши
    - SetWindowPos — перемещение без мерцания
    - GetSystemMetrics — размер экрана
    """

    def __init__(self, root, panel_width: int, collapsed_width: int,
                 anim_step: int = 20, anim_delay: int = 12):
        self.root = root
        self.panel_width = panel_width
        self.collapsed_width = collapsed_width
        self.anim_step = anim_step
        self.anim_delay = anim_delay
        self.state = SidebarState.COLLAPSED

        # Экранные метрики
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()

        # Позиции
        self.x_expanded = self.screen_width - self.panel_width
        self.x_collapsed = self.screen_width - self.collapsed_width
        self.current_x = self.x_collapsed

        self._collapse_timer = None

    def setup(self):
        """Начальное позиционирование и привязка событий."""
        # TODO: Реализовать
        # 1. root.geometry(f"{panel_width}x{screen_height}+{x_collapsed}+0")
        # 2. Привязать <Enter>/<Leave> для отслеживания курсора
        # 3. Нарисовать trigger-полоску (тонкий frame с иконкой)
        pass

    def expand(self):
        """Анимация выезда панели."""
        # TODO: пошаговое уменьшение self.current_x до self.x_expanded
        pass

    def collapse(self):
        """Анимация скрытия панели (с задержкой)."""
        # TODO: задержка 500мс, затем увеличение self.current_x до self.x_collapsed
        pass

    def toggle(self):
        """Переключение состояния (для хоткея)."""
        if self.state == SidebarState.EXPANDED:
            self.collapse()
        else:
            self.expand()

    def _move_window(self, x: int):
        """Перемещение окна через Win32 API (без мерцания)."""
        # TODO: ctypes.windll.user32.SetWindowPos(...)
        pass
