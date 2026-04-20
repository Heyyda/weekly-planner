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


# ---------- Forest Phase D: inline edit-mode ----------


def _make_with_update(ds_deps, on_task_update, day_date=None):
    """Helper — создать DaySection с on_task_update callback."""
    if day_date is None:
        day_date = date.today()
    return DaySection(
        ds_deps["root"], day_date, False, ds_deps["theme"], "line",
        "user-1", ds_deps["on_toggle"], ds_deps["on_edit"],
        ds_deps["on_delete"], ds_deps["on_inline_add"],
        on_task_update=on_task_update,
    )


def test_enter_edit_mode_replaces_task_widget_with_card(ds_deps):
    """Forest Phase D: клик ✎ → TaskEditCard в позиции TaskWidget + flag."""
    ds = _make(ds_deps)
    task = ds_deps["factory"](text="orig")
    ds.render_tasks([task])
    ds_deps["root"].update_idletasks()

    ds.enter_edit_mode(task.id)
    ds_deps["root"].update_idletasks()

    assert ds._editing_task_id == task.id
    assert ds._edit_card is not None
    # TaskWidget frame pack_forget → winfo_manager() пусто.
    widget = ds._task_widgets[task.id]
    assert widget.frame.winfo_manager() == ""
    ds.destroy()


def test_second_edit_mode_saves_first_then_opens_new(ds_deps):
    """Forest Phase D: открытие ✎ на task B когда редактируем task A →
    A автосохраняется, B становится активной."""
    on_task_update = MagicMock()
    ds = _make_with_update(ds_deps, on_task_update)
    t1 = ds_deps["factory"](text="a", position=0)
    t2 = ds_deps["factory"](text="b", position=1)
    ds.render_tasks([t1, t2])
    ds_deps["root"].update_idletasks()

    ds.enter_edit_mode(t1.id)
    ds_deps["root"].update_idletasks()
    ds.enter_edit_mode(t2.id)
    ds_deps["root"].update_idletasks()

    # Первый task автосохранён (callback вызвался минимум раз с t1.id).
    assert on_task_update.called
    call_task_ids = [c.args[0] for c in on_task_update.call_args_list]
    assert t1.id in call_task_ids
    assert ds._editing_task_id == t2.id
    ds.destroy()


def test_exit_edit_mode_save_calls_on_task_update(ds_deps):
    """exit_edit_mode(save=True) → on_task_update(task_id, fields)."""
    on_task_update = MagicMock()
    ds = _make_with_update(ds_deps, on_task_update)
    task = ds_deps["factory"](text="x")
    ds.render_tasks([task])
    ds_deps["root"].update_idletasks()

    ds.enter_edit_mode(task.id)
    ds_deps["root"].update_idletasks()
    ds.exit_edit_mode(save=True)

    on_task_update.assert_called_once()
    args = on_task_update.call_args[0]
    assert args[0] == task.id
    assert isinstance(args[1], dict)
    assert "text" in args[1]
    assert args[1]["text"] == "x"
    ds.destroy()


def test_exit_edit_mode_cancel_does_not_call_on_task_update(ds_deps):
    """exit_edit_mode(save=False) → callback НЕ вызван."""
    on_task_update = MagicMock()
    ds = _make_with_update(ds_deps, on_task_update)
    task = ds_deps["factory"](text="x")
    ds.render_tasks([task])
    ds_deps["root"].update_idletasks()

    ds.enter_edit_mode(task.id)
    ds_deps["root"].update_idletasks()
    ds.exit_edit_mode(save=False)

    on_task_update.assert_not_called()
    # TaskWidget вернулся на место.
    widget = ds._task_widgets[task.id]
    assert widget.frame.winfo_manager() == "pack"
    assert ds._editing_task_id is None
    assert ds._edit_card is None
    ds.destroy()


# ---------- Forest Phase H: plus-btn hover tween + archive dimming ----------


def _pump_tween(root, widget, attr: str, expected_hex: str, timeout_s: float = 1.5) -> str:
    """Phase H helper — идентичен _pump_tween из test_task_widget.py."""
    import time
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        root.update()
        try:
            last = widget.cget(attr)
        except Exception:
            last = ""
        if str(last).lower() == expected_hex.lower():
            return last
    return last


def test_plus_btn_hover_tween(ds_deps):
    """Phase H Fix 1: <Enter> на plus-btn запускает ColorTween к accent_brand.

    Реализация уже в Phase G (строки ~330-333 day_section.py), этот тест
    фиксирует контракт — tween должен довести text_color до accent_brand
    за ~150ms."""
    ds = _make(ds_deps)
    ds_deps["root"].update_idletasks()
    assert ds._plus_btn is not None
    target = ds_deps["theme"].get("accent_brand")
    ds._tween_plus(target)
    final = _pump_tween(ds_deps["root"], ds._plus_btn, "text_color", target)
    assert str(final).lower() == target.lower()
    ds.destroy()


def test_plus_btn_hover_leave_restores_tertiary(ds_deps):
    """Phase H: <Leave> возвращает цвет к text_tertiary."""
    ds = _make(ds_deps)
    ds_deps["root"].update_idletasks()
    brand = ds_deps["theme"].get("accent_brand")
    tertiary = ds_deps["theme"].get("text_tertiary")
    # Сначала enter.
    ds._tween_plus(brand)
    _pump_tween(ds_deps["root"], ds._plus_btn, "text_color", brand)
    # Теперь leave.
    ds._tween_plus(tertiary)
    final = _pump_tween(ds_deps["root"], ds._plus_btn, "text_color", tertiary)
    assert str(final).lower() == tertiary.lower()
    ds.destroy()


def test_apply_dimmed_palette_with_dict_applies_dim(ds_deps):
    """Phase H Fix 2: apply_dimmed_palette(dim_dict) меняет frame bg к dim-значению."""
    ds = _make(ds_deps, is_today=True)
    ds_deps["root"].update_idletasks()
    # Построим dim: все ключи = "#000000" (крайний случай — полный чёрный).
    dim_dict = {
        "bg_primary": "#000000",
        "bg_secondary": "#000000",
        "bg_tertiary": "#111111",
        "text_primary": "#222222",
        "text_secondary": "#333333",
        "text_tertiary": "#444444",
        "accent_brand": "#555555",
    }
    ds.apply_dimmed_palette(dim_dict)
    # today секция: fg_color = bg_tertiary из dim-палитры.
    assert ds.frame.cget("fg_color") == "#111111"
    # today strip должен взять accent_brand из dim.
    assert ds._today_strip.cget("fg_color") == "#555555"
    ds.destroy()


def test_apply_dimmed_palette_none_restores_live(ds_deps):
    """Phase H Fix 2: apply_dimmed_palette(None) восстанавливает живую палитру."""
    ds = _make(ds_deps, is_today=True)
    ds_deps["root"].update_idletasks()
    original_bg = ds.frame.cget("fg_color")
    original_strip = ds._today_strip.cget("fg_color")
    # Сначала применим dim.
    dim_dict = {
        "bg_primary": "#000000",
        "bg_secondary": "#000000",
        "bg_tertiary": "#111111",
        "text_primary": "#222222",
        "text_secondary": "#333333",
        "text_tertiary": "#444444",
        "accent_brand": "#555555",
    }
    ds.apply_dimmed_palette(dim_dict)
    # Теперь None — вернёт оригинал.
    ds.apply_dimmed_palette(None)
    assert ds.frame.cget("fg_color") == original_bg
    assert ds._today_strip.cget("fg_color") == original_strip
    ds.destroy()
