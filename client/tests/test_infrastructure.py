"""
Маркер-тест: проверка что Wave 0 fixtures работают.
Эти тесты должны проходить ДО реализации LocalStorage/SyncManager/AuthManager.
"""
import os
import requests


def test_tmp_appdata_isolates_path(tmp_appdata):
    """tmp_appdata подменяет APPDATA на tmp_path (изоляция от реальной AppData)."""
    assert os.environ["APPDATA"] == str(tmp_appdata)
    assert "ЛичныйЕженедельник" not in os.environ["APPDATA"]  # ещё не создана subdir


def test_mock_api_intercepts_request(mock_api, api_base):
    """mock_api перехватывает реальный requests.get — никаких живых HTTP в тестах."""
    mock_api.get(f"{api_base}/health", json={"status": "ok"}, status_code=200)
    resp = requests.get(f"{api_base}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_base_constant(api_base):
    """api_base указывает на production-домен (совпадает с AuthManager/SyncManager константами)."""
    assert api_base == "https://planner.heyda.ru/api"
