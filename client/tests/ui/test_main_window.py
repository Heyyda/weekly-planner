"""Unit-тесты MainWindow (Plan 03-06 lifecycle + Plan 04-10 integration)."""
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from client.core.paths import AppPaths
from client.core.storage import LocalStorage
from client.ui.main_window import MainWindow
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import ThemeManager


# ---------- Phase 3 lifecycle fixture ----------

@pytest.fixture
def mw_deps(tmp_appdata, headless_tk, mock_ctypes_dpi):
    storage = LocalStorage(AppPaths())
    storage.init()
    return {
        "root": headless_tk,
        "settings_store": SettingsStore(storage),
        "settings": UISettings(),
        "theme": ThemeManager(),
    }


def _make(deps):
    return MainWindow(
        deps["root"], deps["settings_store"], deps["settings"], deps["theme"],
    )


# ---------- Phase 3: lifecycle ----------

def test_creates_window(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    assert mw._window.winfo_exists()
    mw.destroy()


def test_initially_hidden(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    assert not mw.is_visible()
    mw.destroy()


def test_show_makes_visible(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw.show()
    mw_deps["root"].update()
    assert mw.is_visible()
    mw.destroy()


def test_toggle_alternates(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw.toggle()
    mw_deps["root"].update()
    v1 = mw.is_visible()
    mw.toggle()
    mw_deps["root"].update()
    v2 = mw.is_visible()
    assert v1 != v2
    mw.destroy()


def test_min_size_is_320(mw_deps):
    assert MainWindow.MIN_SIZE == (320, 320)


def test_default_size_is_460x600(mw_deps):
    assert MainWindow.DEFAULT_SIZE == (460, 600)


def test_apply_theme_changes_bg(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw._apply_theme({
        "bg_primary": "#123456",
        "bg_secondary": "#abcdef",
        "text_primary": "#000000",
        "accent_brand": "#ff0000",
    })
    mw.destroy()


def test_theme_subscribe_called_in_init(mw_deps):
    spy_theme = MagicMock(wraps=mw_deps["theme"])
    spy_theme.subscribe = MagicMock()
    spy_theme.get = mw_deps["theme"].get
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], spy_theme)
    mw_deps["root"].update()
    spy_theme.subscribe.assert_called()
    mw.destroy()


def test_save_window_state_persists(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    spy = MagicMock(wraps=mw._settings_store.save)
    mw._settings_store.save = spy
    mw._save_window_state()
    spy.assert_called_once()
    mw.destroy()


def test_set_always_on_top(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw.set_always_on_top(False)
    mw.set_always_on_top(True)
    mw.destroy()


def test_destroy_cleanup(mw_deps):
    mw = _make(mw_deps)
    mw_deps["root"].update()
    mw.destroy()


# ---------- Phase 4 integration ----------

@pytest.fixture
def mw_phase4_deps(headless_tk, mock_theme_manager, mock_storage):
    settings = UISettings()
    store = MagicMock()
    store.save = MagicMock()
    return {
        "root": headless_tk,
        "settings_store": store,
        "settings": settings,
        "theme": mock_theme_manager,
        "storage": mock_storage,
        "user_id": "test-user",
    }


def _make_mw_p4(deps):
    mw = MainWindow(
        deps["root"], deps["settings_store"], deps["settings"], deps["theme"],
        storage=deps["storage"], user_id=deps["user_id"],
    )
    deps["root"].update_idletasks()
    return mw


def test_main_window_has_week_nav(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert mw._week_nav is not None
    mw.destroy()


def test_main_window_has_seven_day_sections(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert len(mw._day_sections) == 7
    mw.destroy()


def test_main_window_has_undo_toast_manager(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert mw._undo_toast is not None
    mw.destroy()


def test_main_window_has_drag_controller(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert mw._drag_controller is not None
    mw.destroy()


def test_drag_controller_has_seven_drop_zones(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    assert len(mw._drag_controller._drop_zones) == 7
    mw.destroy()


def test_refresh_tasks_renders_tasks_in_day(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory(text="test today")
    mw_phase4_deps["storage"].add_task(task)
    mw._refresh_tasks()
    today = date.today()
    ds = mw._day_sections.get(today)
    assert ds is not None
    assert len(ds._task_widgets) == 1
    mw.destroy()


def test_delete_with_undo_shows_toast(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory()
    mw_phase4_deps["storage"].add_task(task)
    mw._delete_task_with_undo(task.id)
    mw_phase4_deps["root"].update_idletasks()
    assert len(mw._undo_toast._queue) == 1
    mw.destroy()


def test_on_task_toggle_updates_storage(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory(done=False)
    mw_phase4_deps["storage"].add_task(task)
    mw._on_task_toggle(task.id, True)
    updated = mw_phase4_deps["storage"].get_task(task.id)
    assert updated.done is True
    mw.destroy()


def test_on_task_moved_updates_day(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory()
    mw_phase4_deps["storage"].add_task(task)
    new_day = date.today() + timedelta(days=1)
    mw._on_task_moved(task.id, new_day)
    updated = mw_phase4_deps["storage"].get_task(task.id)
    assert updated.day == new_day.isoformat()
    mw.destroy()


def test_handle_quick_capture_save_creates_task(mw_phase4_deps):
    mw = _make_mw_p4(mw_phase4_deps)
    mw.handle_quick_capture_save("test task", date.today().isoformat(), "14:00")
    tasks = mw_phase4_deps["storage"].get_visible_tasks()
    assert len(tasks) == 1
    assert tasks[0].text == "test task"
    assert tasks[0].time_deadline == "14:00"
    mw.destroy()


def test_week_navigation_changes_day_sections(mw_phase4_deps):
    """prev_week() → _update_week → days изменились."""
    mw = _make_mw_p4(mw_phase4_deps)
    initial_days = set(mw._day_sections.keys())
    mw._week_nav.prev_week()
    new_days = set(mw._day_sections.keys())
    assert initial_days != new_days
    mw.destroy()


def test_on_week_changed_reuses_day_sections(mw_phase4_deps):
    """UX-01: _on_week_changed делает diff-rebuild — те же DaySection объекты переиспользуются."""
    mw = _make_mw_p4(mw_phase4_deps)
    first_ids = [id(ds) for ds in mw._day_sections.values()]
    assert len(first_ids) == 7
    mw._week_nav.next_week()
    mw_phase4_deps["root"].update_idletasks()
    new_ids = [id(ds) for ds in mw._day_sections.values()]
    assert first_ids == new_ids, (
        "DaySection должны переиспользоваться при смене недели (diff-rebuild)"
    )
    mw.destroy()


def test_handle_task_style_changed_rebuilds_heavy(mw_phase4_deps):
    """UX-01: handle_task_style_changed использует heavy rebuild (новые объекты)."""
    mw = _make_mw_p4(mw_phase4_deps)
    first_ids = [id(ds) for ds in mw._day_sections.values()]
    mw.handle_task_style_changed("line")
    mw_phase4_deps["root"].update_idletasks()
    new_ids = [id(ds) for ds in mw._day_sections.values()]
    # handle_task_style_changed должен пересоздать секции (heavy rebuild)
    assert first_ids != new_ids, (
        "handle_task_style_changed обязан пересоздавать DaySection (heavy rebuild)"
    )
    mw.destroy()


def test_ctrl_space_binding_present_when_trigger_set(mw_phase4_deps):
    trigger = MagicMock()
    mw_phase4_deps["settings"] = UISettings()
    mw = MainWindow(
        mw_phase4_deps["root"], mw_phase4_deps["settings_store"],
        mw_phase4_deps["settings"], mw_phase4_deps["theme"],
        storage=mw_phase4_deps["storage"], user_id="u",
        quick_capture_trigger=trigger,
    )
    mw_phase4_deps["root"].update_idletasks()
    bindings = mw._window.bind()
    assert any("Control-space" in b or "Control-Key-space" in b for b in bindings)
    mw.destroy()
