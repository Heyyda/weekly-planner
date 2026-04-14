# Testing Patterns

**Analysis Date:** 2026-04-14

## Current State

**Test Status:** No tests found in codebase.

**No test files detected:**
- Search for `*test*.py`, `*spec*.py` returned empty
- No `tests/` or `test/` directories exist
- No test framework configuration found (`pytest.ini`, `setup.cfg`, `tox.ini`, `vitest.config.js`, `jest.config.js`)

**Why missing:**
- Project is in MVP/skeleton phase (most code is unimplemented — methods contain `pass` or `# TODO:`)
- Testing planned for future phases after core functionality is complete
- Typical for desktop app prototyping (UI testing is deferred)

## Recommended Test Strategy

### Test Framework

**Recommended:**
- **Unit tests:** `pytest` (lightweight, Python standard for non-Django)
- **Async testing:** `pytest-asyncio` (if/when FastAPI server is implemented)
- **Mocking:** `unittest.mock` (standard library) + `pytest-mock` fixture
- **Desktop UI testing:** `PyTest + pytest-qt` or `pytest-customtkinter` (when UI is stable)

**Run Commands (once tests are added):**
```bash
pytest                           # Run all tests
pytest -v                        # Verbose output
pytest --cov=client,server       # With coverage report
pytest -x                        # Stop on first failure
pytest -k "auth"                 # Run tests matching pattern
```

### Test File Organization

**Location:**
- Option A (Recommended for this project): Co-located with source — `client/core/test_models.py`, `client/utils/test_hotkeys.py`
- Option B: Separate `tests/` directory at project root — `tests/client/core/test_models.py`, `tests/server/test_api.py`
- This project should use **Option A** (co-located) because:
  - Small desktop app (28 Python files)
  - Easier maintenance when files are adjacent
  - Common pattern in FastAPI projects too

**Naming:**
- Test files: `test_*.py` prefix
- Test functions: `test_*()` prefix
- Test classes: `TestClassName` (matches what they test)

**Structure:**
```
client/
├── core/
│   ├── models.py
│   ├── test_models.py           ← co-located
│   ├── auth.py
│   ├── test_auth.py
│   ├── storage.py
│   └── test_storage.py
├── ui/
│   ├── sidebar.py
│   ├── test_sidebar.py
│   └── ...
└── utils/
    ├── hotkeys.py
    ├── test_hotkeys.py
    └── ...
```

## Test Structure Patterns

### Unit Test Template

```python
# client/core/test_models.py
"""Tests for models (Task, DayPlan, WeekPlan, etc.)."""

import pytest
from datetime import date, datetime
from client.core.models import Task, Priority, DayPlan, WeekPlan


class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation(self):
        """Task should initialize with default values."""
        task = Task(text="Позвонить поставщику", priority=Priority.HIGH)
        assert task.text == "Позвонить поставщику"
        assert task.priority == Priority.HIGH
        assert task.done == False

    def test_is_overdue_false_if_done(self):
        """Overdue task marked done should return False."""
        task = Task(
            text="Old task",
            done=True,
            day="2026-04-01"  # past date
        )
        assert task.is_overdue() == False

    def test_is_overdue_true_if_past_and_not_done(self):
        """Task with past day and done=False should be overdue."""
        task = Task(
            text="Overdue task",
            done=False,
            day="2026-04-01"  # past date
        )
        assert task.is_overdue() == True
```

### Integration Test Pattern

```python
# client/core/test_storage.py
"""Tests for LocalStorage (file I/O and caching)."""

import pytest
import tempfile
import json
from pathlib import Path
from client.core.storage import LocalStorage


class TestLocalStorage:
    """Tests for LocalStorage caching."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage()
            storage.base_path = Path(tmpdir)
            storage.cache_file = storage.base_path / "cache.json"
            storage.settings_file = storage.base_path / "settings.json"
            yield storage

    def test_init_creates_directory(self, temp_storage):
        """init() should create app directory."""
        temp_storage.init()
        assert temp_storage.base_path.exists()

    def test_save_and_load_week(self, temp_storage):
        """Should save and retrieve week data."""
        temp_storage.init()
        week_data = {
            "week_start": "2026-04-14",
            "days": []
        }
        temp_storage.save_week("2026-04-14", week_data)
        loaded = temp_storage.get_week("2026-04-14")
        assert loaded == week_data

    def test_pending_changes_queue(self, temp_storage):
        """Should queue and retrieve pending changes."""
        temp_storage.init()
        op1 = {"op": "create_task", "data": {"id": "1"}, "timestamp": "2026-04-14T10:00:00"}
        op2 = {"op": "update_task", "data": {"id": "2"}, "timestamp": "2026-04-14T10:01:00"}
        
        temp_storage.add_pending_change(op1)
        temp_storage.add_pending_change(op2)
        
        pending = temp_storage.get_pending_changes()
        assert len(pending) == 2
        assert pending[0]["op"] == "create_task"
```

## Mocking Patterns

### Network Mocking

```python
# client/core/test_auth.py
"""Tests for AuthManager (with mocked network calls)."""

import pytest
from unittest.mock import patch, MagicMock
from client.core.auth import AuthManager


class TestAuthManager:
    """Tests for AuthManager."""

    @patch("client.core.auth.requests.post")
    def test_request_code_success(self, mock_post):
        """request_code() should return True on 200 response."""
        mock_post.return_value = MagicMock(status_code=200)
        
        auth = AuthManager()
        result = auth.request_code("john_doe")
        
        assert result == True
        mock_post.assert_called_once()

    @patch("client.core.auth.requests.post")
    def test_request_code_network_error(self, mock_post):
        """request_code() should return False on network error."""
        mock_post.side_effect = requests.RequestException("Connection failed")
        
        auth = AuthManager()
        result = auth.request_code("john_doe")
        
        assert result == False

    @patch("client.core.auth.keyring.get_password")
    def test_load_saved_token_success(self, mock_keyring):
        """Should load token from keyring."""
        mock_keyring.return_value = "token_xyz"
        
        auth = AuthManager()
        # Mock validate_token to avoid network call
        auth._validate_token = MagicMock(return_value=True)
        
        result = auth.load_saved_token()
        
        assert result == True
        assert auth.jwt_token == "token_xyz"
```

### Desktop UI Mocking

```python
# client/ui/test_sidebar.py
"""Tests for SidebarManager (mocking window operations)."""

import pytest
from unittest.mock import patch, MagicMock
from client.ui.sidebar import SidebarManager, SidebarState


class TestSidebarManager:
    """Tests for SidebarManager animation and state."""

    @pytest.fixture
    def mock_root(self):
        """Create mock Tkinter root window."""
        root = MagicMock()
        root.winfo_screenwidth.return_value = 1920
        root.winfo_screenheight.return_value = 1080
        return root

    def test_sidebar_initialization(self, mock_root):
        """SidebarManager should initialize with correct positions."""
        manager = SidebarManager(mock_root, panel_width=360, collapsed_width=6)
        
        assert manager.state == SidebarState.COLLAPSED
        assert manager.x_expanded == 1920 - 360  # 1560
        assert manager.x_collapsed == 1920 - 6   # 1914
        assert manager.current_x == 1914

    @patch("client.ui.sidebar.ctypes.windll")
    def test_move_window(self, mock_windll, mock_root):
        """_move_window() should call SetWindowPos."""
        manager = SidebarManager(mock_root, panel_width=360, collapsed_width=6)
        
        # Implementation pending, but structure should be:
        # manager._move_window(1560)
        # mock_windll.user32.SetWindowPos.assert_called_once()
```

## What to Test

**High Priority (Core Logic):**
- `client/core/models.py` — dataclass validation, `is_overdue()`, calculation properties
- `client/core/auth.py` — token loading/saving, Telegram auth flow, JWT refresh
- `client/core/storage.py` — file I/O, JSON serialization, pending changes queue
- `server/api.py` — REST endpoints when implemented (test fixtures, response shapes)

**Medium Priority (UI Integration):**
- `client/ui/sidebar.py` — animation state machine, position calculations
- `client/utils/hotkeys.py` — hotkey registration/unregistration

**Lower Priority (Can wait):**
- `client/ui/themes.py` — color palette validation (mostly data)
- `client/utils/notifications.py` — when implemented
- `client/utils/tray.py` — system tray integration (requires OS-level mocking)

## What NOT to Mock

- Built-in modules (`json`, `pathlib`, `enum`, `dataclasses`)
- Dataclass initialization (test actual objects)
- Helper functions that are deterministic (e.g., `Priority.HIGH` enum value)

## Coverage

**Requirements:** None enforced yet (test infrastructure not in place)

**View Coverage (when tests exist):**
```bash
pytest --cov=client,server --cov-report=html
# Opens htmlcov/index.html
```

**Target:** 70%+ coverage for core modules (`models.py`, `auth.py`, `storage.py`), 50%+ for UI/utils

## Fixture and Factory Patterns

### Fixture Definition

```python
# conftest.py (in tests/ root or next to test files)
"""Shared test fixtures."""

import pytest
from datetime import date
from client.core.models import Task, Priority, DayPlan, WeekPlan


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        id="task-1",
        text="Позвонить поставщику",
        priority=Priority.HIGH,
        day="2026-04-14"
    )


@pytest.fixture
def sample_day_plan():
    """Create a sample day plan."""
    return DayPlan(
        day="2026-04-14",
        tasks=[
            Task(id="1", text="Task 1", done=False),
            Task(id="2", text="Task 2", done=True),
        ],
        notes="Remember to follow up"
    )


@pytest.fixture
def sample_week_plan():
    """Create a complete week plan."""
    return WeekPlan(
        week_start="2026-04-14",
        days=[
            DayPlan(day="2026-04-14", tasks=[sample_task()]),
            DayPlan(day="2026-04-15", tasks=[]),
            DayPlan(day="2026-04-16", tasks=[]),
            DayPlan(day="2026-04-17", tasks=[]),
            DayPlan(day="2026-04-18", tasks=[]),
        ]
    )
```

### Usage in Tests

```python
def test_week_completion(sample_week_plan):
    """Week statistics should reflect task completion."""
    assert sample_week_plan.total_tasks == 1
    assert sample_week_plan.total_done == 1
    assert sample_week_plan.completion_pct == 100
```

---

*Testing analysis: 2026-04-14*
