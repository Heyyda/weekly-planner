"""Unit-тесты client/core/paths.py и client/core/config.py."""
import os
from pathlib import Path

import pytest

from client.core import AppPaths, config
from client.core.paths import _resolve_appdata_root


def test_app_paths_uses_appdata(tmp_appdata):
    """tmp_appdata подменяет APPDATA → AppPaths видит tmp_path."""
    paths = AppPaths()
    assert str(paths.base_dir).startswith(str(tmp_appdata))
    assert paths.base_dir.name == "ЛичныйЕженедельник"
    assert paths.cache_file.name == "cache.json"
    assert paths.settings_file.name == "settings.json"
    assert paths.logs_dir.name == "logs"


def test_app_paths_ensure_creates_dirs(tmp_appdata):
    """ensure() создаёт base_dir и logs_dir идемпотентно."""
    paths = AppPaths()
    assert not paths.base_dir.exists()
    paths.ensure()
    assert paths.base_dir.is_dir()
    assert paths.logs_dir.is_dir()
    # Повторный вызов — не падает
    paths.ensure()


def test_fallback_to_localappdata(tmp_path, monkeypatch):
    """Пустой APPDATA → fallback на LOCALAPPDATA."""
    monkeypatch.setenv("APPDATA", "")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = _resolve_appdata_root()
    assert root == tmp_path


def test_fallback_to_cwd(tmp_path, monkeypatch):
    """Оба пусты → fallback на cwd (не None, не crash)."""
    monkeypatch.setenv("APPDATA", "")
    monkeypatch.setenv("LOCALAPPDATA", "")
    root = _resolve_appdata_root()
    assert root.is_absolute() or root == Path(".").resolve()


def test_config_api_base_default():
    """API_BASE указывает на production (без trailing slash)."""
    assert config.API_BASE == "https://planner.heyda.ru/api"
    assert not config.API_BASE.endswith("/")


def test_config_keyring_service_is_ascii():
    """KEYRING_SERVICE в ASCII (RESEARCH Finding 5)."""
    assert config.KEYRING_SERVICE == "WeeklyPlanner"
    # Проверка что все символы — ASCII
    assert config.KEYRING_SERVICE.encode("ascii")


def test_config_numeric_constants_sane():
    """Числовые константы имеют разумные значения."""
    assert config.SYNC_INTERVAL_SECONDS == 30.0
    assert config.STALE_THRESHOLD_SECONDS == 300
    assert config.BACKOFF_BASE == 1.0
    assert config.BACKOFF_CAP == 60.0
    assert config.TOMBSTONE_CLEANUP_SECONDS == 3600
    assert config.LOG_ROTATION_MAX_BYTES == 1_000_000
    assert config.LOG_ROTATION_BACKUP_COUNT == 5
