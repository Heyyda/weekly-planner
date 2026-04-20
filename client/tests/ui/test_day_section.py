"""Unit-тесты DaySection (Plan 04-04).

Покрывает: WEEK-01 (7 секций), TASK-07 (sort by position).
"""
import tkinter as tk
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from client.ui.day_section import DaySection, DAY_NAMES_RU_SHORT


@pytest.fixture
def ds_deps(headless_tk, mock_theme_manager, timestamped_task_factory):
    return {
        "root": headless_tk,
        "theme": mock_theme_manager,
        "factory": timestamped_task_factory,
        "on_toggle": MagicMock(),
        "on_edit": MagicMock(),
        "on_delete": MagicMock(),
        "on_inline_add": MagicMock(),
    }


def _make(ds_deps, day_date=None, is_today=False, style="card"):
    if day_date is None:
        day_date = date.today()
    return DaySection(
        ds_deps["root"], day_date, is_today, ds_deps["theme"], style,
        "user-1", ds_deps["on_toggle"], ds_deps["on_edit"],
        ds_deps["on_delete"], ds_deps["on_inline_add"],
    )


# ---------- Header ----------

def test_creates_frame(ds_deps):
    ds = _make(ds_deps)
    assert ds.frame.winfo_exists()
    ds.destroy()


def test_is_today_adds_strip(ds_deps):
    ds = _make(ds_deps, is_today=True)
    assert ds._today_strip is not None
    ds.destroy()


def test_not_today_no_strip(ds_deps):
    ds = _make(ds_deps, is_today=False)
    assert ds._today_strip is None
    ds.destroy()


def test_counter_starts_empty(ds_deps):
    """v0.4.0: count=0 → пустой текст (без '(0)')."""
    ds = _make(ds_deps)
    assert ds._counter_label.cget("text") == ""
    ds.destroy()


# ---------- render_tasks ----------

def test_render_empty_shows_plus(ds_deps):
    """v0.4.0: plus_btn (не plus_label) всегда в header — независимо от tasks."""
    ds = _make(ds_deps)
    ds.render_tasks([])
    assert ds._plus_btn is not None
    ds.destroy()


def test_render_single_task(ds_deps):
    ds = _make(ds_deps)
    task = ds_deps["factory"](text="test")
    ds.render_tasks([task])
    assert task.id in ds._task_widgets
    ds.destroy()


def test_counter_updates(ds_deps):
    """v0.4.0: counter показывает число без скобок."""
    ds = _make(ds_deps)
    t1 = ds_deps["factory"](text="a")
    t2 = ds_deps["factory"](text="b")
    ds.render_tasks([t1, t2])
    assert ds._counter_label.cget("text") == "2"
    ds.destroy()


def test_sorted_by_position(ds_deps):
    """TASK-07: sort by position ASC."""
    ds = _make(ds_deps)
    t_a = ds_deps["factory"](text="a", position=2)
    t_b = ds_deps["factory"](text="b", position=0)
    t_c = ds_deps["factory"](text="c", position=1)
    ds.render_tasks([t_a, t_b, t_c])
    positions = [t.position for t in ds._tasks]
    assert positions == [0, 1, 2]
    texts = [t.text for t in ds._tasks]
    assert texts == ["b", "c", "a"]
    ds.destroy()


def test_partial_update_reuses_widgets(ds_deps):
    """PITFALL 4: existing task reuses widget."""
    ds = _make(ds_deps)
    t1 = ds_deps["factory"](text="original")
    ds.render_tasks([t1])
    original_widget = ds._task_widgets[t1.id]

    t1_updated = ds_deps["factory"](text="updated")
    t1_updated.id = t1.id
    ds.render_tasks([t1_updated])
    assert ds._task_widgets[t1.id] is original_widget
    ds.destroy()


def test_removes_deleted_widgets(ds_deps):
    ds = _make(ds_deps)
    t1 = ds_deps["factory"](text="a")
    t2 = ds_deps["factory"](text="b")
    ds.render_tasks([t1, t2])
    assert len(ds._task_widgets) == 2
    ds.render_tasks([t1])
    assert len(ds._task_widgets) == 1
    assert t1.id in ds._task_widgets
    assert t2.id not in ds._task_widgets
    ds.destroy()


# ---------- Inline add ----------

def test_inline_add_shows_entry(ds_deps):
    ds = _make(ds_deps)
    ds._show_inline_add()
    assert ds._inline_entry is not None
    ds.destroy()


def test_inline_add_enter_calls_callback(ds_deps):
    ds = _make(ds_deps)
    ds._show_inline_add()
    ds._inline_entry.insert(0, "купить хлеб")
    ds._on_inline_enter()
    ds_deps["on_inline_add"].assert_called_once()
    task_arg = ds_deps["on_inline_add"].call_args[0][0]
    assert task_arg.text == "купить хлеб"
    assert task_arg.day == date.today().isoformat()
    ds.destroy()


def test_inline_add_empty_enter_no_callback(ds_deps):
    ds = _make(ds_deps)
    ds._show_inline_add()
    ds._on_inline_enter()
    ds_deps["on_inline_add"].assert_not_called()
    ds.destroy()


def test_inline_add_hides_on_escape(ds_deps):
    ds = _make(ds_deps)
    ds._show_inline_add()
    ds._hide_inline_add()
    assert ds._inline_entry is None
    ds.destroy()


def test_inline_add_with_time_parses(ds_deps):
    ds = _make(ds_deps)
    ds._show_inline_add()
    ds._inline_entry.insert(0, "задача 14:00")
    ds._on_inline_enter()
    task = ds_deps["on_inline_add"].call_args[0][0]
    assert task.time_deadline == "14:00"
    assert task.text == "задача"
    ds.destroy()


# ---------- Archive ----------

def test_archive_mode_blocks_inline_add(ds_deps):
    ds = _make(ds_deps)
    ds.set_archive_mode(True)
    ds._show_inline_add()
    assert ds._inline_entry is None
    ds.destroy()


# ---------- Integration points ----------

def test_get_body_frame_returns_body(ds_deps):
    """Plan 04-09 DnD target."""
    ds = _make(ds_deps)
    body = ds.get_body_frame()
    assert body is ds._body_frame
    ds.destroy()


def test_get_day_date(ds_deps):
    today = date.today()
    ds = _make(ds_deps, day_date=today)
    assert ds.get_day_date() == today
    ds.destroy()


# ---------- Day names ----------

def test_day_names_complete():
    assert len(DAY_NAMES_RU_SHORT) == 7
    assert DAY_NAMES_RU_SHORT[0] == "Пн"
    assert DAY_NAMES_RU_SHORT[6] == "Вс"


# ---------- Destroy ----------

def test_destroy_cleans_widgets(ds_deps):
    ds = _make(ds_deps)
    t = ds_deps["factory"]()
    ds.render_tasks([t])
    ds.destroy()
    ds_deps["root"].update_idletasks()
    assert ds._destroyed is True
    assert ds._task_widgets == {}


# ---------- Forest Phase B: structural polish ----------

def test_today_bg_is_bg_tertiary(ds_deps):
    """Forest Phase B: today-секция использует bg_tertiary (forest-tint),
    а не bg_secondary (lifted surface)."""
    ds = _make(ds_deps, is_today=True)
    expected = ds_deps["theme"].get("bg_tertiary")
    assert ds.frame.cget("fg_color") == expected
    ds.destroy()


def test_regular_day_bg_is_transparent(ds_deps):
    """Forest Phase B: regular days сливаются с фоном окна (bg_primary)
    через fg_color='transparent' — без отдельной карточки."""
    ds = _make(ds_deps, is_today=False)
    assert ds.frame.cget("fg_color") == "transparent"
    ds.destroy()


def test_divider_exists_and_uses_bg_tertiary(ds_deps):
    """Forest Phase B: каждая секция имеет 1px divider цвета bg_tertiary."""
    ds = _make(ds_deps)
    assert ds._divider is not None
    assert ds._divider.cget("fg_color") == ds_deps["theme"].get("bg_tertiary")
    assert int(ds._divider.cget("height")) == 1
    ds.destroy()


def test_corner_radius_is_12():
    """Forest Phase B: CORNER_RADIUS поднят 10 → 12 (spec 4.3)."""
    from client.ui.day_section import CORNER_RADIUS
    assert CORNER_RADIUS == 12


def test_task_widgets_forced_to_line_style(ds_deps):
    """Forest Phase B: TaskWidget принудительно создаётся в стиле 'line',
    даже если caller передал task_style='card'."""
    ds = _make(ds_deps, style="card")
    t = ds_deps["factory"](text="x")
    ds.render_tasks([t])
    w = ds._task_widgets[t.id]
    assert w._style == "line"
    ds.destroy()
