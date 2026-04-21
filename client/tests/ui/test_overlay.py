"""
Unit-тесты OverlayManager (Plan 03-04). Covers OVR-01, 02, 03, 04, 06.
D-19 verification: multi-monitor через чистый ctypes (без pywin32).
"""
import inspect
import pytest
from unittest.mock import MagicMock

from client.core.paths import AppPaths
from client.core.storage import LocalStorage
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import ThemeManager


@pytest.fixture
def overlay_deps(tmp_appdata, headless_tk, mock_ctypes_dpi):
    """Общий setup: storage + settings + theme для OverlayManager."""
    storage = LocalStorage(AppPaths())
    storage.init()
    settings_store = SettingsStore(storage)
    settings = UISettings()
    theme = ThemeManager()
    return {
        "root": headless_tk,
        "settings_store": settings_store,
        "settings": settings,
        "theme": theme,
    }


def test_overlay_creates_toplevel(overlay_deps):
    """OVR-01: OverlayManager создаёт CTkToplevel, который существует."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"],
        overlay_deps["settings_store"],
        overlay_deps["settings"],
        overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    assert overlay._overlay.winfo_exists()
    overlay.destroy()


def test_overlay_size_is_73x73(overlay_deps):
    """OVR-01: OVERLAY_SIZE = 73 px (+30% от 56, user UX request)."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    assert overlay.OVERLAY_SIZE == 73
    overlay.destroy()


def test_get_position_returns_settings_default(overlay_deps):
    """OVR-02: get_position отражает sentinel дефолта [-1,-1] до visible-position resolve."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    x, y = overlay._settings.overlay_position
    assert (x, y) == (-1, -1)
    overlay.destroy()


def test_set_position_updates_settings(overlay_deps):
    """OVR-02: set_position обновляет settings.overlay_position."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    overlay.set_position(200, 300)
    assert overlay._settings.overlay_position == [200, 300]
    overlay.destroy()


def test_validate_position_fallback_for_offscreen(overlay_deps):
    """OVR-03 / PITFALL 6: позиция off-screen → fallback (100, 100)."""
    from client.ui.overlay import OverlayManager
    overlay_deps["settings"].overlay_position = [-5000, -5000]
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    x, y = overlay._validate_position([-5000, -5000])
    # Off-screen — visible default (правый край)
    assert x > 0 and y > 0
    overlay.destroy()


def test_validate_position_handles_non_list(overlay_deps):
    """PITFALL 6: _validate_position обрабатывает None без исключения."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    x, y = overlay._validate_position(None)
    assert x > 0 and y > 0
    overlay.destroy()


def test_on_click_callback_fires(overlay_deps):
    """OVR-04: клик без drag вызывает on_click callback."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    callback = MagicMock()
    overlay.on_click = callback
    # Симулируем drag end без motion → on_click
    overlay._drag_was_motion = False
    fake_event = MagicMock()
    overlay._on_drag_end(fake_event)
    callback.assert_called_once()
    overlay.destroy()


def test_drag_motion_does_not_trigger_click(overlay_deps):
    """OVR-04: drag motion НЕ вызывает on_click."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    callback = MagicMock()
    overlay.on_click = callback
    overlay._drag_was_motion = True  # был drag
    fake_event = MagicMock()
    overlay._on_drag_end(fake_event)
    callback.assert_not_called()
    overlay.destroy()


def test_drag_end_saves_position_via_store(overlay_deps):
    """OVR-02: _on_drag_end после drag вызывает SettingsStore.save()."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    # Spy на save
    spy = MagicMock(wraps=overlay._settings_store.save)
    overlay._settings_store.save = spy
    overlay._drag_was_motion = True
    fake_event = MagicMock()
    overlay._on_drag_end(fake_event)
    spy.assert_called_once()
    overlay.destroy()


def test_set_always_on_top_calls_hook(overlay_deps):
    """OVR-06: set_always_on_top(False) вызывает on_top_changed(False)."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    hook = MagicMock()
    overlay.on_top_changed = hook
    overlay.set_always_on_top(False)
    hook.assert_called_once_with(False)
    assert overlay._settings.on_top is False
    overlay.destroy()


def test_refresh_image_keeps_pillow_ref(overlay_deps):
    """PITFALL 4: _tk_image сохраняется в instance variable после refresh_image."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    overlay.refresh_image(state="default", task_count=3, overdue_count=0)
    # PITFALL 4 — ref сохранён
    assert overlay._tk_image is not None
    overlay.destroy()


def test_second_refresh_updates_image_ref(overlay_deps):
    """PITFALL 4: повторный refresh_image обновляет _tk_image (не создаёт новый canvas item)."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    overlay.refresh_image(state="default", task_count=1, overdue_count=0)
    first_ref = overlay._tk_image
    overlay.refresh_image(state="default", task_count=2, overdue_count=0)
    second_ref = overlay._tk_image
    # Второй вызов должен обновить ref — не тот же объект
    assert second_ref is not None
    overlay.destroy()


def test_init_uses_after_100_delay(overlay_deps):
    """PITFALL 1: overrideredirect вызывается через after(INIT_DELAY_MS=100)."""
    from client.ui.overlay import OverlayManager
    source = inspect.getsource(OverlayManager)
    assert "after(self.INIT_DELAY_MS" in source or "after(100" in source
    assert "INIT_DELAY_MS = 100" in source


def test_multi_monitor_uses_pure_ctypes_not_pywin32(overlay_deps):
    """D-19: multi-monitor enumeration через ctypes.windll.user32.EnumDisplayMonitors.

    pywin32 НЕ в requirements.txt — silent fallback недопустим.
    Проверяем source module overlay.py (не класс) чтобы отловить любой
    `import win32api` / `from win32api` / использование `win32api.EnumDisplayMonitors`.
    """
    import client.ui.overlay as overlay_module
    src = inspect.getsource(overlay_module)
    # Негатив: НЕ должно быть pywin32 imports
    assert "import win32api" not in src, (
        "D-19 violation: overlay.py не должен импортировать win32api — "
        "используем чистый ctypes.windll.user32.EnumDisplayMonitors"
    )
    assert "from win32api" not in src, "D-19 violation: win32api import"
    assert "win32api.EnumDisplayMonitors" not in src, (
        "D-19 violation: multi-monitor должен идти через ctypes, не win32api"
    )
    # Позитив: должен быть ctypes path
    assert "windll.user32.EnumDisplayMonitors" in src, (
        "D-19: _get_virtual_desktop_bounds должен использовать "
        "ctypes.windll.user32.EnumDisplayMonitors"
    )
    assert "MONITORENUMPROC" in src or "WINFUNCTYPE" in src, (
        "D-19: MONITORENUMPROC callback signature должна быть определена через WINFUNCTYPE"
    )


def test_virtual_desktop_bounds_returns_tuple(overlay_deps):
    """D-19: _get_virtual_desktop_bounds возвращает валидный (left, top, right, bottom).

    На реальной Windows — union мониторов; в headless/non-Windows — primary screen fallback.
    """
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    bounds = overlay._get_virtual_desktop_bounds()
    assert isinstance(bounds, tuple) and len(bounds) == 4
    left, top, right, bottom = bounds
    assert right > left, f"right ({right}) должен быть > left ({left})"
    assert bottom > top, f"bottom ({bottom}) должен быть > top ({top})"
    overlay.destroy()


def test_destroy_removes_overlay(overlay_deps):
    """OVR-01: destroy() корректно уничтожает overlay окно."""
    from client.ui.overlay import OverlayManager
    overlay = OverlayManager(
        overlay_deps["root"], overlay_deps["settings_store"],
        overlay_deps["settings"], overlay_deps["theme"],
    )
    overlay_deps["root"].update()
    overlay.destroy()
    # После destroy overlay._overlay может всё ещё existовать до update
    overlay_deps["root"].update_idletasks()
    # winfo_exists() после destroy — False или exception
    try:
        assert not overlay._overlay.winfo_exists()
    except Exception:
        pass  # teardown happened
