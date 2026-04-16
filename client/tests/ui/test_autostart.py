"""Unit-тесты autostart (Plan 03-09).

Тестирует управление записью в HKCU\\...\\Run через mock_winreg fixture.
TDD RED: написано до реализации production-кода.
"""
import winreg

import pytest

from client.utils.autostart import (
    APP_REG_VALUE,
    REG_PATH,
    disable_autostart,
    enable_autostart,
    get_autostart_command,
    is_autostart_enabled,
)


def test_empty_registry_returns_false(mock_winreg):
    """На пустом реестре is_autostart_enabled() должен вернуть False."""
    assert is_autostart_enabled() is False


def test_enable_writes_to_registry(mock_winreg):
    """enable_autostart() должен записать ключ в mock_winreg store."""
    enable_autostart()
    key = (winreg.HKEY_CURRENT_USER, REG_PATH, APP_REG_VALUE)
    assert key in mock_winreg


def test_enable_then_is_enabled_true(mock_winreg):
    """После enable_autostart() is_autostart_enabled() должен вернуть True."""
    enable_autostart()
    assert is_autostart_enabled() is True


def test_disable_removes_value(mock_winreg):
    """disable_autostart() после enable должен удалить запись из реестра."""
    enable_autostart()
    disable_autostart()
    key = (winreg.HKEY_CURRENT_USER, REG_PATH, APP_REG_VALUE)
    assert key not in mock_winreg


def test_disable_without_enable_no_crash(mock_winreg):
    """disable_autostart() на отсутствующей записи не должен крэшить."""
    disable_autostart()  # не должно поднимать исключение
    assert is_autostart_enabled() is False


def test_app_reg_value_is_ascii():
    """Value name должен быть ASCII строкой 'LichnyEzhednevnik'."""
    assert APP_REG_VALUE == "LichnyEzhednevnik"
    # Проверяем что нет кириллицы (frozen-exe safety)
    assert APP_REG_VALUE.isascii()


def test_reg_path_matches_expected():
    """REG_PATH должен содержать корректный путь к Run-ключу."""
    assert "Software" in REG_PATH
    assert "Microsoft" in REG_PATH
    assert "Windows" in REG_PATH
    assert "CurrentVersion" in REG_PATH
    assert "Run" in REG_PATH


def test_get_autostart_command_has_quotes():
    """get_autostart_command() должен возвращать строку в кавычках (пробелы в пути)."""
    cmd = get_autostart_command()
    # Путь должен быть в кавычках для обработки пробелов/кириллицы
    assert cmd.startswith('"')
    assert cmd.count('"') >= 2


def test_roundtrip_enable_disable(mock_winreg):
    """Полный цикл: нет → enable → True → disable → False."""
    assert is_autostart_enabled() is False
    enable_autostart()
    assert is_autostart_enabled() is True
    disable_autostart()
    assert is_autostart_enabled() is False
