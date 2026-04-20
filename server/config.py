"""
Конфигурация сервера Личного Еженедельника.

Переменные читаются из environment (на VPS — из /etc/planner/planner.env через systemd EnvironmentFile).

Обязательные переменные (CONTEXT.md D-27):
- DATABASE_URL         — SQLite путь, e.g. sqlite+aiosqlite:////var/lib/planner/weekly_planner.db
- JWT_SECRET           — openssl rand -hex 32 для access-токенов
- JWT_REFRESH_SECRET   — openssl rand -hex 32 для refresh-токенов (отдельный от access)
- BOT_TOKEN            — токен @Jazzways_bot после /revoke (CONTEXT.md D-03)
- ALLOWED_USERNAMES    — comma-separated список Telegram usernames без @, lowercase

Опциональные (значения по умолчанию заданы здесь):
- HOST                 — 127.0.0.1 (за reverse-proxy, CONTEXT.md D-10)
- PORT                 — 8100 (CONTEXT.md D-10)
- ACCESS_TOKEN_TTL_SECONDS — 900 = 15 мин (D-12)
- REFRESH_TOKEN_TTL_SECONDS — 2592000 = 30 дней (D-13)
- AUTH_CODE_TTL_SECONDS — 300 = 5 мин (D-07)
- AUTH_CODE_LENGTH     — 6 цифр (D-06)
- APP_VERSION          — 0.1.0
- LOG_LEVEL            — INFO
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,  # В проде env читается systemd'ом через EnvironmentFile, не через .env
        env_file_encoding="utf-8",
        case_sensitive=False,  # DATABASE_URL == database_url — не принципиально
        extra="ignore",  # игнорировать незнакомые env vars (чтобы другие приложения на VPS не ломали)
    )

    # --- Обязательные ---
    database_url: str = Field(..., description="SQLAlchemy async URL — sqlite+aiosqlite:///...")
    jwt_secret: str = Field(..., min_length=32, description="Secret для access-токенов (openssl rand -hex 32)")
    jwt_refresh_secret: str = Field(..., min_length=32, description="Secret для refresh-токенов, отдельный от access")
    bot_token: str = Field(..., min_length=10, description="Telegram Bot token (после /revoke — CONTEXT.md D-03)")
    # Хранится как str в env (comma-separated), validator разбирает в list
    allowed_usernames_raw: str = Field(..., alias="ALLOWED_USERNAMES", description="Telegram usernames без @, в lowercase, comma-separated")

    # --- Опциональные с defaults (Claude discretion) ---
    host: str = Field(default="127.0.0.1", description="Слушаем за reverse-proxy — только localhost")
    port: int = Field(default=8100)

    access_token_ttl_seconds: int = Field(default=900, description="15 минут — CONTEXT.md D-12")
    refresh_token_ttl_seconds: int = Field(default=2_592_000, description="30 дней — CONTEXT.md D-13")
    auth_code_ttl_seconds: int = Field(default=300, description="5 минут — CONTEXT.md D-07")
    auth_code_length: int = Field(default=6, description="6 цифр — CONTEXT.md D-06")

    app_version: str = Field(default="0.1.0")
    log_level: str = Field(default="INFO")

    # JWT алгоритм фиксированный (CONTEXT.md Deferred: RS256 только в v2)
    jwt_algorithm: str = Field(default="HS256")

    @field_validator("allowed_usernames_raw", mode="before")
    @classmethod
    def validate_raw_not_empty(cls, v):
        """Быстрая проверка что строка не пустая (детальный парсинг в property)."""
        if isinstance(v, str) and not v.strip().replace(",", "").strip():
            raise ValueError("ALLOWED_USERNAMES не может быть пустым — нужен хотя бы 1 username")
        return v

    @property
    def allowed_usernames(self) -> list[str]:
        """
        ALLOWED_USERNAMES="Nikita_Heyyda, @vasya" → ["nikita_heyyda", "vasya"]
        - Убираем @ если есть
        - Lowercase
        - Strip пробелов
        - Отбрасываем пустые
        """
        parts = self.allowed_usernames_raw.split(",")
        result = []
        for p in parts:
            s = str(p).strip().lstrip("@").lower()
            if s:
                result.append(s)
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Кэшированный singleton — чтобы не парсить env vars на каждый вызов."""
    return Settings()


# Удобный shortcut для импорта: `from server.config import settings`
# Ленивый — создаётся при первом обращении
def __getattr__(name: str):
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module has no attribute {name!r}")
