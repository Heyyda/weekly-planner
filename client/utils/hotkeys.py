"""
Global Hotkeys — глобальные горячие клавиши.

По умолчанию: Win+Q для вызова/скрытия панели.
Настраивается в настройках.

Использует библиотеку keyboard для перехвата на уровне ОС.
Работает даже когда приложение не в фокусе.
"""

import keyboard
from typing import Callable, Optional


class HotkeyManager:
    """Регистрация и управление глобальными хоткеями."""

    def __init__(self):
        self._hotkey_id: Optional[object] = None
        self._current_combo: Optional[str] = None

    def register(self, combo: str, callback: Callable):
        """
        Зарегистрировать глобальный хоткей.
        combo: строка вида "win+q", "ctrl+shift+w"
        """
        self.unregister()
        self._current_combo = combo
        self._hotkey_id = keyboard.add_hotkey(combo, callback)

    def unregister(self):
        """Снять текущий хоткей."""
        if self._hotkey_id is not None:
            keyboard.remove_hotkey(self._hotkey_id)
            self._hotkey_id = None

    def change(self, new_combo: str, callback: Callable):
        """Сменить комбинацию."""
        self.register(new_combo, callback)
