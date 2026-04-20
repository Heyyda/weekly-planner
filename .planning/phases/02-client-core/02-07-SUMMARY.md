---
phase: 02-client-core
plan: 07
subsystem: sync
tags: [threading, event, sync, backoff, tombstone, daemon-thread]

# Dependency graph
requires:
  - phase: 02-client-core/02-04
    provides: AuthManager — get_access_token, bearer_header, AuthExpiredError
  - phase: 02-client-core/02-05
    provides: LocalStorage — drain/restore/merge/commit_drained/cleanup_tombstones
  - phase: 02-client-core/02-06
    provides: SyncApiClient — post_sync, ApiResult, consecutive_errors, current_backoff
provides:
  - SyncManager — daemon thread оркестратор фоновой синхронизации
  - threading.Event wake (force_sync = немедленный push без ожидания 30s)
  - Stale detection: last_sync_at > 5 мин → full resync (since=None)
  - Push-before-resync: pending отправляется в том же запросе с since=None
  - Opportunistic tombstone cleanup после успешного sync
  - auth_expired/client error останавливают loop (не retry-петля)
affects: [app.py, Phase 3 (tray force_sync), Phase 6 (PyInstaller bundling)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - threading.Event вместо time.sleep — graceful shutdown + immediate wake
    - drain→post_sync→merge/restore — атомарный цикл без потери данных
    - _auth_expired флаг — управляемый выход из while loop (не Exception)

key-files:
  created:
    - client/tests/test_sync.py
  modified:
    - client/core/sync.py

key-decisions:
  - "threading.Event.wait(timeout) вместо time.sleep — force_sync() устанавливает Event, поток просыпается немедленно"
  - "drain pending ПЕРЕД стале-resync (D-20): drained + since=None в одном post_sync, локальные изменения не теряются"
  - "client error (4xx) останавливает loop через _auth_expired флаг — бесконечный retry бессмысленен при ошибке клиента"

patterns-established:
  - "Daemon thread: threading.Thread(target=..., daemon=True, name='PlannerSync')"
  - "Graceful stop: stop_event.set() + wake_event.set() → thread замечает в начале следующего цикла"
  - "Idempotent start(): is_running() guard — повторный вызов noop"

requirements-completed: ["SYNC-03", "SYNC-05", "SYNC-07"]

# Metrics
duration: 3min
completed: 2026-04-16
---

# Phase 02 Plan 07: SyncManager Summary

**SyncManager полностью переписан: daemon thread 'PlannerSync' с threading.Event wake, stale-detection (>5 мин → full resync), push-before-resync, и opportunistic tombstone cleanup — покрыт 20 unit-тестами**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-16T04:04:18Z
- **Completed:** 2026-04-16T04:07:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `client/core/sync.py` полностью переписан (удалены `time.sleep`, `requests.post`, дублирование API_BASE)
- threading.Event.wait() вместо time.sleep — force_sync() пробуждает поток немедленно (SYNC-03)
- Stale detection + push-before-resync: pending дренируется и отправляется с since=None в одном запросе (SYNC-07, D-20)
- merge_from_server применяется при каждом успешном 200 (SYNC-05)
- cleanup_tombstones вызывается opportunistically при пустом pending (D-23)
- auth_expired и client error (4xx) корректно останавливают sync loop — нет infinite retry
- 20 unit-тестов, все 97 тестов зелёные (77 existing + 20 новых)

## Task Commits

1. **Task 1: Переписать client/core/sync.py** - `4f21185` (feat)
2. **Task 2: client/tests/test_sync.py** - `ce517df` (test)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `client/core/sync.py` - SyncManager полностью переписан: Event wake, stale detection, drain/restore, cleanup
- `client/tests/test_sync.py` - 20 unit-тестов: lifecycle, force_sync, _attempt_sync, _is_stale

## Decisions Made
- threading.Event.wait(timeout) вместо time.sleep: единственный способ добиться force_sync() immediate wake без race condition
- Drain pending ПЕРЕД stale resync (D-20): pending + since=None в одном вызове, иначе потеря данных при full resync
- client error (4xx не 401) останавливает loop через тот же `_auth_expired` флаг — отдельный флаг не нужен, смысл тот же: "прекратить retry"

## Deviations from Plan

None — план выполнен точно как написан. Тестов написано 20 (план ожидал минимум 12/15 из описания, acceptance criteria требовали 16+).

## Issues Encountered

None — все тесты прошли с первого запуска.

## User Setup Required

None — изменения только в клиентском коде, сервер и конфигурация не затронуты.

## Known Stubs

None — SyncManager использует реальные LocalStorage и SyncApiClient интерфейсы из предыдущих планов.

## Next Phase Readiness
- SyncManager готов для интеграции в `client/app.py` (Phase 3)
- `force_sync()` готов для вызова из tray-меню (Phase 3)
- Все SYNC-03, SYNC-05, SYNC-07 закрыты; SYNC-01/02/04/06/08 закрыты в 02-05/02-06
- Phase 2 полностью завершена (все планы 02-01..02-07 выполнены)

---
*Phase: 02-client-core*
*Completed: 2026-04-16*
