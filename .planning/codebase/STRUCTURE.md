# Codebase Structure

**Analysis Date:** 2026-04-14

## Directory Layout

```
s:\Проекты\ежедневник/
├── main.py                    # Entry point - creates and runs WeeklyPlannerApp
├── requirements.txt           # pip dependencies (client side only)
├── README.md                  # Project overview (TODO: write)
├── CLAUDE.md                  # Project specifications and rules
├── .gitignore                 # Standard Python ignores (TODO: add .env, *.exe, build/)
│
├── client/                    # All client-side code (desktop app)
│   ├── __init__.py
│   ├── app.py                 # WeeklyPlannerApp - main window and lifecycle
│   │
│   ├── ui/                    # UI components (CustomTkinter widgets)
│   │   ├── __init__.py
│   │   ├── sidebar.py         # SidebarManager - slide in/out from screen edge
│   │   ├── week_view.py       # WeekView - week navigation and day list container
│   │   ├── day_panel.py       # DayPanel - collapsible day section with tasks
│   │   ├── task_widget.py     # TaskWidget - single task row (checkbox, text, menu)
│   │   ├── notes_panel.py     # NotesPanel - free-form text notes for a day (stub)
│   │   ├── stats_panel.py     # StatsPanel - week summary (completed/overdue/%) (stub)
│   │   ├── settings_panel.py  # SettingsPanel - preferences UI (stub)
│   │   ├── themes.py          # ThemeManager - color palettes (DARK, LIGHT) and fonts
│   │   └── styles.py          # (planned) CSS-like theme application helper
│   │
│   ├── core/                  # Business logic and data management
│   │   ├── __init__.py
│   │   ├── models.py          # Dataclasses: Task, DayPlan, WeekPlan, Category, AppState
│   │   ├── storage.py         # LocalStorage - JSON cache in %APPDATA%/ЛичныйЕженедельник/
│   │   ├── sync.py            # SyncManager - background sync with server
│   │   └── auth.py            # AuthManager - JWT tokens, Telegram login
│   │
│   ├── utils/                 # System integration utilities
│   │   ├── __init__.py
│   │   ├── hotkeys.py         # HotkeyManager - global Win+Q listener
│   │   ├── tray.py            # TrayManager - system tray icon with menu
│   │   ├── autostart.py       # (planned) Windows Registry autostart setup
│   │   ├── updater.py         # (planned) Version check and .exe download with SHA256
│   │   └── notifications.py   # (planned) Toast notifications for overdue tasks
│   │
│   ├── assets/                # Static files
│   │   └── icon.ico           # Application icon (TODO: design)
│   │
│   └── ui/
│       └── (future) components/  # Reusable custom widgets
│
├── server/                    # FastAPI backend (deployed separately to VPS)
│   ├── __init__.py
│   ├── api.py                 # FastAPI app with route stubs (auth, sync, version)
│   ├── auth.py                # JWT token creation, Telegram code verification
│   ├── models.py              # (planned) Pydantic request/response schemas
│   ├── db.py                  # SQLAlchemy ORM: User, TaskRecord, Category, DayNote, RecurringTemplate
│   ├── config.py              # Environment config, constants, database path
│   └── (planned)
│       ├── routes/            # Endpoint handlers by domain (auth.py, tasks.py, etc.)
│       ├── services/          # Business logic (conflict resolution, recurring task generation)
│       └── migrations/        # Alembic database migrations
│
├── build/                     # PyInstaller build artifacts
│   ├── build.bat              # Build script: `pyinstaller ... main.py`
│   └── (generated)
│       ├── build/             # Build folder (PyInstaller)
│       ├── dist/              # Output folder (.exe file here)
│       └── *.spec             # PyInstaller spec file
│
└── docs/                      # Documentation
    ├── ARCHITECTURE.md        # Detailed architecture and decisions
    ├── API.md                 # REST API specification (endpoints, request/response)
    └── FEATURES.md            # Feature list with priorities
```

## Directory Purposes

**client/ (Desktop Application):**
- Purpose: Everything for the CustomTkinter GUI app
- Contains: UI widgets, models, auth, storage, utils
- Key files: `app.py` (orchestrator), `core/models.py` (data), `ui/*.py` (presentation)

**client/ui/ (Presentation Layer):**
- Purpose: CustomTkinter widgets, layout, themes
- Contains: Sidebar, week view, day panels, task widgets, settings UI
- Key files: `sidebar.py` (slide animation), `week_view.py` (week nav), `day_panel.py` (day container), `themes.py` (colors)

**client/core/ (Business Logic):**
- Purpose: Data models, local persistence, auth, sync
- Contains: Task/DayPlan/WeekPlan dataclasses, JSON cache, sync thread, JWT keyring
- Key files: `models.py` (schema), `storage.py` (local cache), `sync.py` (server sync), `auth.py` (login)

**client/utils/ (System Integration):**
- Purpose: OS-level features - hotkeys, tray, autostart, updates, notifications
- Contains: keyboard library hookups, pystray integration, Windows Registry access
- Key files: `hotkeys.py` (Win+Q listener), `tray.py` (system tray icon), `updater.py` (auto-update)

**server/ (Backend API):**
- Purpose: Data repository, auth provider, sync resolver (depl separately)
- Contains: FastAPI routes, SQLAlchemy ORM, JWT/Telegram auth, SQLite database
- Key files: `api.py` (endpoints), `db.py` (schema), `auth.py` (token logic), `config.py` (secrets)

**build/ (Packaging):**
- Purpose: PyInstaller configuration and output
- Contains: build.bat script, spec file, dist folder with .exe
- Generated by: `pyinstaller --onefile ... main.py` from build.bat

**docs/ (Documentation):**
- Purpose: Architecture decisions, API spec, feature roadmap
- Contains: Design docs, endpoint reference, backlog
- Key files: `ARCHITECTURE.md` (this file), `API.md` (routes), `FEATURES.md` (backlog)

## Key File Locations

**Entry Points:**
- `main.py`: Application entry point - imports WeeklyPlannerApp, calls run()
- `client/app.py`: WeeklyPlannerApp class - window setup, component initialization
- `server/api.py`: FastAPI app instance (deployed to VPS)

**Configuration:**
- `requirements.txt`: pip dependencies (client only)
- `server/config.py`: Environment vars, db path, JWT secrets, Telegram token
- `client/ui/themes.py`: Color palettes (DARK, LIGHT) and font definitions

**Core Logic:**
- `client/core/models.py`: Task, DayPlan, WeekPlan, Category, AppState dataclasses
- `client/core/storage.py`: LocalStorage - reads/writes `%APPDATA%/ЛичныйЕженедельник/cache.json`
- `client/core/sync.py`: SyncManager - background thread syncs to API
- `client/core/auth.py`: AuthManager - Telegram login, JWT token management

**UI Components:**
- `client/ui/sidebar.py`: SidebarManager - window positioning and slide animation
- `client/ui/week_view.py`: WeekView - week navigation, day list, title formatting
- `client/ui/day_panel.py`: DayPanel - collapsible day section
- `client/ui/task_widget.py`: TaskWidget - single task row

**System Integration:**
- `client/utils/hotkeys.py`: HotkeyManager - global Win+Q hotkey
- `client/utils/tray.py`: TrayManager - system tray icon and menu
- `client/utils/autostart.py`: AutostartManager - Windows Registry modifications (stub)
- `client/utils/updater.py`: UpdaterManager - version check and .exe download (stub)
- `client/utils/notifications.py`: Notifications - toast alerts (stub)

**Server:**
- `server/api.py`: FastAPI app with route definitions (version, health, auth, sync endpoints)
- `server/db.py`: SQLAlchemy models (User, TaskRecord, CategoryRecord, DayNote, RecurringTemplate)
- `server/auth.py`: JWT token functions, Telegram code verification

**Testing:**
- Not yet created (plan: `tests/` directory with pytest)

## Naming Conventions

**Files:**
- Snake_case: `week_view.py`, `day_panel.py`, `task_widget.py`
- Purpose in name: `sidebar.py` (sidebar logic), `themes.py` (themes), `models.py` (data definitions)
- Grouped by domain: `ui/` for widgets, `core/` for business logic, `utils/` for system services

**Directories:**
- Plural for collections: `client/ui/`, `server/routes/` (when created)
- Functional names: `core/` (business logic), `utils/` (utilities), `assets/` (static)

**Classes:**
- PascalCase: `WeeklyPlannerApp`, `SidebarManager`, `LocalStorage`, `SyncManager`, `AuthManager`
- Suffix _Manager for coordinator classes: `SidebarManager`, `ThemeManager`, `HotkeyManager`, `TrayManager`
- Suffix _View for UI containers: `WeekView`
- Suffix _Panel for UI sections: `DayPanel`, `NotesPanel`, `StatsPanel`, `SettingsPanel`
- Suffix _Widget for UI components: `TaskWidget`

**Functions:**
- Snake_case with descriptive names: `_setup()`, `_refresh()`, `toggle()`, `load_saved_token()`, `get_week_title()`
- Prefix underscore for private/internal: `_setup()`, `_refresh()`, `_sync_loop()`, `_do_sync()`

**Variables & Properties:**
- Snake_case: `current_week_start`, `panel_width`, `is_today`, `jwt_token`, `pending_changes`
- All-caps for constants: `PANEL_WIDTH = 360`, `SYNC_INTERVAL = 30`, `API_BASE = "..."`
- Prefix underscore for private: `_running`, `_data`, `_thread`

**Types (Dataclasses):**
- PascalCase: `Task`, `DayPlan`, `WeekPlan`, `Category`, `RecurringTemplate`, `AppState`
- Enums also PascalCase: `Priority` (IntEnum), `SidebarState` (Enum)

## Where to Add New Code

**New Feature (e.g., "Repeat Task" button):**
- Logic: Modify `client/core/models.py` (add RecurringTemplate if needed), `client/core/sync.py` (new operation type)
- UI: Add button to `client/ui/task_widget.py`, modal dialog in `client/ui/` (new file)
- Tests: `tests/test_recurring.py`
- Server: New endpoint `POST /api/templates` in `server/api.py`, handler in `server/services/` (new)

**New UI Component (e.g., Category selector):**
- Implementation: `client/ui/category_selector.py` (new file)
- Integration: Import in `client/ui/__init__.py`, use in `client/ui/task_widget.py`
- Styling: Add colors to `client/ui/themes.py`

**New Utility Module (e.g., Logger):**
- Implementation: `client/utils/logger.py` (new file)
- Integration: Import in `client/app.py`, use throughout

**New Server Endpoint (e.g., GET /api/categories):**
- Implementation: Handler function in `server/api.py` (initially) or `server/routes/categories.py` (when refactored)
- Models: Request/response schemas in `server/models.py` (plan to create)
- Database: Use existing `CategoryRecord` from `server/db.py`

**New Local Cache Feature (e.g., star favorite tasks):**
- Storage: Add new field to `Task` in `client/core/models.py`, add to pending_changes operation
- File format: New top-level key in JSON cache (alongside "weeks", "categories")
- Implementation: Modify `client/core/storage.py` to get/set new data type

## Special Directories

**%APPDATA%/ЛичныйЕженедельник/ (Runtime):**
- Purpose: Local cache and settings on user's machine
- Generated: By `client/core/storage.py` at first run
- Committed: No (user-local data)
- Contains: `cache.json` (weeks, categories, pending_changes), `settings.json` (theme, hotkey, etc.)
- Example path: `C:\Users\Lecoo\AppData\Roaming\ЛичныйЕженедельник\cache.json`

**/opt/planner/ (Server Runtime):**
- Purpose: VPS server runtime directory
- Generated: During deployment
- Committed: No
- Contains: `weekly_planner.db` (SQLite), .env (secrets), logs
- Deployment: Via git push to VPS repo, triggers systemd restart

**dist/ (PyInstaller Output):**
- Purpose: Compiled .exe file for distribution
- Generated: By build.bat (PyInstaller)
- Committed: No (binary, too large)
- Contains: `Личный Еженедельник.exe` (one-file executable)
- Distribution: Uploaded to heyda.ru/planner/download

**build/ (PyInstaller Artifacts):**
- Purpose: Intermediate compilation files
- Generated: By PyInstaller
- Committed: No (temporary, large)
- Contains: .spec file, build folder, dist folder

## Imports and Dependencies

**Client dependencies** (`requirements.txt`):
- `customtkinter>=5.2.0` — CustomTkinter GUI framework
- `Pillow>=10.0.0` — Image handling (icons in tray)
- `pystray>=0.19.0` — System tray integration
- `keyboard>=0.13.5` — Global hotkey capture
- `keyring>=25.0.0` — Secure credential storage (Windows Credential Manager)
- `requests>=2.31.0` — HTTP client (sync, auth)

**Server dependencies** (commented in requirements.txt, separate deployment):
- `fastapi>=0.110.0` — Web framework
- `uvicorn>=0.29.0` — ASGI server
- `sqlalchemy>=2.0.0` — ORM
- `python-jose[cryptography]>=3.3.0` — JWT handling
- `passlib[bcrypt]>=1.7.4` — Password hashing (for future password auth)

**Python version:**
- 3.12+ required (f-strings, match statements, type hints)

## Import Organization Pattern

**Observed pattern in codebase:**

```python
# 1. Standard library (stdlib)
import json
import os
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional, Callable
from enum import IntEnum

# 2. Third-party libraries
import customtkinter as ctk
import requests
import keyring
from jose import jwt, JWTError

# 3. Local application imports
from client.ui.sidebar import SidebarManager
from client.core.models import Task, DayPlan
from client.core.storage import LocalStorage
from server.config import JWT_SECRET
```

**Guidelines:**
- Separate groups with blank lines
- Alphabetical within groups
- Use full paths (from client.ui...) not relative imports
- Use `as` aliases for clarity (ctk, jwt)

---

*Structure analysis: 2026-04-14*
