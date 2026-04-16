"""
Unit-тесты client/core/api_client.py — wire format, 401 retry, backoff.

11 тестов:
  1. happy path — 200, payload, backoff reset
  2. wire format — {since, changes: [{op, task_id, ...}]}
  3. bearer header присутствует
  4. 401 → refresh → retry 200
  5. 401 → refresh raises AuthExpiredError → auth_expired()
  6. 500 → backoff bump
  7. network error → backoff bump
  8. 400 → client_error, backoff НЕ растёт
  9. backoff cap at 60s
  10. reset backoff on success
  11. idempotent CREATE — task_id сохраняется при повторной отправке (SYNC-06)
"""

import pytest
import requests

from client.core import config
from client.core.api_client import ApiResult, SyncApiClient
from client.core.auth import AuthExpiredError, AuthManager
from client.core.models import TaskChange


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_with_token():
    """AuthManager с уже установленным access_token (минуем verify_code)."""
    m = AuthManager()
    m.access_token = "test-jwt-token"
    m._refresh_token = "test-refresh-token"
    return m


@pytest.fixture
def client(auth_with_token):
    """SyncApiClient готовый к использованию."""
    return SyncApiClient(auth_with_token)


def _ok_sync_response() -> dict:
    """Стандартный успешный ответ /api/sync."""
    return {
        "server_timestamp": "2026-04-15T10:00:00.000000Z",
        "changes": [],
    }


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


def test_post_sync_happy_path(client, mock_api, api_base):
    """200 → ok=True, payload содержит server_timestamp; backoff сброшен."""
    mock_api.post(f"{api_base}/sync", json=_ok_sync_response(), status_code=200)
    result = client.post_sync(since=None, changes=[])

    assert result.ok is True
    assert result.status == 200
    assert result.payload is not None
    assert "server_timestamp" in result.payload
    assert result.payload["server_timestamp"] == "2026-04-15T10:00:00.000000Z"
    # Backoff сброшен после успеха
    assert client.consecutive_errors == 0
    assert client.current_backoff == config.BACKOFF_BASE


def test_post_sync_wire_format(client, mock_api, api_base):
    """Request body содержит {since, changes:[{op, task_id, ...}]} — wire format."""
    captured: dict = {}

    def matcher(request, _ctx):
        captured["body"] = request.json()
        captured["headers"] = dict(request.headers)
        return _ok_sync_response()

    mock_api.post(f"{api_base}/sync", json=matcher, status_code=200)

    changes = [
        TaskChange(op="create", task_id="t-uuid-1", text="купить молоко",
                   day="2026-04-14", done=False, position=0),
        TaskChange(op="update", task_id="t-uuid-2", done=True),
        TaskChange(op="delete", task_id="t-uuid-3"),
    ]
    client.post_sync(since="2026-04-14T00:00:00Z", changes=changes)

    body = captured["body"]
    assert body["since"] == "2026-04-14T00:00:00Z"
    assert len(body["changes"]) == 3

    # CREATE — полный набор ненулевых полей
    create_change = body["changes"][0]
    assert create_change["op"] == "create"
    assert create_change["task_id"] == "t-uuid-1"
    assert create_change["text"] == "купить молоко"
    assert create_change["day"] == "2026-04-14"

    # UPDATE — partial (только done=True, task_id и op)
    update_change = body["changes"][1]
    assert update_change == {"op": "update", "task_id": "t-uuid-2", "done": True}

    # DELETE — минимум (op + task_id)
    delete_change = body["changes"][2]
    assert delete_change == {"op": "delete", "task_id": "t-uuid-3"}


def test_post_sync_includes_bearer(client, mock_api, api_base):
    """Authorization: Bearer <token> присутствует в каждом запросе."""
    captured: dict = {}

    def matcher(request, _ctx):
        captured["auth"] = request.headers.get("Authorization", "")
        return _ok_sync_response()

    mock_api.post(f"{api_base}/sync", json=matcher, status_code=200)
    client.post_sync(since=None, changes=[])

    assert captured["auth"] == "Bearer test-jwt-token"


def test_post_sync_401_then_refresh_then_200(client, mock_api, api_base, monkeypatch):
    """401 → refresh_access() → новый токен → второй запрос 200 → ok=True."""

    def fake_refresh():
        """Имитирует успешный refresh: обновляет access_token в памяти."""
        client._auth.access_token = "rotated-jwt-token"
        return True

    monkeypatch.setattr(client._auth, "refresh_access", fake_refresh)

    # Первый POST → 401, второй → 200
    mock_api.post(f"{api_base}/sync", [
        {"status_code": 401, "json": {"error": {"code": "INVALID", "message": "expired"}}},
        {"status_code": 200, "json": _ok_sync_response()},
    ])

    result = client.post_sync(since=None, changes=[])

    assert result.ok is True
    assert client._auth.access_token == "rotated-jwt-token"


def test_post_sync_401_refresh_expired_returns_auth_expired(
    client, mock_api, api_base, monkeypatch
):
    """refresh_access() raises AuthExpiredError → ApiResult.auth_expired()."""

    def fake_refresh():
        raise AuthExpiredError("Сессия истекла")

    monkeypatch.setattr(client._auth, "refresh_access", fake_refresh)
    mock_api.post(
        f"{api_base}/sync",
        status_code=401,
        json={"error": {"code": "INVALID", "message": "expired"}},
    )

    result = client.post_sync(since=None, changes=[])

    assert result.ok is False
    assert result.error_kind == "auth_expired"
    assert result.status == 401


def test_post_sync_500_bumps_backoff(client, mock_api, api_base):
    """500 → error_kind='server', retry_after >= 2*BACKOFF_BASE, consecutive_errors=1."""
    mock_api.post(f"{api_base}/sync", status_code=500, text="internal server error")

    result = client.post_sync(since=None, changes=[])

    assert result.ok is False
    assert result.error_kind == "server"
    assert result.status == 500
    assert result.retry_after is not None
    assert result.retry_after >= config.BACKOFF_BASE * 2  # хотя бы раз удвоилось
    assert client.consecutive_errors == 1


def test_post_sync_network_error_bumps_backoff(client, mock_api, api_base):
    """ConnectionError → error_kind='network', retry_after возвращён, backoff bump."""
    mock_api.post(f"{api_base}/sync", exc=requests.ConnectionError("нет сети"))

    result = client.post_sync(since=None, changes=[])

    assert result.ok is False
    assert result.error_kind == "network"
    assert result.retry_after is not None
    assert client.consecutive_errors == 1


def test_post_sync_400_client_error_no_backoff(client, mock_api, api_base):
    """400 → error_kind='client'; backoff НЕ растёт (баг клиента, retry бесполезен)."""
    mock_api.post(f"{api_base}/sync", status_code=400, text="bad request")

    result = client.post_sync(since=None, changes=[])

    assert result.ok is False
    assert result.error_kind == "client"
    assert result.status == 400
    # consecutive_errors НЕ увеличился — 4xx не backoff
    assert client.consecutive_errors == 0
    assert client.current_backoff == config.BACKOFF_BASE


def test_backoff_caps_at_60s(client, mock_api, api_base):
    """10+ ошибок 5xx подряд → backoff не превышает BACKOFF_CAP (60s). Покрывает D-13."""
    mock_api.post(f"{api_base}/sync", status_code=500)

    for _ in range(15):  # 2^15 >> 60 — точно превысили бы без cap
        client.post_sync(since=None, changes=[])

    assert client.current_backoff == config.BACKOFF_CAP


def test_reset_backoff_on_success(client, mock_api, api_base):
    """После нескольких ошибок + успешный ответ → backoff сбрасывается в BACKOFF_BASE."""
    mock_api.post(f"{api_base}/sync", [
        {"status_code": 500},
        {"status_code": 500},
        {"status_code": 200, "json": _ok_sync_response()},
    ])

    # Две ошибки — backoff растёт
    client.post_sync(since=None, changes=[])
    client.post_sync(since=None, changes=[])
    assert client.current_backoff > config.BACKOFF_BASE
    assert client.consecutive_errors == 2

    # Третья — успех → reset
    client.post_sync(since=None, changes=[])
    assert client.current_backoff == config.BACKOFF_BASE
    assert client.consecutive_errors == 0


def test_idempotent_create_preserves_uuid(client, mock_api, api_base):
    """
    SYNC-06: повторный CREATE с тем же task_id отправляет тот же UUID.

    Клиент НЕ генерирует новый UUID при ретрае — UUID сохраняется в TaskChange.task_id.
    Сервер принимает повторный CREATE идемпотентно (INSERT OR IGNORE → UPDATE).
    """
    captured_bodies: list[dict] = []

    def matcher(request, _ctx):
        captured_bodies.append(request.json())
        return _ok_sync_response()

    mock_api.post(f"{api_base}/sync", json=matcher, status_code=200)

    # Один и тот же TaskChange с фиксированным task_id — имитирует retry
    fixed_change = TaskChange(
        op="create",
        task_id="fixed-uuid-abc-123",
        text="задача для sync-06",
        day="2026-04-14",
        done=False,
        position=0,
    )

    client.post_sync(since=None, changes=[fixed_change])
    client.post_sync(since=None, changes=[fixed_change])

    # Оба запроса отправили тот же UUID (client-generated UUID — основа idempotency)
    assert len(captured_bodies) == 2
    assert captured_bodies[0]["changes"][0]["task_id"] == "fixed-uuid-abc-123"
    assert captured_bodies[1]["changes"][0]["task_id"] == "fixed-uuid-abc-123"
