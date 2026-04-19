"""Unit-тесты EditDialog (Plan 04-07). Покрывает TASK-03."""
import inspect
from unittest.mock import MagicMock

import pytest

from client.ui.edit_dialog import EditDialog, _RE_HHMM


@pytest.fixture
def ed_deps(headless_tk, mock_theme_manager, timestamped_task_factory):
    return {
        "parent": headless_tk,
        "theme": mock_theme_manager,
        "factory": timestamped_task_factory,
        "on_save": MagicMock(),
        "on_delete": MagicMock(),
    }


def _make(ed_deps, task=None):
    if task is None:
        task = ed_deps["factory"](text="original")
    dlg = EditDialog(
        ed_deps["parent"], task, ed_deps["theme"],
        ed_deps["on_save"], ed_deps["on_delete"],
    )
    ed_deps["parent"].update_idletasks()
    return dlg


# ---------- Modal (grab_set) ----------

def test_dialog_title_russian(ed_deps):
    dlg = _make(ed_deps)
    assert dlg._dialog.title() == "Задача"
    dlg._cancel()


# ---------- Fields ----------

def test_text_field_initial_value(ed_deps):
    task = ed_deps["factory"](text="my task")
    dlg = _make(ed_deps, task=task)
    text = dlg._text_box.get("1.0", "end-1c")
    assert text == "my task"
    dlg._cancel()


def test_time_field_initial_value(ed_deps):
    task = ed_deps["factory"](time="14:30")
    dlg = _make(ed_deps, task=task)
    assert dlg._hh_var.get() == "14"
    assert dlg._mm_var.get() == "30"
    assert dlg._time_enabled_var.get() is True
    dlg._cancel()


def test_time_field_empty_for_no_time(ed_deps):
    task = ed_deps["factory"]()
    dlg = _make(ed_deps, task=task)
    assert dlg._time_enabled_var.get() is False
    dlg._cancel()


def test_done_checkbox_initial_state(ed_deps):
    task = ed_deps["factory"](done=True)
    dlg = _make(ed_deps, task=task)
    assert dlg._done_var.get() is True
    dlg._cancel()


# ---------- Validation ----------

def test_save_enabled_with_valid_data(ed_deps):
    task = ed_deps["factory"](text="text", time="14:30")
    dlg = _make(ed_deps, task=task)
    assert str(dlg._save_btn.cget("state")) == "normal"
    dlg._cancel()


def test_save_disabled_empty_text(ed_deps):
    dlg = _make(ed_deps)
    dlg._text_box.delete("1.0", "end")
    dlg._update_save_state()
    assert str(dlg._save_btn.cget("state")) == "disabled"
    dlg._cancel()


def test_time_picker_options_are_valid(ed_deps):
    """HH picker — 24 options 00-23; MM picker — 12 options в 5-минутных шагах."""
    from client.ui.edit_dialog import HH_OPTIONS, MM_OPTIONS
    assert len(HH_OPTIONS) == 24
    assert HH_OPTIONS[0] == "00" and HH_OPTIONS[-1] == "23"
    assert len(MM_OPTIONS) == 12
    assert MM_OPTIONS[0] == "00" and MM_OPTIONS[-1] == "55"


def test_clear_time_disables(ed_deps):
    task = ed_deps["factory"](time="14:30")
    dlg = _make(ed_deps, task=task)
    assert dlg._time_enabled_var.get() is True
    dlg._clear_time()
    assert dlg._time_enabled_var.get() is False
    dlg._cancel()


def test_time_empty_save_enabled(ed_deps):
    """Задача без времени сохраняется нормально (текст есть)."""
    dlg = _make(ed_deps)
    assert str(dlg._save_btn.cget("state")) == "normal"
    dlg._cancel()


def test_is_valid_hhmm_regex():
    assert _RE_HHMM.match("14:30")
    assert _RE_HHMM.match("09:00")
    assert not _RE_HHMM.match("abc")
    assert not _RE_HHMM.match("14:5")
    assert EditDialog._is_valid_hhmm("00:00") is True
    assert EditDialog._is_valid_hhmm("23:59") is True
    assert EditDialog._is_valid_hhmm("24:00") is False
    assert EditDialog._is_valid_hhmm("14:60") is False


# ---------- Actions ----------

def test_cancel_closes_dialog(ed_deps):
    dlg = _make(ed_deps)
    dlg._cancel()
    assert dlg._closed is True


def test_save_calls_callback(ed_deps):
    task = ed_deps["factory"](text="original")
    dlg = _make(ed_deps, task=task)
    dlg._text_box.delete("1.0", "end")
    dlg._text_box.insert("1.0", "new text")
    dlg._save()
    ed_deps["on_save"].assert_called_once()
    updated = ed_deps["on_save"].call_args[0][0]
    assert updated.text == "new text"
    assert updated.id == task.id


def test_delete_calls_on_delete(ed_deps):
    task = ed_deps["factory"]()
    dlg = _make(ed_deps, task=task)
    dlg._delete()
    ed_deps["on_delete"].assert_called_once_with(task.id)


# ---------- Time clear ----------

def test_clear_time(ed_deps):
    task = ed_deps["factory"](time="14:30")
    dlg = _make(ed_deps, task=task)
    dlg._clear_time()
    assert dlg._time_enabled_var.get() is False
    dlg._cancel()


# ---------- Markers ----------

def test_end_minus_1c_marker():
    source = inspect.getsource(EditDialog)
    assert "end-1c" in source


def test_grab_release_on_all_exits():
    """PITFALL 1: grab_release через _close_dialog helper."""
    source = inspect.getsource(EditDialog)
    assert "_close_dialog" in source
    assert "grab_release" in source


def test_close_dialog_called_from_multiple_exits():
    source = inspect.getsource(EditDialog)
    assert source.count("self._close_dialog()") >= 3


def test_time_picker_is_optionmenu():
    """v0.4.0: time picker = CTkOptionMenu, не Entry с trace_add."""
    source = inspect.getsource(EditDialog)
    assert "CTkOptionMenu" in source
    assert "_hh_var" in source and "_mm_var" in source


def test_rehhmm_pattern():
    import client.ui.edit_dialog as ed
    assert hasattr(ed, "_RE_HHMM")
    assert ed._RE_HHMM.pattern == r'^(\d{1,2}):(\d{2})$'
