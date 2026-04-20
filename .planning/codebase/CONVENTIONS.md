# Coding Conventions

**Analysis Date:** 2026-04-14

## Naming Patterns

**Files:**
- Module files: `lowercase_with_underscores` (e.g., `auth.py`, `task_widget.py`, `hotkeys.py`)
- Class files: match class name if single class per file (e.g., `ThemeManager` → optional: could use `themes.py` or `theme_manager.py`; project uses `themes.py`)
- Configuration: `config.py`, `models.py`, `__init__.py`
- Logical grouping: `client/`, `server/`, `ui/`, `core/`, `utils/` directories

**Functions:**
- camelCase for public methods: `toggle_done()`, `request_code()`, `expand()`, `set_appearance_mode()`
- snake_case for internal/private methods with `_` prefix: `_setup()`, `_do_sync()`, `_save_tokens()`, `_move_window()`
- Verb-first convention: `get_week()`, `save_settings()`, `load_saved_token()`, `toggle()`, `delete()`

**Variables:**
- snake_case: `panel_width`, `anim_step`, `current_x`, `jwt_token`, `collapse_timer`
- Private instance variables: `_running`, `_thread`, `_hotkey_id`, `_data`
- Constants/class variables: UPPER_CASE: `PANEL_WIDTH`, `ANIMATION_STEP`, `SYNC_INTERVAL`, `SERVICE_NAME`, `APP_DIR`, `DB_PATH`, `JWT_ALGORITHM`

**Types:**
- Type hints used extensively: `Optional[str]`, `list[Task]`, `dict`, `bool`, `int`, `Callable`
- Dataclasses for models: `@dataclass` decorator with typed fields
- Enums for discrete states: `IntEnum` (Priority) and string `Enum` (SidebarState)

## Code Style

**Formatting:**
- No explicit linter/formatter config detected (no `.eslintrc`, `.prettierrc`, `pylintrc`, `pyproject.toml` with formatting rules found)
- PEP 8 style followed: 4-space indentation, max line length not enforced visually
- Imports at file top, grouped logically

**Linting:**
- No linting config detected — style maintained through developer discipline and code review

## Import Organization

**Order:**
1. Standard library imports: `sys`, `os`, `json`, `pathlib`, `threading`, `time`
2. Third-party imports: `customtkinter`, `requests`, `keyring`, `keyboard`, `enum`, `dataclasses`
3. Local imports: relative imports from `client.*`, `server.*`

**Path Aliases:**
- No explicit aliases (no `jsconfig.json`, no `baseUrl` config) — relative imports used throughout
- Pattern: `from client.ui.sidebar import SidebarManager` (fully qualified from project root)
- Relative imports within same package: `from .models import Task` (in `client/core/models.py`)

## Error Handling

**Patterns:**
- Try/except for network calls: `requests.RequestException` caught silently with `pass` or `return False/None`
- Bare except for generic failures: `except Exception: pass` (in `load_saved_token()`)
- Return `False`/`None` for failure cases instead of raising (graceful degradation for offline)
- Offline-tolerant: network errors logged implicitly (not catching/logging) or ignored (typical for UI apps)

**Strategy:**
- No explicit try/finally cleanup observed — assumed resources (file handles, network) are properly managed
- `requests.RequestException` is caught for network timeouts and connection errors
- Missing validation on edge cases (e.g., `date.fromisoformat()` could raise if format is wrong) — TODO-level concerns

## Logging

**Framework:** `print()` / console logging not explicitly configured; not yet implemented (skeleton code)

**Patterns:**
- No logging imports found yet
- TODO: expected to use Python `logging` module on server (FastAPI app)
- Client might use `sys.stdout`/stderr for debug info during dev

## Comments

**When to Comment:**
- Docstrings for classes and public methods (Google/NumPy style observed)
- Russian comments in docstrings allowed and used: `"""Главный класс приложения."""`
- Module-level docstrings at top of every file explaining purpose and usage
- Inline comments for non-obvious logic (minimal in skeleton code)

**JSDoc/TSDoc:**
- Python docstrings follow triple-quote format: `"""Purpose and usage."""`
- Arguments and return types documented in docstrings where needed
- Example from `WeeklyPlannerApp`: docstring lists 5-step lifecycle

**Docstring Style:**
```python
def get_week(self, week_start: str) -> Optional[dict]:
    """Получить данные недели из кеша."""
    ...
```

## Function Design

**Size:** Not enforced; skeleton methods are ~10-15 lines (TODOs); full methods expected to be 20-40 lines

**Parameters:**
- Type hints required: all function parameters and return types are annotated
- Optional parameters use `Optional[Type] = None` pattern
- No `*args/**kwargs` observed — explicit parameters preferred

**Return Values:**
- Boolean returns for success/failure: `verify_code() -> bool`, `load_saved_token() -> bool`
- Optional returns for nullable data: `get_week(week_start) -> Optional[dict]`
- Explicit `None` vs `False` distinction: `None` = not found, `False` = operation failed
- Methods with side effects return `None` implicitly: `toggle()`, `collapse()`, `save()`

## Module Design

**Exports:**
- Classes exported as public (e.g., `WeeklyPlannerApp`, `TaskWidget`, `SyncManager`)
- Private classes/functions prefixed with `_` (e.g., `_sync_loop`, `_save_tokens`)
- No explicit `__all__` lists found

**Barrel Files:**
- `client/__init__.py`, `client/core/__init__.py`, `client/ui/__init__.py`, `server/__init__.py` exist but are empty
- No re-exports of submodules; consumers import directly from modules

**Dataclass Serialization:**
- Models in `client/core/models.py` designed for JSON serialization via `dataclasses.asdict()` → JSON (implicit, via `json.dump()`)
- No custom `__post_init__` or `__repr__` overrides yet

## Cross-Module Patterns

**Manager Classes:**
- Singleton-like pattern: `ThemeManager`, `SidebarManager`, `LocalStorage`, `AuthManager`, `HotkeyManager`, `SyncManager`
- Stateful managers hold internal state (`_data`, `_running`, `_hotkey_id`, etc.)
- Initialization via `__init__()` and optional `setup()`/`init()` methods for lazy initialization

**Storage/Config:**
- Centralized configuration: `server/config.py` with `HOST`, `PORT`, `DB_PATH`, `JWT_SECRET` as module-level constants
- Client config inlined in app.py: `PANEL_WIDTH = 360`, `ANIMATION_STEP = 20`
- Settings stored in JSON files: `cache.json` and `settings.json` in `%APPDATA%/ЛичныйЕженедельник/`

---

*Convention analysis: 2026-04-14*
