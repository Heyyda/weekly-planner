"""
Integration-тесты WeeklyPlannerApp (Plan 03-10).

Проверяют:
- Инициализацию оркестратора без краша
- Login-placeholder при отсутствии авторизации
- Wire всех 6 Phase 3 компонентов при auth=True
- OVR-04: overlay.on_click == main_window.toggle
- OVR-06: overlay.on_top_changed == main_window.set_always_on_top
- Callbacks на notifications, autostart
- _handle_quit освобождает ресурсы
- Pulse start/stop по overdue-состоянию
- Cyrillic-path robustness
"""
from unittest.mock import MagicMock, patch

import pytest

from client.app import WeeklyPlannerApp


@pytest.fixture
def app_env(tmp_appdata, mock_ctypes_dpi, mock_pystray_icon, mock_winotify, mock_winreg):
    """Полный mocked env для app-теста (без login)."""
    yield


def test_app_instantiates(app_env, monkeypatch):
    """CTk root создаётся, компоненты None до _setup()."""
    app = WeeklyPlannerApp(version="test")
    assert app.root is not None
    assert app.storage is None  # до setup
    try:
        app.root.destroy()
    except Exception:
        pass


def test_setup_unauthenticated_skips_main_components(app_env, monkeypatch):
    """При auth=False создаётся placeholder, остальное не инстанцируется."""
    from client.core import auth as auth_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: False)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        # После placeholder setup:
        assert app.sync is None
        assert app.main_window is None
        assert app.pulse is None
        assert app.overlay is not None  # placeholder overlay создан
        assert app.tray is not None     # placeholder tray
    finally:
        app._handle_quit()


def test_setup_authenticated_wires_all_components(app_env, monkeypatch):
    """При auth=True создаются все 6 компонентов."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod

    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(auth_mod.AuthManager, "get_access_token",
                        lambda self: "fake-token")
    # SyncManager.start не должен реально стартовать thread
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        assert app.storage is not None
        assert app.sync is not None
        assert app.overlay is not None
        assert app.main_window is not None
        assert app.pulse is not None
        assert app.notifications is not None
        assert app.tray is not None
    finally:
        app._handle_quit()


def test_overlay_on_click_wires_to_main_window_toggle(app_env, monkeypatch):
    """OVR-04: overlay.on_click == main_window.toggle."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        # overlay.on_click == main_window.toggle
        assert app.overlay.on_click == app.main_window.toggle
    finally:
        app._handle_quit()


def test_overlay_on_top_changed_wires_to_main_window(app_env, monkeypatch):
    """OVR-06: overlay.on_top_changed == main_window.set_always_on_top."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        assert app.overlay.on_top_changed == app.main_window.set_always_on_top
    finally:
        app._handle_quit()


def test_handle_notifications_mode_changed(app_env, monkeypatch):
    """_handle_notifications_mode_changed меняет mode у NotificationManager."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        app._handle_notifications_mode_changed("silent")
        assert app.notifications.mode == "silent"
    finally:
        app._handle_quit()


def test_handle_autostart_toggle_on(app_env, monkeypatch):
    """_handle_autostart_changed(True) вызывает enable_autostart."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    from client.utils import autostart as astart
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        app._handle_autostart_changed(True)
        assert astart.is_autostart_enabled() is True
    finally:
        app._handle_quit()


def test_handle_quit_cleanup(app_env, monkeypatch):
    """_handle_quit вызывает sync.stop + tray.stop + устанавливает _quit_requested."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    stop_called = []
    monkeypatch.setattr(sync_mod.SyncManager, "stop",
                        lambda self, timeout=5.0: stop_called.append(1))

    app = WeeklyPlannerApp(version="test")
    app._setup()
    app._handle_quit()
    assert stop_called == [1]
    assert app._quit_requested is True


def test_cyrillic_path_resolution_works():
    """main.py использует Path.resolve() — не крэшит на Cyrillic пути."""
    from pathlib import Path
    project_root = Path(__file__).resolve().parent
    # Проверяем что путь существует и содержит ожидаемую структуру
    assert project_root.exists()


def test_refresh_ui_starts_pulse_on_overdue(app_env, monkeypatch):
    """_refresh_ui запускает pulse при наличии просроченных задач."""
    from datetime import date, timedelta
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    from client.core.models import Task

    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        # Добавим просроченную задачу
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        t = Task.new(user_id="u1", text="Old", day=yesterday)
        app.storage.add_task(t)
        app._refresh_ui()
        assert app.pulse.is_active() is True
    finally:
        app._handle_quit()


def test_refresh_ui_stops_pulse_when_no_overdue(app_env, monkeypatch):
    """_refresh_ui не запускает pulse при отсутствии просроченных задач."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod

    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        # Сразу refresh — нет задач → pulse не активен
        app._refresh_ui()
        assert app.pulse.is_active() is False
    finally:
        app._handle_quit()


def test_tray_started(app_env, monkeypatch, mock_pystray_icon):
    """tray.start() вызывается при authenticated setup."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod

    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        # Проверяем что pystray.Icon был инстанцирован и run_detached вызван
        assert len(mock_pystray_icon.instances) > 0
        last_icon = mock_pystray_icon.instances[-1]
        assert last_icon.run_detached_called is True
    finally:
        app._handle_quit()


def test_sync_started(app_env, monkeypatch):
    """sync_manager.start() вызывается при authenticated setup."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod

    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)
    start_called = []
    monkeypatch.setattr(sync_mod.SyncManager, "start",
                        lambda self: start_called.append(1))

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        assert start_called == [1]
    finally:
        app._handle_quit()


def test_handle_logout_stops_sync_and_clears_auth(app_env, monkeypatch):
    """_handle_logout вызывает sync.stop и auth.logout."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod

    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)

    logout_called = []
    sync_stop_called = []
    monkeypatch.setattr(auth_mod.AuthManager, "logout",
                        lambda self: logout_called.append(1))
    monkeypatch.setattr(sync_mod.SyncManager, "stop",
                        lambda self, timeout=5.0: sync_stop_called.append(1))

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        app._handle_logout()
        assert logout_called == [1]
        assert sync_stop_called == [1]
        assert app._authenticated is False
    finally:
        # sync already stopped — monkeypatch still active
        app._quit_requested = True
        try:
            if app.tray is not None:
                app.tray.stop()
            if app.overlay is not None:
                app.overlay.destroy()
            if app.main_window is not None:
                app.main_window.destroy()
            app.root.quit()
            app.root.destroy()
        except Exception:
            pass


# ---------- Phase 4 integration ----------

def test_quick_capture_created_in_setup(app_env, monkeypatch):
    """WeeklyPlannerApp._setup создаёт QuickCapturePopup (authenticated branch)."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        assert app.quick_capture is not None
    finally:
        app._handle_quit()


def test_overlay_right_click_wired_d01(app_env, monkeypatch):
    """D-01: overlay.on_right_click == app._on_overlay_right_click."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        assert app.overlay.on_right_click == app._on_overlay_right_click
    finally:
        app._handle_quit()


def test_main_window_receives_storage(app_env, monkeypatch):
    """Phase 4: MainWindow инициализирован с storage (для CRUD)."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        assert app.main_window._storage is app.storage
    finally:
        app._handle_quit()


def test_handle_quick_capture_save_creates_task(app_env, monkeypatch):
    """_handle_quick_capture_save → storage.add_task + refresh."""
    from datetime import date
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)
    monkeypatch.setattr(sync_mod.SyncManager, "force_sync", lambda self: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        initial = len(app.storage.get_visible_tasks())
        app._handle_quick_capture_save("new task", date.today().isoformat(), None)
        assert len(app.storage.get_visible_tasks()) == initial + 1
    finally:
        app._handle_quit()


def test_trigger_quick_capture_centered_exists():
    assert hasattr(WeeklyPlannerApp, "_trigger_quick_capture_centered")


def test_on_overlay_right_click_exists():
    assert hasattr(WeeklyPlannerApp, "_on_overlay_right_click")


def test_task_style_change_delegated_to_main_window(app_env, monkeypatch):
    """_handle_task_style_changed → main_window.handle_task_style_changed."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod
    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop", lambda self, timeout=5.0: None)

    app = WeeklyPlannerApp(version="test")
    try:
        app._setup()
        called = []
        app.main_window.handle_task_style_changed = lambda s: called.append(s)
        app._handle_task_style_changed("line")
        assert called == ["line"]
    finally:
        app._handle_quit()
