"""Unit-тесты UISettings + SettingsStore (Plan 03-02)."""
from dataclasses import asdict

import pytest
from client.core.storage import LocalStorage
from client.core.paths import AppPaths
from client.ui.settings import (
    UISettings, SettingsStore,
    VALID_THEMES, VALID_TASK_STYLES, VALID_NOTIFICATIONS,
)


def test_defaults():
    s = UISettings()
    assert s.theme == "forest_light"
    assert s.task_style == "card"
    assert s.notifications_mode == "sound_pulse"
    assert s.on_top is True
    assert s.autostart is False
    assert s.overlay_position == [-1, -1]  # sentinel: overlay computes visible default on first run
    assert s.window_size == [460, 600]
    assert s.window_position is None
    assert s.version == 1


def test_to_dict_has_all_keys():
    d = UISettings().to_dict()
    expected = {
        "theme", "task_style", "notifications_mode", "on_top",
        "autostart", "overlay_position", "window_size", "window_position", "version",
    }
    assert set(d.keys()) == expected


def test_from_dict_round_trip():
    original = UISettings(theme="beige", autostart=True, overlay_position=[50, 75])
    restored = UISettings.from_dict(original.to_dict())
    assert restored == original


def test_from_dict_ignores_unknown_keys():
    s = UISettings.from_dict({"theme": "dark", "unknown_future_key": 42})
    assert s.theme == "dark"
    assert not hasattr(s, "unknown_future_key")


def test_from_dict_uses_defaults_for_missing():
    s = UISettings.from_dict({"theme": "dark"})
    assert s.theme == "dark"
    assert s.task_style == "card"  # default


def test_validate_resets_invalid_theme():
    s = UISettings(theme="purple")
    s.validate()
    assert s.theme == "forest_light"


def test_validate_resets_invalid_task_style():
    s = UISettings(task_style="bubble")
    s.validate()
    assert s.task_style == "card"


def test_validate_resets_invalid_notifications():
    s = UISettings(notifications_mode="loud")
    s.validate()
    assert s.notifications_mode == "sound_pulse"


def test_store_load_fresh_returns_defaults(tmp_appdata):
    storage = LocalStorage(AppPaths())
    storage.init()
    store = SettingsStore(storage)
    loaded = store.load()
    assert loaded == UISettings()


def test_store_save_then_load_round_trip(tmp_appdata):
    storage = LocalStorage(AppPaths())
    storage.init()
    store = SettingsStore(storage)
    original = UISettings(theme="dark", task_style="minimal", on_top=False,
                          overlay_position=[200, 300])
    store.save(original)
    restored = store.load()
    assert restored == original


def test_store_load_with_corrupted_theme_sanitizes(tmp_appdata):
    storage = LocalStorage(AppPaths())
    storage.init()
    # Подсовываем невалидный theme напрямую
    storage.save_settings({"theme": "corrupted", "task_style": "card"})
    store = SettingsStore(storage)
    loaded = store.load()
    assert loaded.theme == "forest_light"  # validate() sanitized
