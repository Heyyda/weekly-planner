"""
Общие pytest fixtures для серверных тестов.

Паттерн:
- `test_engine` — async SQLite in-memory engine, создаёт все таблицы через Base.metadata.create_all
- `db_session` — async-сессия SQLAlchemy для одного теста
- `client` — httpx.AsyncClient, привязан к FastAPI приложению через ASGITransport
- `mock_telegram_send` — патчит httpx POST к api.telegram.org (чтобы тесты не ходили в реальный Telegram API)
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


# Импорты ниже будут раскомментированы по мере появления кода в plans 02-06:
# from server.db.engine import Base, get_db
# from server.api.app import app


@pytest_asyncio.fixture
async def test_engine():
    """
    Async SQLite in-memory engine для тестов.

    PRAGMA WAL и busy_timeout не применяются в in-memory режиме (бессмысленно) —
    только foreign_keys=ON для консистентности с production.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    # Импорт Base и create_all будут добавлены в Plan 02, когда модели существуют:
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncSession:
    """Async-сессия SQLAlchemy для одного теста."""
    async_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """
    httpx.AsyncClient привязанный к FastAPI приложению через in-memory ASGI транспорт.

    В Plan 06 будет дополнен dependency_overrides для подмены get_db на test_engine.
    """
    # app будет импортирован в Plan 06 когда api.app существует:
    # from server.api.app import app
    # async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
    #     yield ac
    pytest.skip("Fixture будет активирован в Plan 06 когда FastAPI app.py существует")


@pytest.fixture
def mock_telegram_send(monkeypatch):
    """
    Патчит httpx.AsyncClient.post чтобы перехватить вызовы к api.telegram.org.

    В Plan 05 будет наполнен конкретной логикой записи sent-сообщений в list.
    """
    sent = []
    # Заглушка — конкретная логика добавится в Plan 05
    return sent
