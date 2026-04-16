"""Unit-тесты TaskWidget (Plan 04-03).

Покрывает: WEEK-04 (overdue visual), WEEK-05 (3 стиля), TASK-02 (toggle).
"""
import inspect
from unittest.mock import MagicMock

import pytest

from client.ui.task_widget import TaskWidget, VALID_STYLES


@pytest.fixture
def tw_deps(headless_tk, mock_theme_manager, timestamped_task_factory):
    return {
        "root": headless_tk,
        "theme": mock_theme_manager,
        "factory": timestamped_task_factory,
        "on_toggle": MagicMock(),
        "on_edit": MagicMock(),
        "on_delete": MagicMock(),
    }


def _make_widget(deps, task=None, style="card"):
    if task is None:
        task = deps["factory"]()
    w = TaskWidget(
        deps["root"], task, style, deps["theme"],
        deps["on_toggle"], deps["on_edit"], deps["on_delete"],
    )
    deps["root"].update_idletasks()
    return w


# ---------- Styles ----------

def test_three_styles(tw_deps):
    for style in ("card", "line", "minimal"):
        w = _make_widget(tw_deps, style=style)
        assert w._style == style
        w.destroy()


def test_invalid_style_falls_back_to_card(tw_deps):
    w = _make_widget(tw_deps, style="unknown_style")
    assert w._style == "card"
    w.destroy()


def test_valid_styles_set_has_three(tw_deps):
    assert VALID_STYLES == {"card", "line", "minimal"}


def test_card_style_corner_radius(tw_deps):
    w = _make_widget(tw_deps, style="card")
    assert w.frame.cget("corner_radius") == 8
    w.destroy()


def test_line_style_corner_radius_zero(tw_deps):
    w = _make_widget(tw_deps, style="line")
    assert w.frame.cget("corner_radius") == 0
    w.destroy()


def test_minimal_style_corner_radius(tw_deps):
    w = _make_widget(tw_deps, style="minimal")
    assert w.frame.cget("corner_radius") == 6
    w.destroy()


# ---------- Checkbox states ----------

def test_checkbox_canvas_size(tw_deps):
    w = _make_widget(tw_deps)
    assert int(w._cb_canvas.cget("width")) == 18
    assert int(w._cb_canvas.cget("height")) == 18
    w.destroy()


def test_checkbox_not_done_renders_border(tw_deps):
    task = tw_deps["factory"](done=False)
    w = _make_widget(tw_deps, task=task)
    items = w._cb_canvas.find_all()
    assert len(items) >= 1
    w.destroy()


def test_checkbox_done_renders_fill_and_checkmark(tw_deps):
    task = tw_deps["factory"](done=True)
    w = _make_widget(tw_deps, task=task)
    items = w._cb_canvas.find_all()
    assert len(items) >= 2
    w.destroy()


def test_checkbox_overdue_border_color(tw_deps):
    """WEEK-04: overdue → border = accent_overdue."""
    task = tw_deps["factory"](day_offset=-2, done=False)
    assert task.is_overdue() is True
    w = _make_widget(tw_deps, task=task)
    items = w._cb_canvas.find_all()
    assert len(items) >= 1
    outline = w._cb_canvas.itemcget(items[0], "outline")
    assert outline == tw_deps["theme"].get("accent_overdue")
    w.destroy()


# ---------- Time field ----------

def test_time_field_visible_with_time(tw_deps):
    task = tw_deps["factory"](time="14:30")
    w = _make_widget(tw_deps, task=task)
    assert w._time_label is not None
    assert "14:30" in w._time_label.cget("text")
    w.destroy()


def test_time_field_absent_without_time(tw_deps):
    task = tw_deps["factory"]()
    w = _make_widget(tw_deps, task=task)
    assert w._time_label is None
    w.destroy()


# ---------- Callbacks ----------

def test_checkbox_click_calls_on_toggle(tw_deps):
    """TASK-02: click → on_toggle(task_id, new_done)."""
    task = tw_deps["factory"](done=False)
    w = _make_widget(tw_deps, task=task)
    w._on_checkbox_click()
    tw_deps["on_toggle"].assert_called_once_with(task.id, True)
    w.destroy()


def test_checkbox_click_toggles_done(tw_deps):
    task = tw_deps["factory"](done=False)
    w = _make_widget(tw_deps, task=task)
    w._on_checkbox_click()
    assert w._task.done is True
    w._on_checkbox_click()
    assert w._task.done is False
    w.destroy()


def test_edit_callback_invokes(tw_deps):
    task = tw_deps["factory"]()
    w = _make_widget(tw_deps, task=task)
    w._on_edit(task.id)
    tw_deps["on_edit"].assert_called_once_with(task.id)
    w.destroy()


def test_delete_callback_invokes(tw_deps):
    task = tw_deps["factory"]()
    w = _make_widget(tw_deps, task=task)
    w._on_delete(task.id)
    tw_deps["on_delete"].assert_called_once_with(task.id)
    w.destroy()


# ---------- Hover ----------

def test_hover_enter_sets_flag(tw_deps):
    w = _make_widget(tw_deps)
    w._on_hover_enter()
    assert w._hover is True
    w.destroy()


def test_hover_leave_clears_flag(tw_deps):
    w = _make_widget(tw_deps)
    w._on_hover_enter()
    w._on_hover_leave()
    assert w._hover is False
    w.destroy()


# ---------- Update task ----------

def test_update_task_changes_text_without_rebuild(tw_deps):
    """PITFALL 4: update_task не пересоздаёт frame."""
    task = tw_deps["factory"](text="old")
    w = _make_widget(tw_deps, task=task)
    original_frame = w.frame
    new_task = tw_deps["factory"](text="new")
    new_task.id = task.id
    w.update_task(new_task)
    assert w.frame is original_frame
    assert w._text_label.cget("text") == "new"
    w.destroy()


# ---------- Theme switch ----------

def test_theme_switch_survives(tw_deps):
    w = _make_widget(tw_deps)
    tw_deps["theme"].set_theme("dark")
    assert w._cb_canvas.winfo_exists()
    w.destroy()


# ---------- Cyrillic ----------

def test_cyrillic_text_renders(tw_deps):
    task = tw_deps["factory"](text="Позвонить Иванову")
    w = _make_widget(tw_deps, task=task)
    assert w._text_label.cget("text") == "Позвонить Иванову"
    w.destroy()


# ---------- Markers ----------

def test_d11_constants_present():
    """D-11 grep marker."""
    source = inspect.getsource(TaskWidget)
    assert "CHECKBOX_SIZE = 18" in source
    assert "CHECKBOX_RADIUS = 3" in source


def test_get_body_frame_returns_body(tw_deps):
    """Plan 04-09 DnD integration point."""
    w = _make_widget(tw_deps)
    body = w.get_body_frame()
    assert body is not None
    assert body is w._body_frame
    w.destroy()


def test_destroy_marks_widget(tw_deps):
    w = _make_widget(tw_deps)
    w.destroy()
    tw_deps["root"].update_idletasks()
    assert w._destroyed is True
