---
phase: 02-client-core
plan: "05"
subsystem: storage
tags: [threading, atomic-write, json-cache, pending-queue, tombstone, sync]

# Dependency graph
requires:
  - phase: 02-client-core/02-02
    provides: Task, TaskChange, utcnow_iso models + AppPaths + config constants
provides:
  - LocalStorage class — atomic JSON cache + thread-safe pending queue + tombstone soft-delete
affects: [02-06-sync, 02-07-integration, 03-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Atomic write: os.replace(tmp, dst) — крэш не повреждает cache.json"
    - "Single threading.Lock — защищает весь _data (tasks + pending_changes)"
    - "drain_pending_changes() — атомарный take-and-clear; единственный safe способ для sync thread"
    - "restore_pending_changes() — вернуть в начало очереди при failed push"
    - "soft_delete_task() — tombstone (deleted_at) вместо физического удаления (SYNC-08)"
    - "server-wins merge: сравниваем ISO updated_at строки лексикографически"

key-files:
  created:
    - client/tests/test_storage.py
  modified:
    - client/core/storage.py

key-decisions:
  - "threading.Lock (не RLock) — D-12: никаких nested acquire, простой паттерн"
  - "drain НЕ сохраняет cache.json — сохраняем только после confirmed push (commit_drained)"
  - "merge_from_server возвращает dict с applied/conflicts/tombstones_received для диагностики"
  - "AppPaths injection в __init__ для тестируемости (paths: Optional[AppPaths] = None)"
  - "cleanup_tombstones пропускает задачи с pending op — ждём подтверждения сервера"

patterns-established:
  - "Pattern: _save_locked() вызывается ТОЛЬКО под захваченным self._lock — никогда снаружи"
  - "Pattern: все публичные мутации = with self._lock + _save_locked() в одном блоке"
  - "Pattern: drain → try push → on success: commit_drained; on fail: restore_pending_changes"

requirements-completed: ["SYNC-01", "SYNC-02", "SYNC-04", "SYNC-08"]

# Metrics
duration: 8min
completed: 2026-04-16
---

# Phase 02 Plan 05: LocalStorage Summary

**LocalStorage переписан с нуля: threading.Lock на всех мутациях, atomic write через os.replace(tmp), атомарный drain_pending_changes() для sync thread, soft-delete tombstones (SYNC-08), server-wins merge — 24 теста включая stress-test 5000 concurrent ops без потерь.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-16T03:55:05Z
- **Completed:** 2026-04-16T04:03:00Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- LocalStorage полностью переписан: устранены все race conditions из скелета (Pitfall 5)
- Atomic write через `os.replace(tmp, dst)` — крэш приложения не может повредить cache.json
- `drain_pending_changes()` — единственный thread-safe способ изъять очередь для sync thread
- `soft_delete_task()` реализует tombstone-паттерн (SYNC-08): deleted_at + pending DELETE
- `merge_from_server()` применяет server-wins по updated_at, логирует конфликты с pending
- `cleanup_tombstones()` opportunistic cleanup: только после confirmed push и min_age_seconds
- 24 unit-теста (все зелёные, 3.7s) включая stress-test D-12: 50 потоков x 100 ops = 5000 без потерь и дубликатов

## Task Commits

1. **Task 1: LocalStorage rewrite** - `c88473d` (feat)
2. **Task 2: test_storage.py — 24 тестов** - `b07398f` (test)

**Plan metadata:** создаётся ниже

## Files Created/Modified

- `client/core/storage.py` — полная перезапись: Lock + atomic write + drain/restore + soft-delete + merge + cleanup (362 строки)
- `client/tests/test_storage.py` — 24 unit-теста: lifecycle, mutations, drain/restore, merge, tombstones, concurrent stress (392 строки)

## Deviations from Plan

None — план выполнен точно как написан. Единственное: план говорил 23 теста, реализовано 24 (добавлен `test_soft_delete_already_deleted_returns_false` как очевидная граничная проверка).

## Known Stubs

None — LocalStorage не содержит заглушек. Все публичные методы полностью реализованы.

## Self-Check: PASSED

- `client/core/storage.py` — файл существует, 362 строки
- `client/tests/test_storage.py` — файл существует, 392 строки
- Commit `c88473d` — существует (feat: LocalStorage rewrite)
- Commit `b07398f` — существует (test: 24 тестов)
- `python -m pytest client/tests/test_storage.py -v` → 24 passed
- `python -m pytest client/tests/ -v` → 66 passed
