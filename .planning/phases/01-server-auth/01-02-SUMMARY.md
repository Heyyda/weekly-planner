---
phase: 01-server-auth
plan: 02
subsystem: database
tags: [sqlalchemy, alembic, sqlite, orm, migrations]

# Dependency graph
requires:
  - phase: 01-server-auth plan 01
    provides: "pyproject.toml, conftest.py с test_engine fixture, структура пакетов server/"
provides:
  - "SQLAlchemy 2.x модели: User, AuthCode, Session, Task (server/db/models.py)"
  - "DeclarativeBase + utcnow() helper (server/db/base.py)"
  - "Alembic конфиг (server/alembic.ini) и первая миграция 0001_initial_schema"
  - "7 unit-тестов на структуру моделей (server/tests/test_models.py)"
affects:
  - "01-server-auth plan 03 (engine + WAL): импортирует Base для create_all"
  - "01-server-auth plan 04 (JWT + sessions): использует Session, User модели"
  - "01-server-auth plan 05 (auth codes): использует AuthCode, User модели"
  - "01-server-auth plan 06 (endpoints): использует все 4 модели через dependency injection"
  - "01-server-auth plan 10 (deploy): вызывает alembic upgrade head на VPS"

# Tech tracking
tech-stack:
  added:
    - "SQLAlchemy 2.0.49 — ORM с Mapped/mapped_column API"
    - "Alembic 1.18.4 — миграции"
  patterns:
    - "SQLAlchemy 2.x DeclarativeBase (не legacy declarative_base())"
    - "Mapped[T] + mapped_column() вместо Column() для type hints"
    - "server_default=func.now() + onupdate=func.now() для server-side timestamps"
    - "Task.id без default — client-generated UUID PK (SYNC-паттерн)"
    - "deleted_at tombstone для soft-delete / SYNC delta"
    - "Alembic sync URL (без +aiosqlite) для миграций при async приложении"

key-files:
  created:
    - "server/db/base.py — DeclarativeBase, utcnow()"
    - "server/db/models.py — User, AuthCode, Session, Task модели"
    - "server/alembic.ini — Alembic конфиг"
    - "server/migrations/env.py — Alembic env с sync URL фиксом"
    - "server/migrations/script.py.mako — шаблон для новых миграций"
    - "server/migrations/README — инструкция по командам Alembic"
    - "server/migrations/versions/0001_initial_schema.py — CREATE TABLE x4"
    - "server/tests/test_models.py — 7 unit-тестов"
  modified: []

key-decisions:
  - "Alembic env.py срезает +aiosqlite из DATABASE_URL — sync connections для миграций (Pitfall 5)"
  - "Task.id без server default — UUID генерирует клиент (SYNC-паттерн из CONTEXT.md)"
  - "server/db.py оставлен без изменений до Plan 03 (engine factory переедет там)"
  - "utcnow() через datetime.now(timezone.utc), не deprecated datetime.utcnow()"

patterns-established:
  - "TDD: тесты написаны до реализации, запущены в RED состоянии, затем GREEN"
  - "Модели импортируются из server.db.models, Base — из server.db.base"
  - "from server.db import models — импорт для регистрации в Base.metadata (нужен Alembic)"

requirements-completed: ["SRV-04", "SRV-06"]

# Metrics
duration: 3min
completed: 2026-04-14
---

# Phase 1 Plan 02: SQLAlchemy модели + Alembic первая миграция Summary

**SQLAlchemy 2.x ORM модели (User, AuthCode, Session, Task) с DeclarativeBase и первая Alembic-миграция, создающая 4 таблицы в SQLite**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-14T23:20:51Z
- **Completed:** 2026-04-14T23:23:58Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- 4 SQLAlchemy 2.x ORM-модели с полями из CONTEXT.md D-21: User (telegram auth), AuthCode (6-digit bcrypt hash, 5min TTL), Session (refresh token hash, revokable), Task (client UUID PK, deleted_at tombstone, server-side updated_at)
- Alembic настроен и проверен: `upgrade head` создаёт 4 таблицы, `downgrade base` откатывает — оба работают корректно
- 7 unit-тестов покрывают структуру моделей (TDD: RED→GREEN) — все зелёные
- SRV-06 закреплён через `onupdate=func.now()` на Task.updated_at и User.updated_at

## Task Commits

1. **Task 1: SQLAlchemy модели + TDD тесты** — `d2baa87` (feat)
2. **Task 2: Alembic настройка + первая миграция** — `c018136` (feat)

**Plan metadata:** будет добавлен в финальный коммит docs

## Files Created/Modified

- `server/db/base.py` — DeclarativeBase + timezone-aware utcnow()
- `server/db/models.py` — User, AuthCode, Session, Task (160 строк)
- `server/tests/test_models.py` — 7 unit-тестов структуры моделей
- `server/alembic.ini` — Alembic конфиг, script_location=migrations
- `server/migrations/env.py` — sync URL фикс (+aiosqlite удаляется), импорт Base.metadata
- `server/migrations/script.py.mako` — шаблон для новых миграций
- `server/migrations/README` — инструкция по Alembic командам
- `server/migrations/versions/0001_initial_schema.py` — CREATE TABLE users, auth_codes, sessions, tasks + индексы

## Decisions Made

- Alembic использует sync SQLite URL (без `+aiosqlite`) — отдельно от async engine приложения (Pitfall 5 из RESEARCH.md)
- Task.id не имеет server default — UUID генерирует клиент, это ключевой паттерн для SYNC в Фазе 2
- `server/db.py` (старый скелет) не тронут — удалится в Plan 03 при переезде engine factory
- `datetime.now(timezone.utc)` вместо deprecated `datetime.utcnow()` (Python 3.12 DeprecationWarning)

## Deviations from Plan

None — план выполнен точно по спецификации.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 03 (engine + WAL): может импортировать `from server.db.base import Base` и `from server.db import models` для `create_all` в тестах
- Plan 04 (JWT + sessions): Session и User модели готовы к использованию
- Plan 05 (auth codes): AuthCode модель готова
- Plan 10 (deploy): `cd server && alembic upgrade head` создаст схему на VPS

---
*Phase: 01-server-auth*
*Completed: 2026-04-14*
