---
phase: 02-client-core
plan: 01
subsystem: testing
tags: [pytest, requests-mock, pytest-mock, fixtures, conftest]

# Dependency graph
requires: []
provides:
  - pytest config (client/pyproject.toml) с testpaths=client/tests
  - shared fixtures: tmp_appdata (APPDATA isolation), mock_api (requests-mock), api_base (URL константа)
  - client/requirements-dev.txt с pytest + requests-mock + pytest-mock + pytest-timeout
  - client/tests/ пакет готов к расширению в последующих планах
affects:
  - 02-02 (models)
  - 02-03 (storage)
  - 02-04 (sync)
  - 02-05 (auth)

# Tech tracking
tech-stack:
  added:
    - pytest>=8.0.0
    - pytest-mock>=3.14.0
    - pytest-timeout>=2.2.0
    - requests-mock>=1.12.0
  patterns:
    - "tmp_appdata fixture: monkeypatch.setenv APPDATA + LOCALAPPDATA → изолированный tmp_path"
    - "mock_api fixture: requests_mock.Mocker как контекстный менеджер (thread-safe)"
    - "api_base fixture: строковая константа URL — единственный источник истины для тестов"
    - "TDD: RED (тест без conftest) → GREEN (conftest) → commit каждый этап"

key-files:
  created:
    - client/pyproject.toml
    - client/requirements-dev.txt
    - client/tests/__init__.py
    - client/tests/conftest.py
    - client/tests/test_infrastructure.py
  modified: []

key-decisions:
  - "client/pyproject.toml — отдельный от server/pyproject.toml; asyncio_mode не нужен (client sync)"
  - "requests-mock выбран вместо responses — thread-safe, достаточен для SYNC-тестов"
  - "api_base='https://planner.heyda.ru/api' как fixture-константа — избегаем дублирования в тестах"
  - "LOCALAPPDATA также подменяется в tmp_appdata — fallback для LocalStorage D-02"

patterns-established:
  - "Fixtures в conftest.py используют pytest builtin tmp_path (не создаём tmpdir вручную)"
  - "requests_mock.Mocker через with-блок (yield fixture) — гарантирует cleanup после теста"
  - "monkeypatch.setenv (не os.environ direct) — автоматический rollback между тестами"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-04-16
---

# Phase 2 Plan 01: Тестовая инфраструктура клиента (Wave 0) Summary

**pytest config + shared fixtures (tmp_appdata APPDATA isolation, requests-mock mock_api) для изолированного тестирования client-core без реального сервера и AppData**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-16T03:46:46Z
- **Completed:** 2026-04-16T03:48:44Z
- **Tasks:** 2 (Task 1 auto + Task 2 TDD)
- **Files modified:** 5

## Accomplishments

- pytest обнаруживает `client/tests/` через `client/pyproject.toml` без CollectError
- Fixture `tmp_appdata` подменяет `APPDATA` и `LOCALAPPDATA` через monkeypatch — тесты LocalStorage пишут в tmp_path, не в реальный `%APPDATA%`
- Fixture `mock_api` перехватывает HTTP запросы через `requests_mock.Mocker` — тесты SyncManager/AuthManager не требуют живого сервера
- 3 маркер-теста проходят: `test_infrastructure.py` — `3 passed in 0.02s`

## Task Commits

1. **Task 1: pytest-инфраструктура** - `116470c` (chore)
2. **Task 2 RED: failing tests** - `4ee9b69` (test)
3. **Task 2 GREEN: conftest fixtures** - `200181b` (test)

## Files Created/Modified

- `client/pyproject.toml` — pytest config (testpaths=client/tests, --timeout=10, --strict-markers)
- `client/requirements-dev.txt` — dev-зависимости: pytest + pytest-mock + pytest-timeout + requests-mock
- `client/tests/__init__.py` — маркер пакета тестов
- `client/tests/conftest.py` — shared fixtures: tmp_appdata, mock_api, api_base
- `client/tests/test_infrastructure.py` — 3 маркер-теста Wave 0

## Decisions Made

- `client/pyproject.toml` отдельный от `server/pyproject.toml` — клиент синхронный, asyncio_mode не нужен
- `requests-mock` выбран вместо `responses` — thread-safe (важно для SYNC-04 concurrent tests)
- `api_base` как pytest fixture-константа вместо module-level import — гибкость для будущего переопределения
- `LOCALAPPDATA` также подменяется в `tmp_appdata` — покрывает fallback из D-02 (если APPDATA недоступен)

## Deviations from Plan

None — план выполнен точно как написан.

## Issues Encountered

None.

## User Setup Required

None — зависимости устанавливаются через `pip install -r client/requirements-dev.txt`.

## Next Phase Readiness

- Fixtures `tmp_appdata`, `mock_api`, `api_base` готовы к использованию в планах 02-02..02-05
- `client/tests/` пакет инициализирован — следующие планы просто создают `test_storage.py`, `test_sync.py`, `test_models.py`, `test_auth.py`
- Команда верификации: `python -m pytest client/tests/ -v` → должна показывать все тесты зелёными

---

## Self-Check

*Checking created files and commits...*

- `client/pyproject.toml` — FOUND
- `client/requirements-dev.txt` — FOUND
- `client/tests/__init__.py` — FOUND
- `client/tests/conftest.py` — FOUND
- `client/tests/test_infrastructure.py` — FOUND
- Commit `116470c` — FOUND
- Commit `4ee9b69` — FOUND
- Commit `200181b` — FOUND

## Self-Check: PASSED

---
*Phase: 02-client-core*
*Completed: 2026-04-16*
