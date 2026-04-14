"""
Autostart — автозапуск с Windows.

Добавляет/удаляет запись в реестре:
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
"""

import sys
import winreg


APP_NAME = "ЛичныйЕженедельник"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_autostart_enabled() -> bool:
    """Проверить, включён ли автозапуск."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def enable_autostart():
    """Добавить приложение в автозагрузку."""
    exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')


def disable_autostart():
    """Убрать приложение из автозагрузки."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass
