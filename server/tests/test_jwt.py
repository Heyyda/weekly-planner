"""Тесты JWT create/decode — access + refresh с раздельными секретами."""
import time
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """Минимальный env для каждого теста в этом файле."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:ABC")
    monkeypatch.setenv("ALLOWED_USERNAMES", "test")
    from server.config import get_settings
    get_settings.cache_clear()


def test_access_token_roundtrip():
    from server.auth.jwt import create_access_token, decode_access_token
    token = create_access_token("user-123")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_refresh_token_has_session_id():
    from server.auth.jwt import create_refresh_token, decode_refresh_token
    token = create_refresh_token("user-123", "session-abc")
    payload = decode_refresh_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["sid"] == "session-abc"
    assert payload["type"] == "refresh"


def test_access_token_rejected_as_refresh():
    """Важная проверка D-14: access не работает как refresh и наоборот."""
    from server.auth.jwt import create_access_token, decode_refresh_token
    access = create_access_token("user-123")
    # Попытка декодировать access через refresh-decoder (разный секрет — сразу fail)
    assert decode_refresh_token(access) is None


def test_refresh_token_rejected_as_access():
    from server.auth.jwt import create_refresh_token, decode_access_token
    refresh = create_refresh_token("user-123", "sess-abc")
    assert decode_access_token(refresh) is None


def test_expired_token_returns_none():
    """Просроченный token → None, без exception (RESEARCH.md Pattern 2)."""
    from server.config import get_settings
    settings = get_settings()
    # Собираем token с exp в прошлом (low-level PyJWT)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    expired_token = pyjwt.encode(
        {"sub": "u", "type": "access", "iat": past, "exp": past},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    from server.auth.jwt import decode_access_token
    assert decode_access_token(expired_token) is None


def test_tampered_token_returns_none():
    from server.auth.jwt import create_access_token, decode_access_token
    token = create_access_token("user-123")
    # Подменить payload (decode вернёт invalid signature)
    parts = token.split(".")
    tampered = parts[0] + "." + "X" * len(parts[1]) + "." + parts[2]
    assert decode_access_token(tampered) is None


def test_hash_refresh_token_deterministic():
    from server.auth.jwt import hash_refresh_token
    h1 = hash_refresh_token("my-secret-token-abc")
    h2 = hash_refresh_token("my-secret-token-abc")
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex
    # Разные входы → разные выходы
    h3 = hash_refresh_token("different")
    assert h1 != h3


def test_access_token_ttl_matches_settings():
    from server.config import get_settings
    from server.auth.jwt import create_access_token, decode_access_token
    settings = get_settings()
    before = datetime.now(timezone.utc).timestamp()
    token = create_access_token("u")
    payload = decode_access_token(token)
    after = datetime.now(timezone.utc).timestamp()
    # exp должен быть в пределах [before + ttl, after + ttl]
    expected_min = before + settings.access_token_ttl_seconds - 2
    expected_max = after + settings.access_token_ttl_seconds + 2
    assert expected_min <= payload["exp"] <= expected_max
