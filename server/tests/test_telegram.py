"""Тесты send_auth_code — через mock httpx.AsyncClient (не делаем реальные запросы)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "test-token-12345")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita")
    from server.config import get_settings
    get_settings.cache_clear()


def _make_mock_client(status_code: int = 200, json_body: dict | None = None, raise_exc: Exception | None = None):
    """Создать AsyncMock httpx-like client."""
    client = MagicMock(spec=httpx.AsyncClient)
    client.aclose = AsyncMock()

    if raise_exc is not None:
        client.post = AsyncMock(side_effect=raise_exc)
    else:
        response = MagicMock()
        response.status_code = status_code
        response.text = ""
        response.json = MagicMock(return_value=json_body or {"ok": True})
        client.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_send_returns_bot_not_started_if_chat_id_none():
    from server.auth.telegram import send_auth_code, TelegramSendError
    client = _make_mock_client()
    result = await send_auth_code(
        chat_id=None, code="123456", hostname="test-pc", msk_time_str="2026-04-14 10:00",
        client=client,
    )
    assert result == TelegramSendError.BOT_NOT_STARTED
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_send_posts_to_telegram_api_with_correct_url():
    from server.auth.telegram import send_auth_code, TelegramSendError
    client = _make_mock_client(status_code=200, json_body={"ok": True})
    result = await send_auth_code(
        chat_id=12345, code="654321", hostname="work-pc", msk_time_str="2026-04-14 14:23",
        client=client,
    )
    assert result == TelegramSendError.OK
    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert "api.telegram.org/bottest-token-12345/sendMessage" in args[0]


@pytest.mark.asyncio
async def test_send_text_contains_code_and_context():
    from server.auth.telegram import send_auth_code
    client = _make_mock_client(status_code=200, json_body={"ok": True})
    await send_auth_code(
        chat_id=12345, code="987654", hostname="my-laptop", msk_time_str="2026-04-14 14:23",
        client=client,
    )
    args, kwargs = client.post.call_args
    text = kwargs["json"]["text"]
    assert "987654" in text
    assert "my-laptop" in text
    assert "2026-04-14 14:23" in text
    assert "MSK" in text
    assert "5 минут" in text
    assert "игнорируй" in text
    assert "Личный Еженедельник" in text
    assert kwargs["json"]["parse_mode"] == "HTML"
    assert kwargs["json"]["chat_id"] == 12345


@pytest.mark.asyncio
async def test_send_api_error_on_400():
    from server.auth.telegram import send_auth_code, TelegramSendError
    client = _make_mock_client(status_code=400, json_body={"ok": False, "description": "chat not found"})
    result = await send_auth_code(
        chat_id=12345, code="000000", hostname="x", msk_time_str="t", client=client,
    )
    assert result == TelegramSendError.API_ERROR


@pytest.mark.asyncio
async def test_send_api_error_when_ok_false_in_body():
    from server.auth.telegram import send_auth_code, TelegramSendError
    client = _make_mock_client(status_code=200, json_body={"ok": False, "description": "error"})
    result = await send_auth_code(
        chat_id=12345, code="000000", hostname="x", msk_time_str="t", client=client,
    )
    assert result == TelegramSendError.API_ERROR


@pytest.mark.asyncio
async def test_send_network_error_on_request_error():
    from server.auth.telegram import send_auth_code, TelegramSendError
    client = _make_mock_client(raise_exc=httpx.RequestError("Connection refused"))
    result = await send_auth_code(
        chat_id=12345, code="000000", hostname="x", msk_time_str="t", client=client,
    )
    assert result == TelegramSendError.NETWORK_ERROR


@pytest.mark.asyncio
async def test_send_ok_on_200_with_ok_true():
    from server.auth.telegram import send_auth_code, TelegramSendError
    client = _make_mock_client(status_code=200, json_body={"ok": True, "result": {"message_id": 42}})
    result = await send_auth_code(
        chat_id=12345, code="000000", hostname="x", msk_time_str="t", client=client,
    )
    assert result == TelegramSendError.OK
