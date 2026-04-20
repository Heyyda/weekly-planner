"""Unit-тесты WeekNavigation (Plan 04-05).

Покрывает WEEK-02 (prev/next), WEEK-03 (today visibility), WEEK-06 (archive).
"""
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from client.ui.week_navigation import (
    WeekNavigation,
    get_week_monday,
    get_current_week_monday,
    get_iso_week_number,
    is_archive_week,
    format_week_header,
    interpolate_palette,
)


# ---------- Helpers ----------

def test_get_week_monday_tuesday():
    tuesday = date(2026, 4, 14)
    assert get_week_monday(tuesday) == date(2026, 4, 13)


def test_get_week_monday_sunday():
    sunday = date(2026, 4, 12)
    assert get_week_monday(sunday) == date(2026, 4, 6)


def test_get_iso_week_number():
    assert get_iso_week_number(date(2026, 4, 14)) > 0
    assert isinstance(get_iso_week_number(date(2026, 4, 14)), int)


def test_is_archive_week_past():
    past_monday = get_current_week_monday() - timedelta(days=7)
    assert is_archive_week(past_monday) is True


def test_is_archive_week_current():
    assert is_archive_week(get_current_week_monday()) is False


def test_is_archive_week_future():
    """D-32: future = not archive."""
    future_monday = get_current_week_monday() + timedelta(days=7)
    assert is_archive_week(future_monday) is False


def test_format_week_header_has_week_label():
    header = format_week_header(date(2026, 4, 13))
    assert "Неделя" in header
    assert "•" in header


def test_format_week_header_has_month():
    header = format_week_header(date(2026, 4, 13))
    assert "апр" in header or "май" in header


# ---------- interpolate_palette ----------

def test_interpolate_palette_factor_half_blends_white_and_black():
    pal = {"c": "#ffffff"}
    r = interpolate_palette(pal, "#000000", 0.5)
    assert r["c"] == "#7f7f7f"


def test_interpolate_palette_preserves_non_hex():
    pal = {"bg": "#ffffff", "shadow_card": "rgba(0, 0, 0, 0.3)"}
    r = interpolate_palette(pal, "#000000", 0.5)
    assert r["shadow_card"] == "rgba(0, 0, 0, 0.3)"


def test_interpolate_palette_full_factor_matches_target():
    pal = {"c": "#ff0000"}
    r = interpolate_palette(pal, "#000000", 1.0)
    assert r["c"] == "#000000"


# ---------- WeekNavigation class ----------

@pytest.fixture
def wn_deps(headless_tk, mock_theme_manager):
    return {
        "parent": headless_tk,
        "window": headless_tk,
        "theme": mock_theme_manager,
        "on_week_changed": MagicMock(),
        "on_archive_changed": MagicMock(),
    }


def _make(wn_deps):
    return WeekNavigation(
        wn_deps["parent"], wn_deps["window"], wn_deps["theme"],
        wn_deps["on_week_changed"], wn_deps["on_archive_changed"],
    )


def test_initial_is_current_week(wn_deps):
    wn = _make(wn_deps)
    assert wn.get_week_monday() == get_current_week_monday()
    wn.destroy()


def test_prev_week_shifts_minus_seven(wn_deps):
    wn = _make(wn_deps)
    initial = wn.get_week_monday()
    wn.prev_week()
    assert wn.get_week_monday() == initial - timedelta(days=7)
    wn_deps["on_week_changed"].assert_called_with(wn.get_week_monday())
    wn.destroy()


def test_next_week_shifts_plus_seven(wn_deps):
    wn = _make(wn_deps)
    initial = wn.get_week_monday()
    wn.next_week()
    assert wn.get_week_monday() == initial + timedelta(days=7)
    wn.destroy()


def test_today_resets(wn_deps):
    wn = _make(wn_deps)
    wn.prev_week()
    wn.prev_week()
    wn.today()
    assert wn.get_week_monday() == get_current_week_monday()
    wn.destroy()


def test_today_button_hidden_on_current(wn_deps):
    """WEEK-03."""
    wn = _make(wn_deps)
    wn_deps["window"].update_idletasks()
    assert not wn._today_btn.winfo_ismapped()
    wn.destroy()


def test_today_button_visible_after_prev(wn_deps):
    """После prev_week — today_btn имеет pack manager (видим через pack_info)."""
    wn = _make(wn_deps)
    wn.prev_week()
    wn_deps["window"].update_idletasks()
    # pack_info() работает если виджет упакован; иначе throws
    info = wn._today_btn.pack_info() if wn._today_btn.winfo_manager() else None
    assert info is not None
    wn.destroy()


def test_today_button_hidden_after_today(wn_deps):
    wn = _make(wn_deps)
    wn.prev_week()
    wn.today()
    wn_deps["window"].update_idletasks()
    assert not wn._today_btn.winfo_ismapped()
    wn.destroy()


def test_is_current_archive_past(wn_deps):
    wn = _make(wn_deps)
    wn.prev_week()
    assert wn.is_current_archive() is True
    wn.destroy()


def test_is_current_archive_future(wn_deps):
    wn = _make(wn_deps)
    wn.next_week()
    assert wn.is_current_archive() is False
    wn.destroy()


def test_on_archive_changed_on_enter_archive(wn_deps):
    wn = _make(wn_deps)
    wn_deps["on_archive_changed"].reset_mock()
    wn.prev_week()
    wn_deps["on_archive_changed"].assert_called_with(True)
    wn.destroy()


def test_on_archive_changed_on_leave_archive(wn_deps):
    wn = _make(wn_deps)
    wn.prev_week()
    wn_deps["on_archive_changed"].reset_mock()
    wn.today()
    wn_deps["on_archive_changed"].assert_called_with(False)
    wn.destroy()


def test_on_archive_changed_not_called_twice(wn_deps):
    """Debounce."""
    wn = _make(wn_deps)
    wn.prev_week()
    wn_deps["on_archive_changed"].reset_mock()
    wn.prev_week()
    wn_deps["on_archive_changed"].assert_not_called()
    wn.destroy()


def test_header_label_updates_on_nav(wn_deps):
    wn = _make(wn_deps)
    original_text = wn._header_label.cget("text")
    wn.prev_week()
    new_text = wn._header_label.cget("text")
    assert new_text != original_text
    wn.destroy()


def test_archive_banner_visible_in_archive(wn_deps):
    wn = _make(wn_deps)
    wn.prev_week()
    wn_deps["window"].update_idletasks()
    assert wn._archive_banner.winfo_manager() == "pack"
    wn.destroy()


def test_archive_banner_hidden_in_current(wn_deps):
    wn = _make(wn_deps)
    wn_deps["window"].update_idletasks()
    assert wn._archive_banner.winfo_manager() != "pack"
    wn.destroy()


# ---------- Keyboard (D-30) ----------
# Note: event_generate() плохо работает с session-shared headless_tk.
# Вместо этого проверяем что bindings зарегистрированы на window.

def test_keyboard_ctrl_left_bound(wn_deps):
    wn = _make(wn_deps)
    bindings = wn_deps["window"].bind("<Control-Left>")
    assert bindings  # non-empty string = bound
    wn.destroy()


def test_keyboard_ctrl_right_bound(wn_deps):
    wn = _make(wn_deps)
    bindings = wn_deps["window"].bind("<Control-Right>")
    assert bindings
    wn.destroy()


def test_keyboard_ctrl_t_bound(wn_deps):
    wn = _make(wn_deps)
    bindings = wn_deps["window"].bind("<Control-t>")
    assert bindings
    wn.destroy()
