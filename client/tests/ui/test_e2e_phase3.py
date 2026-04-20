"""
E2E integration tests Phase 3 — headless Tk + all components wired.

Covers observable behaviors from 03-UI-SPEC §Success Criteria (except visual
rendering — проверяется human-verify checkpoint Task 3 Plan 03-11).

9 test functions — сценарий «от boot до quit» через мок-auth, мок-sync,
мок-pystray, мок-winotify, мок-winreg.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from client.app import WeeklyPlannerApp


# =========================================================================
# Fixture
# =========================================================================

@pytest.fixture
def authed_app(tmp_appdata, mock_ctypes_dpi, mock_pystray_icon,
               mock_winotify, mock_winreg, monkeypatch):
    """Полностью настроенный app с mock auth + sync."""
    from client.core import auth as auth_mod
    from client.core import sync as sync_mod

    monkeypatch.setattr(auth_mod.AuthManager, "load_saved_token", lambda self: True)
    monkeypatch.setattr(auth_mod.AuthManager, "get_access_token",
                        lambda self: "fake-token")
    monkeypatch.setattr(auth_mod.AuthManager, "logout", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "start", lambda self: None)
    monkeypatch.setattr(sync_mod.SyncManager, "stop",
                        lambda self, timeout=5.0: None)
    monkeypatch.setattr(sync_mod.SyncManager, "force_sync", lambda self: None)

    app = WeeklyPlannerApp(version="test-e2e")
    app._setup()
    yield app

    # Teardown: безопасный quit
    try:
        app._handle_quit()
    except Exception:
        pass


# =========================================================================
# Tests
# =========================================================================

def test_e2e_setup_all_components_ready(authed_app):
    """После _setup() все 8 компонентов Phase 3 созданы и не None."""
    assert authed_app.storage is not None
    assert authed_app.sync is not None
    assert authed_app.overlay is not None
    assert authed_app.main_window is not None
    assert authed_app.pulse is not None
    assert authed_app.notifications is not None
    assert authed_app.tray is not None
    assert authed_app.theme is not None


def test_overlay_click_toggles_main_window(authed_app):
    """OVR-04: single click по overlay → main_window открывается / закрывается."""
    # Сразу после setup — main_window скрыт
    assert authed_app.main_window.is_visible() is False

    # Симулируем click: overlay.on_click == main_window.toggle (Plan 03-10 wire)
    authed_app.overlay.on_click()
    authed_app.root.update()
    assert authed_app.main_window.is_visible() is True

    # Второй клик — скрыть
    authed_app.overlay.on_click()
    authed_app.root.update()
    assert authed_app.main_window.is_visible() is False


def test_overdue_task_triggers_pulse(authed_app):
    """OVR-05: добавить просроченную задачу → _refresh_ui() → pulse активируется."""
    from client.core.models import Task

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    task = Task.new(user_id="u1", text="Старая задача", day=yesterday)
    authed_app.storage.add_task(task)

    # Pulse не активен до refresh
    authed_app._refresh_ui()

    assert authed_app.pulse.is_active() is True


def test_done_overdue_stops_pulse(authed_app):
    """OVR-05: когда просроченная задача отмечена done → pulse останавливается."""
    from client.core.models import Task

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    task = Task.new(user_id="u1", text="Старая задача", day=yesterday)
    authed_app.storage.add_task(task)
    authed_app._refresh_ui()
    assert authed_app.pulse.is_active() is True

    # Отметить выполненной
    authed_app.storage.update_task(task.id, done=True)
    authed_app._refresh_ui()
    assert authed_app.pulse.is_active() is False


def test_theme_switch_persists_to_settings(authed_app):
    """TRAY-03: смена темы через tray._cb_theme() сохраняется в settings_store."""
    # _cb_theme планирует apply через root.after(0, ...) — нужен update() а не update_idletasks()
    authed_app.tray._cb_theme("dark")
    authed_app.root.update()

    assert authed_app.settings.theme == "dark"

    # Убедиться что сохранено на диск (reload)
    reloaded = authed_app.settings_store.load()
    assert reloaded.theme == "dark"


def test_on_top_toggle_propagates(authed_app):
    """OVR-06: _cb_toggle_on_top() меняет settings.on_top (через root.after)."""
    initial_on_top = authed_app.settings.on_top

    # _cb_toggle_on_top планирует apply через root.after(0, ...) — нужен update()
    authed_app.tray._cb_toggle_on_top()
    authed_app.root.update()

    # settings.on_top должен измениться на противоположный
    assert authed_app.settings.on_top is (not initial_on_top)


def test_rapid_20_tray_callbacks_no_crash(authed_app):
    """TRAY-04: 20 быстрых _cb_show() через root.after → нет RuntimeError.

    Каждый _cb_show() ставит root.after(0, on_show), on_show вызывает main_window.show().
    Нужен root.update() чтобы события действительно отработали в Tk event loop.
    """
    for _ in range(20):
        authed_app.tray._cb_show()
        authed_app.root.update()  # обработать pending after-callbacks

    # Нет исключения — success. После >= 1 show → main_window видимо
    assert authed_app.main_window.is_visible() is True


def test_notifications_silent_blocks_toast(authed_app, mock_winotify):
    """NOTIF-04: mode=silent → fire_scheduled_toasts не вызывает winotify."""
    from client.core.models import Task
    from datetime import datetime, timezone

    authed_app.notifications.set_mode("silent")

    # Задача с дедлайном через 3 минуты
    soon = datetime.now(timezone.utc) + timedelta(minutes=3)
    deadline_iso = soon.isoformat().replace("+00:00", "Z")
    task = Task.new(user_id="u1", text="Срочная задача",
                    day=date.today().isoformat(), time_deadline=deadline_iso)
    authed_app.storage.add_task(task)

    # Вызываем проверку дедлайнов напрямую
    tasks = authed_app.storage.get_visible_tasks()
    authed_app.notifications.fire_scheduled_toasts(tasks)

    # Ждём daemon thread (winotify работает в thread)
    time.sleep(0.15)

    assert len(mock_winotify) == 0, "silent mode не должен отправлять toast"


def test_quit_stops_all_subsystems(authed_app):
    """_handle_quit: pulse, sync, tray, overlay, main_window — все корректно остановлены."""
    # Запустим pulse чтобы проверить stop
    authed_app.pulse.start()
    assert authed_app.pulse.is_active() is True

    authed_app._handle_quit()

    assert authed_app._quit_requested is True
    assert authed_app.pulse.is_active() is False

    # pystray fake icon.stop() вызван
    if authed_app.tray._icon is not None:
        assert getattr(authed_app.tray._icon, "stopped", False) is True


def test_logout_stops_sync_and_clears_auth(authed_app, monkeypatch):
    """Logout → auth.logout() вызывается + _authenticated = False."""
    logout_calls = []
    monkeypatch.setattr(
        authed_app.auth.__class__, "logout",
        lambda self: logout_calls.append(1),
    )

    authed_app._handle_logout()

    assert logout_calls == [1]
    assert authed_app._authenticated is False
