---
phase: 01-server-auth
plan: "03"
subsystem: database
tags: [pydantic-settings, sqlalchemy, aiosqlite, sqlite-wal, fastapi-dependency]

# Dependency graph
requires:
  - phase: 01-server-auth
    plan: "01"
    provides: "pytest infrastructure, conftest fixtures, pyproject.toml"
  - phase: 01-server-auth
    plan: "02"
    provides: "SQLAlchemy Base + User/Task/AuthCode/Session models"
provides:
  - "server/config.py — pydantic-settings Settings с env vars CONTEXT.md D-27"
  - "server/db/engine.py — async engine + PRAGMA WAL event hook + get_db dependency"
  - "SRV-03: WAL + busy_timeout=5000 — concurrent writes не вызывают database is locked"
affects: [01-04, 01-05, 01-06, 01-07, 01-08]

# Tech tracking
tech-stack:
  added:
    - pydantic-settings 2.x (BaseSettings, SettingsConfigDict)
    - SQLAlchemy async engine (create_async_engine + aiosqlite)
    - SQLAlchemy event listener (event.listens_for sync_engine "connect")
  patterns:
    - "PRAGMA WAL через event hook на sync_engine — применяется к каждому новому connection"
    - "Ленивый singleton engine — _engine_singleton = None, создаётся при первом вызове"
    - "allowed_usernames как str в env (comma-separated), property возвращает list[str]"
    - "lru_cache(maxsize=1) на get_settings() — singleton без импорт-тайм побочных эффектов"

key-files:
  created:
    - server/db/engine.py
    - server/tests/test_config.py
    - server/tests/test_engine.py
  modified:
    - server/config.py

key-decisions:
  - "allowed_usernames объявлена как str (alias=ALLOWED_USERNAMES), property возвращает list — обход ограничения pydantic-settings который пытается JSON-декодировать List[str] из env"
  - "engine singleton ленивый (не при импорте) — engine.py импортируется без env vars в тестах"
  - "module-level __getattr__ для обратной совместимости: from server.db.engine import engine, AsyncSessionLocal"

patterns-established:
  - "WAL pattern: _attach_pragma_listener(engine) — 4 PRAGMA в одном cursor block"
  - "Settings pattern: get_settings() с lru_cache, cache_clear() в тестах через monkeypatch"

requirements-completed: [SRV-03]

# Metrics
duration: 4min
completed: "2026-04-14"
---

# Phase 01 Plan 03: Config + Engine Summary

**pydantic-settings Config (D-27 env vars) + SQLAlchemy async engine с WAL PRAGMA event hook, доказанный тестом concurrent-writes без database is locked (SRV-03)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-14T23:21:01Z
- **Completed:** 2026-04-14T23:24:52Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Переписан `server/config.py` на pydantic-settings BaseSettings с 5 обязательными env vars из CONTEXT.md D-27 (DATABASE_URL, JWT_SECRET, JWT_REFRESH_SECRET, BOT_TOKEN, ALLOWED_USERNAMES) и разумными defaults (access_token_ttl=900, refresh_token_ttl=2592000, auth_code_ttl=300)
- Создан `server/db/engine.py`: async engine с aiosqlite, PRAGMA WAL/busy_timeout=5000/foreign_keys=ON/synchronous=NORMAL через `event.listens_for(engine.sync_engine, "connect")`, `get_db` FastAPI dependency
- SRV-03 доказан: `test_concurrent_writes_no_lock` — 2 параллельных INSERT через `asyncio.gather` проходят без OperationalError

## Task Commits

1. **Task 1: pydantic-settings Config** - `7cf7554` (feat)
2. **Task 2: async engine + WAL PRAGMA** - `098e56f` (feat)

**Plan metadata:** (создаётся следующим коммитом)

## Files Created/Modified

- `server/config.py` — Settings(BaseSettings) с полями D-27, field_validator для allowed_usernames, lru_cache singleton
- `server/db/engine.py` — async engine factory, _attach_pragma_listener(), get_db dependency, ленивые singletons
- `server/tests/test_config.py` — 6 тестов: загрузка из env, comma-split, lowercase+strip @, defaults TTL, missing required, empty ALLOWED_USERNAMES
- `server/tests/test_engine.py` — 6 тестов: WAL mode, busy_timeout=5000, foreign_keys=1, synchronous=1, concurrent writes, get_db AsyncSession

## Decisions Made

1. **allowed_usernames как str + property**: pydantic-settings v2 пытается JSON-декодировать `List[str]` из env, что ломает plaintext "nikita,vasya". Решение: поле объявлено как `str` с `alias="ALLOWED_USERNAMES"`, парсинг в `@property allowed_usernames`. Валидатор проверяет что строка не пустая.

2. **Ленивый engine singleton**: если `engine = _create_engine()` на уровне модуля — импорт падает без env vars. Решение: `_engine_singleton = None`, создаётся при первом вызове `_get_engine()`. Тесты импортируют модуль без env vars, только `_attach_pragma_listener` используется напрямую.

3. **`__getattr__` для обратной совместимости**: plans 04-08 могут делать `from server.db.engine import engine, AsyncSessionLocal` — module-level `__getattr__` перехватывает эти имена и возвращает ленивые singletons.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pydantic-settings JSON-декодирует List[str] из env**
- **Found during:** Task 1 (config.py GREEN phase)
- **Issue:** `allowed_usernames: List[str]` в BaseSettings → pydantic-settings пытается `json.loads("nikita,vasya")` → JSONDecodeError. Тесты падают с `SettingsError: error parsing value for field allowed_usernames`
- **Fix:** Изменён тип поля на `str` с `alias="ALLOWED_USERNAMES"`, добавлен `@property allowed_usernames` с comma-split + lowercase логикой. `field_validator` проверяет что raw строка не пустая.
- **Files modified:** server/config.py
- **Verification:** `pytest tests/test_config.py -v` — 6 passed
- **Committed in:** 7cf7554 (Task 1 commit)

**2. [Rule 3 - Blocking] Module-level engine singleton падает при импорте без env vars**
- **Found during:** Task 2 (engine.py GREEN phase, первый запуск тестов)
- **Issue:** `engine: AsyncEngine = _create_engine()` на уровне модуля → при импорте `from server.db.engine import _attach_pragma_listener` без env vars → `ValidationError: 5 fields required`
- **Fix:** Убран eager singleton. Добавлены `_engine_singleton = None` и `_get_engine()` с lazy init. `module.__getattr__` предоставляет `engine` и `AsyncSessionLocal` для обратной совместимости.
- **Files modified:** server/db/engine.py
- **Verification:** `pytest tests/test_engine.py -v` — 6 passed (все тесты импортируют модуль без env vars)
- **Committed in:** 098e56f (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (Rule 3 — blocking issues)
**Impact on plan:** Оба fix'а необходимы для корректной работы. Логика не изменилась — только способ инициализации. Публичный API (get_db, allowed_usernames, все PRAGMAs) остался идентичным плану.

## Issues Encountered

None — оба blocking issue диагностированы сразу по первым test runs и исправлены за 1 итерацию.

## Known Stubs

None — все поля Settings имеют реальные значения из env vars. engine.py полностью функционален.

## Next Phase Readiness

- Plans 04-08 могут импортировать `from server.db.engine import get_db` и `from server.config import get_settings` / `from server.config import settings`
- WAL + busy_timeout=5000 доказаны тестом `test_concurrent_writes_no_lock` — SRV-03 выполнен
- Settings содержит все необходимые переменные: jwt_secret, jwt_refresh_secret, bot_token, allowed_usernames, все TTL values

---
*Phase: 01-server-auth*
*Completed: 2026-04-14*
