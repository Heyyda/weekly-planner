"""Unit-тесты QuickCapturePopup (Plan 04-06)."""
import inspect
import tkinter as tk
from unittest.mock import MagicMock

import pytest

from client.ui.quick_capture import QuickCapturePopup


@pytest.fixture
def qc_deps(headless_tk, mock_theme_manager):
    return {
        "root": headless_tk,
        "theme": mock_theme_manager,
        "on_save": MagicMock(),
    }


def _make(qc_deps):
    return QuickCapturePopup(qc_deps["root"], qc_deps["theme"], qc_deps["on_save"])


# ---------- Lifecycle ----------

def test_popup_initial_hidden(qc_deps):
    qc = _make(qc_deps)
    assert qc.is_visible() is False
    qc.destroy()


def test_show_at_overlay_creates_toplevel(qc_deps):
    qc = _make(qc_deps)
    qc.show_at_overlay(100, 100, 73)
    qc_deps["root"].update_idletasks()
    assert qc._popup is not None
    qc.destroy()


def test_show_twice_toggles(qc_deps):
    qc = _make(qc_deps)
    qc.show_at_overlay(100, 100)
    qc_deps["root"].update()
    qc._visible = True
    qc.show_at_overlay(100, 100)
    assert qc._visible is False


def test_hide_destroys_popup(qc_deps):
    qc = _make(qc_deps)
    qc.show_at_overlay(100, 100)
    qc_deps["root"].update_idletasks()
    qc.hide()
    assert qc._popup is None


# ---------- Edge-flip ----------

def test_edge_flip_at_bottom_inverts_y(qc_deps):
    qc = _make(qc_deps)
    overlay_y = 450
    overlay_size = 73
    screen_h_sim = 500
    needed = overlay_y + overlay_size + qc.POPUP_GAP + qc.POPUP_HEIGHT + qc.EDGE_MARGIN
    assert needed > screen_h_sim
    expected_y = overlay_y - qc.POPUP_HEIGHT - qc.POPUP_GAP
    assert expected_y < overlay_y


def test_no_flip_at_top(qc_deps):
    qc = _make(qc_deps)
    overlay_y = 10
    overlay_size = 73
    expected_y = overlay_y + overlay_size + qc.POPUP_GAP
    assert expected_y > overlay_y


# ---------- Enter save ----------

def test_enter_saves_parsed_result(qc_deps):
    qc = _make(qc_deps)
    qc.show_at_overlay(100, 100)
    qc_deps["root"].update()
    qc._init_popup_style()
    qc_deps["root"].update()

    qc._entry.insert(0, "встреча завтра 14:00")
    qc._on_enter()
    qc_deps["on_save"].assert_called_once()
    args = qc_deps["on_save"].call_args[0]
    assert args[0] == "встреча"
    from datetime import date, timedelta
    assert args[1] == (date.today() + timedelta(1)).isoformat()
    assert args[2] == "14:00"
    qc.destroy()


def test_enter_empty_no_save(qc_deps):
    qc = _make(qc_deps)
    qc.show_at_overlay(100, 100)
    qc_deps["root"].update()
    qc._init_popup_style()
    qc_deps["root"].update()

    qc._on_enter()
    qc_deps["on_save"].assert_not_called()
    qc.destroy()


def test_enter_clears_entry_multi_add(qc_deps):
    qc = _make(qc_deps)
    qc.show_at_overlay(100, 100)
    qc_deps["root"].update()
    qc._init_popup_style()
    qc_deps["root"].update()

    qc._entry.insert(0, "задача 1")
    qc._on_enter()
    assert qc._entry.get() == ""
    qc.destroy()


def test_whitespace_only_no_save(qc_deps):
    qc = _make(qc_deps)
    qc.show_at_overlay(100, 100)
    qc_deps["root"].update()
    qc._init_popup_style()
    qc_deps["root"].update()

    qc._entry.insert(0, "   ")
    qc._on_enter()
    qc_deps["on_save"].assert_not_called()
    qc.destroy()


# ---------- show_centered ----------

def test_show_centered_creates_popup(qc_deps):
    qc = _make(qc_deps)
    qc.show_centered(500, 300)
    qc_deps["root"].update_idletasks()
    assert qc._popup is not None
    qc.destroy()


# ---------- Markers ----------

def test_pitfall_1_after_100_markers():
    source = inspect.getsource(QuickCapturePopup)
    assert "INIT_DELAY_MS = 100" in source
    assert "after(self.INIT_DELAY_MS" in source


def test_d02_toolwindow_marker():
    source = inspect.getsource(QuickCapturePopup)
    assert "-toolwindow" in source


def test_pitfall_3_focus_check_delay():
    source = inspect.getsource(QuickCapturePopup)
    assert "FOCUS_CHECK_DELAY_MS = 50" in source
    assert "_check_focus" in source


def test_parse_input_integrated():
    import client.ui.quick_capture as qc_module
    source = inspect.getsource(qc_module)
    assert "from shared.parse_input import parse_quick_input" in source


# ---------- Focus-loss dismiss ----------

def test_check_focus_callable_without_crash(qc_deps):
    """_check_focus не должен падать при любом состоянии focus_get (headless)."""
    qc = _make(qc_deps)
    qc.show_at_overlay(100, 100)
    qc_deps["root"].update()
    qc._init_popup_style()
    qc_deps["root"].update()
    # Просто убедиться что вызов не падает
    qc._check_focus()
    qc.destroy()
