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
    assert w.frame.cget("corner_radius") == 10
    w.destroy()


def test_line_style_corner_radius_zero(tw_deps):
    w = _make_widget(tw_deps, style="line")
    assert w.frame.cget("corner_radius") == 0
    w.destroy()


def test_minimal_style_corner_radius(tw_deps):
    w = _make_widget(tw_deps, style="minimal")
    assert w.frame.cget("corner_radius") == 10
    w.destroy()


# ---------- Checkbox states ----------

def test_checkbox_canvas_size(tw_deps):
    w = _make_widget(tw_deps)
    assert int(w._cb_canvas.cget("width")) == 22  # v0.4.0 bumped 18→22
    assert int(w._cb_canvas.cget("height")) == 22
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
    """v0.4.0: time_label создаётся но не packнут (скрыт) если time пустое."""
    task = tw_deps["factory"]()
    w = _make_widget(tw_deps, task=task)
    # Label существует, но без pack manager (скрыт)
    assert w._time_label is not None
    assert w._time_label.winfo_manager() == ""  # not packed
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
    """D-11 grep marker (v0.4.0: bumped to 22×22 с r=4)."""
    source = inspect.getsource(TaskWidget)
    assert "CHECKBOX_SIZE = 22" in source
    assert "CHECKBOX_RADIUS = 4" in source


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


# ---------- Forest Phase B: palette-driven checkmark + clay delete hover ----------

def test_done_checkmark_uses_bg_primary(tw_deps):
    """Forest Phase B: чекмарк берёт цвет из палитры (bg_primary), не захардкожен white."""
    task = tw_deps["factory"](done=True)
    w = _make_widget(tw_deps, task=task)
    # Checkmark = второй item на canvas (первый — fill rectangle).
    items = w._cb_canvas.find_all()
    assert len(items) >= 2
    checkmark_line = items[1]
    fill = w._cb_canvas.itemcget(checkmark_line, "fill")
    assert fill == tw_deps["theme"].get("bg_primary")
    w.destroy()


def _pump_tween(root, btn, expected_hex: str, timeout_s: float = 1.5) -> str:
    """Phase G: прокрутить event-loop пока ColorTween не доведёт btn.text_color
    до expected_hex. Возвращает финальный cget значение."""
    import time
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        root.update()
        try:
            last = btn.cget("text_color")
        except Exception:
            last = ""
        if str(last).lower() == expected_hex.lower():
            return last
    return last


def test_delete_icon_hover_uses_accent_overdue(tw_deps):
    """Forest Phase B: hover на 🗑 красит иконку в accent_overdue (clay).
    Phase G: цвет достигается через ColorTween (~150ms), pump'им event-loop."""
    w = _make_widget(tw_deps)
    target = tw_deps["theme"].get("accent_overdue")
    w._icon_hover(w._del_btn, entering=True)
    final = _pump_tween(tw_deps["root"], w._del_btn, target)
    assert str(final).lower() == target.lower()
    w.destroy()


def test_edit_icon_hover_still_uses_accent_brand(tw_deps):
    """Forest Phase B: hover на ✎ → accent_brand (forest). Phase G: через tween."""
    w = _make_widget(tw_deps)
    target = tw_deps["theme"].get("accent_brand")
    w._icon_hover(w._edit_btn, entering=True)
    final = _pump_tween(tw_deps["root"], w._edit_btn, target)
    assert str(final).lower() == target.lower()
    w.destroy()


# ---------- Forest Phase H: done-task overstrike ----------


def test_done_task_has_overstrike(tw_deps):
    """Phase H Fix 4: done-задача рендерится с overstrike через tkinter font-tuple
    (family, size, 'overstrike'). Проверяем через tkinter.font.Font на text_label.

    Реализация в task_widget.py _update_text_decoration: для done
    configure(font=(family, size, 'overstrike')). Tk интерпретирует строку
    'overstrike' как font-style flag → overstrike=1 в Font.actual()."""
    import tkinter.font as tkfont
    task = tw_deps["factory"](done=True)
    w = _make_widget(tw_deps, task=task)
    label = w._text_label
    assert label is not None and label.winfo_exists()
    # Получить актуальный font-spec после configure.
    font_spec = label.cget("font")
    # font_spec может быть tuple или CTkFont — резолвим через tkfont.Font().
    try:
        f = tkfont.Font(root=tw_deps["root"], font=font_spec)
        actual_overstrike = f.actual("overstrike")
    except Exception:
        # Fallback: проверить на tuple-form.
        actual_overstrike = int("overstrike" in str(font_spec).lower())
    assert int(actual_overstrike) == 1, (
        f"done-task текст должен быть overstrike, получили font={font_spec!r}"
    )
    w.destroy()


def test_not_done_task_has_no_overstrike(tw_deps):
    """Phase H Fix 4: недовыполненная задача НЕ имеет overstrike."""
    import tkinter.font as tkfont
    task = tw_deps["factory"](done=False)
    w = _make_widget(tw_deps, task=task)
    label = w._text_label
    font_spec = label.cget("font")
    try:
        f = tkfont.Font(root=tw_deps["root"], font=font_spec)
        actual_overstrike = f.actual("overstrike")
    except Exception:
        actual_overstrike = int("overstrike" in str(font_spec).lower())
    assert int(actual_overstrike) == 0
    w.destroy()


def test_done_toggle_applies_and_removes_overstrike(tw_deps):
    """Phase H Fix 4: переключение done=True/False меняет overstrike-flag."""
    import tkinter.font as tkfont
    task = tw_deps["factory"](done=False)
    w = _make_widget(tw_deps, task=task)
    # Toggle → done=True → overstrike=1
    w._on_checkbox_click()
    tw_deps["root"].update_idletasks()
    f1 = tkfont.Font(root=tw_deps["root"], font=w._text_label.cget("font"))
    assert f1.actual("overstrike") == 1
    # Toggle back → done=False → overstrike=0
    w._on_checkbox_click()
    tw_deps["root"].update_idletasks()
    f2 = tkfont.Font(root=tw_deps["root"], font=w._text_label.cget("font"))
    assert f2.actual("overstrike") == 0
    w.destroy()
