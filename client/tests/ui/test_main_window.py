"""Unit-тесты MainWindow (Plan 03-06). Shell + persistence + theme subscribe + D-07 today-strip."""
from unittest.mock import MagicMock

import pytest

from client.core.paths import AppPaths
from client.core.storage import LocalStorage
from client.ui.main_window import MainWindow, DAY_NAMES_RU
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import ThemeManager


@pytest.fixture
def mw_deps(tmp_appdata, headless_tk, mock_ctypes_dpi):
    storage = LocalStorage(AppPaths())
    storage.init()
    return {
        "root": headless_tk,
        "settings_store": SettingsStore(storage),
        "settings": UISettings(),
        "theme": ThemeManager(),
    }


def test_creates_window(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    assert mw._window.winfo_exists()
    mw.destroy()


def test_initially_hidden(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    assert not mw.is_visible()
    mw.destroy()


def test_show_makes_visible(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    mw.show()
    mw_deps["root"].update()
    assert mw.is_visible()
    mw.destroy()


def test_toggle_alternates(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    mw.toggle()
    mw_deps["root"].update()
    v1 = mw.is_visible()
    mw.toggle()
    mw_deps["root"].update()
    v2 = mw.is_visible()
    assert v1 != v2
    mw.destroy()


def test_min_size_is_320(mw_deps):
    assert MainWindow.MIN_SIZE == (320, 320)


def test_default_size_is_460x600(mw_deps):
    assert MainWindow.DEFAULT_SIZE == (460, 600)


def test_today_strip_width_is_3(mw_deps):
    """D-07: полоска точно 3px (per UI-SPEC §Day Section — Expanded State)."""
    assert MainWindow.TODAY_STRIP_WIDTH == 3


def test_seven_day_sections(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    assert len(mw._day_sections) == 7
    mw.destroy()


def test_day_names_russian(mw_deps):
    assert DAY_NAMES_RU == ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def test_today_section_has_blue_strip(mw_deps):
    """D-07: today-секция должна иметь инстанс _today_strip (CTkFrame, accent_brand, 3px)."""
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    # _today_strip существует (сегодня всегда в текущей неделе)
    assert mw._today_strip is not None, "Today-секция должна иметь blue strip (D-07)"
    # Цвет == accent_brand текущей темы
    strip_color = mw._today_strip.cget("fg_color")
    expected = mw_deps["theme"].get("accent_brand")
    assert strip_color == expected or (
        isinstance(strip_color, (list, tuple)) and expected in strip_color
    ), f"Strip fg_color {strip_color!r} не совпадает с accent_brand {expected!r}"
    mw.destroy()


def test_today_strip_updates_on_theme_change(mw_deps):
    """D-07: при смене темы strip перекрашивается в новый accent_brand."""
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    assert mw._today_strip is not None
    # Применяем новую палитру с другим accent
    mw._apply_theme({
        "bg_primary": "#000000",
        "bg_secondary": "#111111",
        "text_primary": "#ffffff",
        "accent_brand": "#ff0000",
    })
    mw_deps["root"].update()
    strip_color = mw._today_strip.cget("fg_color")
    assert strip_color == "#ff0000" or (
        isinstance(strip_color, (list, tuple)) and "#ff0000" in strip_color
    ), f"После _apply_theme strip должен быть #ff0000, got {strip_color!r}"
    mw.destroy()


def test_apply_theme_changes_bg(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    mw._apply_theme({
        "bg_primary": "#123456",
        "bg_secondary": "#abcdef",
        "text_primary": "#000000",
        "accent_brand": "#ff0000",
    })
    # Без crash
    mw.destroy()


def test_theme_subscribe_called_in_init(mw_deps):
    spy_theme = MagicMock(wraps=mw_deps["theme"])
    spy_theme.subscribe = MagicMock()
    spy_theme.get = mw_deps["theme"].get
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], spy_theme)
    mw_deps["root"].update()
    spy_theme.subscribe.assert_called_once()
    mw.destroy()


def test_save_window_state_persists(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    spy = MagicMock(wraps=mw._settings_store.save)
    mw._settings_store.save = spy
    mw._save_window_state()
    spy.assert_called_once()
    mw.destroy()


def test_set_always_on_top(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    mw.set_always_on_top(False)
    # Attribute не крэшит
    mw.set_always_on_top(True)
    mw.destroy()


def test_destroy_cleanup(mw_deps):
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    mw.destroy()
    # Не крэшит


def test_non_today_sections_have_no_strip(mw_deps):
    """D-07: секции НЕ сегодня не имеют today-strip."""
    mw = MainWindow(mw_deps["root"], mw_deps["settings_store"],
                    mw_deps["settings"], mw_deps["theme"])
    mw_deps["root"].update()
    # Проверяем через _today_strip_map: только один день помечен
    assert hasattr(mw, "_today_strip_map"), "_today_strip_map должен существовать"
    today_count = sum(1 for v in mw._today_strip_map.values() if v is not None)
    assert today_count <= 1, f"Только 1 секция может иметь strip, найдено: {today_count}"
    mw.destroy()
