"""Unit-тесты client/core/logging_setup.py."""
import logging

import pytest

from client.core.logging_setup import (
    SecretFilter, reset_client_logging, setup_client_logging,
)

# Константы для теста (дублируют config.py, чтобы не зависеть от порядка инициализации)
LOG_FILE_NAME = "client.log"


@pytest.fixture(autouse=True)
def _reset_logging():
    """Сбрасывает root logger перед/после каждого теста — изоляция."""
    reset_client_logging()
    yield
    reset_client_logging()


def test_setup_creates_log_file(tmp_appdata):
    """setup_client_logging создаёт файл client.log в logs_dir."""
    from client.core.logging_setup import setup_client_logging

    # Создаём AppPaths через временный APPDATA
    from client.core.paths import AppPaths
    paths = AppPaths()
    paths.ensure()

    setup_client_logging(paths)
    log = logging.getLogger("client.test")
    log.info("первая запись")

    log_file = paths.logs_dir / LOG_FILE_NAME
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "первая запись" in content
    assert "client.test" in content


def test_setup_is_idempotent(tmp_appdata):
    """Повторный вызов setup НЕ дублирует handlers."""
    from client.core.paths import AppPaths
    from logging.handlers import RotatingFileHandler

    paths = AppPaths()
    paths.ensure()
    h1 = setup_client_logging(paths)
    h2 = setup_client_logging(paths)
    # Повторный вызов возвращает тот же handler
    assert h1 is h2
    # Только один RotatingFileHandler в root
    rfh_count = sum(
        1 for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
    )
    assert rfh_count == 1


def test_secret_filter_masks_bearer(tmp_appdata):
    """SecretFilter маскирует 'Bearer XYZ' → 'Bearer ***'."""
    from client.core.paths import AppPaths

    paths = AppPaths()
    paths.ensure()
    setup_client_logging(paths)
    log = logging.getLogger("client.test")
    log.error("Sync request: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")

    log_file = paths.logs_dir / LOG_FILE_NAME
    content = log_file.read_text(encoding="utf-8")
    assert "Bearer ***" in content
    assert "eyJhbGciOiJIUzI1NiJ9" not in content


def test_secret_filter_masks_refresh_token(tmp_appdata):
    """SecretFilter маскирует refresh_token=VALUE."""
    from client.core.paths import AppPaths

    paths = AppPaths()
    paths.ensure()
    setup_client_logging(paths)
    log = logging.getLogger("client.test")
    log.error("Refresh failed: refresh_token=secretvalue123")

    log_file = paths.logs_dir / LOG_FILE_NAME
    content = log_file.read_text(encoding="utf-8")
    assert "refresh_token=***" in content
    assert "secretvalue123" not in content


def test_secret_filter_unit_mask():
    """Прямой unit-тест SecretFilter._mask."""
    f = SecretFilter()
    assert f._mask("Bearer abc.def.ghi") == "Bearer ***"
    assert f._mask('"access_token": "xyz123"') == '"access_token": "***"'
    assert f._mask("refresh_token=foo-bar_baz.qux") == "refresh_token=***"
    # Без секретов — без изменений
    assert f._mask("normal log message") == "normal log message"


def test_noisy_loggers_set_to_warning(tmp_appdata):
    """requests/urllib3 на WARNING — не засоряют DEBUG."""
    from client.core.paths import AppPaths

    paths = AppPaths()
    paths.ensure()
    setup_client_logging(paths, level=logging.DEBUG)
    assert logging.getLogger("requests").level == logging.WARNING
    assert logging.getLogger("urllib3").level == logging.WARNING
