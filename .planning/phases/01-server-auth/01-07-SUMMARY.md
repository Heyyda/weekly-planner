---
phase: 01-server-auth
plan: 07
subsystem: api
tags: [fastapi, sqlalchemy, sqlite, pydantic, sync, delta, tombstone]

requires:
  - phase: 01-06
    provides: auth endpoints + get_current_user dependency + FastAPI app
  - phase: 01-04
    provides: JWT + SessionService + get_current_user
  - phase: 01-02
    provides: Task ORM model с tombstone (deleted_at) и onupdate=func.now()

provides:
  - POST /api/sync — delta-sync endpoint (create/update/delete ops, tombstone, delta-query)
  - SyncIn/SyncOut/TaskChange/TaskState pydantic schemas в sync_schemas.py
  - Row-level isolation: user_id из JWT, не из тела запроса
  - 8 integration тестов покрывающих все sync сценарии

affects:
  - 01-08 (app.py уже содержит include_router(sync_router))
  - 02-client-core (клиент будет вызывать /api/sync через SyncManager)

tech-stack:
  added: []
  patterns:
    - delta-sync через since-timestamp (updated_at > since)
    - soft-delete tombstone через deleted_at поле (не hard DELETE)
    - idempotent CREATE через client-generated UUID (retry-safe)
    - partial UPDATE: только переданные поля, updated_at server-side (SRV-06)
    - row-level isolation через Depends(get_current_user) без body user_id

key-files:
  created:
    - server/api/sync_routes.py
    - server/api/sync_schemas.py
    - server/tests/test_sync_routes.py
  modified:
    - server/api/app.py

key-decisions:
  - "Idempotent CREATE: при повторном task_id существующего user — трактуется как UPDATE (не ошибка)"
  - "Partial UPDATE через None-check: только поля != None обновляются; updated_at server-side через onupdate"
  - "server_timestamp возвращается до delta-query (не after) — клиент сохраняет как новый since"
  - "Фикстура authed_client включает limiter.reset() чтобы rate-limit не мешал sync тестам"

requirements-completed: ["SRV-02", "SRV-06"]

duration: 35min
completed: 2026-04-15
---

# Phase 01 Plan 07: Sync Endpoint Summary

**POST /api/sync с delta-sync по updated_at > since, tombstone через deleted_at, server-side updated_at (SRV-06), row-level isolation через JWT**

## Performance

- **Duration:** 35 min
- **Started:** 2026-04-15T09:12:00Z
- **Completed:** 2026-04-15T09:47:00Z
- **Tasks:** 3 (schemas, endpoint, tests)
- **Files modified:** 4

## Accomplishments

- POST /api/sync endpoint с тремя операциями: CREATE (idempotent), UPDATE (partial), DELETE (tombstone)
- Delta-query: возвращает только tasks с `updated_at > since` — эффективная синхронизация без передачи всей БД
- SRV-06 гарантия: `updated_at` всегда из onupdate=func.now() на сервере, клиент не может его подменить
- 8 зелёных integration тестов покрывающих auth guard, CRUD, tombstone, delta, SRV-06, cross-user isolation

## Task Commits

1. **Task 1: Pydantic схемы** — `44f48e6` (feat) — sync_schemas.py с SyncIn/SyncOut/TaskChange/SyncOp
2. **Task 2: Sync endpoint + app wiring** — `bdcb61e` (feat) — sync_routes.py + app.py
3. **Task 3: Integration тесты** — `6a7f5e1` (test) — test_sync_routes.py (8 тестов)

## Files Created/Modified

- `server/api/sync_schemas.py` — Pydantic v2 схемы: SyncIn, SyncOut, TaskChange, TaskState, SyncOp enum
- `server/api/sync_routes.py` — POST /api/sync с _apply_create/_apply_update/_apply_delete/_to_state
- `server/api/app.py` — добавлен include_router(sync_router), limiter setup (для Plan 08)
- `server/tests/test_sync_routes.py` — 8 integration тестов через authed_client fixture

## Decisions Made

- Idempotent CREATE: повторный op=create с существующим task_id трактуется как UPDATE (не ошибка и не ignore) — потому что клиент мог не получить response на первый CREATE и ретраит
- Partial UPDATE: поля обновляются только если `field is not None` — позволяет менять только `done` не затирая `text`
- `server_timestamp` вычисляется ДО delta-query — клиент сохраняет его как `since` для следующего sync; если вычислять после, можно пропустить tasks созданные между commit и delta-query
- В тестах: `limiter.reset()` в authed_client fixture т.к. rate-limit из Plan 08 глобальный

## Пример request/response

```bash
# CREATE task
curl -X POST http://localhost:8100/api/sync \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "since": null,
    "changes": [
      {"op": "create", "task_id": "uuid-1", "text": "купить молоко", "day": "2026-04-14", "done": false, "position": 0}
    ]
  }'

# Response:
{
  "server_timestamp": "2026-04-15T09:30:00.123456Z",
  "changes": [
    {
      "task_id": "uuid-1", "text": "купить молоко", "day": "2026-04-14",
      "done": false, "position": 0, "time_deadline": null,
      "created_at": "2026-04-15T09:30:00.123456Z",
      "updated_at": "2026-04-15T09:30:00.123456Z",  // SRV-06: server-side
      "deleted_at": null
    }
  ]
}

# DELETE task (tombstone)
curl -X POST http://localhost:8100/api/sync \
  -H "Authorization: Bearer <access_token>" \
  -d '{"since": null, "changes": [{"op": "delete", "task_id": "uuid-1"}]}'

# Response includes task with deleted_at != null (tombstone, not hard-delete)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Исправлена naive datetime в тесте SRV-06**
- **Found during:** Task 3 (test_sync_server_sets_updated_at_not_client)
- **Issue:** `datetime.fromisoformat()` без "+00:00" возвращал naive datetime, вычитание с UTC aware datetime давало TypeError
- **Fix:** Нормализация строки: `rstrip("Z") + "+00:00"` + fallback `replace(tzinfo=timezone.utc)` для naive
- **Files modified:** server/tests/test_sync_routes.py
- **Verification:** Тест проходит корректно
- **Committed in:** 6a7f5e1

**2. [Rule 1 - Bug] Исправлено: models не в Base.metadata при create_all**
- **Found during:** Task 3 (authed_client fixture)
- **Issue:** `from server.db.base import Base` без предшествующего `import models` → Base.metadata пустая → create_all создаёт 0 таблиц → "no such table: users"
- **Fix:** Переместить `from server.db.models import User` ПЕРЕД `engine.begin() + create_all`
- **Files modified:** server/tests/test_sync_routes.py
- **Verification:** 8 тестов зелёные
- **Committed in:** 6a7f5e1

---

**Total deviations:** 2 auto-fixed (2 Rule 1 - Bug)
**Impact on plan:** Оба исправления в тестах, не в production коде. Никакого scope creep.

## Issues Encountered

- Rate-limit из Plan 08 (глобальный limiter) ломал sync тесты через `request-code` — решено через `limiter.reset()` в fixture

## Next Phase Readiness

- /api/sync endpoint готов для использования клиентом (Phase 2: client core)
- SRV-02 (delta-sync) и SRV-06 (server-side updated_at) покрыты
- Tombstone механизм реализован (SYNC-08 поддержан на сервере)

---
*Phase: 01-server-auth*
*Completed: 2026-04-15*

## Self-Check: PASSED
