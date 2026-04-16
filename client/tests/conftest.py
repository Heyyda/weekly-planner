"""
Shared pytest fixtures для client/tests/.

Fixtures:
- tmp_appdata: изолирует APPDATA в tmp_path (LocalStorage пишет в tmp)
- mock_api: requests_mock.Mocker для перехвата HTTP
- api_base: базовый URL API (константа)
"""
import os
from pathlib import Path

import pytest
import requests_mock as req_mock_module


API_BASE_URL = "https://planner.heyda.ru/api"


@pytest.fixture
def api_base() -> str:
    """Базовый URL API, используемый во всех client-тестах."""
    return API_BASE_URL


@pytest.fixture
def tmp_appdata(tmp_path: Path, monkeypatch) -> Path:
    """
    Подменяет переменную окружения APPDATA на tmp_path.
    LocalStorage и RotatingFileHandler будут писать в tmp_path/ЛичныйЕженедельник/.
    """
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # LOCALAPPDATA тоже устанавливаем (fallback в client/core/paths.py)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


@pytest.fixture
def mock_api():
    """
    requests_mock.Mocker для перехвата HTTP-вызовов.

    Использование:
        def test_sync(mock_api, api_base):
            mock_api.post(f"{api_base}/sync", json={"server_timestamp": "...", "changes": []})
            ... requests.post(f"{api_base}/sync") ...
    """
    with req_mock_module.Mocker() as m:
        yield m
