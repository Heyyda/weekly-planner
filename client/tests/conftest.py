"""
Shared pytest fixtures для client/tests/.

Fixtures:
- tmp_appdata: изолирует APPDATA в tmp_path (LocalStorage пишет в tmp)
- mock_api: requests_mock.Mocker для перехвата HTTP
- api_base: базовый URL API (константа)
"""
import os
from pathlib import Path

import pytest
import requests_mock as req_mock_module


API_BASE_URL = "https://planner.heyda.ru/api"


@pytest.fixture
def api_base() -> str:
    """Базовый URL API, используемый во всех client-тестах."""
    return API_BASE_URL


@pytest.fixture
def tmp_appdata(tmp_path: Path, monkeypatch) -> Path:
    """
    Подменяет переменную окружения APPDATA на tmp_path.
    LocalStorage и RotatingFileHandler будут писать в tmp_path/ЛичныйЕженедельник/.
    """
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # LOCALAPPDATA тоже устанавливаем (fallback в client/core/paths.py)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


@pytest.fixture
def mock_api():
    """
    requests_mock.Mocker для перехвата HTTP-вызовов.

    Использование:
        def test_sync(mock_api, api_base):
            mock_api.post(f"{api_base}/sync", json={"server_timestamp": "...", "changes": []})
            ... requests.post(f"{api_base}/sync") ...
    """
    with req_mock_module.Mocker() as m:
        yield m


# ---------- Phase 3 UI fixtures ----------

@pytest.fixture(scope="session")
def headless_tk():
    """
    CTk root в headless-режиме для UI-тестов (session-scoped).

    Session scope необходим: Tcl/Tk интерпретатор нельзя корректно
    пересоздать внутри одной pytest-сессии после destroy(). Один root
    на всю сессию — стандартный паттерн для Tkinter unit-тестов.
    withdraw() — окно невидимо, update() процессирует events без mainloop().
    """
    import customtkinter as ctk
    root = ctk.CTk()
    root.withdraw()
    try:
        yield root
    finally:
        try:
            root.update_idletasks()
            root.destroy()
        except Exception:
            pass


@pytest.fixture
def mock_pystray_icon(monkeypatch):
    """
    Патчит pystray.Icon → FakeIcon. Yield'ит класс для инспекции.
    Каждый инстанс запоминает: icon, title, menu, run_detached_called.
    """
    class FakeIcon:
        instances = []

        def __init__(self, name, icon=None, title="", menu=None):
            self.name = name
            self.icon = icon
            self.title = title
            self.menu = menu
            self.run_detached_called = False
            self.stopped = False
            FakeIcon.instances.append(self)

        def run_detached(self):
            self.run_detached_called = True

        def stop(self):
            self.stopped = True

        def update_menu(self):
            pass

    FakeIcon.instances = []
    monkeypatch.setattr("pystray.Icon", FakeIcon)
    yield FakeIcon


@pytest.fixture
def mock_winotify(monkeypatch):
    """
    Патчит winotify.Notification → FakeNotification.
    Yield'ит list — каждый toast.show() append'ит dict параметров.
    """
    calls = []

    class FakeNotification:
        def __init__(self, app_id=None, title=None, msg=None, icon=None, **kwargs):
            self.kwargs = {
                "app_id": app_id,
                "title": title,
                "msg": msg,
                "icon": icon,
            }
            self.kwargs.update(kwargs)

        def show(self):
            calls.append(dict(self.kwargs))

        def set_audio(self, *a, **kw):
            pass

        def add_actions(self, *a, **kw):
            pass

    monkeypatch.setattr("winotify.Notification", FakeNotification)
    yield calls


@pytest.fixture
def mock_winreg(monkeypatch):
    """
    In-memory stub для winreg. Yield'ит dict store: {(hkey, path, name): value}.
    """
    import winreg as _real_winreg
    store = {}

    class _FakeKeyCtx:
        def __init__(self, hkey, path):
            self.hkey = hkey
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_open(hkey, path, reserved=0, access=0):
        return _FakeKeyCtx(hkey, path)

    def fake_set(key, name, reserved, typ, value):
        store[(key.hkey, key.path, name)] = value

    def fake_query(key, name):
        v = store.get((key.hkey, key.path, name))
        if v is None:
            raise FileNotFoundError
        return v, _real_winreg.REG_SZ

    def fake_delete(key, name):
        k = (key.hkey, key.path, name)
        if k not in store:
            raise FileNotFoundError
        del store[k]

    monkeypatch.setattr("winreg.OpenKey", fake_open)
    monkeypatch.setattr("winreg.SetValueEx", fake_set)
    monkeypatch.setattr("winreg.QueryValueEx", fake_query)
    monkeypatch.setattr("winreg.DeleteValue", fake_delete)
    yield store


@pytest.fixture
def mock_ctypes_dpi(monkeypatch):
    """
    No-op замены SetProcessDpiAwareness / SetProcessDPIAware.
    Нужно чтобы CTk на CI без DPI-контекста не падал.
    """
    try:
        import ctypes
        monkeypatch.setattr(
            ctypes.windll.shcore, "SetProcessDpiAwareness",
            lambda *a, **kw: 0, raising=False,
        )
        monkeypatch.setattr(
            ctypes.windll.user32, "SetProcessDPIAware",
            lambda *a, **kw: 0, raising=False,
        )
    except (AttributeError, OSError):
        pass  # не-Windows — пропускаем
    yield


# ---------- Phase 4 UI fixtures ----------

@pytest.fixture
def timestamped_task_factory():
    """Фабрика Task с настраиваемыми day/time/done для UI-тестов Phase 4.

    Usage:
        task = timestamped_task_factory(text="hello", day_offset=-1)  # вчера
        overdue = timestamped_task_factory(day_offset=-2, done=False)
        future = timestamped_task_factory(day_offset=3, time="14:30")
    """
    from datetime import date, timedelta
    from client.core.models import Task

    def factory(
        text: str = "Test task",
        day_offset: int = 0,
        time: str | None = None,
        done: bool = False,
        user_id: str = "test-user",
        position: int = 0,
    ) -> Task:
        target_date = (date.today() + timedelta(days=day_offset)).isoformat()
        task = Task.new(
            user_id=user_id,
            text=text,
            day=target_date,
            time_deadline=time,
            position=position,
        )
        task.done = done
        return task

    return factory


@pytest.fixture
def mock_storage(tmp_appdata):
    """LocalStorage готовый к использованию (инициализированный на tmp_appdata).

    Phase 4 UI-тесты используют этот fixture вместо ручного создания AppPaths+LocalStorage.
    get_visible_tasks() вернёт [] для свежего storage.
    """
    from client.core.paths import AppPaths
    from client.core.storage import LocalStorage
    storage = LocalStorage(AppPaths())
    storage.init()
    return storage


@pytest.fixture
def mock_theme_manager():
    """ThemeManager('light') без субскриберов — для widget-тестов Phase 4."""
    from client.ui.themes import ThemeManager
    return ThemeManager(initial="light")


@pytest.fixture
def dnd_event_simulator():
    """Фабрика MagicMock-событий для DnD unit-тестов.

    Симулирует tk.Event с нужными атрибутами x_root, y_root, x, y, widget.
    Используется в test_drag_controller.py вместо реальных event_generate().
    """
    from unittest.mock import MagicMock

    def simulate(x_root: int = 0, y_root: int = 0,
                 x: int = 0, y: int = 0, widget=None) -> MagicMock:
        event = MagicMock()
        event.x_root = x_root
        event.y_root = y_root
        event.x = x
        event.y = y
        event.widget = widget
        return event

    return simulate
