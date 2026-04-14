# Technology Stack

**Analysis Date:** 2026-04-14

## Languages

**Primary:**
- Python 3.12+ - Desktop client and FastAPI server

**Supporting:**
- Batch (.bat) - Build scripts for PyInstaller (`build/build.bat`)

## Runtime

**Client:**
- Python 3.12+ interpreter
- Runs as single executable (PyInstaller --onefile)

**Server:**
- Python 3.12+ with FastAPI/Uvicorn
- Target deployment: VPS 109.94.211.29 (port 8100)

**Package Manager:**
- pip (requirements.txt)
- Lockfile: None (pinned versions only)

## Frameworks

**Client UI:**
- CustomTkinter 5.2.0+ - Desktop GUI framework with dark/light themes
  - Used in `client/app.py`, `client/ui/` modules
  - Modern alternative to Tkinter with built-in styling

**Server API:**
- FastAPI 0.110.0+ - REST API framework (commented in requirements.txt, deployed separately)
- Uvicorn 0.29.0+ - ASGI server for FastAPI

**Authentication:**
- python-jose[cryptography] 3.3.0+ - JWT token encoding/decoding
  - Implementation: `server/auth.py` with HS256 algorithm
  - 7-day access tokens, 30-day refresh tokens

**Database:**
- SQLAlchemy 2.0.0+ - ORM for database models
  - Models: `server/db.py` (User, TaskRecord, CategoryRecord, DayNote, RecurringTemplate)
  - SQLite backend: `weekly_planner.db`

**Password Management:**
- passlib[bcrypt] 1.7.4+ - Reserved for future password hashing (not currently used)

## Key Dependencies

**Critical:**
- `customtkinter>=5.2.0` - Desktop window, panels, widgets (`client/app.py`)
- `pystray>=0.19.0` - System tray icon with menu (`client/utils/tray.py`)
- `keyboard>=0.13.5` - Global hotkey capture (Win+Q) (`client/utils/hotkeys.py`)
- `keyring>=25.0.0` - Secure credential storage for JWT tokens (`client/core/auth.py`)
- `requests>=2.31.0` - HTTP client for API calls (auth, sync, updates)
- `Pillow>=10.0.0` - Image handling for tray icon and assets

**Build:**
- PyInstaller 6.0.0+ - Bundles Python + dependencies into single .exe
  - Command: `pyinstaller --onefile --windowed --icon=... main.py`

## Configuration

**Environment Variables:**

*Client (Windows Registry + keyring):*
- JWT tokens stored in Windows Credential Manager via `keyring`
- Settings cached locally: `%APPDATA%/ЛичныйЕженедельник/cache.json`
- Hotkey preferences: stored in `cache.json`

*Server:*
- `PLANNER_DB` - SQLite database path (default: `/opt/planner/weekly_planner.db`)
- `PLANNER_JWT_SECRET` - HS256 signing key (MUST be changed in production)
- `PLANNER_TG_BOT_TOKEN` - Telegram bot token for auth flow
- `PLANNER_TG_ADMIN_CHAT` - Admin chat ID for logging
- `PLANNER_EXE_PATH` - Path to latest .exe for updates

**Files:**
- `.gitignore` - Standard Python exclusions
- `build/build.bat` - Windows batch script for PyInstaller
- Client config: `server/config.py` (hardcoded API_BASE, port 8100)

## Build Process

**Development:**
```bash
pip install -r requirements.txt
python main.py
```

**Production (Windows):**
```bash
build\build.bat
# Generates: dist\Личный Еженедельник.exe
```

**Process:**
1. `pip install -r requirements.txt` + PyInstaller
2. PyInstaller bundles everything into single .exe
3. Assets embedded: `client/assets/icon.ico`
4. Result: ~100MB+ single executable file

## Platform Requirements

**Development:**
- Windows 10/11 (ctypes, winreg, win32gui APIs)
- Python 3.12+
- pip for dependency installation

**Production Client:**
- Windows 10/11 only (hardcoded win32 APIs)
  - System tray support
  - Registry access for autostart
  - Global hotkey capture
  - No installer needed - single .exe

**Production Server:**
- Linux VPS (109.94.211.29)
- Python 3.12+
- SQLite database file writable at `/opt/planner/`

## API Communication

**Protocol:** HTTPS REST
**Base URL:** `https://heyda.ru/planner/api` (defined in `client/core/auth.py`, `client/core/sync.py`)
**Port:** 8100 on VPS (server only - client uses external domain)

**Key Endpoints:**
- `POST /api/auth/request` - Request verification code
- `POST /api/auth/verify` - Verify code, get JWT
- `GET /api/weeks/{start}` - Fetch week data
- `POST /api/sync` - Sync pending changes
- `GET /api/version` - Check for updates

## Dependency Management

**Current state:**
- requirements.txt uses `>=` pins (minimum versions)
- Server dependencies commented out (deployed separately)
- No lock file (simple environment)

**Notable:**
- CustomTkinter requires CTk root before creating widgets
- pystray requires running in separate daemon thread
- keyboard library requires elevated privileges on some Windows versions
- keyring uses Windows Credential Manager backend (platform-specific)

---

*Stack analysis: 2026-04-14*
