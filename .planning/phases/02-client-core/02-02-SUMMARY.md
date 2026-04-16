---
phase: 02-client-core
plan: "02"
subsystem: core
tags: [dataclass, uuid, wire-format, sync, appdata, keyring, config, paths]

requires:
  - phase: 02-01
    provides: pytest инфраструктура, conftest fixtures (tmp_appdata, mock_api)

provides:
  - "Task dataclass зеркалит server TaskState: UUID client-side, user_id, deleted_at, time_deadline"
  - "TaskChange.to_wire() — сериализация в server wire-format (CREATE/UPDATE/DELETE partial)"
  - "utcnow_iso() — UTC timestamp с суффиксом Z, совместимый с server_timestamp"
  - "AppPaths — резолюция %APPDATA% с fallback LOCALAPPDATA → cwd"
  - "config.py — централизованные константы (API_BASE, SYNC_INTERVAL, BACKOFF, KEYRING_SERVICE)"
  - "client/core/__init__.py — публичный API ядра (re-exports)"

affects:
  - 02-03-logging
  - 02-04-storage
  - 02-05-sync
  - 02-06-auth
  - phase-03-overlay
  - phase-04-ui-week

tech-stack:
  added: []
  patterns:
    - "client-side UUID generation via uuid.uuid4() (SYNC-06 — идемпотентный CREATE)"
    - "to_wire() pattern — отдельная сериализация для wire-format vs cache-format"
    - "APPDATA fallback chain: APPDATA → LOCALAPPDATA → cwd (D-02)"
    - "ASCII keyring service name WeeklyPlanner (избегает frozen exe проблему, D-25)"
    - "utcnow_iso() — строка с Z суффиксом для lexicographic timestamp compare"

key-files:
  created:
    - client/core/config.py
    - client/core/paths.py
    - client/tests/test_models.py
    - client/tests/test_paths.py
  modified:
    - client/core/models.py
    - client/core/__init__.py

key-decisions:
  - "Task dataclass хранит все timestamps как str (ISO 8601) — никаких datetime объектов в модели (D-05)"
  - "KEYRING_SERVICE=WeeklyPlanner (ASCII) — не Cyrillic — избегаем frozen exe проблему (D-25, Pitfall 4)"
  - "TaskChange.to_wire() для UPDATE исключает None поля — partial update (сервер не трогает неуказанные поля)"
  - "AppPaths — lightweight, не singleton — создаётся по необходимости, не хранит состояние"
  - "utcnow_iso() заменяет replace('+00:00', 'Z') — одно место, нет дублирования"

patterns-established:
  - "to_wire(): wire-format сериализация отдельно от to_dict() (cache-format)"
  - "is_alive() / is_overdue(): поведенческие методы на dataclass вместо внешних функций"
  - "from_dict(to_dict(obj)) roundtrip: паттерн для cache persistence тестирования"
  - "_resolve_appdata_root(): module-level helper (не метод класса) — testable через monkeypatch"

requirements-completed: [SYNC-06]

duration: 3min
completed: "2026-04-15"
---

# Phase 2 Plan 02: Models + Paths + Config Summary

**Task dataclass зеркалит server TaskState (UUID client-side, deleted_at, time_deadline), TaskChange.to_wire() обеспечивает wire-format совместимость, AppPaths разрешает %APPDATA% с fallback, config.py централизует все константы (KEYRING_SERVICE=WeeklyPlanner)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-15T11:09:52Z
- **Completed:** 2026-04-15T11:12:43Z
- **Tasks:** 2/2
- **Files modified:** 6

## Accomplishments

- Полная перезапись client/core/models.py: убраны Priority/Category/RecurringTemplate, добавлены user_id/deleted_at/time_deadline, TaskChange с to_wire() partial update
- client/core/config.py с централизованными константами — единый source of truth для API_BASE, SYNC_INTERVAL, BACKOFF, KEYRING_SERVICE, LOG_ROTATION
- client/core/paths.py с AppPaths и APPDATA fallback chain; client/core/__init__.py ре-экспортирует публичный API
- 18 новых unit-тестов: 11 models (UUID, wire-format, overdue, DayPlan/WeekPlan) + 7 paths (APPDATA fallback, ensure, config constants)
- Суммарно 27/27 client тестов зелёных (3 infra + 6 logging + 11 models + 7 paths)

## Task Commits

1. **Task 1: Переписать models.py — Task + TaskChange + DayPlan + WeekPlan + utcnow_iso** - `bff9679` (feat)
2. **Task 2: Создать paths.py + config.py + обновить __init__.py** - `1a81614` (feat)

**Plan metadata:** _(docs commit follows)_

_Note: Оба task — TDD (RED → GREEN); REFACTOR не потребовался_

## Files Created/Modified

- `client/core/models.py` — Полная перезапись: Task/TaskChange/DayPlan/WeekPlan/AppState + utcnow_iso
- `client/core/config.py` — Новый: API_BASE, SYNC_INTERVAL, BACKOFF, KEYRING_SERVICE, LOG_ROTATION
- `client/core/paths.py` — Новый: AppPaths с APPDATA→LOCALAPPDATA→cwd fallback
- `client/core/__init__.py` — Обновлён: ре-экспорт Task, TaskChange, AppPaths, config
- `client/tests/test_models.py` — Новый: 11 unit-тестов моделей
- `client/tests/test_paths.py` — Новый: 7 unit-тестов путей и конфигурации

## Decisions Made

- **ASCII keyring service name:** KEYRING_SERVICE="WeeklyPlanner" (не "ЛичныйЕженедельник") — PITFALLS Pitfall 4 подтверждает что Cyrillic ломается в frozen exe; ASCII избегает проблему с самого начала, migration не нужна позже
- **str timestamps в dataclass:** Task хранит created_at/updated_at/deleted_at как str (не datetime) — минимум conversion при JSON сериализации через asdict(); сравнение ISO strings лексикографически (требует единого формата с Z суффиксом)
- **Lightweight AppPaths:** не singleton, не сохраняет state — создаётся по необходимости, легко тестировать через monkeypatch env vars

## Deviations from Plan

None — план выполнен точно как написан.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **02-03 (logging):** config.LOG_ROTATION_MAX_BYTES, config.LOG_ROTATION_BACKUP_COUNT, AppPaths.logs_dir готовы
- **02-04 (storage):** Task.to_dict(), TaskChange.to_dict()/from_dict(), AppPaths.cache_file/.settings_file готовы
- **02-05 (sync):** TaskChange.to_wire(), config.SYNC_INTERVAL_SECONDS, config.BACKOFF_BASE/CAP, config.STALE_THRESHOLD_SECONDS готовы
- **02-06 (auth):** config.KEYRING_SERVICE, config.KEYRING_REFRESH_KEY/USERNAME_KEY готовы

Никаких блокеров для следующих планов.

---
*Phase: 02-client-core*
*Completed: 2026-04-15*
