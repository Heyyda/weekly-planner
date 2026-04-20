"""Unit-тесты UpdateBanner (Forest Phase E 260421-1jo).

Проверяем что:
  - "Обновить" использует accent_brand (forest) + bg_primary (cream) text
  - "Позже" — ghost: transparent fill + border text_tertiary
  - Кнопки обновляются при смене темы (forest_light → forest_dark)
  - Нет хардкода #1E73E8 / синих оттенков
"""
import inspect
import tkinter as tk
from unittest.mock import MagicMock

import pytest

from client.ui.update_banner import UpdateBanner
from client.ui.themes import PALETTES, ThemeManager


@pytest.fixture
def updater_stub():
    """MagicMock UpdateManager с current_version."""
    u = MagicMock()
    u.current_version = "0.4.1"
    u.download_and_verify.return_value = None
    u.apply_update.return_value = False
    return u


@pytest.fixture
def theme_forest_light():
    return ThemeManager(initial="forest_light")


@pytest.fixture
def banner_deps(headless_tk, theme_forest_light, updater_stub):
    return {
        "root": headless_tk,
        "theme": theme_forest_light,
        "updater": updater_stub,
    }


def _make(banner_deps):
    return UpdateBanner(
        banner_deps["root"],
        banner_deps["theme"],
        banner_deps["updater"],
        new_version="0.4.2",
        download_url="https://example.com/new.exe",
        sha256="deadbeef" * 8,
    )


def _normalize(color) -> str:
    """CustomTkinter cget может вернуть tuple (light, dark) или str — берём первый."""
    if isinstance(color, (tuple, list)):
        return color[0]
    return color


# ==================== Init / layout ====================

def test_banner_creates_toplevel(banner_deps):
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()
    assert banner._banner.winfo_exists()
    banner._banner.destroy()


# ==================== Forest styling — primary button ====================

def test_update_button_uses_accent_brand(banner_deps):
    """'Обновить' fg_color == palette['accent_brand'] (forest #1E5239)."""
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()
    fg = _normalize(banner._update_btn.cget("fg_color"))
    expected = PALETTES["forest_light"]["accent_brand"]  # #1E5239
    assert fg == expected, f"Update btn fg_color должен быть forest {expected}, got {fg}"
    banner._banner.destroy()


def test_update_button_text_color_cream(banner_deps):
    """Текст 'Обновить' — palette['bg_primary'] (cream) для контраста на forest."""
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()
    tc = _normalize(banner._update_btn.cget("text_color"))
    expected = PALETTES["forest_light"]["bg_primary"]  # #EEE9DC
    assert tc == expected, f"Update btn text_color должен быть cream {expected}, got {tc}"
    banner._banner.destroy()


def test_update_button_hover_forest_light(banner_deps):
    """Hover color = accent_brand_light (слегка осветлён forest)."""
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()
    hc = _normalize(banner._update_btn.cget("hover_color"))
    expected = PALETTES["forest_light"]["accent_brand_light"]
    assert hc == expected
    banner._banner.destroy()


# ==================== Forest styling — ghost dismiss button ====================

def test_dismiss_button_transparent(banner_deps):
    """'Позже' — transparent fill (ghost)."""
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()
    fg = _normalize(banner._dismiss_btn.cget("fg_color"))
    assert fg == "transparent", f"Dismiss btn должен быть transparent, got {fg}"
    banner._banner.destroy()


def test_dismiss_button_border_text_tertiary(banner_deps):
    """Dismiss border_color = text_tertiary (subtle)."""
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()
    bc = _normalize(banner._dismiss_btn.cget("border_color"))
    expected = PALETTES["forest_light"]["text_tertiary"]
    assert bc == expected
    banner._banner.destroy()


def test_dismiss_button_text_color_secondary(banner_deps):
    """Dismiss text_color = text_secondary."""
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()
    tc = _normalize(banner._dismiss_btn.cget("text_color"))
    expected = PALETTES["forest_light"]["text_secondary"]
    assert tc == expected
    banner._banner.destroy()


# ==================== Theme subscription ====================

def test_buttons_update_on_theme_change(banner_deps):
    """set_theme('forest_dark') обновляет fg_color на dark-palette forest."""
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()

    banner_deps["theme"].set_theme("forest_dark")
    banner_deps["root"].update_idletasks()

    fg = _normalize(banner._update_btn.cget("fg_color"))
    expected_dark = PALETTES["forest_dark"]["accent_brand"]  # #5E9E7A
    assert fg == expected_dark, (
        f"После set_theme('forest_dark') update btn должен быть {expected_dark}, got {fg}"
    )
    banner._banner.destroy()


def test_dismiss_button_updates_on_theme_change(banner_deps):
    """set_theme('forest_dark') обновляет border/text dismiss-кнопки."""
    banner = _make(banner_deps)
    banner_deps["root"].update_idletasks()

    banner_deps["theme"].set_theme("forest_dark")
    banner_deps["root"].update_idletasks()

    bc = _normalize(banner._dismiss_btn.cget("border_color"))
    expected = PALETTES["forest_dark"]["text_tertiary"]
    assert bc == expected
    banner._banner.destroy()


# ==================== No legacy hardcoded hex ====================

def test_no_hardcoded_blue_in_source():
    """update_banner.py не должен содержать #1E73E8 / #4EA1FF / #C94A4A."""
    import client.ui.update_banner as mod
    src = inspect.getsource(mod)
    for forbidden in ("#1E73E8", "#4EA1FF", "#C94A4A", "#E85A5A", "#F07272"):
        assert forbidden not in src, f"Found forbidden hex {forbidden} in update_banner.py"
