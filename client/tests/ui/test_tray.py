"""
Unit-тесты TrayManager (Plan 03-07). Covers TRAY-01, 02, 03, 04.

Fixtures:
  tray_deps — собирает все зависимости TrayManager через conftest fixtures.
  Использует mock_pystray_icon для изоляции от реального pystray.
"""
from unittest.mock import MagicMock

import pytest

from client.core.paths import AppPaths
from client.core.storage import LocalStorage
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import ThemeManager
from client.utils.tray import TrayManager, CALLBACK_KEYS


@pytest.fixture
def tray_deps(tmp_appdata, headless_tk, mock_ctypes_dpi, mock_pystray_icon):
    """Собрать все зависимости TrayManager с моками."""
    storage = LocalStorage(AppPaths())
    storage.init()
    callbacks = {k: MagicMock() for k in CALLBACK_KEYS}
    callbacks["is_autostart_enabled"] = MagicMock(return_value=False)
    return {
        "root": headless_tk,
        "settings_store": SettingsStore(storage),
        "settings": UISettings(),
        "theme": ThemeManager(),
        "callbacks": callbacks,
        "fake_icon_cls": mock_pystray_icon,
    }


def test_instantiation_no_side_effects(tray_deps):
    """TrayManager.__init__ не создаёт pystray.Icon до start()."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    # Никакой icon не создан до start()
    assert tm._icon is None
    assert len(tray_deps["fake_icon_cls"].instances) == 0


def test_start_creates_icon_and_runs_detached(tray_deps):
    """start() создаёт pystray.Icon и вызывает run_detached() (TRAY-04)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm.start()
    assert len(tray_deps["fake_icon_cls"].instances) == 1
    icon = tray_deps["fake_icon_cls"].instances[0]
    # TRAY-04: run_detached использован, не run()
    assert icon.run_detached_called is True


def test_stop_calls_icon_stop(tray_deps):
    """stop() вызывает icon.stop() и обнуляет _icon."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm.start()
    tm.stop()
    assert tray_deps["fake_icon_cls"].instances[0].stopped is True


def test_cb_show_uses_root_after_zero(tray_deps):
    """_cb_show проходит через root.after(0, ...) — D-27 thread safety."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    original_after = tray_deps["root"].after
    spy = MagicMock(wraps=original_after)
    tray_deps["root"].after = spy
    try:
        tm._cb_show()
        # root.after вызван с (0, callable)
        args_list = [call.args for call in spy.call_args_list]
        assert any(a[0] == 0 for a in args_list), "_cb_show должен использовать root.after(0, ...)"
    finally:
        # Восстановить оригинальный after
        tray_deps["root"].after = original_after


def test_cb_sync_triggers_callback_via_after(tray_deps):
    """_cb_sync → root.after(0, ...) → callbacks['on_sync'] (D-27)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm._cb_sync()
    tray_deps["root"].update()  # after(0, ...) требует update(), не update_idletasks()
    tray_deps["callbacks"]["on_sync"].assert_called_once()


def test_cb_quit_triggers_callback_via_after(tray_deps):
    """_cb_quit → root.after(0, ...) → callbacks['on_quit'] (D-27)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm._cb_quit()
    tray_deps["root"].update()
    tray_deps["callbacks"]["on_quit"].assert_called_once()


def test_cb_theme_updates_settings_and_persists(tray_deps):
    """_cb_theme("dark") → settings.theme = "dark" + settings_store.save (TRAY-03)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm.start()
    spy_save = MagicMock(wraps=tray_deps["settings_store"].save)
    tray_deps["settings_store"].save = spy_save
    tm._cb_theme("dark")
    tray_deps["root"].update()
    assert tray_deps["settings"].theme == "dark"
    spy_save.assert_called_once()


def test_cb_toggle_on_top_flips_and_notifies(tray_deps):
    """_cb_toggle_on_top: on_top True→False + on_top_changed callback (TRAY-02)."""
    tray_deps["settings"].on_top = True
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm.start()
    tm._cb_toggle_on_top()
    tray_deps["root"].update()
    assert tray_deps["settings"].on_top is False
    tray_deps["callbacks"]["on_top_changed"].assert_called_with(False)


def test_cb_toggle_autostart_calls_callback(tray_deps):
    """_cb_toggle_autostart → on_autostart_changed вызван (TRAY-03)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm.start()
    tm._cb_toggle_autostart()
    tray_deps["root"].update()
    tray_deps["callbacks"]["on_autostart_changed"].assert_called_once()


def test_cb_task_style_persists(tray_deps):
    """_cb_task_style("line") → settings.task_style = "line" + on_task_style_changed (TRAY-03)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm.start()
    tm._cb_task_style("line")
    tray_deps["root"].update()
    assert tray_deps["settings"].task_style == "line"
    tray_deps["callbacks"]["on_task_style_changed"].assert_called_with("line")


def test_cb_notifications_mode_persists(tray_deps):
    """_cb_notifications_mode("silent") → settings.notifications_mode = "silent" (TRAY-03)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm.start()
    tm._cb_notifications_mode("silent")
    tray_deps["root"].update()
    assert tray_deps["settings"].notifications_mode == "silent"


def test_update_icon_changes_icon(tray_deps):
    """update_icon() заменяет icon.icon на новый PIL Image."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm.start()
    original = tm._icon.icon
    tm.update_icon("overdue", task_count=5, overdue_count=2)
    assert tm._icon.icon is not original


def test_menu_structure_has_all_required_labels():
    """TRAY-01/02: структурная проверка — меню содержит все обязательные пункты per UI-SPEC §Tray Menu."""
    import inspect
    from client.utils import tray as tray_mod
    source = inspect.getsource(tray_mod)
    required = [
        "Открыть окно", "Скрыть", "Добавить задачу", "Настройки",
        "Тема", "Светлая", "Тёмная", "Бежевая", "Системная",
        "Вид задач", "Карточки", "Строки", "Минимализм",
        "Уведомления", "Звук+pulse", "Только pulse", "Тихо",
        "Поверх всех окон", "Автозапуск",
        "Обновить синхронизацию", "Разлогиниться", "Выход",
    ]
    for label in required:
        assert label in source, f"Menu missing label: {label}"


def test_run_detached_not_run_grep():
    """TRAY-04 source grep guard: run_detached() присутствует, self._icon.run() отсутствует."""
    import inspect
    from client.utils import tray as tray_mod
    source = inspect.getsource(tray_mod)
    assert "run_detached()" in source
    # Убедимся что нет вызова `self._icon.run()`
    assert "self._icon.run()" not in source


def test_all_callbacks_use_after_zero():
    """TRAY-04/D-27 source grep — каждый _cb_ использует root.after(0, ...) — минимум 9."""
    import inspect
    from client.utils import tray as tray_mod
    source = inspect.getsource(tray_mod)
    # Считаем случаи "self._root.after(0" — минимум по числу callbacks (9+)
    count = source.count("self._root.after(0")
    assert count >= 9, f"Ожидалось >= 9 вызовов self._root.after(0, ...), got {count}"


def test_hide_callback_via_after(tray_deps):
    """_cb_hide → root.after(0, ...) → callbacks['on_hide'] (D-27)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm._cb_hide()
    tray_deps["root"].update()
    tray_deps["callbacks"]["on_hide"].assert_called_once()


def test_logout_callback_via_after(tray_deps):
    """_cb_logout → root.after(0, ...) → callbacks['on_logout'] (D-27)."""
    tm = TrayManager(
        tray_deps["root"], tray_deps["settings_store"],
        tray_deps["settings"], tray_deps["theme"], tray_deps["callbacks"],
    )
    tm._cb_logout()
    tray_deps["root"].update()
    tray_deps["callbacks"]["on_logout"].assert_called_once()
