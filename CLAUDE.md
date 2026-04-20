# Личный Еженедельник

## Описание
Десктопное приложение — недельный планировщик задач с боковой панелью.
Прячется за край экрана, выезжает при наведении/клике. Один .exe файл.
Название: **Личный Еженедельник**.

## Владелец
Никита (GitHub: Heyyda, email: zibr@yandex.ru). Язык общения: русский.

## Стек
- **Клиент**: Python 3.12+, CustomTkinter, ctypes/win32gui (sidebar), pystray (tray)
- **Сервер**: FastAPI на VPS 109.94.211.29 (рядом с E-bot device-manager.py)
- **БД**: SQLite на сервере (файл `weekly_planner.db`)
- **Авторизация**: JWT + Telegram (как в E-bot)
- **Сборка**: PyInstaller --onefile
- **Автообновление**: SHA256 проверка, как в E-bot

## Архитектура

```
S:\Проекты\ежедневник\
├── CLAUDE.md              ← ты тут
├── README.md
├── .gitignore
├── requirements.txt
├── main.py                ← точка входа (запуск приложения)
│
├── client/                ← весь клиентский код
│   ├── app.py             ← класс WeeklyPlannerApp (главное окно + sidebar логика)
│   ├── ui/
│   │   ├── sidebar.py     ← авто-скрытие за край экрана, анимация выезда
│   │   ├── week_view.py   ← навигация по неделям (стрелки, номер недели, даты)
│   │   ├── day_panel.py   ← сворачиваемая секция дня (заголовок + список задач)
│   │   ├── task_widget.py ← виджет задачи (checkbox + текст + приоритет + действия)
│   │   ├── notes_panel.py ← свободные заметки к дню
│   │   ├── stats_panel.py ← итоги недели (выполнено/просрочено/процент)
│   │   ├── settings_panel.py ← настройки (тема, автозапуск, хоткей, "не беспокоить")
│   │   └── themes.py      ← тёмная/светлая тема (палитры + шрифты)
│   ├── core/
│   │   ├── models.py      ← dataclass: Task, DayPlan, WeekPlan, Category
│   │   ├── storage.py     ← локальный кеш (JSON файл для оффлайн-работы)
│   │   ├── sync.py        ← синхронизация с сервером (pull/push/merge)
│   │   └── auth.py        ← JWT авторизация, Telegram-регистрация
│   ├── utils/
│   │   ├── hotkeys.py     ← глобальный хоткей (Win+Q) для вызова/скрытия
│   │   ├── tray.py        ← иконка в system tray, badge с кол-вом задач
│   │   ├── autostart.py   ← добавление/удаление из автозагрузки Windows
│   │   ├── updater.py     ← проверка обновлений, скачивание, SHA256
│   │   └── notifications.py ← всплывающие напоминания о просроченных задачах
│   └── assets/
│       └── icon.ico        ← иконка приложения (TODO: нарисовать)
│
├── server/                 ← серверная часть (деплоится на VPS)
│   ├── api.py              ← FastAPI роуты: /auth, /tasks, /weeks, /sync
│   ├── models.py           ← SQLAlchemy модели: User, Task, Category
│   ├── auth.py             ← JWT создание/проверка, Telegram webhook
│   ├── db.py               ← подключение к SQLite, миграции
│   └── config.py           ← серверные настройки (порт, секреты, пути)
│
├── build/
│   └── build.bat           ← скрипт сборки PyInstaller
│
└── docs/
    ├── ARCHITECTURE.md     ← подробная архитектура и решения
    ├── API.md              ← спецификация REST API
    └── FEATURES.md         ← полный список фич с приоритетами
```

## Ключевые решения

### Sidebar-поведение
- Окно `overrideredirect=True` (без рамки), `topmost=True`
- Позиционирование: правый край экрана, `x = screen_width - panel_width`
- Скрытое состояние: видна полоска 4px + иконка, остальное за экраном
- Выезд: анимация через `after()` с шагом 10px/16ms
- Win32: `SetWindowPos` с `HWND_TOPMOST` для поверх всех окон

### Синхронизация
- Optimistic UI: задачи сохраняются локально мгновенно, фоновый sync
- Конфликты: server wins (сервер — source of truth)
- Оффлайн: полноценная работа с локальным кешем, sync при восстановлении сети
- Формат: JSON через REST API

### Задачи
- Поля: id, text, done, priority (1-3), day (ISO date), position (порядок), category_id, created_at, updated_at
- Просроченные: задачи с done=false и day < today подсвечиваются красным
- Перенос: меняет day, сохраняет остальное
- Повторяющиеся: шаблон (template) с cron-подобным правилом, генерация при открытии недели

### Авторизация
- Первый запуск → ввод Telegram username → бот отправляет код → ввод кода → JWT
- JWT хранится в keyring (как пароль E-bot)
- Refresh token для бесшовного продления сессии

## Правила разработки
- Коммиты на русском, спрашивать перед пушем
- Не коммитить .env, секреты, keyring данные
- CustomTkinter стиль: минималистичный, как E-bot но элегантнее
- Один файл main.py для точки входа, вся логика в модулях client/
- Сервер деплоится на VPS отдельно от клиента

## Git
- GitHub: https://github.com/Heyyda/weekly-planner (private, создать при первом пуше)
- Ветка: main

## Сборка
```bash
pyinstaller --clean --onefile --windowed --icon=client/assets/icon.ico --add-data "client/assets/icon.ico;client/assets" --name "Личный Еженедельник" main.py
```

## Связанные проекты
- **E-bot** (`S:\Проекты\е-бот\`) — переиспользуем паттерны: авторизация через Telegram, автообновление, system tray, тёмная тема, keyring
- **VPS** (109.94.211.29) — сервер API будет рядом с device-manager.py

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Личный Еженедельник**

Десктопный недельный планировщик для Windows с мобильным дополнением через Telegram-бот. На рабочем столе живёт перетаскиваемый круглый оверлей — клик открывает компактное окно с задачами текущей недели. Задачи синхронизируются между несколькими PC и Telegram-ботом. Владелец и единственный подтверждённый пользователь — Никита, менеджер по снабжению; коллеги возможны как расширение аудитории после валидации на себе.

**Core Value:** Быстро записать задачу, которая прилетела "в моменте" (в перерыве между делами), и не забыть её — даже если записываю на работе с двух экранов и потом доделываю дома. Если speed-of-capture сломан — продукт не нужен. Всё остальное (синхронизация, архив, мобилка) существует чтобы обеспечить этот цикл.

### Constraints

- **Tech stack (client)**: Python 3.12+, CustomTkinter, ctypes/win32gui, pystray — зафиксировано в CLAUDE.md и скелете, менять нецелесообразно
- **Tech stack (server)**: FastAPI + SQLite + SQLAlchemy + python-jose — зафиксировано
- **Инфраструктура**: сервер деплоится на VPS 109.94.211.29 рядом с E-bot-сервисами
- **Дистрибуция**: один `.exe` через `PyInstaller --onefile --windowed` — требование для простоты установки на рабочих PC
- **Коммуникация**: коммиты и документация на русском, UI на русском
- **Аудитория**: Windows 10/11 (DWM-совместимость `overrideredirect`/`SetWindowPos` — потенциальный риск, упомянут в CLAUDE.md)
- **Безопасность**: `.env`, секреты, keyring-данные не коммитятся; JWT в keyring аналогично E-bot
- **Дизайн-ресурс**: визуальная сложность UI должна оставаться низкой (минимализм — требование владельца, а не компромисс)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12+ - Desktop client and FastAPI server
- Batch (.bat) - Build scripts for PyInstaller (`build/build.bat`)
## Runtime
- Python 3.12+ interpreter
- Runs as single executable (PyInstaller --onefile)
- Python 3.12+ with FastAPI/Uvicorn
- Target deployment: VPS 109.94.211.29 (port 8100)
- pip (requirements.txt)
- Lockfile: None (pinned versions only)
## Frameworks
- CustomTkinter 5.2.0+ - Desktop GUI framework with dark/light themes
- FastAPI 0.110.0+ - REST API framework (commented in requirements.txt, deployed separately)
- Uvicorn 0.29.0+ - ASGI server for FastAPI
- python-jose[cryptography] 3.3.0+ - JWT token encoding/decoding
- SQLAlchemy 2.0.0+ - ORM for database models
- passlib[bcrypt] 1.7.4+ - Reserved for future password hashing (not currently used)
## Key Dependencies
- `customtkinter>=5.2.0` - Desktop window, panels, widgets (`client/app.py`)
- `pystray>=0.19.0` - System tray icon with menu (`client/utils/tray.py`)
- `keyboard>=0.13.5` - Global hotkey capture (Win+Q) (`client/utils/hotkeys.py`)
- `keyring>=25.0.0` - Secure credential storage for JWT tokens (`client/core/auth.py`)
- `requests>=2.31.0` - HTTP client for API calls (auth, sync, updates)
- `Pillow>=10.0.0` - Image handling for tray icon and assets
- PyInstaller 6.0.0+ - Bundles Python + dependencies into single .exe
## Configuration
- JWT tokens stored in Windows Credential Manager via `keyring`
- Settings cached locally: `%APPDATA%/ЛичныйЕженедельник/cache.json`
- Hotkey preferences: stored in `cache.json`
- `PLANNER_DB` - SQLite database path (default: `/opt/planner/weekly_planner.db`)
- `PLANNER_JWT_SECRET` - HS256 signing key (MUST be changed in production)
- `PLANNER_TG_BOT_TOKEN` - Telegram bot token for auth flow
- `PLANNER_TG_ADMIN_CHAT` - Admin chat ID for logging
- `PLANNER_EXE_PATH` - Path to latest .exe for updates
- `.gitignore` - Standard Python exclusions
- `build/build.bat` - Windows batch script for PyInstaller
- Client config: `server/config.py` (hardcoded API_BASE, port 8100)
## Build Process
# Generates: dist\Личный Еженедельник.exe
## Platform Requirements
- Windows 10/11 (ctypes, winreg, win32gui APIs)
- Python 3.12+
- pip for dependency installation
- Windows 10/11 only (hardcoded win32 APIs)
- Linux VPS (109.94.211.29)
- Python 3.12+
- SQLite database file writable at `/opt/planner/`
## API Communication
- `POST /api/auth/request` - Request verification code
- `POST /api/auth/verify` - Verify code, get JWT
- `GET /api/weeks/{start}` - Fetch week data
- `POST /api/sync` - Sync pending changes
- `GET /api/version` - Check for updates
## Dependency Management
- requirements.txt uses `>=` pins (minimum versions)
- Server dependencies commented out (deployed separately)
- No lock file (simple environment)
- CustomTkinter requires CTk root before creating widgets
- pystray requires running in separate daemon thread
- keyboard library requires elevated privileges on some Windows versions
- keyring uses Windows Credential Manager backend (platform-specific)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Module files: `lowercase_with_underscores` (e.g., `auth.py`, `task_widget.py`, `hotkeys.py`)
- Class files: match class name if single class per file (e.g., `ThemeManager` → optional: could use `themes.py` or `theme_manager.py`; project uses `themes.py`)
- Configuration: `config.py`, `models.py`, `__init__.py`
- Logical grouping: `client/`, `server/`, `ui/`, `core/`, `utils/` directories
- camelCase for public methods: `toggle_done()`, `request_code()`, `expand()`, `set_appearance_mode()`
- snake_case for internal/private methods with `_` prefix: `_setup()`, `_do_sync()`, `_save_tokens()`, `_move_window()`
- Verb-first convention: `get_week()`, `save_settings()`, `load_saved_token()`, `toggle()`, `delete()`
- snake_case: `panel_width`, `anim_step`, `current_x`, `jwt_token`, `collapse_timer`
- Private instance variables: `_running`, `_thread`, `_hotkey_id`, `_data`
- Constants/class variables: UPPER_CASE: `PANEL_WIDTH`, `ANIMATION_STEP`, `SYNC_INTERVAL`, `SERVICE_NAME`, `APP_DIR`, `DB_PATH`, `JWT_ALGORITHM`
- Type hints used extensively: `Optional[str]`, `list[Task]`, `dict`, `bool`, `int`, `Callable`
- Dataclasses for models: `@dataclass` decorator with typed fields
- Enums for discrete states: `IntEnum` (Priority) and string `Enum` (SidebarState)
## Code Style
- No explicit linter/formatter config detected (no `.eslintrc`, `.prettierrc`, `pylintrc`, `pyproject.toml` with formatting rules found)
- PEP 8 style followed: 4-space indentation, max line length not enforced visually
- Imports at file top, grouped logically
- No linting config detected — style maintained through developer discipline and code review
## Import Organization
- No explicit aliases (no `jsconfig.json`, no `baseUrl` config) — relative imports used throughout
- Pattern: `from client.ui.sidebar import SidebarManager` (fully qualified from project root)
- Relative imports within same package: `from .models import Task` (in `client/core/models.py`)
## Error Handling
- Try/except for network calls: `requests.RequestException` caught silently with `pass` or `return False/None`
- Bare except for generic failures: `except Exception: pass` (in `load_saved_token()`)
- Return `False`/`None` for failure cases instead of raising (graceful degradation for offline)
- Offline-tolerant: network errors logged implicitly (not catching/logging) or ignored (typical for UI apps)
- No explicit try/finally cleanup observed — assumed resources (file handles, network) are properly managed
- `requests.RequestException` is caught for network timeouts and connection errors
- Missing validation on edge cases (e.g., `date.fromisoformat()` could raise if format is wrong) — TODO-level concerns
## Logging
- No logging imports found yet
- TODO: expected to use Python `logging` module on server (FastAPI app)
- Client might use `sys.stdout`/stderr for debug info during dev
## Comments
- Docstrings for classes and public methods (Google/NumPy style observed)
- Russian comments in docstrings allowed and used: `"""Главный класс приложения."""`
- Module-level docstrings at top of every file explaining purpose and usage
- Inline comments for non-obvious logic (minimal in skeleton code)
- Python docstrings follow triple-quote format: `"""Purpose and usage."""`
- Arguments and return types documented in docstrings where needed
- Example from `WeeklyPlannerApp`: docstring lists 5-step lifecycle
## Function Design
- Type hints required: all function parameters and return types are annotated
- Optional parameters use `Optional[Type] = None` pattern
- No `*args/**kwargs` observed — explicit parameters preferred
- Boolean returns for success/failure: `verify_code() -> bool`, `load_saved_token() -> bool`
- Optional returns for nullable data: `get_week(week_start) -> Optional[dict]`
- Explicit `None` vs `False` distinction: `None` = not found, `False` = operation failed
- Methods with side effects return `None` implicitly: `toggle()`, `collapse()`, `save()`
## Module Design
- Classes exported as public (e.g., `WeeklyPlannerApp`, `TaskWidget`, `SyncManager`)
- Private classes/functions prefixed with `_` (e.g., `_sync_loop`, `_save_tokens`)
- No explicit `__all__` lists found
- `client/__init__.py`, `client/core/__init__.py`, `client/ui/__init__.py`, `server/__init__.py` exist but are empty
- No re-exports of submodules; consumers import directly from modules
- Models in `client/core/models.py` designed for JSON serialization via `dataclasses.asdict()` → JSON (implicit, via `json.dump()`)
- No custom `__post_init__` or `__repr__` overrides yet
## Cross-Module Patterns
- Singleton-like pattern: `ThemeManager`, `SidebarManager`, `LocalStorage`, `AuthManager`, `HotkeyManager`, `SyncManager`
- Stateful managers hold internal state (`_data`, `_running`, `_hotkey_id`, etc.)
- Initialization via `__init__()` and optional `setup()`/`init()` methods for lazy initialization
- Centralized configuration: `server/config.py` with `HOST`, `PORT`, `DB_PATH`, `JWT_SECRET` as module-level constants
- Client config inlined in app.py: `PANEL_WIDTH = 360`, `ANIMATION_STEP = 20`
- Settings stored in JSON files: `cache.json` and `settings.json` in `%APPDATA%/ЛичныйЕженедельник/`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Desktop-first**: CustomTkinter GUI on Windows, sidebar auto-hides at screen edge
- **Offline-first**: All changes persist locally, background sync with server
- **Optimistic updates**: UI changes immediately, sync validates against server truth
- **Push-to-top sidebar**: 360px panel slides in/out from right edge, always topmost window
- **JWT + Telegram auth**: Server validates users via Telegram bot, issues JWT tokens
- **Thin API**: Server is primarily data repository and sync conflict resolver
## Layers
- Purpose: Render weekly planner interface, capture user input, visual feedback
- Location: `client/ui/`
- Contains: CustomTkinter widgets (sidebar, week view, day panels, tasks, notes, stats)
- Depends on: `client/core/models` (Task, DayPlan, WeekPlan), `client/core/storage` (load/save), theme colors
- Used by: `client/app.WeeklyPlannerApp`
- Purpose: Manage global app lifecycle, coordinate layers
- Location: `client/app.py`
- Contains: `WeeklyPlannerApp` class - window creation, component initialization, event loop
- Depends on: All UI/core components
- Used by: `main.py` (entry point)
- Purpose: Data models, local persistence, auth, sync orchestration
- Location: `client/core/`
- Contains:
- Depends on: requests (HTTP), keyring (secure storage)
- Used by: UI components, WeeklyPlannerApp
- Purpose: OS integration and background services
- Location: `client/utils/`
- Contains:
- Used by: WeeklyPlannerApp lifecycle
- Purpose: User authentication, data persistence, sync conflict resolution
- Location: `server/`
- Contains:
- Deployed separately to VPS 109.94.211.29:8100
- Depends on: FastAPI, SQLAlchemy, python-jose
## Data Flow
- **UI state**: Stored in component instances (expanded/collapsed days, current week)
- **App state**: `AppState` dataclass - user_id, jwt, theme, hotkey, sidebar position, do_not_disturb
- **Persistent state**: JSON file (weeks, categories, templates, pending changes)
- **Secure state**: Windows keyring (JWT, refresh token, username)
## Key Abstractions
- Purpose: Represents one todo item with metadata
- Examples: `client/core/models.py:Task` (dataclass with id, text, done, priority, day, category_id, timestamps)
- Pattern: Immutable-like (modified in-place but always saved to storage), UUID key, ISO date strings
- Purpose: Aggregates 5 days (Mon-Fri) plus computed metrics
- Examples: `client/core/models.py:WeekPlan`
- Pattern: Contains list of DayPlan, exposes properties (total_tasks, completion_pct, overdue count)
- Purpose: Background thread for server reconciliation
- Examples: `client/core/sync.py:SyncManager`
- Pattern: Daemon thread, 30-sec polling loop, silent on network errors (resilient), force_sync() for urgent operations
- Purpose: Single source of truth for offline work
- Examples: `client/core/storage.py:LocalStorage`
- Pattern: Wraps JSON file, thread-safe via locks (TODO), dict-based access by week_start key
- Purpose: Each panel (sidebar, week_view, day_panel, task_widget) owns its visual representation
- Examples: `client/ui/week_view.py:WeekView`, `client/ui/day_panel.py:DayPanel`, `client/ui/task_widget.py:TaskWidget`
- Pattern: Mutable state (expanded, current_week), _refresh() method to redraw, separation of model (Task dataclass) from view (TaskWidget)
## Entry Points
- Location: `main.py`
- Triggers: User double-clicks `Личный Еженедельник.exe` (built via PyInstaller)
- Responsibilities: Parse version, instantiate WeeklyPlannerApp, run event loop
- Location: `client/app.py:WeeklyPlannerApp.run()`
- Triggers: Called by main.py
- Responsibilities: Call _setup(), enter Tkinter mainloop (blocks until window closes)
- Location: `client/app.py:WeeklyPlannerApp._setup()`
- Triggers: run() method
- Responsibilities: Load theme, sidebar, storage, check auth, render UI, start system tray, register hotkeys, start sync
- Location: `client/core/sync.py:SyncManager._sync_loop()`
- Triggers: Started by start() method in a daemon thread
- Responsibilities: Poll pending_changes every 30 seconds, POST to API, merge response data
- Location: `client/utils/hotkeys.py:HotkeyManager.register()`
- Triggers: App startup, keyboard event at OS level
- Responsibilities: Call toggle() on sidebar when Win+Q pressed, works even if app is unfocused
## Error Handling
## Cross-Cutting Concerns
- Not yet implemented
- TODO: Add logging module, structured JSON output to file in %APPDATA%
- Light validation on models (optional Category, date format)
- Server validates all changes before persisting
- No input sanitization on task text (TODO: XSS if web UI added later)
- JWT tokens via keyring (Windows Credential Manager)
- Telegram Telegram bot as identity provider (no password)
- Refresh token for automatic re-auth (30 days)
- No CORS or rate limiting yet (server behind heyda.ru)
- Global ThemeManager singleton approach planned
- Color palette in `client/ui/themes.py` (DARK, LIGHT dicts)
- Per-widget application of colors (TODO: not implemented yet)
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
