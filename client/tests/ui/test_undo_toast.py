"""Unit-тесты UndoToastManager (Plan 04-08). TASK-04."""
import inspect
import tkinter as tk
from unittest.mock import MagicMock

import pytest

from client.ui.undo_toast import UndoToastManager, ToastEntry


@pytest.fixture
def ut_deps(headless_tk, mock_theme_manager):
    import customtkinter as ctk
    parent = ctk.CTkFrame(headless_tk, width=460, height=600)
    parent.pack()
    headless_tk.update_idletasks()
    yield {
        "parent": parent,
        "root": headless_tk,
        "theme": mock_theme_manager,
    }
    try:
        parent.destroy()
    except Exception:
        pass


def _make(ut_deps):
    return UndoToastManager(ut_deps["parent"], ut_deps["root"], ut_deps["theme"])


# ---------- Lifecycle ----------

def test_manager_initial_empty(ut_deps):
    mgr = _make(ut_deps)
    assert mgr._queue == []
    assert mgr._frames == []
    mgr.destroy()


def test_show_creates_toast(ut_deps):
    mgr = _make(ut_deps)
    cb = MagicMock()
    mgr.show("task-1", "my task", cb)
    ut_deps["root"].update_idletasks()
    assert len(mgr._queue) == 1
    assert len(mgr._frames) == 1
    mgr.destroy()


def test_show_multiple(ut_deps):
    mgr = _make(ut_deps)
    for i in range(2):
        mgr.show(f"task-{i}", f"task {i}", MagicMock())
    assert len(mgr._queue) == 2
    mgr.destroy()


def test_max_3_evicts_oldest(ut_deps):
    """D-21."""
    mgr = _make(ut_deps)
    for i in range(4):
        mgr.show(f"task-{i}", f"task {i}", MagicMock())
    assert len(mgr._queue) == 3
    ids = [e.task_id for e in mgr._queue]
    assert "task-0" not in ids
    assert ids == ["task-1", "task-2", "task-3"]
    mgr.destroy()


# ---------- Undo ----------

def test_undo_calls_callback(ut_deps):
    mgr = _make(ut_deps)
    cb = MagicMock()
    mgr.show("task-undo", "text", cb)
    mgr._undo("task-undo")
    cb.assert_called_once()
    mgr.destroy()


def test_undo_removes_from_queue(ut_deps):
    mgr = _make(ut_deps)
    mgr.show("task-1", "text", MagicMock())
    mgr._undo("task-1")
    assert len(mgr._queue) == 0
    mgr.destroy()


def test_undo_unknown_no_error(ut_deps):
    mgr = _make(ut_deps)
    mgr._undo("nonexistent")
    mgr.destroy()


# ---------- Auto dismiss ----------

def test_auto_dismiss_does_not_call_callback(ut_deps):
    mgr = _make(ut_deps)
    cb = MagicMock()
    mgr.show("task-auto", "text", cb)
    mgr._auto_dismiss("task-auto")
    cb.assert_not_called()
    assert len(mgr._queue) == 0
    mgr.destroy()


# ---------- Hide all ----------

def test_hide_all_clears(ut_deps):
    mgr = _make(ut_deps)
    for i in range(3):
        mgr.show(f"task-{i}", "text", MagicMock())
    mgr.hide_all()
    assert len(mgr._queue) == 0
    mgr.destroy()


# ---------- Stacking ----------

def test_stacking_count(ut_deps):
    mgr = _make(ut_deps)
    mgr.show("t1", "first", MagicMock())
    mgr.show("t2", "second", MagicMock())
    ut_deps["root"].update_idletasks()
    assert len(mgr._frames) == 2
    mgr.destroy()


# ---------- Content ----------

def test_toast_contains_undo_text(ut_deps):
    mgr = _make(ut_deps)
    mgr.show("task-1", "mytext", MagicMock())
    ut_deps["root"].update_idletasks()
    frame = mgr._frames[0]
    found_undo = False

    def walk(w):
        nonlocal found_undo
        try:
            if "Отменить" in str(w.cget("text")):
                found_undo = True
                return
        except (tk.TclError, ValueError, AttributeError):
            pass
        try:
            for child in w.winfo_children():
                walk(child)
        except (tk.TclError, AttributeError):
            pass
    walk(frame)
    assert found_undo
    mgr.destroy()


# ---------- Destroy ----------

def test_destroy_empties(ut_deps):
    mgr = _make(ut_deps)
    mgr.show("t1", "text", MagicMock())
    mgr.destroy()
    assert len(mgr._queue) == 0


# ---------- Markers ----------

def test_max_toasts_marker():
    source = inspect.getsource(UndoToastManager)
    assert "MAX_TOASTS = 3" in source


def test_ctkframe_not_toplevel():
    source = inspect.getsource(UndoToastManager)
    assert "CTkFrame" in source
    assert "CTkToplevel" not in source


def test_countdown_interval():
    source = inspect.getsource(UndoToastManager)
    assert "COUNTDOWN_INTERVAL_MS = 50" in source
    assert "self._root.after(" in source


def test_place_anchor_sw():
    source = inspect.getsource(UndoToastManager)
    assert 'anchor="sw"' in source
    assert "rely=1.0" in source


def test_toast_entry_dataclass():
    e = ToastEntry(task_id="t1", task_text="text", undo_callback=lambda: None)
    assert e.task_id == "t1"
    assert e.task_text == "text"
