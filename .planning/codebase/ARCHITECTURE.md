# Architecture

**Analysis Date:** 2026-04-14

## Pattern Overview

**Overall:** Client-Server with Optimistic UI + Local-First Storage

**Key Characteristics:**
- **Desktop-first**: CustomTkinter GUI on Windows, sidebar auto-hides at screen edge
- **Offline-first**: All changes persist locally, background sync with server
- **Optimistic updates**: UI changes immediately, sync validates against server truth
- **Push-to-top sidebar**: 360px panel slides in/out from right edge, always topmost window
- **JWT + Telegram auth**: Server validates users via Telegram bot, issues JWT tokens
- **Thin API**: Server is primarily data repository and sync conflict resolver

## Layers

**Presentation (UI):**
- Purpose: Render weekly planner interface, capture user input, visual feedback
- Location: `client/ui/`
- Contains: CustomTkinter widgets (sidebar, week view, day panels, tasks, notes, stats)
- Depends on: `client/core/models` (Task, DayPlan, WeekPlan), `client/core/storage` (load/save), theme colors
- Used by: `client/app.WeeklyPlannerApp`

**Application State:**
- Purpose: Manage global app lifecycle, coordinate layers
- Location: `client/app.py`
- Contains: `WeeklyPlannerApp` class - window creation, component initialization, event loop
- Depends on: All UI/core components
- Used by: `main.py` (entry point)

**Business Logic (Core):**
- Purpose: Data models, local persistence, auth, sync orchestration
- Location: `client/core/`
- Contains:
  - `models.py`: Dataclasses (Task, DayPlan, WeekPlan, Category, RecurringTemplate, AppState)
  - `storage.py`: LocalStorage - read/write JSON cache to `%APPDATA%/ЛичныйЕженедельник/cache.json`
  - `sync.py`: SyncManager - background thread pulls/pushes changes to API
  - `auth.py`: AuthManager - JWT tokens in Windows keyring, Telegram login
- Depends on: requests (HTTP), keyring (secure storage)
- Used by: UI components, WeeklyPlannerApp

**System Utilities:**
- Purpose: OS integration and background services
- Location: `client/utils/`
- Contains:
  - `hotkeys.py`: Global Win+Q hotkey listener (keyboard library)
  - `tray.py`: System tray icon (pystray) with menu
  - `autostart.py`: Windows Registry autostart (not yet implemented)
  - `updater.py`: SHA256 version check, .exe download (not yet implemented)
  - `notifications.py`: Toast alerts for overdue tasks (not yet implemented)
- Used by: WeeklyPlannerApp lifecycle

**Server API (FastAPI):**
- Purpose: User authentication, data persistence, sync conflict resolution
- Location: `server/`
- Contains:
  - `api.py`: FastAPI app with route stubs (version, health checks only)
  - `auth.py`: JWT creation/validation, Telegram code verification
  - `db.py`: SQLAlchemy ORM models (User, TaskRecord, CategoryRecord, DayNote, RecurringTemplate)
  - `config.py`: Environment variables, constants, db path
- Deployed separately to VPS 109.94.211.29:8100
- Depends on: FastAPI, SQLAlchemy, python-jose

## Data Flow

**User Opens App:**
1. `main.py` → creates `WeeklyPlannerApp`
2. `app._setup()` initializes components (theme, storage, auth, sidebar, sync)
3. `storage.init()` loads `cache.json` from disk
4. `auth.load_saved_token()` checks keyring for JWT
5. If no JWT: show login screen → `auth.request_code()` → `auth.verify_code()` → save to keyring
6. `week_view._refresh()` renders current week from `storage.get_week()`
7. `sync.start()` launches background thread
8. `hotkeys.register("win+q", toggle_callback)` and `tray.start()`

**User Adds Task:**
1. UI calls `day_panel.add_task(text, priority)` → creates Task dataclass with UUID
2. Task added to in-memory `DayPlan.tasks` list
3. UI updated immediately (optimistic)
4. `storage.add_pending_change({"op": "create_task", "data": {...}})` queues operation
5. `SyncManager._do_sync()` polls pending changes every 30 seconds
6. `requests.post("/api/sync", {"changes": [...]}, headers={"Authorization": "Bearer JWT"})`
7. Server validates, upserts to SQLite, returns canonical week data
8. Client merges response: `storage.save_week()` overwrites local copy with server truth
9. If conflict: server wins (idempotent overwrites)

**User Checks Off Task:**
1. UI: `task.toggle_done()` → `task.done = not task.done`
2. `DayPlan.done_count` property updates automatically
3. Pending change enqueued
4. Sync cycle sends operation, server updates, local cache harmonized

**Offline Work:**
1. All changes still persist to local JSON
2. `pending_changes` array accumulates operations
3. When network returns: next sync cycle sends queue
4. If last sync was 3 weeks ago, multiple weeks might be out of date
5. After sync: `storage.save_week()` overwrites each week with server data

**State Management:**
- **UI state**: Stored in component instances (expanded/collapsed days, current week)
- **App state**: `AppState` dataclass - user_id, jwt, theme, hotkey, sidebar position, do_not_disturb
- **Persistent state**: JSON file (weeks, categories, templates, pending changes)
- **Secure state**: Windows keyring (JWT, refresh token, username)

## Key Abstractions

**Task Model:**
- Purpose: Represents one todo item with metadata
- Examples: `client/core/models.py:Task` (dataclass with id, text, done, priority, day, category_id, timestamps)
- Pattern: Immutable-like (modified in-place but always saved to storage), UUID key, ISO date strings

**WeekPlan Container:**
- Purpose: Aggregates 5 days (Mon-Fri) plus computed metrics
- Examples: `client/core/models.py:WeekPlan`
- Pattern: Contains list of DayPlan, exposes properties (total_tasks, completion_pct, overdue count)

**SyncManager Worker:**
- Purpose: Background thread for server reconciliation
- Examples: `client/core/sync.py:SyncManager`
- Pattern: Daemon thread, 30-sec polling loop, silent on network errors (resilient), force_sync() for urgent operations

**LocalStorage Cache:**
- Purpose: Single source of truth for offline work
- Examples: `client/core/storage.py:LocalStorage`
- Pattern: Wraps JSON file, thread-safe via locks (TODO), dict-based access by week_start key

**UI Components as Stateful Objects:**
- Purpose: Each panel (sidebar, week_view, day_panel, task_widget) owns its visual representation
- Examples: `client/ui/week_view.py:WeekView`, `client/ui/day_panel.py:DayPanel`, `client/ui/task_widget.py:TaskWidget`
- Pattern: Mutable state (expanded, current_week), _refresh() method to redraw, separation of model (Task dataclass) from view (TaskWidget)

## Entry Points

**Client Executable:**
- Location: `main.py`
- Triggers: User double-clicks `Личный Еженедельник.exe` (built via PyInstaller)
- Responsibilities: Parse version, instantiate WeeklyPlannerApp, run event loop

**WeeklyPlannerApp.run():**
- Location: `client/app.py:WeeklyPlannerApp.run()`
- Triggers: Called by main.py
- Responsibilities: Call _setup(), enter Tkinter mainloop (blocks until window closes)

**_setup() Initialization Sequence:**
- Location: `client/app.py:WeeklyPlannerApp._setup()`
- Triggers: run() method
- Responsibilities: Load theme, sidebar, storage, check auth, render UI, start system tray, register hotkeys, start sync

**Sync Background Thread:**
- Location: `client/core/sync.py:SyncManager._sync_loop()`
- Triggers: Started by start() method in a daemon thread
- Responsibilities: Poll pending_changes every 30 seconds, POST to API, merge response data

**Hotkey Listener:**
- Location: `client/utils/hotkeys.py:HotkeyManager.register()`
- Triggers: App startup, keyboard event at OS level
- Responsibilities: Call toggle() on sidebar when Win+Q pressed, works even if app is unfocused

## Error Handling

**Strategy:** Fail-soft offline-first approach

**Patterns:**

1. **Network unavailable**: `SyncManager._do_sync()` catches `requests.RequestException` and silently continues (resilient)
   - Example: `client/core/sync.py` lines 86-87
   - Effect: UI keeps working with stale data, sync retries on next cycle

2. **Auth failure**: `AuthManager._validate_token()` catches connection errors and assumes valid offline
   - Example: `client/core/auth.py` line 101
   - Effect: Offline work continues, token refresh deferred until network returns

3. **Keyring unavailable**: `AuthManager.load_saved_token()` broad exception catch
   - Example: `client/core/auth.py` lines 44-45
   - Effect: Return False, trigger login screen

4. **Missing cache file**: `LocalStorage.init()` checks file existence before load
   - Example: `client/core/storage.py` line 54
   - Effect: Creates new empty cache, app starts with blank week

5. **Concurrent writes**: Lock pattern planned but not implemented
   - TODO: `client/core/storage.py` line 40 mentions threading.Lock
   - Risk: UI thread reads while sync thread writes (rare but possible)

## Cross-Cutting Concerns

**Logging:** 
- Not yet implemented
- TODO: Add logging module, structured JSON output to file in %APPDATA%

**Validation:**
- Light validation on models (optional Category, date format)
- Server validates all changes before persisting
- No input sanitization on task text (TODO: XSS if web UI added later)

**Authentication:**
- JWT tokens via keyring (Windows Credential Manager)
- Telegram Telegram bot as identity provider (no password)
- Refresh token for automatic re-auth (30 days)
- No CORS or rate limiting yet (server behind heyda.ru)

**Theme:**
- Global ThemeManager singleton approach planned
- Color palette in `client/ui/themes.py` (DARK, LIGHT dicts)
- Per-widget application of colors (TODO: not implemented yet)

---

*Architecture analysis: 2026-04-14*
