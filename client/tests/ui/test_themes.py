"""Unit-тесты ThemeManager (Plan 03-02)."""
import pytest
from client.ui.themes import PALETTES, FONTS, ThemeManager


def test_palettes_has_all_five_themes():
    assert set(PALETTES.keys()) == {"light", "dark", "beige", "forest_light", "forest_dark"}


def test_each_palette_has_11_tokens():
    expected_tokens = {
        "bg_primary", "bg_secondary", "bg_tertiary",
        "text_primary", "text_secondary", "text_tertiary",
        "accent_brand", "accent_brand_light",
        "accent_done", "accent_overdue",
        "shadow_card",
    }
    for name, palette in PALETTES.items():
        assert set(palette.keys()) == expected_tokens, f"Палитра {name!r} не имеет 11 токенов"


def test_light_palette_exact_hex_per_ui_spec():
    p = PALETTES["light"]
    assert p["bg_primary"] == "#F5EFE6"
    assert p["text_primary"] == "#2B2420"
    assert p["accent_brand"] == "#1E73E8"
    assert p["accent_brand_light"] == "#4EA1FF"
    assert p["accent_done"] == "#38A169"
    assert p["accent_overdue"] == "#E85A5A"


def test_dark_palette_exact_hex_per_ui_spec():
    p = PALETTES["dark"]
    assert p["bg_primary"] == "#1F1B16"
    assert p["accent_brand"] == "#4EA1FF"
    assert p["accent_done"] == "#48B97D"


def test_beige_palette_exact_hex_per_ui_spec():
    p = PALETTES["beige"]
    assert p["bg_primary"] == "#E8DDC4"
    assert p["text_primary"] == "#3D2F1F"
    assert p["accent_brand"] == "#2966C4"


def test_forest_light_palette_exact_hex_per_spec():
    p = PALETTES["forest_light"]
    assert p["bg_primary"] == "#EEE9DC"
    assert p["bg_secondary"] == "#F5F0E3"
    assert p["bg_tertiary"] == "#E2E0D2"
    assert p["text_primary"] == "#2E2B24"
    assert p["accent_brand"] == "#1E5239"
    assert p["accent_brand_light"] == "#234E3A"  # intentionally darker than brand
    assert p["accent_done"] == "#1E5239"          # same as accent_brand by design
    assert p["accent_overdue"] == "#9E6A5A"


def test_forest_dark_palette_exact_hex_per_spec():
    p = PALETTES["forest_dark"]
    assert p["bg_primary"] == "#161E1A"
    assert p["bg_secondary"] == "#202A24"
    assert p["bg_tertiary"] == "#1B2620"
    assert p["text_primary"] == "#E6E3D5"
    assert p["accent_brand"] == "#5E9E7A"
    assert p["accent_brand_light"] == "#6BAF8A"
    assert p["accent_done"] == "#5E9E7A"
    assert p["accent_overdue"] == "#B87D6F"


def test_fonts_has_segoe_and_cascadia():
    # Hotfix 260421-0jb: Segoe UI (не Variable) — Win10 совместимость
    assert FONTS["body"][0] == "Segoe UI"
    assert FONTS["mono"][0] in ("Cascadia Code", "Cascadia Mono")


def test_default_theme_is_forest_light():
    tm = ThemeManager()
    assert tm.current == "forest_light"


def test_set_theme_dark_changes_current(mock_ctypes_dpi):
    tm = ThemeManager()
    tm.set_theme("dark")
    assert tm.current == "dark"


def test_subscribe_callback_fires_on_set_theme(mock_ctypes_dpi):
    tm = ThemeManager()
    received = []
    tm.subscribe(lambda p: received.append(p["bg_primary"]))
    tm.set_theme("beige")
    assert received == ["#E8DDC4"]


def test_multiple_subscribers_all_fire(mock_ctypes_dpi):
    tm = ThemeManager()
    calls = []
    tm.subscribe(lambda p: calls.append("a"))
    tm.subscribe(lambda p: calls.append("b"))
    tm.set_theme("dark")
    assert calls == ["a", "b"]


def test_system_theme_resolves_via_winreg(mock_winreg, mock_ctypes_dpi):
    import winreg
    mock_winreg[
        (
            winreg.HKEY_CURRENT_USER,
            r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
            "AppsUseLightTheme",
        )
    ] = 0  # dark
    tm = ThemeManager()
    tm.set_theme("system")
    assert tm.current == "dark"


def test_unknown_theme_falls_back_to_forest_light(mock_ctypes_dpi):
    tm = ThemeManager()
    tm.set_theme("rainbow")
    assert tm.current == "forest_light"


def test_get_returns_hex_from_current_palette(mock_ctypes_dpi):
    tm = ThemeManager()
    tm.set_theme("dark")
    assert tm.get("accent_brand") == "#4EA1FF"


def test_get_unknown_key_returns_white_fallback(mock_ctypes_dpi):
    tm = ThemeManager()
    assert tm.get("nonexistent") == "#ffffff"
