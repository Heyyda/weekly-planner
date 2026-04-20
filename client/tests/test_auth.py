"""Unit-тесты client/core/auth.py — все exception paths и keyring interactions."""
import threading

import pytest
import requests

from client.core import config
from client.core.auth import (
    AuthError, AuthExpiredError, AuthInvalidCodeError,
    AuthManager, AuthNetworkError, AuthRateLimitError,
)


@pytest.fixture
def fake_keyring(monkeypatch):
    """Заменяет keyring на in-memory dict — изолирует тесты от реального credential store."""
    store: dict[tuple, str] = {}

    def get(service, name):
        return store.get((service, name))

    def set_pw(service, name, value):
        store[(service, name)] = value

    def delete(service, name):
        if (service, name) in store:
            del store[(service, name)]
        else:
            raise Exception("Not found")

    import keyring as kr_module
    monkeypatch.setattr(kr_module, "get_password", get)
    monkeypatch.setattr(kr_module, "set_password", set_pw)
    monkeypatch.setattr(kr_module, "delete_password", delete)
    return store


@pytest.fixture
def auth(fake_keyring):
    """AuthManager с пустым fake_keyring."""
    return AuthManager()


def test_request_code_happy(auth, mock_api, api_base):
    """200 response → request_id возвращается."""
    mock_api.post(
        f"{api_base}/auth/request-code",
        json={"request_id": "req-uuid-1", "expires_in": 300},
        status_code=200,
    )
    rid = auth.request_code(username="nikita", hostname="WORK-PC")
    assert rid == "req-uuid-1"
    assert auth.username == "nikita"


def test_request_code_rate_limit(auth, mock_api, api_base):
    """429 → AuthRateLimitError."""
    mock_api.post(f"{api_base}/auth/request-code", status_code=429,
                  json={"error": {"code": "RATE_LIMITED", "message": "wait"}})
    with pytest.raises(AuthRateLimitError):
        auth.request_code(username="nikita")


def test_request_code_network_error(auth, mock_api, api_base):
    """ConnectionError → AuthNetworkError."""
    mock_api.post(f"{api_base}/auth/request-code", exc=requests.ConnectionError("offline"))
    with pytest.raises(AuthNetworkError):
        auth.request_code(username="nikita")


def test_verify_code_happy_saves_to_keyring(auth, mock_api, api_base, fake_keyring):
    """200 → access_token в RAM, refresh+username в keyring."""
    auth.username = "nikita"  # set by request_code in real flow
    mock_api.post(
        f"{api_base}/auth/verify",
        json={
            "access_token": "jwt-access-1",
            "refresh_token": "rt-1",
            "expires_in": 900,
            "user_id": "user-uuid-1",
            "token_type": "bearer",
        },
        status_code=200,
    )
    ok = auth.verify_code(request_id="req-1", code="123456", device_name="WORK-PC")
    assert ok is True
    assert auth.get_access_token() == "jwt-access-1"
    assert auth.user_id == "user-uuid-1"
    # Keyring содержит refresh
    assert fake_keyring[(config.KEYRING_SERVICE, config.KEYRING_REFRESH_KEY)] == "rt-1"
    assert fake_keyring[(config.KEYRING_SERVICE, config.KEYRING_USERNAME_KEY)] == "nikita"
    # access_token НЕ должен быть в keyring (D-26)
    assert (config.KEYRING_SERVICE, "access_token") not in fake_keyring
    assert (config.KEYRING_SERVICE, "jwt") not in fake_keyring


def test_verify_code_invalid(auth, mock_api, api_base):
    """400 → AuthInvalidCodeError."""
    mock_api.post(
        f"{api_base}/auth/verify",
        status_code=400,
        json={"error": {"code": "INVALID_CODE", "message": "Неверный код"}},
    )
    with pytest.raises(AuthInvalidCodeError):
        auth.verify_code(request_id="req-1", code="000000")


def test_refresh_access_rotates_keyring(auth, mock_api, api_base, fake_keyring):
    """200 + новый refresh_token → ротация в keyring (D-13)."""
    auth._refresh_token = "rt-old"
    auth.username = "nikita"
    mock_api.post(
        f"{api_base}/auth/refresh",
        json={
            "access_token": "jwt-new",
            "refresh_token": "rt-new",
            "expires_in": 900,
            "token_type": "bearer",
        },
        status_code=200,
    )
    ok = auth.refresh_access()
    assert ok is True
    assert auth.get_access_token() == "jwt-new"
    # Ротация: keyring обновился
    assert fake_keyring[(config.KEYRING_SERVICE, config.KEYRING_REFRESH_KEY)] == "rt-new"


def test_refresh_access_401_raises_expired(auth, mock_api, api_base):
    """401 → AuthExpiredError + state cleared."""
    auth._refresh_token = "rt-old"
    auth.access_token = "old-access"
    mock_api.post(f"{api_base}/auth/refresh", status_code=401,
                  json={"error": {"code": "INVALID_REFRESH", "message": "expired"}})
    with pytest.raises(AuthExpiredError):
        auth.refresh_access()
    # state cleared
    assert auth.access_token is None
    assert auth._refresh_token is None


def test_refresh_access_network_error_returns_false(auth, mock_api, api_base):
    """ConnectionError → False (не raises — offline-tolerant)."""
    auth._refresh_token = "rt-1"
    mock_api.post(f"{api_base}/auth/refresh", exc=requests.ConnectionError("offline"))
    assert auth.refresh_access() is False


def test_load_saved_token_empty_keyring(auth):
    """Нет refresh в keyring → False."""
    assert auth.load_saved_token() is False


def test_load_saved_token_with_refresh(auth, mock_api, api_base, fake_keyring):
    """Refresh в keyring + сервер 200 → True."""
    fake_keyring[(config.KEYRING_SERVICE, config.KEYRING_REFRESH_KEY)] = "rt-saved"
    fake_keyring[(config.KEYRING_SERVICE, config.KEYRING_USERNAME_KEY)] = "nikita"
    mock_api.post(
        f"{api_base}/auth/refresh",
        json={
            "access_token": "jwt-restored",
            "refresh_token": "rt-rotated",
            "expires_in": 900,
            "token_type": "bearer",
        },
        status_code=200,
    )
    ok = auth.load_saved_token()
    assert ok is True
    assert auth.get_access_token() == "jwt-restored"
    assert auth.username == "nikita"


def test_load_saved_token_refresh_expired(auth, mock_api, api_base, fake_keyring):
    """Refresh в keyring но сервер 401 → False (а не raises)."""
    fake_keyring[(config.KEYRING_SERVICE, config.KEYRING_REFRESH_KEY)] = "rt-old"
    mock_api.post(f"{api_base}/auth/refresh", status_code=401,
                  json={"error": {"code": "INVALID_REFRESH", "message": "expired"}})
    assert auth.load_saved_token() is False


def test_logout_clears_keyring_and_state(auth, mock_api, api_base, fake_keyring):
    """logout удаляет keyring и сбрасывает self.*."""
    fake_keyring[(config.KEYRING_SERVICE, config.KEYRING_REFRESH_KEY)] = "rt"
    fake_keyring[(config.KEYRING_SERVICE, config.KEYRING_USERNAME_KEY)] = "nikita"
    auth.access_token = "jwt"
    auth._refresh_token = "rt"
    auth.username = "nikita"
    auth._user_id = "u-1"
    # logout пытается POST — мокаем 204
    mock_api.post(f"{api_base}/auth/logout", status_code=204)
    auth.logout()
    # state cleared
    assert auth.access_token is None
    assert auth._refresh_token is None
    assert auth.username is None
    assert auth._user_id is None
    # keyring пустой
    assert (config.KEYRING_SERVICE, config.KEYRING_REFRESH_KEY) not in fake_keyring
    assert (config.KEYRING_SERVICE, config.KEYRING_USERNAME_KEY) not in fake_keyring


def test_bearer_header_unauthenticated_raises(auth):
    """bearer_header() без access_token → AuthError."""
    with pytest.raises(AuthError):
        auth.bearer_header()


def test_bearer_header_with_token(auth):
    """bearer_header() с access_token возвращает Authorization."""
    auth.access_token = "jwt-1"
    h = auth.bearer_header()
    assert h == {"Authorization": "Bearer jwt-1"}


def test_get_access_token_thread_safe(auth):
    """50 параллельных read/write не падают и не дают неконсистентного состояния."""
    auth.access_token = "initial"
    errors = []

    def reader():
        for _ in range(100):
            try:
                _ = auth.get_access_token()
            except Exception as e:
                errors.append(e)

    def writer():
        for i in range(100):
            with auth._lock:
                auth.access_token = f"jwt-{i}"

    threads = [threading.Thread(target=reader) for _ in range(5)]
    threads += [threading.Thread(target=writer) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert errors == []
