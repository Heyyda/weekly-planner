"""
TrayManager — pystray system tray icon + menu (TRAY-01..04).

Критические pitfall'ы (строго):
  PITFALL 2 / D-26 / TRAY-04: pystray.Icon.run_detached() ТОЛЬКО. НЕ run() — apartment crash.
  PITFALL 2 / D-27: каждый callback делает self._root.after(0, lambda: work()).
                    НЕ трогаем Tk виджеты из pystray thread напрямую.

Меню — per 03-UI-SPEC §Tray Menu verbatim.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

import pystray
from PIL import Image

from client.ui.icon_compose import render_overlay_image
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import ThemeManager

logger = logging.getLogger(__name__)

TRAY_ICON_SIZE = 64  # v0.4.0: 64×64 для корректного отображения на HiDPI ноутбуках
                     # (32 становился 1/4 размера на 200% scale)
APP_TITLE = "Личный Еженедельник"

# ---- Callback keys (контракт с WeeklyPlannerApp Plan 03-10) ----
CALLBACK_KEYS = {
    "on_show", "on_hide", "on_add", "on_sync", "on_logout", "on_quit",
    "on_top_changed", "on_task_style_changed",
    "on_notifications_mode_changed", "on_autostart_changed",
    "is_autostart_enabled",  # предикат для галочки в меню
}


class TrayManager:
    """System tray icon wrapper. См. 03-UI-SPEC §Tray Menu + §Tray Icon."""

    def __init__(
        self,
        root,
        settings_store: SettingsStore,
        settings: UISettings,
        theme_manager: ThemeManager,
        callbacks: dict,
    ) -> None:
        self._root = root
        self._settings_store = settings_store
        self._settings = settings
        self._theme = theme_manager
        self._callbacks = dict(callbacks)
        self._icon: Optional[pystray.Icon] = None
        # Проверить наличие всех callback-ключей
        missing = CALLBACK_KEYS - set(self._callbacks.keys())
        if missing:
            logger.warning("TrayManager missing callbacks: %s", missing)

    # ---- Lifecycle ----

    def start(self) -> None:
        """Создать pystray.Icon и запустить в detached thread (D-26)."""
        image = render_overlay_image(
            size=TRAY_ICON_SIZE,
            state="default",
            task_count=0,
            overdue_count=0,
        )
        self._icon = pystray.Icon(
            "weekly-planner",
            icon=image,
            title=APP_TITLE,
            menu=self._build_menu(),
        )
        # D-26 / TRAY-04: run_detached — не run()
        self._icon.run_detached()
        logger.info("TrayManager started (run_detached)")

    def stop(self) -> None:
        """Остановить иконку в трее."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as exc:
                logger.debug("tray.stop failed: %s", exc)
            self._icon = None

    def update_icon(self, state: str, task_count: int, overdue_count: int) -> None:
        """Обновить tray иконку (вызывать из main thread через root.after(0, ...))."""
        if self._icon is None:
            return
        try:
            new_image = render_overlay_image(
                size=TRAY_ICON_SIZE,
                state=state,
                task_count=task_count,
                overdue_count=overdue_count,
            )
            self._icon.icon = new_image
        except Exception as exc:
            logger.error("update_icon failed: %s", exc)

    def update_tooltip(self, text: str) -> None:
        """Обновить tooltip иконки в трее."""
        if self._icon is not None:
            self._icon.title = text

    # ---- Menu building ----

    def _build_menu(self) -> pystray.Menu:
        """Построить меню per 03-UI-SPEC §Tray Menu — полная структура."""
        return pystray.Menu(
            pystray.MenuItem("Открыть окно", self._cb_show, default=True),
            pystray.MenuItem("Скрыть", self._cb_hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Добавить задачу", self._cb_add),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Настройки", pystray.Menu(
                pystray.MenuItem("Тема", pystray.Menu(
                    pystray.MenuItem(
                        "Светлая",
                        lambda i, it: self._cb_theme("light"),
                        checked=lambda it: self._settings.theme == "light",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Тёмная",
                        lambda i, it: self._cb_theme("dark"),
                        checked=lambda it: self._settings.theme == "dark",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Бежевая",
                        lambda i, it: self._cb_theme("beige"),
                        checked=lambda it: self._settings.theme == "beige",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Forest (светлая)",
                        lambda i, it: self._cb_theme("forest_light"),
                        checked=lambda it: self._settings.theme == "forest_light",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Forest (тёмная)",
                        lambda i, it: self._cb_theme("forest_dark"),
                        checked=lambda it: self._settings.theme == "forest_dark",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Системная",
                        lambda i, it: self._cb_theme("system"),
                        checked=lambda it: self._settings.theme == "system",
                        radio=True,
                    ),
                )),
                pystray.MenuItem("Вид задач", pystray.Menu(
                    pystray.MenuItem(
                        "Карточки",
                        lambda i, it: self._cb_task_style("card"),
                        checked=lambda it: self._settings.task_style == "card",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Строки",
                        lambda i, it: self._cb_task_style("line"),
                        checked=lambda it: self._settings.task_style == "line",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Минимализм",
                        lambda i, it: self._cb_task_style("minimal"),
                        checked=lambda it: self._settings.task_style == "minimal",
                        radio=True,
                    ),
                )),
                pystray.MenuItem("Уведомления", pystray.Menu(
                    pystray.MenuItem(
                        "Звук+pulse",
                        lambda i, it: self._cb_notifications_mode("sound_pulse"),
                        checked=lambda it: self._settings.notifications_mode == "sound_pulse",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Только pulse",
                        lambda i, it: self._cb_notifications_mode("pulse_only"),
                        checked=lambda it: self._settings.notifications_mode == "pulse_only",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Тихо",
                        lambda i, it: self._cb_notifications_mode("silent"),
                        checked=lambda it: self._settings.notifications_mode == "silent",
                        radio=True,
                    ),
                )),
                pystray.MenuItem(
                    "Поверх всех окон",
                    self._cb_toggle_on_top,
                    checked=lambda it: self._settings.on_top,
                ),
                pystray.MenuItem(
                    "Автозапуск",
                    self._cb_toggle_autostart,
                    checked=lambda it: self._is_autostart_enabled(),
                ),
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Обновить синхронизацию", self._cb_sync),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Разлогиниться", self._cb_logout),
            pystray.MenuItem("Выход", self._cb_quit),
        )

    # ---- Callbacks (ВСЕ через root.after(0, ...) per D-27 / PITFALL 2) ----

    def _cb_show(self, icon=None, item=None) -> None:
        """Открыть окно — D-27: через root.after(0, ...)."""
        self._root.after(0, lambda: self._invoke("on_show"))

    def _cb_hide(self, icon=None, item=None) -> None:
        """Скрыть окно — D-27: через root.after(0, ...)."""
        self._root.after(0, lambda: self._invoke("on_hide"))

    def _cb_add(self, icon=None, item=None) -> None:
        """Добавить задачу — D-27: через root.after(0, ...)."""
        self._root.after(0, lambda: self._invoke("on_add"))

    def _cb_sync(self, icon=None, item=None) -> None:
        """Обновить синхронизацию — D-27: через root.after(0, ...)."""
        self._root.after(0, lambda: self._invoke("on_sync"))

    def _cb_logout(self, icon=None, item=None) -> None:
        """Разлогиниться — D-27: через root.after(0, ...)."""
        self._root.after(0, lambda: self._invoke("on_logout"))

    def _cb_quit(self, icon=None, item=None) -> None:
        """Выход — D-27: через root.after(0, ...)."""
        self._root.after(0, lambda: self._invoke("on_quit"))

    def _cb_theme(self, theme: str) -> None:
        """Сменить тему — D-27: через root.after(0, ...). TRAY-03: сохранить settings."""
        def apply() -> None:
            self._settings.theme = theme
            self._theme.set_theme(theme)
            self._settings_store.save(self._settings)
            self._refresh_menu()
        self._root.after(0, apply)

    def _cb_task_style(self, style: str) -> None:
        """Сменить вид задач — D-27: через root.after(0, ...). TRAY-03: сохранить settings."""
        def apply() -> None:
            self._settings.task_style = style
            self._settings_store.save(self._settings)
            self._invoke("on_task_style_changed", style)
            self._refresh_menu()
        self._root.after(0, apply)

    def _cb_notifications_mode(self, mode: str) -> None:
        """Сменить режим уведомлений — D-27: через root.after(0, ...). TRAY-03: сохранить settings."""
        def apply() -> None:
            self._settings.notifications_mode = mode
            self._settings_store.save(self._settings)
            self._invoke("on_notifications_mode_changed", mode)
            self._refresh_menu()
        self._root.after(0, apply)

    def _cb_toggle_on_top(self, icon=None, item=None) -> None:
        """Toggle поверх всех окон — D-27: через root.after(0, ...). TRAY-03: сохранить settings."""
        def apply() -> None:
            self._settings.on_top = not self._settings.on_top
            self._settings_store.save(self._settings)
            self._invoke("on_top_changed", self._settings.on_top)
            self._refresh_menu()
        self._root.after(0, apply)

    def _cb_toggle_autostart(self, icon=None, item=None) -> None:
        """Toggle автозапуска — D-27: через root.after(0, ...). TRAY-03: сохранить settings."""
        def apply() -> None:
            enabled = self._is_autostart_enabled()
            new_state = not enabled
            self._settings.autostart = new_state
            self._invoke("on_autostart_changed", new_state)
            self._settings_store.save(self._settings)
            self._refresh_menu()
        self._root.after(0, apply)

    # ---- Helpers ----

    def _is_autostart_enabled(self) -> bool:
        """Получить актуальное состояние автозапуска (через callback или settings)."""
        predicate = self._callbacks.get("is_autostart_enabled")
        if predicate is None:
            return self._settings.autostart
        try:
            return bool(predicate())
        except Exception as exc:
            logger.debug("is_autostart_enabled failed: %s", exc)
            return self._settings.autostart

    def _invoke(self, key: str, *args) -> None:
        """Вызвать callback по ключу. Логирует warning если callback не подключён."""
        cb = self._callbacks.get(key)
        if cb is None:
            logger.warning("TrayManager: callback %r not wired", key)
            return
        try:
            cb(*args)
        except Exception as exc:
            logger.error("TrayManager callback %s failed: %s", key, exc)

    def _refresh_menu(self) -> None:
        """Обновить checkmarks меню (pystray update_menu — thread-safe внутренне)."""
        if self._icon is not None:
            try:
                self._icon.update_menu()
            except Exception as exc:
                logger.debug("update_menu failed: %s", exc)
