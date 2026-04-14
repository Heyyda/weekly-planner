---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 01-server-auth-01-06-PLAN.md
last_updated: "2026-04-14T23:41:15.659Z"
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 11
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Быстро записать задачу "в моменте" и не забыть её — даже между двумя PC и телефоном. Speed-of-capture — единственная метрика, которая имеет значение.
**Current focus:** Phase 01 — server-auth

## Current Position

Phase: 01 (server-auth) — EXECUTING
Plan: 7 of 11

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-server-auth P01 | 4 | 3 tasks | 12 files |
| Phase 01-server-auth P02 | 3 | 2 tasks | 8 files |
| Phase 01-server-auth P03 | 4 | 2 tasks | 4 files |
| Phase 01-server-auth P04 | 4 | 3 tasks | 6 files |
| Phase 01-server-auth P05 | 5 | 2 tasks | 4 files |
| Phase 01-server-auth P06 | 263 | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: 6 фаз (Сервер → Ядро → Оверлей+Tray → UI Неделя → Bot → Dist)
- Roadmap: DnD (TASK-05, TASK-06) — высокий риск, требует phase-research перед Фазой 4
- Roadmap: Фазы 3 и 4 требуют `/gsd:ui-phase` до планирования
- Stack: python-jose заменить на PyJWT; keyboard заменить на pynput (см. research/STACK.md)
- [Phase 01-server-auth]: Wave 0: плоские server/*.py файлы не удаляются — остаются до Plan 06 (endpoints)
- [Phase 01-server-auth]: pytest запускается из корня проекта (python -m pytest server/tests/), не из server/
- [Phase 01-server-auth]: Alembic использует sync URL (без +aiosqlite) отдельно от async engine приложения
- [Phase 01-server-auth]: Task.id без server default — UUID генерирует клиент (ключевой SYNC-паттерн Фазы 2)
- [Phase 01-server-auth]: allowed_usernames объявлена как str с alias+property чтобы обойти JSON-декодирование List[str] в pydantic-settings v2
- [Phase 01-server-auth]: engine singleton ленивый (_engine_singleton=None) — импорт engine.py не требует env vars
- [Phase 01-server-auth]: PyJWT вместо python-jose (abandoned): раздельные секреты для access и refresh (D-14), SHA256 для refresh hash
- [Phase 01-server-auth]: HTTPBearer(auto_error=False) для контроля формата ошибок D-18 в get_current_user dependency
- [Phase 01-server-auth]: bcrypt используется напрямую вместо passlib (passlib 1.7.4 несовместима с bcrypt 5.x)
- [Phase 01-server-auth]: SQLite naive datetime нормализуется к UTC в verify_code через replace(tzinfo=utc)
- [Phase 01-server-auth]: created_at в AuthCode передаётся явно из Python для microsecond-precision порядка записей
- [Phase 01-server-auth]: tzdata добавлен в requirements.txt для ZoneInfo('Europe/Moscow') на Windows

### Pending Todos

None yet.

### Blockers/Concerns

- Фаза 3: `overrideredirect(True)` на Windows 11 требует `after(100, ...)` delay — проверить при первом запуске
- Фаза 3: pystray + Tkinter threading — только `run_detached()` + `root.after(0, fn)` паттерн
- Фаза 4: DnD на CustomTkinter не задокументирован официально — провести research перед планированием
- Фаза 6: CustomTkinter --onefile требует `.spec` + `sys._MEIPASS` chdir — без этого серые виджеты
- Фаза 6: keyring в frozen exe — явный import `keyring.backends.Windows` обязателен

## Session Continuity

Last session: 2026-04-14T23:41:15.653Z
Stopped at: Completed 01-server-auth-01-06-PLAN.md
Resume file: None
