"""
Autostart — управление записью в HKCU\\...\\Run для автозапуска Windows.

Value name (ASCII): "LichnyEzhednevnik" — избегаем frozen-exe проблему с Cyrillic
(параллельный паттерн с config.KEYRING_SERVICE = "WeeklyPlanner" per D-25 / PITFALL 4).

Phase 3: dev-режим → python.exe main.py
Phase 6: frozen exe → sys.executable (PyInstaller --onefile).
Переключение автоматическое через getattr(sys, 'frozen', False).
"""
from __future__ import annotations

import logging
import sys
import winreg
from pathlib import Path

logger = logging.getLogger(__name__)

# ASCII value name — frozen-exe safety (см. D-30 в 03-CONTEXT.md)
# Кириллица в winreg value name вызывает ошибку кодировки в frozen PyInstaller exe
APP_REG_VALUE = "LichnyEzhednevnik"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_autostart_enabled() -> bool:
    """Проверить наличие value в HKCU\\...\\Run.

    Returns:
        True если запись существует, False если нет или ошибка доступа.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_REG_VALUE)
            return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("is_autostart_enabled OS error: %s", exc)
        return False


def enable_autostart() -> None:
    """Записать путь запуска в реестр HKCU\\...\\Run.

    Raises:
        OSError: если нет прав на запись в реестр.
    """
    command = get_autostart_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_REG_VALUE, 0, winreg.REG_SZ, command)
        logger.info("Autostart enabled: %s", command)
    except OSError as exc:
        logger.error("enable_autostart failed: %s", exc)
        raise


def disable_autostart() -> None:
    """Удалить value из реестра. Если не было — no-op (FileNotFoundError handled).

    Не поднимает исключение если запись отсутствует.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_REG_VALUE)
        logger.info("Autostart disabled")
    except FileNotFoundError:
        logger.debug("Autostart value not present — skip delete")
    except OSError as exc:
        logger.error("disable_autostart failed: %s", exc)


def get_autostart_command() -> str:
    """Вернуть строку команды для записи в реестр.

    Frozen exe (PyInstaller --onefile):
        ``"C:\\path\\to\\exe.exe"``

    Dev-режим (python.exe + main.py):
        ``"C:\\python.exe" "S:\\path\\to\\main.py"``

    Обе части в кавычках — корректная обработка пробелов и кириллицы в пути.

    Returns:
        Строка команды готовая для записи в REG_SZ.
    """
    if getattr(sys, "frozen", False):
        # Phase 6 — собранный PyInstaller .exe
        return f'"{sys.executable}"'

    # Dev-режим — python.exe + путь к main.py
    script = (
        Path(sys.argv[0]).resolve()
        if sys.argv and sys.argv[0]
        else Path("main.py").resolve()
    )
    return f'"{sys.executable}" "{script}"'
