"""Unit-тесты LoginDialog (Forest Phase E 260421-1jo).

Проверяем:
  - Primary buttons ("Запросить код", "Войти") — forest fill + cream text
  - Back button — ghost (transparent + border text_tertiary)
  - Error status — accent_overdue (clay), НЕ #C94A4A
  - Success status — accent_brand (forest)
  - Theme switching live-обновляет buttons и status color
  - Нет хардкода #C94A4A в source
"""
import inspect
import tkinter as tk
from unittest.mock import MagicMock

import pytest

from client.ui.login_dialog import LoginDialog
from client.ui.themes import PALETTES, ThemeManager


@pytest.fixture
def auth_stub():
    am = MagicMock()
    am.request_code.return_value = "req-123"
    am.verify_code.return_value = True
    return am


@pytest.fixture
def theme_forest_light():
    return ThemeManager(initial="forest_light")


@pytest.fixture
def dialog_deps(headless_tk, theme_forest_light, auth_stub):
    return {
        "root": headless_tk,
        "theme": theme_forest_light,
        "auth": auth_stub,
    }


def _make(dialog_deps):
    return LoginDialog(
        dialog_deps["root"],
        dialog_deps["theme"],
        dialog_deps["auth"],
    )


def _normalize(color) -> str:
    if isinstance(color, (tuple, list)):
        return color[0]
    return color


# ==================== Init ====================

def test_dialog_creates_toplevel(dialog_deps):
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()
    assert dlg._dialog.winfo_exists()
    assert dlg._primary_btn is not None
    dlg._close_dialog()


# ==================== Primary button (forest filled) ====================

def test_primary_button_forest_fill(dialog_deps):
    """Запросить код: fg_color == accent_brand forest."""
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()
    fg = _normalize(dlg._primary_btn.cget("fg_color"))
    expected = PALETTES["forest_light"]["accent_brand"]
    assert fg == expected
    dlg._close_dialog()


def test_primary_button_cream_text(dialog_deps):
    """Запросить код: text_color == bg_primary (cream) для контраста."""
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()
    tc = _normalize(dlg._primary_btn.cget("text_color"))
    expected = PALETTES["forest_light"]["bg_primary"]
    assert tc == expected
    dlg._close_dialog()


def test_primary_button_hover_forest_light(dialog_deps):
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()
    hc = _normalize(dlg._primary_btn.cget("hover_color"))
    expected = PALETTES["forest_light"]["accent_brand_light"]
    assert hc == expected
    dlg._close_dialog()


# ==================== Back button (ghost) ====================

def test_back_button_is_ghost(dialog_deps):
    """Step 2: back button — transparent fill."""
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()

    # Переходим на step 2 через call build_code_step напрямую (обход request API)
    dlg._request_id = "req-fake"
    dlg._build_code_step()
    dialog_deps["root"].update_idletasks()

    assert dlg._back_btn is not None
    fg = _normalize(dlg._back_btn.cget("fg_color"))
    assert fg == "transparent", f"Back btn должен быть transparent, got {fg}"

    bc = _normalize(dlg._back_btn.cget("border_color"))
    expected = PALETTES["forest_light"]["text_tertiary"]
    assert bc == expected
    dlg._close_dialog()


def test_back_button_text_secondary(dialog_deps):
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()
    dlg._request_id = "req-fake"
    dlg._build_code_step()
    dialog_deps["root"].update_idletasks()

    tc = _normalize(dlg._back_btn.cget("text_color"))
    expected = PALETTES["forest_light"]["text_secondary"]
    assert tc == expected
    dlg._close_dialog()


# ==================== Status color (error = clay, success = forest) ====================

def test_error_status_uses_accent_overdue(dialog_deps):
    """_set_status(..., error=True) → text_color == palette['accent_overdue'] (clay)."""
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()
    dlg._set_status("Ошибка какая-то", error=True)
    dialog_deps["root"].update_idletasks()

    tc = _normalize(dlg._status_label.cget("text_color"))
    expected = PALETTES["forest_light"]["accent_overdue"]  # #9E6A5A
    assert tc == expected, f"Error status должен быть clay {expected}, got {tc}"
    dlg._close_dialog()


def test_success_status_uses_accent_brand(dialog_deps):
    """_set_status(..., error=False) → text_color == palette['accent_brand'] (forest)."""
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()
    dlg._set_status("Успех!", error=False)
    dialog_deps["root"].update_idletasks()

    tc = _normalize(dlg._status_label.cget("text_color"))
    expected = PALETTES["forest_light"]["accent_brand"]
    assert tc == expected
    dlg._close_dialog()


# ==================== Theme switching ====================

def test_primary_button_updates_on_theme_change(dialog_deps):
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()

    dialog_deps["theme"].set_theme("forest_dark")
    dialog_deps["root"].update_idletasks()

    fg = _normalize(dlg._primary_btn.cget("fg_color"))
    expected_dark = PALETTES["forest_dark"]["accent_brand"]
    assert fg == expected_dark
    dlg._close_dialog()


def test_error_status_updates_on_theme_change(dialog_deps):
    """После set_theme('forest_dark') error status цвет — dark accent_overdue."""
    dlg = _make(dialog_deps)
    dialog_deps["root"].update_idletasks()
    dlg._set_status("Ошибка", error=True)
    dialog_deps["root"].update_idletasks()

    dialog_deps["theme"].set_theme("forest_dark")
    dialog_deps["root"].update_idletasks()

    tc = _normalize(dlg._status_label.cget("text_color"))
    expected = PALETTES["forest_dark"]["accent_overdue"]  # #B87D6F
    assert tc == expected
    dlg._close_dialog()


# ==================== No hardcoded hex ====================

def test_no_hardcoded_c94a4a_in_source():
    """login_dialog.py не должен содержать #C94A4A (старый error hex)."""
    import client.ui.login_dialog as mod
    src = inspect.getsource(mod)
    assert "#C94A4A" not in src, "Legacy #C94A4A найден — должно быть через palette['accent_overdue']"


def test_no_hardcoded_blue_in_source():
    """Никаких старых синих/красных."""
    import client.ui.login_dialog as mod
    src = inspect.getsource(mod)
    for forbidden in ("#1E73E8", "#4EA1FF", "#E85A5A", "#F07272", "#C94A4A"):
        assert forbidden not in src, f"Found forbidden hex {forbidden}"
