# Phase 1: Сервер и авторизация — Research

**Researched:** 2026-04-14
**Domain:** FastAPI + SQLite WAL + PyJWT + aiogram 3.x + systemd deployment
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Один бот `@Jazzways_bot` на весь проект. Фаза 1 — только отправка кодов.
- **D-02:** Имя бота не меняем. Семантика неважна для личного проекта.
- **D-03:** Bot-токен ревокнуть через `@BotFather /revoke` при первом деплое. Старый токен скомпрометирован.
- **D-04:** Токен хранится в `/etc/planner/planner.env` (EnvironmentFile, права 600). В репозиторий не попадает.
- **D-05:** Формат сообщения кода — расширенный (hostname, время MSK, срок, подсказка "если не ты").
- **D-06:** Длина кода: 6 цифр.
- **D-07:** Срок жизни кода: 5 минут.
- **D-08:** Код single-use — после `/auth/verify` помечается `used_at`.
- **D-09:** Rate limit: 1 запрос/мин на username, 5 запросов/час.
- **D-10:** URL клиента: `https://planner.heyda.ru/api/` через reverse-proxy → `127.0.0.1:8100`.
- **D-11:** Поддомен создаётся в плане Фазы 1 как отдельный deploy-таск.
- **D-12:** Access token TTL: 15 минут.
- **D-13:** Refresh token TTL: 30 дней, rolling refresh при активности.
- **D-14:** Refresh token в keyring + server-side `Session` таблице (revokable). Access — только в памяти.
- **D-15:** При logout удаляется `Session` на сервере — все refresh-токены устройства инвалидируются.
- **D-16:** Префикс `/api/` без `/v1/`.
- **D-17:** Эндпойнты: `/api/auth/{request-code,verify,refresh,logout,me}`, `/api/sync`, `/api/health`, `/api/version`.
- **D-18:** Ошибки: `{"error": {"code": "...", "message": "..."}}`.
- **D-19:** SQLite: `/var/lib/planner/weekly_planner.db`, owner `planner`, права 600.
- **D-20:** PRAGMA: `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`, `synchronous=NORMAL`.
- **D-21:** Таблицы Фазы 1: `users`, `auth_codes`, `sessions`, `tasks` (с `deleted_at` tombstone).
- **D-22:** Миграции через Alembic, первая миграция = стартовая схема.
- **D-23:** `planner-api.service` systemd unit, непривилегированный user `planner`, `Restart=always`.
- **D-24:** `planner-bot.service` — отдельный unit для aiogram long-polling.
- **D-25:** Reverse proxy: существующий Caddy/nginx, `planner.heyda.ru` → `127.0.0.1:8100`.
- **D-26:** Логирование: stdout/stderr → journalctl, JSON-формат.
- **D-27:** Секреты в `/etc/planner/planner.env`: `BOT_TOKEN`, `JWT_SECRET`, `JWT_REFRESH_SECRET`, `DATABASE_URL`, `ALLOWED_USERNAMES`.

### Claude's Discretion

- Конкретные библиотеки: `fastapi`, `sqlalchemy`, `alembic`, `pyjwt`, `aiogram`, `uvicorn`, `passlib[bcrypt]`
- Структура кода (subpackages vs flat files в `server/`)
- Точный формат systemd-юнитов
- Health-check endpoint поведение
- OpenAPI: автогенерится FastAPI, не переписывать вручную

### Deferred Ideas (OUT OF SCOPE)

- Rate limiting на `/api/sync` — Фаза 2+
- Multi-device named sessions UI — Фаза 2+
- OpenAPI auth — Фаза 6
- JWT RS256 — только если появятся внешние интеграции (v2)
- Allow-list → многопользовательская таблица — v2+
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | Запрос кода через Telegram (username → 6-значный код в Telegram DM) | aiogram 3.x `bot.send_message(chat_id, ...)` — требует предварительный `/start` от пользователя для получения chat_id |
| AUTH-02 | Ввод кода → JWT (access + refresh) | PyJWT `jwt.encode()` + DB-хранение хеша refresh-токена в `sessions` |
| AUTH-03 | JWT в keyring между запусками | Клиентская сторона: `keyring.set_password("weekly-planner", username, token)` — ASCII service name |
| AUTH-04 | Авторобновление access через refresh | `/api/auth/refresh` + rolling-refresh логика на сервере |
| AUTH-05 | Разлогин через tray (keyring + кеш) | `POST /api/auth/logout` → revoke session; клиент чистит keyring |
| SRV-01 | REST API `/auth/*` | FastAPI routers, Pydantic v2 схемы, dependency injection `Depends(get_current_user)` |
| SRV-02 | REST API `/sync` — delta sync с tombstones | `POST /sync` принимает `{since, changes:[]}`, возвращает `{server_timestamp, changes:[]}` |
| SRV-03 | SQLite WAL + busy_timeout=5000 | `event.listens_for(engine.sync_engine, "connect")` + 4 PRAGMA |
| SRV-04 | Модели: User, Task (UUID, deleted_at, updated_at), AuthCode, Session | SQLAlchemy 2.x declarative + Alembic первая миграция |
| SRV-05 | FastAPI на VPS как systemd unit рядом с E-bot | systemd EnvironmentFile pattern, uvicorn `--workers 1` |
| SRV-06 | Согласованные timestamps (server-side updated_at) | `server_default=func.now()`, `onupdate=func.now()` в SQLAlchemy; клиент никогда не передаёт updated_at |
</phase_requirements>

---

## Summary

Фаза 1 строит весь серверный фундамент: FastAPI + SQLite (WAL) + Telegram-based JWT авторизация + systemd deployment. Стек полностью определён в CONTEXT.md и research/STACK.md — никаких альтернатив не рассматриваем.

Главные технические сложности: (1) aiogram 3.x и FastAPI должны работать как **два отдельных процесса** (не в одном event loop — иначе блокировка long-poll), (2) существующий скелет `server/auth.py` использует заброшенный `python-jose` — требует замены на `PyJWT`, (3) codes хранятся в памяти (`_pending_codes` dict) — в Фазе 1 переносим в БД (`auth_codes` таблица), (4) конфиг `config.py` использует переменные типа `PLANNER_JWT_SECRET` — CONTEXT.md решил использовать другие имена (`JWT_SECRET`, `BOT_TOKEN` и т.д.) в `planner.env`.

**Первичная рекомендация:** Реализовать сервер как плоский `server/` пакет (не дробить на subpackages) — достаточно 4-5 файлов для минимума Фазы 1. Бот — в отдельном `server/bot.py` (отдельный process).

---

## Standard Stack

### Core (Server)

| Библиотека | Версия | Назначение | Почему стандарт |
|------------|--------|------------|-----------------|
| FastAPI | >=0.115.0 (latest 0.135.3, Apr 2026) | REST API framework | Async-native, Pydantic v2, auto-OpenAPI |
| Uvicorn | >=0.30.0 | ASGI сервер | Стандартный companion FastAPI |
| SQLAlchemy | >=2.0.30 (latest 2.0.49, Apr 2026) | ORM + WAL pragma | Async поддержка через aiosqlite |
| aiosqlite | >=0.20.0 | Async SQLite драйвер | Нужен для SQLAlchemy async engine |
| PyJWT | >=2.9.0 (latest 2.12.1, Mar 2026) | JWT encode/decode | Замена заброшенного python-jose |
| passlib[bcrypt] | >=1.7.4 | Хеширование кодов в DB | bcrypt для `auth_codes.code_hash` |
| aiogram | >=3.15.0 (latest 3.27.0, Apr 2026) | Telegram bot | Async-native, отдельный process |
| python-dotenv | >=1.0.0 | Загрузка .env | Простой стандарт для env vars |
| alembic | >=1.13.0 | DB миграции | Стандарт с SQLAlchemy |

### Supporting

| Библиотека | Версия | Назначение | Когда использовать |
|------------|--------|------------|-------------------|
| slowapi | >=0.1.9 | Rate limiting | `/api/auth/request-code` — 1/мин, 5/час |
| pydantic-settings | >=2.0.0 | Config из env | Типизированный config через pydantic BaseSettings |

### Alternatives Considered

| Вместо | Можно | Tradeoff |
|--------|-------|----------|
| aiosqlite (async) | sync SQLAlchemy + run_in_executor | Sync проще, но блокирует event loop под нагрузкой. Для single-user окей, но async — правильная привычка |
| slowapi | Кастомный middleware | slowapi — 5 строк кода; кастомный — 50+ строк |
| pydantic-settings | os.environ.get() напрямую | Текущий config.py уже использует os.environ; pydantic-settings добавляет типизацию и валидацию |

**Установка (server):**
```bash
pip install fastapi>=0.115.0 uvicorn[standard]>=0.30.0 \
    sqlalchemy>=2.0.30 aiosqlite>=0.20.0 \
    PyJWT>=2.9.0 passlib[bcrypt]>=1.7.4 \
    aiogram>=3.15.0 python-dotenv>=1.0.0 \
    alembic>=1.13.0 slowapi>=0.1.9
```

---

## Architecture Patterns

### Recommended Project Structure (Фаза 1)

```
server/
├── __init__.py
├── api.py            # FastAPI app, роуты через include_router
├── auth.py           # JWT create/decode, get_current_user Depends
├── db.py             # SQLAlchemy async engine + WAL pragma + модели
├── models.py         # Pydantic v2 request/response схемы
├── config.py         # pydantic-settings Config (или os.environ)
├── bot.py            # aiogram Bot + Dispatcher, long-polling entry
└── requirements.txt  # серверные зависимости (отдельно от клиента)
```

**Почему плоская структура (не subpackages):** Фаза 1 создаёт ~7 эндпойнтов. Папки `routes/`, `services/` добавляют смысл только при 15+ эндпойнтах. Плоская структура проще читать и рефакторить в Фазе 5 (когда бот добавит команды). Архитектурный research (`ARCHITECTURE.md`) уже предусматривает это расширение.

### Pattern 1: SQLAlchemy Async Engine + WAL Pragma

**Что:** Async SQLAlchemy engine с aiosqlite, PRAGMA применяются через event hook на каждом новом соединении.

**Когда:** При инициализации `db.py` — до первого запроса.

```python
# server/db.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:////var/lib/planner/weekly_planner.db"
engine = create_async_engine(DATABASE_URL, echo=False)

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# FastAPI dependency
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

**Источник:** SQLAlchemy SQLite dialect docs (HIGH confidence)

### Pattern 2: PyJWT — Access + Refresh Tokens

**Что:** Два раздельных секрета для access и refresh токенов. Access — 15 мин, payload включает `type: "access"`. Refresh — 30 дней, хранится хеш в `sessions`.

**КРИТИЧНО:** Существующий `server/auth.py` использует `from jose import jwt` — НУЖНО ЗАМЕНИТЬ на `import jwt` (PyJWT). Интерфейс похожий, но разный: PyJWT возвращает строку напрямую (не bytes).

```python
# server/auth.py — НОВАЯ версия
import jwt
from datetime import datetime, timedelta, timezone
from server.config import JWT_SECRET, JWT_REFRESH_SECRET

ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = 15
REFRESH_EXPIRE_DAYS = 30

def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def create_refresh_token(user_id: str, session_id: str) -> str:
    payload = {
        "sub": user_id,
        "sid": session_id,  # session ID для revocation
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=ALGORITHM)

def decode_token(token: str, token_type: str = "access") -> dict | None:
    secret = JWT_SECRET if token_type == "access" else JWT_REFRESH_SECRET
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except jwt.PyJWTError:
        return None
```

**Важно:** `datetime.now(timezone.utc)` вместо `datetime.utcnow()` — deprecated в Python 3.12.

**Источник:** PyJWT 2.12.1 docs, fastapi PR #11589 (HIGH confidence)

### Pattern 3: FastAPI Dependency Injection для Auth

**Что:** `get_current_user` как FastAPI Depends — извлекает Bearer token из заголовка, декодирует, возвращает `User` объект.

```python
# server/auth.py — продолжение
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from server.db import get_db

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials
    payload = decode_token(token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Токен недействителен или истёк"}}
        )
    user = await get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail={"error": {"code": "USER_NOT_FOUND", "message": ""}})
    return user
```

**Источник:** FastAPI Security docs (HIGH confidence)

### Pattern 4: aiogram 3.x — Отдельный Процесс

**Что:** Бот запускается как **отдельный процесс** (`planner-bot.service`), не внутри FastAPI event loop. Это ключевое архитектурное решение.

**Почему отдельный процесс:** aiogram 3.x long-polling использует `asyncio.run()` внутри, что конфликтует с уже запущенным event loop FastAPI/uvicorn. Запуск в одном процессе требует сложного lifecycle управления через FastAPI lifespan + asyncio.TaskGroup. Для personal-use проекта отдельный process — надёжнее.

**Взаимодействие FastAPI → Бот:**
- FastAPI записывает pending message в `auth_codes` таблицу с флагом `bot_notify=True`
- Бот опрашивает таблицу каждые 500ms (или DB-polling через NOTIFY-like механизм)
- **Проще:** FastAPI напрямую вызывает Telegram API через `httpx` (без aiogram) для отправки кода — 3 строки кода

**РЕКОМЕНДАЦИЯ для Фазы 1:** FastAPI отправляет код напрямую через Telegram Bot API (HTTP POST), без aiogram. aiogram понадобится в Фазе 5 для команд бота. Это упрощает Фазу 1 значительно.

```python
# server/telegram.py — прямой HTTP вызов без aiogram
import httpx
from server.config import BOT_TOKEN

async def send_auth_code(chat_id: int, code: str, hostname: str, msk_time: str) -> bool:
    """Отправить 6-значный код через Telegram Bot API."""
    text = (
        f"🔐 Запрошен вход в Личный Еженедельник\n\n"
        f"Код: <b>{code}</b>\n"
        f"Устройство: {hostname}\n"
        f"Время: {msk_time} MSK\n"
        f"Срок: 5 минут\n\n"
        f"Если это не ты — игнорируй это сообщение."
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=5.0,
        )
    return resp.status_code == 200
```

**Источник:** Telegram Bot API docs (HIGH confidence)

### Pattern 5: Telegram Auth Flow — Критическая Проблема с chat_id

**Проблема:** Бот может отправить сообщение только по `chat_id` (числовой ID), не по `@username`. Пользователь должен **сначала написать боту `/start`**, чтобы бот узнал его `chat_id`.

**Поток:**
1. Пользователь запускает приложение впервые
2. Клиент показывает инструкцию: "Напишите `/start` боту `@Jazzways_bot` в Telegram"
3. Бот получает `/start`, сохраняет `telegram_chat_id` для `telegram_username` в `users`
4. Пользователь возвращается в клиент, вводит username → запрашивает код
5. Сервер находит `chat_id` для этого username → отправляет код

**Если пользователь не написал `/start`:** `users.telegram_chat_id IS NULL` → сервер возвращает специальную ошибку:
```json
{"error": {"code": "BOT_NOT_STARTED", "message": "Напишите /start боту @Jazzways_bot в Telegram"}}
```

**`planner-bot.service` в Фазе 1** нужен именно для этого — получить `/start` и сохранить `chat_id`. Без него вся авторизация невозможна.

**Источник:** Telegram Bot API docs + aiogram 3.x docs (HIGH confidence)

### Pattern 6: Auth Code Rate Limiting с slowapi

**Что:** slowapi — thin wrapper над limits library для FastAPI.

```python
# server/api.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

limiter = Limiter(key_func=lambda request: request.json().get("username", get_remote_address(request)))
app = FastAPI(...)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/auth/request-code")
@limiter.limit("1/minute;5/hour")
async def request_code(request: Request, body: RequestCodeIn, db: AsyncSession = Depends(get_db)):
    ...
```

**Источник:** slowapi docs (MEDIUM confidence — нужно проверить что `key_func` может быть async для чтения body)

**Альтернатива если slowapi не поддерживает async key_func:** Rate limit по IP (get_remote_address) — для personal-use приемлемо.

### Pattern 7: Alembic — Инициализация и Первая Миграция

**Что:** Alembic хранит миграции в `server/migrations/`.

```bash
# Один раз при инициализации
cd server
alembic init migrations
# Настроить migrations/env.py — указать SQLAlchemy URL и Base.metadata
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**env.py** должен импортировать все модели перед `target_metadata = Base.metadata`:
```python
# migrations/env.py
from server.db import Base
import server.db  # импорт нужен чтобы модели зарегистрировались на Base
target_metadata = Base.metadata
```

**Источник:** Alembic docs (HIGH confidence)

### Pattern 8: systemd Unit — FastAPI + Uvicorn

```ini
# /etc/systemd/system/planner-api.service
[Unit]
Description=Личный Еженедельник API
After=network.target
Wants=network.target

[Service]
Type=simple
User=planner
Group=planner
WorkingDirectory=/opt/planner
EnvironmentFile=/etc/planner/planner.env
ExecStart=/opt/planner/venv/bin/uvicorn server.api:app \
    --host 127.0.0.1 \
    --port 8100 \
    --workers 1 \
    --log-config /opt/planner/uvicorn-log.json
Restart=always
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=planner-api
ReadWritePaths=/var/lib/planner
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/planner-bot.service
[Unit]
Description=Личный Еженедельник Telegram Bot
After=network.target planner-api.service
Wants=network.target

[Service]
Type=simple
User=planner
Group=planner
WorkingDirectory=/opt/planner
EnvironmentFile=/etc/planner/planner.env
ExecStart=/opt/planner/venv/bin/python -m server.bot
Restart=always
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=planner-bot

[Install]
WantedBy=multi-user.target
```

**Источник:** systemd docs + паттерн из E-bot inference (MEDIUM confidence — E-bot на VPS, но его unit-файл недоступен)

### Pattern 9: Reverse Proxy (Caddy)

**Исследование E-bot:** E-bot использует `WEBHOOK_URL = "https://heyda.ru/webhook/search"` — значит на VPS уже настроен обратный прокси для `heyda.ru`. Скорее всего Caddy (автоматический TLS). Новый поддомен добавляется в Caddyfile:

```
# /etc/caddy/Caddyfile — добавить блок
planner.heyda.ru {
    reverse_proxy 127.0.0.1:8100
}
```

**Если nginx:** `nginx -t && systemctl reload nginx` после добавления конфига.

**DNS:** Нужна A-запись или CNAME `planner.heyda.ru` → IP VPS (109.94.211.29). Для Caddy TLS выдастся автоматически через Let's Encrypt.

**Confidence:** MEDIUM — точный тип прокси на VPS неизвестен. Плановик должен добавить таск "определить reverse proxy тип" как первый деплой-шаг.

### Pattern 10: `/api/sync` — Минимальная реализация для Фазы 1

SRV-02 требует `/sync`. В Фазе 1 реализуем **только серверную часть** (API принимает изменения и сохраняет в DB). Клиент будет использовать это в Фазе 2. Структура:

```python
# POST /api/sync
# Вход: {"since": "ISO datetime or null", "changes": [...]}
# Выход: {"server_timestamp": "ISO", "changes": [...tasks since `since`]}

async def handle_sync(body: SyncRequest, user: User = Depends(get_current_user), db = Depends(get_db)):
    # 1. Применить changes (upsert tasks, tombstones)
    # 2. Вернуть delta: tasks WHERE user_id=? AND updated_at > since
    # 3. server_timestamp = datetime.now(UTC).isoformat()
```

### Anti-Patterns to Avoid

- **Хранить коды в памяти (`_pending_codes` dict):** Текущий скелет это делает — при рестарте сервера все pending коды теряются. Код авторизации в процессе — пользователь не может войти. Использовать `auth_codes` таблицу с `expires_at`.
- **Использовать `datetime.utcnow()`:** Deprecated в Python 3.12+. Использовать `datetime.now(timezone.utc)`.
- **`python-jose` импорт:** Текущий `server/auth.py` строка 16: `from jose import jwt, JWTError` — заменить на `import jwt` + `jwt.PyJWTError`.
- **Sync SQLAlchemy engine на async сервере:** `create_engine()` вместо `create_async_engine()` блокирует event loop.
- **JWT_ALGORITHM как строка без отдельного refresh secret:** Текущий скелет использует один `JWT_SECRET` для access и refresh — добавить `JWT_REFRESH_SECRET` отдельный.
- **env var имена:** Текущий скелет (`PLANNER_JWT_SECRET`) vs CONTEXT.md (`JWT_SECRET` в `planner.env`) — выбрать одно (следовать CONTEXT.md: без PLANNER_ prefix в .env файле, но с prefix в config.py если нужна совместимость).

---

## Don't Hand-Roll

| Проблема | Не строить | Использовать | Почему |
|----------|-----------|--------------|--------|
| JWT encode/decode | Кастомный HMAC | PyJWT 2.12.1 | Корректный exp/iat, алгоритмы, leeway |
| Rate limiting | In-memory счётчик | slowapi | Thread-safe, per-key buckets, декоратор |
| Хеширование кодов | MD5/SHA без соли | passlib[bcrypt] | bcrypt автоматически солит, устойчив к rainbow tables |
| DB миграции | `CREATE TABLE IF NOT EXISTS` в коде | alembic | Версионирование, rollback, autogenerate |
| Reverse proxy TLS | Кастомный SSL в Python | Caddy/nginx | Let's Encrypt, HTTP/2, connection pooling |
| Pydantic validation | Кастомные if/else проверки | Pydantic v2 (встроен в FastAPI) | Типизированные ошибки, auto-OpenAPI |

**Ключевой инсайт:** Хеширование auth-кода в БД через passlib — не очевидная, но обязательная деталь. 6-значный код с 5-мин TTL имеет низкую энтропию; если БД утечёт — голый код тривиально брутфорсится. bcrypt делает брутфорс практически невозможным даже для 6-значного числа.

---

## Common Pitfalls

### Pitfall 1: `_pending_codes` dict при рестарте
**Что идёт не так:** Сервер перезапускается (deploy, systemd restart), пользователь ввёл username и ждёт кода — код потерян, нужно повторно запрашивать. Тихий сбой без объяснений.
**Почему:** Память процесса не persistent.
**Как избежать:** Хранить коды в `auth_codes` таблице с `expires_at`. Сервер при старте просто продолжает работать со старыми не-истёкшими кодами.
**Признаки:** "Код не пришёл" или "Код неверный" сразу после deploy.

### Pitfall 2: Пользователь не написал `/start` боту
**Что идёт не так:** `POST /auth/request-code` с правильным username, но `users.telegram_chat_id IS NULL` → нельзя отправить код → ошибка.
**Почему:** Telegram API не поддерживает отправку по username без предварительного `/start`.
**Как избежать:** Клиент при первом запуске показывает шаг "Напишите /start боту @Jazzways_bot". Сервер возвращает специальный код ошибки `BOT_NOT_STARTED` (не generic 500).
**Признаки:** "Код не приходит" несмотря на правильный username.

### Pitfall 3: Race condition при refresh token rotation
**Что идёт не так:** Клиент с двух устройств одновременно refresh — первый получает новый access, второй invalidates первый refresh, первое устройство не может использовать новый refresh.
**Почему:** Rolling refresh revokes старый refresh-токен при использовании.
**Как избежать:** Для personal single-device use случай редкий. Решение: `sessions.last_used_at` — если два refresh в течение 5 секунд, оба принимаются (grace window). Для Фазы 1: простой подход — revoke старый, выдать новый, предупредить в документации.
**Признаки:** Пользователь видит экран логина неожиданно на одном из устройств.

### Pitfall 4: SQLite busy_timeout без WAL
**Что идёт не так:** FastAPI API пишет задачу, одновременно Telegram бот пишет chat_id — `OperationalError: database is locked`.
**Почему:** SQLite без WAL допускает только одну транзакцию одновременно.
**Как избежать:** PRAGMA `journal_mode=WAL` + `busy_timeout=5000` применяются НЕМЕДЛЕННО при каждом connect через SQLAlchemy event hook (не через одноразовый скрипт).
**Признаки:** 5xx ошибки сервера при параллельных запросах; "database is locked" в journalctl.

### Pitfall 5: Alembic async engine
**Что идёт не так:** `alembic upgrade head` падает с ошибкой если `env.py` настроен на sync URL, а `db.py` создаёт async engine.
**Почему:** Alembic использует sync connections для миграций; URL должен быть `sqlite:///...` (без `+aiosqlite`).
**Как избежать:** В `env.py` использовать отдельный sync URL для Alembic; в приложении — async URL. Или использовать `alembic.runtime.environment.EnvironmentContext.configure(connection=...)` с sync connection.
```python
# migrations/env.py
SYNC_URL = DATABASE_URL.replace("+aiosqlite", "")
```
**Признаки:** `alembic upgrade head` ошибка про event loop или async dialect.

### Pitfall 6: slowapi key_func читает request body
**Что идёт не так:** `request.json()` в `key_func` для slowapi — async операция, но slowapi вызывает key_func синхронно.
**Как избежать:** Rate limit по IP (`get_remote_address`) или по header. Для single-user VPS-проекта rate limit по IP достаточен.
**Признаки:** `RuntimeError: body read twice` или зависание при rate limit проверке.

### Pitfall 7: `datetime.utcnow()` deprecation
**Что идёт не так:** Python 3.12 выдаёт `DeprecationWarning` для `datetime.utcnow()`. В будущих версиях — ошибка.
**Как избежать:** Использовать `datetime.now(timezone.utc)` везде. JWT claims `exp` и `iat` — секунды Unix timestamp, PyJWT принимает datetime объект и конвертирует сам.

### Pitfall 8: Env var имена — конфликт скелета и CONTEXT.md
**Что идёт не так:** Скелет `config.py` ожидает `PLANNER_JWT_SECRET`, CONTEXT.md определил `planner.env` с `JWT_SECRET`. После деплоя сервер стартует с дефолтным `"CHANGE_ME_IN_PRODUCTION"`.
**Как избежать:** При рефакторинге `config.py` согласовать имена с `planner.env`. Рекомендация: использовать имена из CONTEXT.md (без PLANNER_ prefix).

---

## Code Examples

### SQLAlchemy Async Session как FastAPI dependency

```python
# Source: FastAPI + SQLAlchemy 2.0 official docs
from contextlib import asynccontextmanager
from fastapi import FastAPI
from server.db import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables если нет (dev only; prod — alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan, title="Личный Еженедельник API", docs_url="/api/docs")
```

### Pydantic v2 Request/Response схемы

```python
# Source: FastAPI + Pydantic v2 docs
from pydantic import BaseModel, field_validator
from datetime import datetime

class RequestCodeIn(BaseModel):
    username: str  # Telegram username без @
    hostname: str = "неизвестно"

class VerifyCodeIn(BaseModel):
    request_id: str   # UUID из request-code ответа
    code: str

    @field_validator("code")
    @classmethod
    def code_must_be_6_digits(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError("Код должен быть 6 цифр")
        return v

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int  # секунды до истечения access token
    token_type: str = "bearer"

class ErrorDetail(BaseModel):
    code: str
    message: str

class ErrorOut(BaseModel):
    error: ErrorDetail
```

### Auth code hash в БД

```python
# Source: passlib docs
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_code(code: str) -> str:
    return pwd_context.hash(code)

def verify_code_hash(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

### SQLAlchemy модели (Фаза 1)

```python
# Source: SQLAlchemy 2.x declarative docs
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean, Integer, Text, func

class Base(DeclarativeBase):
    pass

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    telegram_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AuthCode(Base):
    __tablename__ = "auth_codes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String, nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    device_name: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID от клиента
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    day: Mapped[str] = mapped_column(String, nullable=False)  # ISO date "2026-04-14"
    time_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### Deploy команды на VPS

```bash
# На VPS — первоначальный deploy
sudo useradd -r -s /bin/false planner
sudo mkdir -p /opt/planner /var/lib/planner /etc/planner
sudo chown planner:planner /var/lib/planner

# Секреты
sudo tee /etc/planner/planner.env << 'EOF'
BOT_TOKEN=<новый токен после revoke>
JWT_SECRET=<openssl rand -hex 32>
JWT_REFRESH_SECRET=<openssl rand -hex 32>
DATABASE_URL=sqlite+aiosqlite:////var/lib/planner/weekly_planner.db
ALLOWED_USERNAMES=nikita_heyyda
EOF
sudo chmod 600 /etc/planner/planner.env
sudo chown root:planner /etc/planner/planner.env

# Код
sudo git clone https://github.com/Heyyda/weekly-planner.git /opt/planner
cd /opt/planner
sudo -u planner python3 -m venv venv
sudo -u planner venv/bin/pip install -r server/requirements.txt

# Миграции
sudo -u planner venv/bin/alembic -c server/migrations/alembic.ini upgrade head

# systemd
sudo systemctl daemon-reload
sudo systemctl enable --now planner-api planner-bot

# Reverse proxy (Caddy)
# Добавить planner.heyda.ru блок в Caddyfile → sudo systemctl reload caddy
```

---

## State of the Art

| Старый подход | Текущий подход | Изменение | Влияние |
|--------------|----------------|-----------|---------|
| `python-jose` | `PyJWT>=2.9.0` | FastAPI PR #11589, 2024 | python-jose заброшен; PyJWT — официальный стандарт |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | Python 3.12 | Deprecation warning; будет ошибкой в 3.14+ |
| SQLAlchemy sync + FastAPI | SQLAlchemy async + aiosqlite | SQLAlchemy 2.0, 2023 | Не блокирует event loop |
| SQLAlchemy `declarative_base()` | `DeclarativeBase` class | SQLAlchemy 2.0 | Старый API deprecated |
| FastAPI `on_event("startup")` | FastAPI lifespan context manager | FastAPI 0.93+, 2023 | `on_event` deprecated |

**Deprecated/outdated в текущем скелете:**
- `from jose import jwt` → заменить на `import jwt` (PyJWT)
- `engine = create_engine(...)` без WAL → заменить на async engine + PRAGMA event
- `SessionLocal = sessionmaker(bind=engine)` → `async_sessionmaker(engine, expire_on_commit=False)`
- `Base = declarative_base()` → `class Base(DeclarativeBase): pass`
- `JWT_ACCESS_EXPIRE_DAYS = 7` → 15 минут access (CONTEXT.md D-12)
- `DB_PATH = /opt/planner/...` → `/var/lib/planner/...` (CONTEXT.md D-19)
- `_pending_codes` dict → `auth_codes` таблица

---

## Open Questions

1. **Тип reverse proxy на VPS (Caddy vs nginx)**
   - Что знаем: E-bot использует `https://heyda.ru/webhook/search` — значит TLS настроен
   - Неясно: Caddy (Caddyfile) или nginx (конфиг файлы)?
   - Рекомендация: Добавить таск "SSH на VPS, выполнить `systemctl status caddy nginx`" как первый deploy-шаг

2. **ALLOWED_USERNAMES формат**
   - Что знаем: CONTEXT.md говорит `ALLOWED_USERNAMES=nikita_heyyda,...` (comma-separated)
   - Неясно: Telegram username с @ или без? Регистрозависимость?
   - Рекомендация: Хранить без @, сравнивать в lowercase

3. **aiogram для /start в Фазе 1 vs httpx-only**
   - Что знаем: Для отправки кода httpx достаточен; для получения /start нужен бот
   - Неясно: Когда именно пользователь напишет /start (до или после установки клиента)
   - Рекомендация: `planner-bot.service` в Фазе 1 — минимальный aiogram bot только для `/start` handler; расширяется в Фазе 5

4. **Python версия на VPS**
   - Что знаем: CLAUDE.md говорит "Python 3.12+" для сервера
   - Неясно: Реальная установленная версия на VPS
   - Рекомендация: `python3 --version` на VPS как первый таск; если < 3.10 — установить через deadsnakes PPA

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + httpx (AsyncClient) |
| Config file | `server/tests/conftest.py` — Wave 0 создать |
| Quick run command | `pytest server/tests/ -x -q` |
| Full suite command | `pytest server/tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | POST /auth/request-code → бот получает chat_id, код сохранён в DB | integration | `pytest server/tests/test_auth.py::test_request_code -x` | ❌ Wave 0 |
| AUTH-02 | POST /auth/verify с правильным кодом → access + refresh token | integration | `pytest server/tests/test_auth.py::test_verify_code -x` | ❌ Wave 0 |
| AUTH-02 | POST /auth/verify с неверным кодом → 400 + INVALID_CODE | unit | `pytest server/tests/test_auth.py::test_verify_wrong_code -x` | ❌ Wave 0 |
| AUTH-02 | POST /auth/verify с истёкшим кодом → 400 + CODE_EXPIRED | unit | `pytest server/tests/test_auth.py::test_verify_expired_code -x` | ❌ Wave 0 |
| AUTH-04 | POST /auth/refresh с валидным refresh → новый access | integration | `pytest server/tests/test_auth.py::test_refresh -x` | ❌ Wave 0 |
| AUTH-05 | POST /auth/logout → session revoked, refresh больше не работает | integration | `pytest server/tests/test_auth.py::test_logout -x` | ❌ Wave 0 |
| SRV-01 | GET /api/auth/me с Bearer → user info | integration | `pytest server/tests/test_auth.py::test_me -x` | ❌ Wave 0 |
| SRV-02 | POST /api/sync с changes → сохранены в DB, delta возвращена | integration | `pytest server/tests/test_sync.py::test_sync_roundtrip -x` | ❌ Wave 0 |
| SRV-03 | WAL enabled — две concurrent транзакции без OperationalError | integration | `pytest server/tests/test_db.py::test_wal_concurrent -x` | ❌ Wave 0 |
| SRV-04 | Модели создаются через Alembic: all tables exist | integration | `pytest server/tests/test_db.py::test_schema -x` | ❌ Wave 0 |
| SRV-06 | updated_at устанавливается сервером, не клиентом | unit | `pytest server/tests/test_sync.py::test_server_timestamp -x` | ❌ Wave 0 |
| AUTH-01 | Rate limit: второй /auth/request-code в течение минуты → 429 | integration | `pytest server/tests/test_rate_limit.py::test_rate_limit -x` | ❌ Wave 0 |

### Smoke Tests (curl — ручная проверка после deploy)

```bash
# Health check
curl https://planner.heyda.ru/api/health
# Expected: {"status": "ok"}

# Version
curl https://planner.heyda.ru/api/version
# Expected: {"version": "0.1.0", ...}

# Auth flow (Telegram bot должен быть запущен)
curl -X POST https://planner.heyda.ru/api/auth/request-code \
  -H "Content-Type: application/json" \
  -d '{"username": "nikita_heyyda", "hostname": "test-pc"}'
# Expected: {"request_id": "...", "expires_in": 300}
```

### Sampling Rate

- **Per task commit:** `pytest server/tests/ -x -q` (< 10 секунд на SQLite in-memory)
- **Per wave merge:** `pytest server/tests/ -v --tb=short`
- **Phase gate:** Full suite green + ручные curl smoke tests на VPS

### Wave 0 Gaps

- [ ] `server/tests/__init__.py` — пустой файл
- [ ] `server/tests/conftest.py` — fixtures: async test db (SQLite in-memory), test client, mock Telegram API call
- [ ] `server/tests/test_auth.py` — AUTH-01..05, SRV-01
- [ ] `server/tests/test_sync.py` — SRV-02, SRV-06
- [ ] `server/tests/test_db.py` — SRV-03, SRV-04
- [ ] `server/tests/test_rate_limit.py` — AUTH-01 rate limit
- [ ] Framework install: `pip install pytest pytest-asyncio httpx` — если нет

**conftest.py паттерн:**

```python
# server/tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from server.api import app
from server.db import Base, get_db

@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async def override_get_db():
        async with session_factory() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    await engine.dispose()
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def client(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

---

## Sources

### Primary (HIGH confidence)
- PyJWT 2.12.1 — latest version verified via `pip index versions PyJWT`; docs at https://pyjwt.readthedocs.io/
- SQLAlchemy 2.0 async docs — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- SQLAlchemy SQLite WAL — https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#connect-args
- FastAPI Security — https://fastapi.tiangolo.com/tutorial/security/
- FastAPI lifespan — https://fastapi.tiangolo.com/advanced/events/
- Telegram Bot API — https://core.telegram.org/bots/api#sendmessage
- aiogram 3.x docs — https://docs.aiogram.dev/
- `.planning/research/STACK.md` — PyJWT vs python-jose, aiogram 3.x, версии библиотек
- `.planning/research/ARCHITECTURE.md` — sync protocol, API sketch, separate bot process
- `.planning/research/PITFALLS.md` — SQLite WAL, keyring, concurrency

### Secondary (MEDIUM confidence)
- slowapi GitHub + PyPI — rate limiting for FastAPI; key_func async limitation noted
- systemd unit pattern — inferred from E-bot VPS deployment model (E-bot's unit file not accessible)
- Caddy/nginx на VPS — inferred from E-bot WEBHOOK_URL = https://heyda.ru/webhook/search

### Tertiary (LOW confidence)
- Reverse proxy type (Caddy vs nginx) — unknown, requires SSH investigation on VPS

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — все версии верифицированы через PyPI/pip
- Architecture Patterns: HIGH — FastAPI + SQLAlchemy async + PyJWT официально задокументированы
- aiogram process isolation: HIGH — архитектурное решение из research/ARCHITECTURE.md
- Systemd unit format: MEDIUM — паттерн стандартный, точная конфигурация VPS неизвестна
- Reverse proxy: MEDIUM — тип неизвестен, требует проверки на VPS

**Research date:** 2026-04-14
**Valid until:** 2026-06-14 (stable stack — 60 дней)
