---
phase: 02-client-core
plan: 03
subsystem: logging
tags: [python, logging, RotatingFileHandler, SecretFilter, jwt-masking, observability]

# Dependency graph
requires:
  - phase: 02-02
    provides: AppPaths.logs_dir, config.LOG_FILE_NAME/LOG_ROTATION_* constants
  - phase: 02-01
    provides: pytest infrastructure, tmp_appdata fixture
provides:
  - setup_client_logging(paths) — единая точка инициализации root logger
  - SecretFilter — маскирует Bearer/access_token/refresh_token в любых log-записях
  - reset_client_logging() — сброс для изоляции тестов
affects: [02-04, 02-05, 02-06, 02-07, 03-client-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RotatingFileHandler через AppPaths.logs_dir (D-27)"
    - "Маркер идемпотентности на root logger (_SETUP_MARKER attribute)"
    - "Duck-typed paths parameter — совместимость при параллельной разработке волн"
    - "try/except import для config — graceful fallback при параллельном выполнении"

key-files:
  created:
    - client/core/logging_setup.py
    - client/tests/test_logging.py
  modified: []

key-decisions:
  - "SecretFilter добавляется к root logger (не к конкретным handlers) — наследуется всеми child-логгерами автоматически"
  - "Идемпотентность через getattr/setattr маркер на root logger объекте — без глобальных переменных модуля"
  - "Duck-typed paths argument (Any с .logs_dir) — не требует жёсткой зависимости от AppPaths при импорте"
  - "reset_client_logging() сбрасывает уровни requests/urllib3 чтобы не загрязнять другие тесты"

patterns-established:
  - "SecretFilter pattern: filter() всегда возвращает True, мутирует record.msg и record.args"
  - "TDD: test_logging.py написан до logging_setup.py, 1 passed на RED (test_secret_filter_unit_mask не требует paths)"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-04-16
---

# Phase 02 Plan 03: Logging Setup Summary

**Python RotatingFileHandler с SecretFilter для маскировки JWT-токенов — централизованная инициализация логирования клиента (D-27, D-29)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-16T03:49:56Z
- **Completed:** 2026-04-16T03:52:34Z
- **Tasks:** 1/1
- **Files modified:** 2

## Accomplishments

- `setup_client_logging(paths)` настраивает RotatingFileHandler в `logs_dir/client.log` с maxBytes=1MB, backupCount=5 (D-27)
- `SecretFilter` маскирует Bearer, access_token, refresh_token через regex в record.msg и record.args (D-29)
- Идемпотентность — повторный вызов возвращает тот же RotatingFileHandler, не создаёт дублей
- requests/urllib3/keyring логгеры установлены на WARNING (D-28)
- 6 unit-тестов зелёных, включая изолированный test_secret_filter_unit_mask (не требует AppPaths)

## Task Commits

1. **Task 1: logging_setup с RotatingFileHandler + SecretFilter** - `ec44f8f` (feat)

## Files Created/Modified

- `client/core/logging_setup.py` — setup_client_logging() + SecretFilter + reset_client_logging()
- `client/tests/test_logging.py` — 6 unit-тестов: log file creation, idempotency, bearer masking, refresh_token masking, unit mask, noisy loggers

## Decisions Made

- **SecretFilter на root logger**: фильтр добавляется к root logger а не к handler, чтобы работать со всеми child-логгерами без дополнительной конфигурации
- **Duck-typed paths**: `setup_client_logging(paths: Any)` принимает любой объект с `.logs_dir` — при параллельном выполнении волн paths.py может ещё не существовать при импорте
- **Try/except import config**: константы логирования импортируются с fallback значениями на случай отсутствия config.py (параллельное выполнение Wave 1)

## Deviations from Plan

None — план выполнен точно. Единственная адаптация: duck-typed `paths: Any` вместо `paths: AppPaths` в сигнатуре — предусмотрено `<parallel_awareness>` в задании (не требует rule-violation).

## Issues Encountered

- **Параллельная зависимость**: при запуске 02-03 параллельно с 02-02, `paths.py` и `config.py` ещё не существовали. Решено через:
  1. `try/except ImportError` для config с inline fallback-константами в `logging_setup.py`
  2. Ожидание появления `paths.py` (создан 02-02 через ~30 секунд)
  3. Тесты запущены после появления `paths.py` — все 6 passed

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `logging_setup` готов к использованию в AuthManager (план 02-04), LocalStorage (02-05), SyncManager (02-06, 02-07)
- Паттерн: `from client.core.logging_setup import setup_client_logging` + один вызов при старте app
- Паттерн: `logger = logging.getLogger("client.auth")` внутри модулей — без setup_logging в каждом модуле

---
*Phase: 02-client-core*
*Completed: 2026-04-16*
