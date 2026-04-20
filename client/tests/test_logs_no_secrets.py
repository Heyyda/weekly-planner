"""
D-29 verification: после полного auth+sync flow в client.log НЕТ:
  - access_token (jwt значения)
  - refresh_token значения
  - "Bearer XXX" (фактические заголовки)

Это страховка от регрессии — в логах AuthManager/SyncApiClient/SyncManager не должно
случайно появиться logger.error("token=%s", token) или аналогичное.

Тесты используют реальный setup_client_logging с RotatingFileHandler в tmp_path.
После каждого теста состояние логирования сбрасывается (reset_client_logging).
"""
from __future__ import annotations

import logging

import pytest

from client.core import AppPaths, config
from client.core.api_client import SyncApiClient
from client.core.auth import AuthManager
from client.core.logging_setup import reset_client_logging, setup_client_logging
from client.core.models import Task
from client.core.storage import LocalStorage
from client.core.sync import SyncManager


# Токены-маркеры: уникальные строки которых НЕ ДОЛЖНО быть в client.log
SECRET_ACCESS_TOKEN = "jwt-secret-access-token-eyJpYXQ"
SECRET_REFRESH_TOKEN = "rt-secret-refresh-token-XYZ123"


@pytest.fixture
def fake_keyring(monkeypatch):
    """In-memory keyring — изолирует от реального Windows Credential Manager."""
    store: dict[tuple, str] = {}
    import keyring as kr
    monkeypatch.setattr(kr, "get_password", lambda s, n: store.get((s, n)))
    monkeypatch.setattr(kr, "set_password", lambda s, n, v: store.__setitem__((s, n), v))

    def delete(s, n):
        if (s, n) in store:
            del store[(s, n)]

    monkeypatch.setattr(kr, "delete_password", delete)
    return store


@pytest.fixture(autouse=True)
def _reset_logging():
    """
    Сбрасывает состояние логирования до и после каждого теста.
    autouse=True — применяется ко всем тестам в файле.
    Гарантирует изоляцию: handlers от одного теста не влияют на следующий.
    """
    reset_client_logging()
    yield
    reset_client_logging()


def _flush_and_read_log(paths: AppPaths) -> str:
    """Флушить все handlers и прочитать содержимое client.log."""
    for h in logging.getLogger().handlers:
        try:
            h.flush()
        except Exception:
            pass
    log_file = paths.logs_dir / config.LOG_FILE_NAME
    if not log_file.exists():
        return ""
    return log_file.read_text(encoding="utf-8")


def test_no_jwt_in_log_after_full_flow(tmp_appdata, fake_keyring, mock_api, api_base):
    """
    D-29: после auth + sync (включая ошибки) — в client.log нет токенов.

    Проверяет что SecretFilter работает в реальном flow:
      1. setup_client_logging → RotatingFileHandler с SecretFilter
      2. AuthManager.request_code + verify_code → логи без токенов
      3. SyncManager._attempt_sync → логи без Bearer заголовков
    """
    # Инициализируем логирование в tmp_path
    paths = AppPaths()
    paths.ensure()
    setup_client_logging(paths, level=logging.DEBUG)

    # Mock auth endpoints
    mock_api.post(
        f"{api_base}/auth/request-code",
        json={"request_id": "rid-logsec-1", "expires_in": 300},
    )
    mock_api.post(
        f"{api_base}/auth/verify",
        json={
            "access_token": SECRET_ACCESS_TOKEN,
            "refresh_token": SECRET_REFRESH_TOKEN,
            "expires_in": 900,
            "user_id": "u-logsec-1",
            "token_type": "bearer",
        },
    )
    # Sync 200 OK
    mock_api.post(
        f"{api_base}/sync",
        json={"server_timestamp": "2026-04-15T10:00:00Z", "changes": []},
    )

    # Полный auth flow
    auth = AuthManager()
    rid = auth.request_code(username="nikita")
    auth.verify_code(request_id=rid, code="123456", device_name="WORK-PC")

    # Sync cycle с реальным логированием
    storage = LocalStorage(paths=paths)
    storage.init()
    api_client = SyncApiClient(auth)
    sync = SyncManager(storage, auth, api_client=api_client)
    t = Task.new(user_id="u-logsec-1", text="test task", day="2026-04-14")
    storage.add_task(t)
    sync._attempt_sync()

    # Читаем log файл
    content = _flush_and_read_log(paths)
    assert content, "client.log должен существовать и не быть пустым"

    # Главные assertions — токены не должны появиться в логах
    assert SECRET_ACCESS_TOKEN not in content, (
        f"access_token утёк в client.log!\n"
        f"Найдено в: {[line for line in content.splitlines() if SECRET_ACCESS_TOKEN in line]}"
    )
    assert SECRET_REFRESH_TOKEN not in content, (
        f"refresh_token утёк в client.log!\n"
        f"Найдено в: {[line for line in content.splitlines() if SECRET_REFRESH_TOKEN in line]}"
    )
    # Bearer заголовок с реальным токеном не должен появиться
    assert f"Bearer {SECRET_ACCESS_TOKEN}" not in content, \
        "Bearer + access_token утёк в client.log!"


def test_no_jwt_in_log_after_auth_failure(tmp_appdata, fake_keyring, mock_api, api_base):
    """
    D-29: даже при auth ошибках (verify 400 INVALID_CODE) — нет утечки в логах.

    verify_code логирует "400: INVALID_CODE" — это безопасно.
    Важно что не логируется сам код или токен (которого в этом случае нет).
    """
    paths = AppPaths()
    paths.ensure()
    setup_client_logging(paths, level=logging.DEBUG)

    mock_api.post(
        f"{api_base}/auth/request-code",
        json={"request_id": "rid-fail-1", "expires_in": 300},
    )
    mock_api.post(
        f"{api_base}/auth/verify",
        status_code=400,
        json={"error": {"code": "INVALID_CODE", "message": "Неверный или истёкший код"}},
    )

    auth = AuthManager()
    rid = auth.request_code(username="nikita")

    from client.core.auth import AuthInvalidCodeError
    with pytest.raises(AuthInvalidCodeError):
        auth.verify_code(request_id=rid, code="000000")

    content = _flush_and_read_log(paths)

    # В этом сценарии access_token не был выдан — проверяем что наш маркер не утёк
    assert SECRET_ACCESS_TOKEN not in content, \
        "SECRET_ACCESS_TOKEN не должен быть в логах (его вообще не было в ответе)"
    # rid может быть в логах — это не секрет
    # Ошибка INVALID_CODE должна быть залогирована (это нормально)
    # Важно: не токен, а только статус ошибки
