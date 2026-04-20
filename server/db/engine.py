"""
Async engine + session factory + PRAGMA-wiring для SQLite WAL.

SRV-03: WAL + busy_timeout=5000 + foreign_keys=ON + synchronous=NORMAL
применяются на КАЖДОМ новом connection через event hook.

Использование:
    # В FastAPI route:
    from server.db.engine import get_db
    @router.post("/foo")
    async def foo(db: AsyncSession = Depends(get_db)): ...
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _create_engine() -> AsyncEngine:
    """
    Создать async engine из settings.database_url.

    Вынесено в функцию чтобы (а) можно было пересоздавать в тестах,
    (б) избегать импорт-тайм побочных эффектов при отсутствии env vars.
    """
    from server.config import get_settings
    settings = get_settings()
    eng = create_async_engine(
        settings.database_url,
        echo=False,
        # SQLite-specific — нужно для async driver в FastAPI worker
        # connect_args пустой по умолчанию для aiosqlite; check_same_thread не нужен
    )
    _attach_pragma_listener(eng)
    return eng


def _attach_pragma_listener(eng: AsyncEngine) -> None:
    """
    Подписаться на event "connect" у underlying sync engine.

    SQLAlchemy async engine wraps sync engine внутри. Event hook для
    установки PRAGMAs вешается на sync_engine, срабатывает при каждом
    открытии нового SQLite connection.

    Важно для SRV-03: PRAGMA journal_mode=WAL persistent для файловой БД —
    один раз установил, дальше всегда WAL. Но busy_timeout — per-connection,
    нужно ставить на каждом connect.
    """
    @event.listens_for(eng.sync_engine, "connect")
    def set_sqlite_pragmas(dbapi_conn, connection_record):  # noqa: ARG001
        cursor = dbapi_conn.cursor()
        try:
            # WAL — параллельные readers + 1 writer
            cursor.execute("PRAGMA journal_mode=WAL")
            # Ждать до 5 секунд если другой writer держит lock — вместо мгновенной ошибки
            cursor.execute("PRAGMA busy_timeout=5000")
            # Включить ForeignKey constraints (SQLite по умолчанию игнорирует FK!)
            cursor.execute("PRAGMA foreign_keys=ON")
            # NORMAL — хороший tradeoff между durability и скоростью (CONTEXT.md D-20)
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


def _get_engine() -> AsyncEngine:
    """Ленивый singleton engine — создаётся при первом обращении."""
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = _create_engine()
    return _engine_singleton


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Ленивый singleton session factory."""
    global _session_factory_singleton
    if _session_factory_singleton is None:
        _session_factory_singleton = async_sessionmaker(
            _get_engine(),
            expire_on_commit=False,  # объекты остаются доступны после commit — важно для FastAPI response'ов
            class_=AsyncSession,
        )
    return _session_factory_singleton


# Внутренние синглтоны (None до первого использования)
_engine_singleton: AsyncEngine | None = None
_session_factory_singleton: async_sessionmaker[AsyncSession] | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: async session, закрывается после response.

    Usage:
        @router.post("/foo")
        async def foo(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
    """
    async with _get_session_factory()() as session:
        yield session


# Публичные имена для обратной совместимости с кодом который делает:
#   from server.db.engine import engine, AsyncSessionLocal
def __getattr__(name: str):
    if name == "engine":
        return _get_engine()
    if name == "AsyncSessionLocal":
        return _get_session_factory()
    raise AttributeError(f"module 'server.db.engine' has no attribute {name!r}")


# Для тестов: функция пересоздания engine (когда monkeypatched settings)
def recreate_engine_for_test() -> AsyncEngine:
    """
    Используется в тестах через conftest override после monkeypatch settings.

    Возвращает новый engine; module-level `engine` при этом НЕ меняется —
    тест должен сам использовать возвращённый engine или через dependency_overrides.
    """
    return _create_engine()
