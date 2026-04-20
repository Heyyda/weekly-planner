---
phase: 02-client-core
plan: "06"
subsystem: api
tags: [requests, http-client, jwt, backoff, retry, sync, python]

# Dependency graph
requires:
  - phase: 02-client-core/02-04
    provides: AuthManager с bearer_header() + refresh_access() + AuthExpiredError
  - phase: 02-client-core/02-02
    provides: TaskChange.to_wire() — wire-format сериализация для /api/sync
provides:
  - SyncApiClient.post_sync(since, changes) → ApiResult — единая точка POST /api/sync
  - ApiResult dataclass с factory-методами (success/network_error/server_error/client_error/auth_expired)
  - 401 refresh-retry: один вызов refresh_access() + один повторный запрос
  - Exponential backoff state: _consecutive_errors + _current_backoff (cap 60s, D-13)
  - SYNC-06 idempotency: client UUID сохраняется при ретраях (без генерации нового UUID)
affects:
  - 02-client-core/02-07  # SyncManager использует SyncApiClient + ApiResult

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ApiResult dataclass — типизированный ответ HTTP без raise (offline-tolerant)"
    - "401-refresh-retry: один refresh + один retry; второй 401 = auth_expired"
    - "Exponential backoff inline без библиотек: счётчик + min(x*2, cap)"
    - "_bump_backoff() только на network/5xx; 4xx не bump (баг клиента — ретрай бесполезен)"

key-files:
  created:
    - client/core/api_client.py
    - client/tests/test_api_client.py
  modified: []

key-decisions:
  - "ApiResult никогда не raise — SyncManager инспектирует поля (offline-tolerant design)"
  - "401 retry ровно один раз: post_sync() → 401 → refresh_access() → _do_post_sync(); второй 401 → auth_expired()"
  - "backoff bump только при network/5xx; 4xx (не 401) — client_error без bump (ретрай бессмысленен)"
  - "SYNC-06: клиент не генерирует новый UUID при ретрае — task_id стабилен в TaskChange, сервер принимает идемпотентно"

patterns-established:
  - "SyncApiClient._do_post_sync(): один HTTP вызов без retry; post_sync() оркестрирует 401-refresh-retry"
  - "current_backoff property: SyncManager читает его для wait(timeout=...) в _sync_loop"
  - "reset_backoff() вызывается автоматически внутри _do_post_sync() при 200"

requirements-completed: ["SYNC-06"]

# Metrics
duration: 2min
completed: 2026-04-16
---

# Phase 02 Plan 06: SyncApiClient Summary

**SyncApiClient с 401-refresh-retry + exponential backoff (cap 60s) — инкапсулирует весь HTTP-слой POST /api/sync, оставляя SyncManager читаемым оркестратором**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-16T03:59:56Z
- **Completed:** 2026-04-16T04:02:12Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- `ApiResult` dataclass с 5 factory-методами для типизированных ответов — SyncManager никогда не обрабатывает исключения от HTTP
- `SyncApiClient.post_sync()` с 401-refresh-retry: при первом 401 вызывает `auth.refresh_access()` и делает один повторный POST; при `AuthExpiredError` → `ApiResult.auth_expired()`
- Exponential backoff: bump при network/5xx, reset при 200, cap 60s — D-13 полностью реализован
- 11 unit-тестов покрывают все пути (happy path, wire format, bearer, 401 retry, AuthExpiredError, 500, ConnectionError, 400, backoff cap, backoff reset, SYNC-06 UUID idempotency)

## Task Commits

1. **Task 1: api_client.py — SyncApiClient + ApiResult** - `9705a69` (feat)
2. **Task 2: test_api_client.py — 11 unit-тестов** - `4908fee` (test)

## Files Created/Modified

- `client/core/api_client.py` — SyncApiClient + ApiResult; POST /api/sync с Bearer, 401-retry, backoff
- `client/tests/test_api_client.py` — 11 тестов; 77 passed в полном client suite (3.76s)

## Decisions Made

- `ApiResult` никогда не `raise` — SyncManager работает в терминах `result.ok` / `result.error_kind`, а не try/except
- 401 retry ровно один раз: `_do_post_sync()` возвращает сырой `status=401`; `post_sync()` оркестрирует refresh → retry; второй 401 = `auth_expired()`
- backoff bump только при `network` и `server` (5xx); `4xx` (не 401) — `client_error` без bump (баг клиента, ретрай бесполезен)
- SYNC-06: `task_id` стабилен в `TaskChange` объекте — при ретрае клиент отправляет тот же UUID; сервер принимает повторный CREATE идемпотентно (INSERT OR IGNORE → UPDATE)

## Deviations from Plan

None — plan executed exactly as written. Оба задания выполнены в точности с планом; 11 тестов вместо упомянутых "9 unit-тестов" в objective (план явно перечислял 11 в behavior-секции — расхождение в тексте objective, не отклонение от реального плана).

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `SyncApiClient` полностью готов для Plan 07 (SyncManager): `SyncManager` вызывает `client.post_sync(since, pending)` → читает `result.ok` / `result.error_kind` / `result.retry_after` → управляет `_wake_event.wait(timeout=client.current_backoff)`
- `ApiResult.auth_expired()` — сигнал для SyncManager остановить поток и триггернуть re-auth flow в UI (Phase 3)
- 77/77 client тестов зелёные; нет регрессий

---
*Phase: 02-client-core*
*Completed: 2026-04-16*
