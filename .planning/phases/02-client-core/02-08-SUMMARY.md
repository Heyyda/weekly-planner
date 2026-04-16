---
phase: 02-client-core
plan: 08
subsystem: testing
tags: [pytest, requests-mock, e2e, integration-tests, logging, jwt, sync, tombstone]

# Dependency graph
requires:
  - phase: 02-client-core
    plan: 04
    provides: AuthManager (JWT request/verify/refresh + keyring)
  - phase: 02-client-core
    plan: 05
    provides: LocalStorage (JSON cache + pending_changes + threading.Lock)
  - phase: 02-client-core
    plan: 06
    provides: SyncApiClient (backoff + 401 retry + ApiResult)
  - phase: 02-client-core
    plan: 07
    provides: SyncManager (daemon thread + force_sync + stale detection)
  - phase: 02-client-core
    plan: 03
    provides: logging_setup (SecretFilter, setup/reset_client_logging)
provides:
  - E2E integration tests для всех 8 SYNC-требований (unit + integration двойное покрытие)
  - FakeServer: stateful mock-сервер с handle_sync callback (хранит tasks, delta, tombstone)
  - Log-safety verification: автоматическая гарантия что D-29 работает в реальном flow
affects:
  - phase: 03 (overlay+tray) — Phase 2 полностью завершена, ready for Phase 3
  - phase: verify-work — все success criteria подтверждены автоматически

# Tech tracking
tech-stack:
  added: []
  patterns:
    - FakeServer pattern: stateful callback для requests-mock (хранит state в closure)
    - autouse fixture для reset состояния логирования между тестами
    - _flush_and_read_log helper: форсирует flush перед проверкой содержимого файла
    - os.environ["APPDATA"] override внутри теста для device B изоляции

key-files:
  created:
    - client/tests/test_e2e_sync.py
    - client/tests/test_logs_no_secrets.py
  modified: []

key-decisions:
  - "test_server_wins_on_conflict: использует stale last_sync_at (>5 мин) для триггера full resync вместо delta — без pending changes _attempt_sync пропускает HTTP"
  - "FakeServer.handle_sync как callback в requests-mock: stateful behavior без сложных fixture цепочек"
  - "autouse _reset_logging fixture: изоляция между тестами без глобальных side effects handlers"

patterns-established:
  - "FakeServer pattern: для E2E тестов с stateful server behavior используем класс с handle_* callback методами"
  - "os.environ override в тесте: для device B изоляции — сохраняем/восстанавливаем через try/finally"
  - "stale + full resync для conflict verification: если нечего пушить, _attempt_sync пропускает — нужно сделать last_sync_at stale"

requirements-completed: [SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06, SYNC-07, SYNC-08]

# Metrics
duration: 15min
completed: 2026-04-15
---

# Phase 02 Plan 08: E2E Integration Tests + Log Safety Summary

**7 E2E integration tests + 2 log-safety tests через FakeServer (requests-mock stateful callback) — все 8 SYNC-требований получили второй слой покрытия (unit + integration), D-29 верифицирован в реальном flow**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-15T09:30:00Z
- **Completed:** 2026-04-15T09:45:00Z
- **Tasks:** 2/2
- **Files created:** 2

## Accomplishments

- FakeServer class: stateful mock с handle_sync callback — хранит tasks dict, поддерживает online/offline toggle, delta по since, tombstone
- 7 E2E тестов покрывают все SYNC-требования в реальном flow (реальные компоненты + только сервер замокан)
- 2 log-safety теста гарантируют что SecretFilter перехватывает JWT-утечки даже при ошибках auth
- Финальный счёт: 106 тестов → 106 passed (97 существующих + 7 E2E + 2 log-safety)

## Task Commits

1. **Task 1: E2E integration тесты** — `9111136` (test)
2. **Task 2: Log-safety verification** — `6fe00c6` (test)

## Files Created/Modified

- `client/tests/test_e2e_sync.py` — 7 E2E сценариев: happy path, 50 offline, tombstone, conflict, full resync, force_sync в потоке, concurrent writes
- `client/tests/test_logs_no_secrets.py` — 2 log-safety теста: D-29 verification в реальном auth+sync flow

## Decisions Made

**test_server_wins_on_conflict требует stale last_sync_at:**
Когда pending_changes пуст и не stale, `_attempt_sync` возвращает noop без HTTP — это корректный skip. Для верификации server-wins нужен real HTTP round-trip → устанавливаем last_sync_at > 5 минут назад → full resync → сервер возвращает обновлённую задачу.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Исправлена логика test_server_wins_on_conflict**
- **Found during:** Task 1 (test_server_wins_on_conflict не проходил)
- **Issue:** Тест устанавливал `old_ts = 2 секунды назад` — не достаточно для stale threshold (300 сек). `_attempt_sync` пропускал HTTP (skip-условие: нет pending + не stale + last_sync_at есть)
- **Fix:** Изменён offset с 2 секунд на `STALE_THRESHOLD_SECONDS + 60` секунд — гарантирует is_stale=True и full resync
- **Files modified:** client/tests/test_e2e_sync.py
- **Verification:** `python -m pytest client/tests/test_e2e_sync.py -v` → 7 passed
- **Committed in:** 9111136 (Task 1 commit, исправление inline)

---

**Total deviations:** 1 auto-fixed (Rule 1 — логическая ошибка в тестовом сценарии)
**Impact on plan:** Тест теперь верифицирует корректный E2E scenario: stale + full resync + server-wins. Никакого scope creep.

## Issues Encountered

None — все компоненты из планов 04-07 работали корректно в E2E setup.

## User Setup Required

None — тесты полностью автоматические, не требуют внешних сервисов.

## SYNC Requirements Coverage (двойной слой)

| Requirement | Unit test | E2E test |
|-------------|-----------|----------|
| SYNC-01 (init dirs) | test_init_creates_dirs | authed_setup fixture |
| SYNC-02 (optimistic UI) | test_add_task_is_optimistic | test_full_happy_path |
| SYNC-03 (force_sync) | test_force_sync_wakes_immediately | test_force_sync_in_running_thread |
| SYNC-04 (threading.Lock) | test_concurrent_add_and_drain | test_concurrent_ui_writes_during_sync |
| SYNC-05 (server-wins) | test_merge_server_wins | test_server_wins_on_conflict |
| SYNC-06 (UUID stable) | test_task_id_is_uuid | test_offline_50_tasks_no_loss |
| SYNC-07 (full resync) | test_full_resync_on_stale | test_full_resync_after_long_offline |
| SYNC-08 (tombstone) | test_server_tombstone_not_recreated | test_tombstone_not_recreated_on_other_device |

## Next Phase Readiness

Phase 2 (client-core) полностью завершена: 106 тестов, все зелёные.
- AuthManager + LocalStorage + SyncApiClient + SyncManager — production-ready
- D-29 (no secrets in logs) — верифицирован в реальном flow
- Готово для Phase 3 (overlay + system tray)

Известные блокеры Phase 3:
- `overrideredirect(True)` на Windows 11 требует `after(100, ...)` delay
- pystray + Tkinter threading — только `run_detached()` + `root.after(0, fn)` паттерн

---
*Phase: 02-client-core*
*Completed: 2026-04-15*
