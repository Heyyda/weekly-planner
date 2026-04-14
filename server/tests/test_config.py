"""Тесты Settings класса — парсинг env vars, defaults, валидация."""
import pytest
from pydantic import ValidationError


def _setup_minimal_env(monkeypatch, **overrides):
    """Установить минимальный valid env для Settings()."""
    defaults = {
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "JWT_SECRET": "a" * 32,
        "JWT_REFRESH_SECRET": "b" * 32,
        "BOT_TOKEN": "1234567890:ABC",
        "ALLOWED_USERNAMES": "nikita_heyyda",
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        monkeypatch.setenv(k, v)
    # Очистить lru_cache чтобы Settings перечитал env
    from server.config import get_settings
    get_settings.cache_clear()


def test_settings_loads_from_env(monkeypatch):
    _setup_minimal_env(monkeypatch)
    from server.config import get_settings
    s = get_settings()
    assert s.database_url == "sqlite+aiosqlite:///:memory:"
    assert s.jwt_secret == "a" * 32
    assert s.bot_token == "1234567890:ABC"
    assert s.allowed_usernames == ["nikita_heyyda"]


def test_allowed_usernames_parsed_comma_separated(monkeypatch):
    _setup_minimal_env(monkeypatch, ALLOWED_USERNAMES="nikita,vasya,petya")
    from server.config import get_settings
    s = get_settings()
    assert s.allowed_usernames == ["nikita", "vasya", "petya"]


def test_allowed_usernames_normalized_lowercase_no_at(monkeypatch):
    _setup_minimal_env(monkeypatch, ALLOWED_USERNAMES="@Nikita_Heyyda, VASYA , @petya")
    from server.config import get_settings
    s = get_settings()
    assert s.allowed_usernames == ["nikita_heyyda", "vasya", "petya"]


def test_defaults_for_ttl_and_lengths(monkeypatch):
    _setup_minimal_env(monkeypatch)
    from server.config import get_settings
    s = get_settings()
    assert s.access_token_ttl_seconds == 900  # 15 min — D-12
    assert s.refresh_token_ttl_seconds == 2_592_000  # 30 days — D-13
    assert s.auth_code_ttl_seconds == 300  # 5 min — D-07
    assert s.auth_code_length == 6  # D-06
    assert s.jwt_algorithm == "HS256"
    assert s.host == "127.0.0.1"
    assert s.port == 8100


def test_missing_jwt_secret_raises(monkeypatch):
    from server.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "b" * 32)
    monkeypatch.setenv("BOT_TOKEN", "1234567890:ABC")
    monkeypatch.setenv("ALLOWED_USERNAMES", "nikita")
    with pytest.raises(ValidationError):
        get_settings()


def test_empty_allowed_usernames_raises(monkeypatch):
    from server.config import get_settings
    get_settings.cache_clear()
    _setup_minimal_env(monkeypatch, ALLOWED_USERNAMES=" , , ")
    with pytest.raises(ValidationError):
        get_settings()
