---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Phase 4 context + UI-SPEC + prototype approved
last_updated: "2026-04-21T00:00:00.000Z"
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 30
  completed_plans: 30
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Быстро записать задачу "в моменте" и не забыть её — даже между двумя PC и телефоном. Speed-of-capture — единственная метрика, которая имеет значение.
**Current focus:** Phase 03 — overlay-system

## Current Position

Phase: 4
Plan: Not started

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
| Phase 03-overlay-system P01 | 2 | 1 tasks | 2 files |
| Phase 03-overlay-system P02 | 3 | 2 tasks | 4 files |
| Phase 03-overlay-system P03 | 4m | 1 tasks | 2 files |
| Phase 03-overlay-system P04 | 3 | 1 tasks | 2 files |
| Phase 03-overlay-system P05 | 5 | 1 tasks | 3 files |
| Phase 03-overlay-system P09 | 2 | 1 tasks | 2 files |
| Phase 03-overlay-system P08 | 15 | 1 tasks | 3 files |
| Phase 03-overlay-system P10 | 3 | 1 tasks | 3 files |

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
- [Phase 03-overlay-system]: headless_tk scope=function — каждый тест получает свежий CTk root для изоляции state
- [Phase 03-overlay-system]: mock_ctypes_dpi с raising=False в monkeypatch.setattr — ctypes.windll атрибуты могут отсутствовать
- [Phase 03-overlay-system]: PALETTES verbatim из UI-SPEC — никакого изобретения hex; shadow_card как rgba() строка для Pillow совместимости
- [Phase 03-overlay-system]: SettingsStore — тонкая обёртка без новой I/O (D-25); UISettings.overlay_position как list[int] для JSON round-trip
- [Phase 03-overlay-system]: Badge тест-координаты (44,4) вместо центра (48,8) — текст badge перекрывает центр ellipse
- [Phase 03-overlay-system]: pulse_t > 1.0 нормализуется как периодичность t=t-int(t), позволяет монотонный счётчик в PulseAnimator
- [Phase 03-overlay-system]: D-19 enforced: pure ctypes EnumDisplayMonitors без pywin32 — нет optional dependency
- [Phase 03-overlay-system]: PITFALL 1/4/6 встроены в OverlayManager с grep-verifiable markers (INIT_DELAY_MS=100, self._tk_image, _validate_position)
- [Phase 03-overlay-system]: headless_tk scope=session — Tcl нельзя пересоздать в одной pytest-сессии
- [Phase 03-overlay-system]: PulseAnimator отдельный модуль (SRP), интегрируется в Plan 03-10 через on_frame callback
- [Phase 03-overlay-system]: autostart: ASCII value name LichnyEzhednevnik вместо кириллицы — frozen-exe safety в HKCU\...\Run
- [Phase 03-overlay-system]: autostart: getattr(sys, 'frozen', False) для auto-detect PyInstaller frozen exe без AttributeError
- [Phase 03-overlay-system]: Mode 'silent' и 'pulse_only' оба блокируют send_toast → returns False (NOTIF-01/04)
- [Phase 03-overlay-system]: winotify импортируется лениво внутри _do_show_toast — graceful degradation если не установлен
- [Phase 03-overlay-system]: Dedup через set((task_id, kind)) — позволяет получить оба уведомления (approaching/overdue) для одной задачи
- [Phase 03-overlay-system]: Login placeholder при auth=False: overlay+tray без main_window/sync/pulse (Phase 4+ реализует login dialog)
- [Phase 03-overlay-system]: _handle_top_changed_from_tray напрямую меняет overlay._overlay.attributes избегая рекурсии через on_top_changed hook

### Pending Todos

None yet.

### Blockers/Concerns

- Фаза 3: `overrideredirect(True)` на Windows 11 требует `after(100, ...)` delay — проверить при первом запуске
- Фаза 3: pystray + Tkinter threading — только `run_detached()` + `root.after(0, fn)` паттерн
- Фаза 4: DnD на CustomTkinter не задокументирован официально — провести research перед планированием
- Фаза 6: CustomTkinter --onefile требует `.spec` + `sys._MEIPASS` chdir — без этого серые виджеты
- Фаза 6: keyring в frozen exe — явный import `keyring.backends.Windows` обязателен

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260421-wng | UX v2: inline-редактирование задачи + sage-палитра overlay + цветная навигация + custom title bar (drag + resize-grip) | 2026-04-21 | e851bab, 0f3d300, 9d150b2, af41c6c | [260421-wng-ux-v2-inline-edit-overlay-title-bar](./quick/260421-wng-ux-v2-inline-edit-overlay-title-bar/) |
| 260421-uxy | UI: новая иконка (крем+синий акцент), рамка 1px главного окна, overlay 56→73px (+30%), явный resize | 2026-04-21 | 9160292 | [260421-uxy-ui-border-width-1-overlay-30-56-73px-off](./quick/260421-uxy-ui-border-width-1-overlay-30-56-73px-off/) |
| 260421-vk4 | DnD fix: перенос задачи на пустой день — DropZone регистрируется на self.frame вместо _body_frame | 2026-04-21 | 076cc69 | [260421-vk4-dnd-dropzone-ds-frame-body-frame](./quick/260421-vk4-dnd-dropzone-ds-frame-body-frame/) |
| 260421-vxz | UX polish: diff-rebuild недели + sync→UI callback + Alt+Z + fade show/hide | 2026-04-21 | 485bee6, e98152d, b18da5e, 444d70e | [260421-vxz-ux-polish-diff-rebuild-sync-ui-callback-](./quick/260421-vxz-ux-polish-diff-rebuild-sync-ui-callback-/) |
| 260422-sue | Главное окно скрыто из taskbar и Alt+Tab: инвертирована EX_STYLE-маска `_apply_borderless` (WS_EX_TOOLWINDOW вместо WS_EX_APPWINDOW) | 2026-04-22 | 84b1f90 | [260422-sue-taskbar-ws-ex-toolwindow-ws-ex-appwindow](./quick/260422-sue-taskbar-ws-ex-toolwindow-ws-ex-appwindow/) |

## Session Continuity

Last session: 2026-04-22T00:00:00.000Z
Stopped at: Quick 260422-sue — WS_EX_TOOLWINDOW применён, ожидание UAT от владельца
Resume file: .planning/phases/04-week-tasks/04-CONTEXT.md
