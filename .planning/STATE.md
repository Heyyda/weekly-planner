---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 02-08-PLAN.md (E2E integration tests + log safety — Phase 2 DONE)
last_updated: "2026-04-16T04:14:00.323Z"
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 19
  completed_plans: 19
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Быстро записать задачу "в моменте" и не забыть её — даже между двумя PC и телефоном. Speed-of-capture — единственная метрика, которая имеет значение.
**Current focus:** Phase 02 — client-core

## Current Position

Phase: 02 (client-core) — EXECUTING
Plan: 8 of 8

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
| Phase 01-server-auth P09 | 141 | 2 tasks | 3 files |
| Phase 01-server-auth P07 | 35 | 3 tasks | 4 files |
| Phase 01-server-auth P08 | 30 | 3 tasks | 6 files |
| Phase 02-client-core P01 | 2 | 2 tasks | 5 files |
| Phase 02-client-core P03 | 2 | 1 tasks | 2 files |
| Phase 02-client-core P02 | 3 | 2 tasks | 6 files |
| Phase 02-client-core P04 | 116 | 2 tasks | 2 files |
| Phase 02-client-core P05 | 8 | 2 tasks | 2 files |
| Phase 02-client-core P06 | 2 | 2 tasks | 2 files |
| Phase 02-client-core P07 | 3 | 2 tasks | 2 files |
| Phase 02-client-core P08 | 15 | 2 tasks | 2 files |

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
- [Phase 01-server-auth]: object.__setattr__ для патчинга frozen aiogram Message в тестах (pydantic frozen model)
- [Phase 01-server-auth]: Long-polling (dp.start_polling) выбран для Фазы 1 — проще для VPS без настроенного webhook endpoint
- [Phase 01-server-auth]: Idempotent CREATE в sync: повторный task_id трактуется как UPDATE, не ошибка — клиент может не знать дошёл ли первый CREATE
- [Phase 01-server-auth]: Rate-limit по IP (не username): slowapi key_func синхронный, не может читать async body() — RuntimeError: body read twice (RESEARCH.md Pitfall 6)
- [Phase 01-server-auth]: limiter.reset() в каждом тестовом fixture который вызывает /request-code — slowapi limiter глобальный синглтон, без reset состояние между тестами ломает 429-логику
- [Phase 02-client-core]: client/pyproject.toml отдельный от server/pyproject.toml — клиент синхронный, asyncio_mode не нужен
- [Phase 02-client-core]: requests-mock выбран для client-тестов — thread-safe (важно для SYNC-04 concurrent write тестов)
- [Phase 02-client-core]: tmp_appdata fixture подменяет и APPDATA и LOCALAPPDATA — покрывает fallback D-02
- [Phase 02-client-core]: SecretFilter на root logger — наследуется всеми child-логгерами без дополнительной конфигурации (D-29)
- [Phase 02-client-core]: Идемпотентность setup_client_logging через маркер на root logger object — без глобальных переменных модуля
- [Phase 02-client-core]: KEYRING_SERVICE=WeeklyPlanner (ASCII) — избегаем frozen exe проблему с Cyrillic (D-25, Pitfall 4)
- [Phase 02-client-core]: Task timestamps хранятся как str (ISO 8601 с Z) — минимум conversion при JSON сериализации; lexicographic compare работает если формат единый
- [Phase 02-client-core]: AppPaths — lightweight не-singleton; создаётся по необходимости, легко тестируется через monkeypatch env vars
- [Phase 02-client-core]: access_token только в RAM — keyring хранит только refresh_token (D-26 подтверждён тестами)
- [Phase 02-client-core]: AuthExpiredError из refresh_access перехватывается load_saved_token — возвращает False (не пробрасывается)
- [Phase 02-client-core]: threading.Lock (не RLock) — D-12: никаких nested acquire, простой паттерн
- [Phase 02-client-core]: drain_pending_changes НЕ сохраняет cache.json — сохраняем только после confirmed push
- [Phase 02-client-core]: ApiResult никогда не raise — SyncManager инспектирует поля (offline-tolerant design)
- [Phase 02-client-core]: 401 retry ровно один раз: refresh_access() + retry; второй 401 → auth_expired()
- [Phase 02-client-core]: SYNC-06: task_id стабилен в TaskChange при ретраях — сервер принимает CREATE идемпотентно
- [Phase 02-07]: threading.Event.wait(timeout) вместо time.sleep — force_sync() устанавливает Event, поток просыпается немедленно без ожидания 30s
- [Phase 02-07]: Drain pending ПЕРЕД stale resync (D-20): drained + since=None в одном post_sync вызове, локальные изменения не теряются
- [Phase 02-07]: client error (4xx) останавливает sync loop через _auth_expired флаг — retry при ошибке клиента бессмысленен
- [Phase 02-08]: test_server_wins_on_conflict: использует stale last_sync_at (>5 мин) для триггера full resync — без pending changes _attempt_sync пропускает HTTP
- [Phase 02-08]: FakeServer.handle_sync как callback в requests-mock: stateful behavior без сложных fixture цепочек

### Pending Todos

None yet.

### Blockers/Concerns

- Фаза 3: `overrideredirect(True)` на Windows 11 требует `after(100, ...)` delay — проверить при первом запуске
- Фаза 3: pystray + Tkinter threading — только `run_detached()` + `root.after(0, fn)` паттерн
- Фаза 4: DnD на CustomTkinter не задокументирован официально — провести research перед планированием
- Фаза 6: CustomTkinter --onefile требует `.spec` + `sys._MEIPASS` chdir — без этого серые виджеты
- Фаза 6: keyring в frozen exe — явный import `keyring.backends.Windows` обязателен

## Session Continuity

Last session: 2026-04-16T04:14:00.321Z
Stopped at: Completed 02-08-PLAN.md (E2E integration tests + log safety — Phase 2 DONE)
Resume file: None
