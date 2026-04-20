---
phase: 01-server-auth
plan: 08
subsystem: api
tags: [fastapi, slowapi, rate-limit, health, version, monitoring]

requires:
  - phase: 01-07
    provides: sync endpoint, app.py с include_router pattern
  - phase: 01-06
    provides: auth endpoints + request_code endpoint для rate-limiting

provides:
  - GET /api/health → 200 {"status": "ok"} без auth (для systemd/proxy)
  - GET /api/version → 200 {"version", "download_url", "sha256"} без auth
  - Rate-limit на /api/auth/request-code: 1/минуту + 5/час по IP
  - Custom 429 handler в формате D-18 + Retry-After header
  - 6 integration тестов (3 health/version + 3 rate-limit)

affects:
  - 01-10 (deploy) — health используется для systemd healthcheck
  - 06-dist (auto-update) — /api/version нужен для проверки обновлений клиентом

tech-stack:
  added:
    - slowapi (rate limiting middleware для FastAPI через starlette-limiter)
  patterns:
    - per-endpoint rate-limit через @limiter.limit декоратор (не глобальный)
    - key_func=get_remote_address (IP-based, не username-based из-за Pitfall 6)
    - custom exception handler для D-18 формата ошибок
    - limiter.reset() в тестовых fixture'ах для изоляции тестов

key-files:
  created:
    - server/api/misc_routes.py
    - server/api/rate_limit.py
    - server/tests/test_health_version.py
    - server/tests/test_rate_limit.py
  modified:
    - server/api/app.py
    - server/api/auth_routes.py
    - server/tests/test_auth_routes.py

key-decisions:
  - "Rate-limit по IP (get_remote_address), не по username: slowapi key_func синхронный, не может читать async request.body() (RESEARCH.md Pitfall 6)"
  - "default_limits=[] в Limiter: rate-limit только per-endpoint через @limiter.limit декоратор, не ко всем endpoints"
  - "limiter.reset() в fixture teardown/setup: slowapi limiter глобальный синглтон, состояние сохраняется между тестами"

requirements-completed: ["SRV-01"]

duration: 30min
completed: 2026-04-15
---

# Phase 01 Plan 08: Health/Version/Rate-limit Summary

**slowapi rate-limit (1/min, 5/hr по IP) на /api/auth/request-code + GET /api/health + GET /api/version без auth, custom 429 D-18 handler**

## Performance

- **Duration:** 30 min
- **Started:** 2026-04-15T09:47:00Z
- **Completed:** 2026-04-15T10:17:00Z
- **Tasks:** 3 (misc_routes, rate_limit, tests)
- **Files modified:** 6

## Accomplishments

- GET /api/health → 200 {"status": "ok"} — готов для systemd `ExecStartPost` healthcheck и nginx upstream check
- GET /api/version → 200 {"version": "0.1.0", "download_url": ..., "sha256": ""} — заглушка для Phase 6 auto-update
- slowapi rate-limit на /api/auth/request-code: 1 запрос/минуту, 5 запросов/час по IP
- 429 ответ в формате D-18 + Retry-After: 60 header — клиент знает когда повторить
- 6 зелёных integration тестов

## Task Commits

1. **Task 1: misc_routes + app wiring** — `db290b0` (feat) — misc_routes.py + app.py include_router
2. **Task 2: rate_limit.py + auth decorator** — `d3759d7` (feat) — rate_limit.py + @limiter.limit на request_code
3. **Task 3: Тесты** — `003a157` (test) — test_health_version.py + test_rate_limit.py

## Files Created/Modified

- `server/api/misc_routes.py` — GET /api/health и GET /api/version без auth
- `server/api/rate_limit.py` — slowapi Limiter + rate_limit_exceeded_handler (D-18 формат)
- `server/api/app.py` — app.state.limiter + add_exception_handler(RateLimitExceeded)
- `server/api/auth_routes.py` — @limiter.limit("1/minute;5/hour") + request: Request параметр
- `server/tests/test_health_version.py` — 3 теста health/version endpoint
- `server/tests/test_rate_limit.py` — 3 теста rate-limit (429, endpoints isolation, Retry-After)
- `server/tests/test_auth_routes.py` — добавлен limiter.reset() в fixture

## Decisions Made

- Rate-limit по IP, не по username — slowapi's `key_func` вызывается синхронно и не может читать `async request.body()`. Попытка читать `body()` внутри key_func вызывает `RuntimeError: body read twice`. IP-based достаточен для personal VPS single-user.
- `default_limits=[]` в `Limiter()` — чтобы rate-limit применялся только к endpoints с `@limiter.limit()`, а не глобально. Health и version должны быть доступны без ограничений.
- `limiter.reset()` в fixture setup и teardown — slowapi хранит счётчики в памяти процесса. Без reset тесты влияют друг на друга: первый тест исчерпывает лимит, второй падает с 429.

## Пример curl

```bash
# Health check
curl http://109.94.211.29:8100/api/health
# → {"status": "ok"}

# Version
curl http://109.94.211.29:8100/api/version
# → {"version": "0.1.0", "download_url": "https://heyda.ru/planner/download", "sha256": ""}

# Rate-limit (второй вызов в минуту → 429)
curl -X POST http://109.94.211.29:8100/api/auth/request-code \
  -d '{"username": "nikita", "hostname": "pc"}'
# → 200 (первый запрос)

curl -X POST http://109.94.211.29:8100/api/auth/request-code \
  -d '{"username": "nikita", "hostname": "pc"}'
# → 429 {"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "..."}}
# Headers: Retry-After: 60
```

## Лимиты и как их сбрасывать в тестах

Rate-limit лимиты (CONTEXT.md D-09):
- 1 запрос в минуту (защита от случайных повторных кликов)
- 5 запросов в час (защита от автоматизированных атак)

Сброс в тестах:
```python
from server.api.rate_limit import limiter
limiter.reset()  # Сбрасывает все счётчики в памяти
```

Это нужно делать в setup И teardown каждого теста, который вызывает `/api/auth/request-code`:
```python
@pytest_asyncio.fixture
async def my_fixture():
    from server.api.rate_limit import limiter
    limiter.reset()  # setup
    yield ...
    limiter.reset()  # teardown
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rate-limit ломал существующие test_auth_routes.py тесты**
- **Found during:** Task 3 (запуск полного test suite)
- **Issue:** После добавления @limiter.limit на request_code, тесты в test_auth_routes.py стали получать 429. Limiter глобальный — состояние сохранялось между тестами в одном процессе
- **Fix:** Добавить `limiter.reset()` в setup и teardown `app_client` fixture в test_auth_routes.py; также добавить reset между двумя `request_code` вызовами в `test_logout_with_specific_refresh_token`
- **Files modified:** server/tests/test_auth_routes.py
- **Verification:** 90/90 тестов зелёные
- **Committed in:** 003a157

**2. [Rule 1 - Bug] Исправлено: models не в Base.metadata при create_all (в rate_limit тестах)**
- **Found during:** Task 3 (test_rate_limit.py fixture)
- **Issue:** `from server.db.base import Base` без предшествующего import models → create_all создаёт 0 таблиц → "no such table: users"
- **Fix:** Переместить `from server.db.models import User` ПЕРЕД `engine.begin() + create_all`
- **Files modified:** server/tests/test_rate_limit.py
- **Verification:** 3 rate_limit теста зелёные
- **Committed in:** 003a157

---

**Total deviations:** 2 auto-fixed (2 Rule 1 - Bug)
**Impact on plan:** Оба исправления в тестах, не в production коде. Первое исправление критично — без него 8 из 11 auth тестов падают.

## Issues Encountered

- slowapi требует `request: Request` как первый параметр в endpoint функции (иначе KeyError при поиске ключа). Порядок параметров важен: сначала `request`, потом `body`, потом `Depends`.

## Known Stubs

- `server/api/misc_routes.py:version()` → `"sha256": ""` — пустая строка, заполнится при Phase 6 build процессе когда появится реальный .exe артефакт. Это интенциональный stub для Фазы 1, не blocking.

## Next Phase Readiness

- Health endpoint готов для systemd `ExecStartPost=/usr/bin/curl -sf http://127.0.0.1:8100/api/health`
- Version endpoint готов (заглушка sha256 — intentional, заполнится в Phase 6)
- Rate-limiting защищает /request-code от повторных кликов и простых ботов
- SRV-01 теперь полностью покрыт (endpoints + rate-limit)

---
*Phase: 01-server-auth*
*Completed: 2026-04-15*

## Self-Check: PASSED
