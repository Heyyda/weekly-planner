---
phase: 01-server-auth
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, sqlalchemy, aiosqlite, fastapi, aiogram, pyjwt]

# Dependency graph
requires: []
provides:
  - pytest инфраструктура для всех последующих plans в Фазе 1 (server/tests/)
  - pyproject.toml с asyncio_mode=auto и testpaths=tests
  - requirements.txt + requirements-dev.txt с декларированными версиями зависимостей
  - server/{api,auth,db,bot}/__init__.py — пустые subpackage markers
  - server/tests/conftest.py — skeleton fixtures (test_engine, db_session, client заглушка)
  - .gitignore обновлён для защиты секретов и артефактов
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-07, 01-08, 01-09, 01-10, 01-11]

# Tech tracking
tech-stack:
  added:
    - pytest>=8.0.0
    - pytest-asyncio>=0.23.0 (asyncio_mode=auto)
    - pytest-cov>=4.1.0
    - pytest-timeout>=2.2.0
    - aiosqlite>=0.20.0 (in-memory SQLite для тестов)
    - sqlalchemy>=2.0.30 (async engine)
  patterns:
    - "pytest-asyncio auto mode: все async тесты подхватываются без @pytest.mark.asyncio"
    - "sqlite+aiosqlite:///:memory: для изолированных тестовых баз"
    - "pytest_asyncio.fixture для async fixtures"
    - "Закомментированные импорты в conftest.py раскомментируются по мере появления кода (plans 02-06)"

key-files:
  created:
    - server/pyproject.toml
    - server/requirements.txt
    - server/requirements-dev.txt
    - server/api/__init__.py
    - server/auth/__init__.py
    - server/db/__init__.py
    - server/bot/__init__.py
    - server/tests/__init__.py
    - server/tests/conftest.py
    - server/tests/test_infrastructure.py
  modified:
    - server/__init__.py (добавлен комментарий)
    - .gitignore (добавлены .pytest_cache, *.exe, *.db-wal, .env.production)

key-decisions:
  - "Wave 0 не удаляет существующие плоские файлы (server/api.py, auth.py, db.py, config.py) — они остаются до Plan 06"
  - "conftest.py содержит закомментированные импорты из server.api.app — будут раскомментированы в Plan 06"
  - "pytest запускается из корня проекта: python -m pytest server/tests/ (PYTHONPATH=project root)"

patterns-established:
  - "Запуск тестов: из корня проекта `python -m pytest server/tests/ -x --timeout=10`"
  - "conftest fixtures: test_engine (in-memory SQLite), db_session, client (заглушка до Plan 06)"
  - "Все server subpackages именуются server.{api,auth,db,bot} (не server.server.*)"

requirements-completed: []

# Metrics
duration: 4min
completed: 2026-04-14
---

# Phase 01 Plan 01: Тестовая инфраструктура и структура subpackages — Summary

**pytest 8.x + asyncio_mode=auto, in-memory SQLite fixtures, 12 production deps + 4 dev deps, subpackages server/{api,auth,db,bot} как пустые namespace placeholders**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-14T23:14:14Z
- **Completed:** 2026-04-14T23:18:30Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- pyproject.toml с pytest конфигом (asyncio_mode=auto, testpaths=tests, --strict-markers)
- requirements.txt (12 production-зависимостей для VPS) + requirements-dev.txt (pytest suite)
- Структура server/{api,auth,db,bot}/\_\_init\_\_.py и server/tests/conftest.py с skeleton fixtures
- Маркер-тест test_infrastructure.py: 3/3 passed за 0.08s

## Task Commits

Каждый task зафиксирован атомарно:

1. **Task 1: pyproject.toml, requirements.txt, requirements-dev.txt** - `7af02b1` (chore)
2. **Task 2: subpackages и conftest.py** - `d0ab0fe` (chore)
3. **Task 3: test_infrastructure.py, 3 passed** - `42b8aaf` (test)

## Files Created/Modified

- `server/pyproject.toml` — pytest config: asyncio_mode=auto, testpaths=tests, 2 кастомных маркера
- `server/requirements.txt` — 12 production deps (fastapi, sqlalchemy, pyjwt, aiogram и др.)
- `server/requirements-dev.txt` — 4 dev deps + -r requirements.txt
- `server/api/__init__.py` — namespace marker (Plan 06 наполнит)
- `server/auth/__init__.py` — namespace marker (Plans 04-05 наполнят)
- `server/db/__init__.py` — namespace marker (Plans 02-03 наполнят)
- `server/bot/__init__.py` — namespace marker (Plan 09 наполнит)
- `server/tests/__init__.py` — package marker для imports
- `server/tests/conftest.py` — fixtures: test_engine (in-memory SQLite), db_session, client (заглушка), mock_telegram_send
- `server/tests/test_infrastructure.py` — 3 маркер-теста Wave 0
- `server/__init__.py` — добавлен комментарий о назначении
- `.gitignore` — добавлены .pytest_cache, *.exe, *.db-wal, .env.production

## Decisions Made

- Существующие плоские файлы (server/api.py, auth.py, db.py, config.py) не удаляются — остаются параллельно с subpackages до Plan 06. Это сознательный выбор: не ломать импорт `from server.api import app` пока новая структура строится.
- conftest.py содержит закомментированные импорты `from server.db.engine import Base` и `from server.api.app import app` — будут раскомментированы по мере появления реальных модулей.
- pytest запускается из корня проекта (`python -m pytest server/tests/`) чтобы `server` был в PYTHONPATH автоматически.

## Deviations from Plan

None — план выполнен точно как написан. Единственное замечание: план предполагал `cd server && pytest`, но фактически нужен `PYTHONPATH=.. pytest` или запуск из корня. Оба варианта работают (проверено).

## Issues Encountered

- Windows cp1251 кодировка при чтении файлов с кириллическими комментариями через subprocess — решено добавлением `encoding='utf-8'` в python -c команды верификации. Не влияет на работу кода.

## User Setup Required

None — только локальная установка зависимостей: `pip install -r server/requirements-dev.txt`

## Known Stubs

- `server/tests/conftest.py:client()` — заглушка с `pytest.skip(...)`, активируется в Plan 06 когда `server/api/app.py` существует.
- `server/tests/conftest.py:mock_telegram_send()` — возвращает пустой list, реальная логика добавится в Plan 05.

Оба стаба намеренны и не блокируют цель Plan 01 (pytest инфраструктура работает, 3/3 passed).

## Next Phase Readiness

- Plans 02-11 могут добавлять `server/tests/test_xxx.py` и запускать через `python -m pytest server/tests/ -x --timeout=10`
- Plan 02 (SQLAlchemy models) должен раскомментировать `from server.db.engine import Base` в conftest.py
- Plan 06 (auth endpoints) должен раскомментировать `from server.api.app import app` и активировать `client` fixture

---
*Phase: 01-server-auth*
*Completed: 2026-04-14*

## Self-Check: PASSED

**Files verified:**
- server/pyproject.toml: EXISTS
- server/requirements.txt: EXISTS
- server/requirements-dev.txt: EXISTS
- server/api/__init__.py: EXISTS
- server/auth/__init__.py: EXISTS
- server/db/__init__.py: EXISTS
- server/bot/__init__.py: EXISTS
- server/tests/__init__.py: EXISTS
- server/tests/conftest.py: EXISTS
- server/tests/test_infrastructure.py: EXISTS

**Commits verified:**
- 7af02b1: EXISTS (pyproject.toml + requirements)
- d0ab0fe: EXISTS (subpackages + conftest)
- 42b8aaf: EXISTS (test_infrastructure.py)

**pytest result:** 3 passed in 0.08s
