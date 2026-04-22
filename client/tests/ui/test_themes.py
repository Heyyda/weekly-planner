"""Unit-тесты ThemeManager (Plan 03-02)."""
import pytest
from client.ui.themes import PALETTES, FONTS, ThemeManager


def test_palettes_has_three_themes():
    assert set(PALETTES.keys()) == {"light", "dark", "beige"}


def test_each_palette_has_12_tokens():
    expected_tokens = {
        "bg_primary", "bg_secondary", "bg_tertiary",
        "text_primary", "text_secondary", "text_tertiary",
        "accent_brand", "accent_brand_light",
        "accent_done", "accent_overdue",
        "shadow_card",
        "border_window",
    }
    for name, palette in PALETTES.items():
        assert set(palette.keys()) == expected_tokens, f"Палитра {name!r} не имеет 12 токенов"


def test_light_palette_exact_hex_per_ui_spec():
    p = PALETTES["light"]
    assert p["bg_primary"] == "#F5EFE6"
    assert p["text_primary"] == "#2B2420"
    # accent_brand обновлён на sage-зелёный (UX-решение post-UI-SPEC, quick 260422-ugq)
    assert p["accent_brand"] == "#7A9B6B"
    assert p["accent_brand_light"] == "#9DBC8A"
    assert p["accent_done"] == "#38A169"
    assert p["accent_overdue"] == "#E85A5A"


def test_dark_palette_exact_hex_per_ui_spec():
    p = PALETTES["dark"]
    assert p["bg_primary"] == "#1F1B16"
    # sage (brighter for dark) post-UI-SPEC UX-решение
    assert p["accent_brand"] == "#94B080"
    assert p["accent_done"] == "#48B97D"


def test_beige_palette_exact_hex_per_ui_spec():
    p = PALETTES["beige"]
    assert p["bg_primary"] == "#E8DDC4"
    assert p["text_primary"] == "#3D2F1F"
    # muted sage для beige темы
    assert p["accent_brand"] == "#6B8B5C"


def test_fonts_has_segoe_and_cascadia():
    assert FONTS["body"][0] == "Segoe UI Variable"
    assert FONTS["mono"][0] in ("Cascadia Code", "Cascadia Mono")


def test_default_theme_is_light():
    tm = ThemeManager()
    assert tm.current == "light"


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


def test_unknown_theme_falls_back_to_light(mock_ctypes_dpi):
    tm = ThemeManager()
    tm.set_theme("rainbow")
    assert tm.current == "light"


def test_get_returns_hex_from_current_palette(mock_ctypes_dpi):
    tm = ThemeManager()
    tm.set_theme("dark")
    assert tm.get("accent_brand") == "#94B080"


def test_get_unknown_key_returns_white_fallback(mock_ctypes_dpi):
    tm = ThemeManager()
    assert tm.get("nonexistent") == "#ffffff"
