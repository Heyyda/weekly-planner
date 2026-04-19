"""
WeeklyPlannerApp — оркестратор Phase 3 компонентов.

Канонический порядок lifecycle (03-RESEARCH §Pattern 10):
  1. ThemeManager (до любых виджетов)
  2. AppPaths + LocalStorage + SettingsStore → load settings → apply theme
  3. AuthManager + load_saved_token()
     ├─ если False → show overlay placeholder, остановиться
     └─ если True  → продолжить
  4. SyncManager (background thread)
  5. OverlayManager (visible)
  6. MainWindow (hidden)
  7. PulseAnimator (связан с overlay через on_frame callback)
  8. NotificationManager (set_mode + set_icon)
  9. TrayManager (run_detached + все callbacks) — ПОСЛЕДНИМ (требует callbacks готовых)
  10. Schedulers: overlay/tray refresh 30s, deadline check 60s

Wire callbacks:
  overlay.on_click = main_window.toggle            (OVR-04)
  overlay.on_top_changed = main_window.set_always_on_top  (OVR-06)

ВАЖНО: все tray callbacks используют root.after(0, ...) через TrayManager внутри —
здесь мы просто передаём чистые functions.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from client.core.auth import AuthManager
from client.core.paths import AppPaths
from client.core.storage import LocalStorage
from client.core.sync import SyncManager
from client.ui.login_dialog import LoginDialog
from client.ui.main_window import MainWindow
from client.ui.overlay import OverlayManager
from client.ui.pulse import PulseAnimator
from client.ui.quick_capture import QuickCapturePopup
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import ThemeManager
from client.utils import autostart as autostart_mod
from client.utils.notifications import NotificationManager
from client.utils.tray import TrayManager
from client.utils.updater import UpdateManager

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_MS = 30_000       # 30 секунд — overlay/tray badge refresh
DEADLINE_CHECK_INTERVAL_MS = 60_000  # 60 секунд — deadline scheduler


class WeeklyPlannerApp:
    """Главный класс — orchestration всех Phase 3 компонентов.

    Жизненный цикл:
        1. Инициализация Tk root (hidden)
        2. _setup() — создание и wire всех компонентов
        3. root.mainloop() — event loop
        4. _handle_quit() — cleanup + root.destroy()
    """

    def __init__(self, version: str = "0.1.0") -> None:
        self.version = version

        # DPI awareness перед созданием CTk (важно для HiDPI мониторов)
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        self.root: ctk.CTk = ctk.CTk()
        self.root.withdraw()  # root невидим — overlay/window — свои Toplevel

        # Компоненты (инициализируются в _setup)
        self.paths: Optional[AppPaths] = None
        self.storage: Optional[LocalStorage] = None
        self.settings_store: Optional[SettingsStore] = None
        self.settings: Optional[UISettings] = None
        self.theme: Optional[ThemeManager] = None
        self.auth: Optional[AuthManager] = None
        self.sync: Optional[SyncManager] = None
        self.overlay: Optional[OverlayManager] = None
        self.main_window: Optional[MainWindow] = None
        self.pulse: Optional[PulseAnimator] = None
        self.notifications: Optional[NotificationManager] = None
        self.tray: Optional[TrayManager] = None
        self.quick_capture: Optional[QuickCapturePopup] = None

        self._authenticated: bool = False
        self._quit_requested: bool = False

    # ---- Lifecycle ----

    def run(self) -> None:
        """Запустить setup + Tk mainloop."""
        try:
            self._setup()
        except Exception as exc:
            logger.exception("Setup failed: %s", exc)
            raise
        self.root.mainloop()

    def _setup(self) -> None:
        """Канонический порядок (03-RESEARCH §Pattern 10)."""
        # 1. Theme (до любых виджетов)
        self.theme = ThemeManager()

        # 2. Paths + Storage + Settings
        self.paths = AppPaths()
        self.paths.ensure()
        self.storage = LocalStorage(self.paths)
        self.storage.init()
        self.settings_store = SettingsStore(self.storage)
        self.settings = self.settings_store.load()
        self.theme.set_theme(self.settings.theme)

        # 3. Auth check
        self.auth = AuthManager()
        self._authenticated = False
        try:
            self._authenticated = self.auth.load_saved_token()
        except Exception as exc:
            logger.error("load_saved_token crashed: %s", exc)
            self._authenticated = False

        if not self._authenticated:
            # Post-v1: показать LoginDialog (блокирует до verify или cancel).
            logger.info("Нет сохранённого токена — открываю LoginDialog")
            dlg = LoginDialog(self.root, self.theme, self.auth)
            success = dlg.wait()
            if success:
                try:
                    self._authenticated = self.auth.load_saved_token()
                except Exception as exc:
                    logger.error("load_saved_token после LoginDialog: %s", exc)
                    self._authenticated = False

            if not self._authenticated:
                logger.warning("Авторизация не завершена — fallback к placeholder overlay")
                self._setup_unauthenticated_placeholder()
                return

        # 4. Sync (background)
        self.sync = SyncManager(self.storage, self.auth)
        self.sync.start()

        # 5. Overlay
        self.overlay = OverlayManager(
            self.root, self.settings_store, self.settings, self.theme,
        )

        # 6. Main window (hidden) — Phase 4: storage + user_id для CRUD
        user_id = ""
        try:
            user = getattr(self.auth, "_user", None) or {}
            user_id = str(user.get("id", "") or "")
        except Exception:
            user_id = ""
        self.main_window = MainWindow(
            self.root, self.settings_store, self.settings, self.theme,
            storage=self.storage, user_id=user_id,
        )

        # 6.5 Phase 4: QuickCapturePopup — D-01 wire через overlay right-click
        self.quick_capture = QuickCapturePopup(
            self.root, self.theme,
            on_save=self._handle_quick_capture_save,
        )
        # Передать trigger в MainWindow для Ctrl+Space (D-30)
        self.main_window._quick_capture_trigger = self._trigger_quick_capture_centered

        # 7. Wire overlay → main window + quick capture
        self.overlay.on_click = self.main_window.toggle              # OVR-04
        self.overlay.on_top_changed = self.main_window.set_always_on_top  # OVR-06
        self.overlay.on_right_click = self._on_overlay_right_click   # D-01

        # 8. Pulse animator — связан с overlay через on_frame callback
        def _on_pulse_frame(t: float) -> None:
            try:
                counts = self._count_tasks()
                self.overlay.refresh_image(
                    state="overdue",
                    task_count=counts["today"],
                    overdue_count=counts["overdue"],
                    pulse_t=t,
                )
            except Exception as exc:
                logger.debug("pulse frame failed: %s", exc)

        self.pulse = PulseAnimator(self.root, on_frame=_on_pulse_frame)

        # 9. Notifications
        self.notifications = NotificationManager(mode=self.settings.notifications_mode)
        icon_path = self._resolve_app_icon_path()
        if icon_path:
            self.notifications.set_icon(icon_path)

        # 10. Tray (последним — callbacks готовы)
        callbacks = {
            "on_show":                      self._handle_show_main_window,
            "on_hide":                      self._handle_hide_main_window,
            "on_add":                       self._handle_add_placeholder,
            "on_sync":                      self._handle_force_sync,
            "on_logout":                    self._handle_logout,
            "on_quit":                      self._handle_quit,
            "on_top_changed":               self._handle_top_changed_from_tray,
            "on_task_style_changed":        self._handle_task_style_changed,
            "on_notifications_mode_changed": self._handle_notifications_mode_changed,
            "on_autostart_changed":         self._handle_autostart_changed,
            "is_autostart_enabled":         autostart_mod.is_autostart_enabled,
        }
        self.tray = TrayManager(
            self.root, self.settings_store, self.settings, self.theme, callbacks,
        )
        self.tray.start()

        # 11. Schedulers
        self.root.after(REFRESH_INTERVAL_MS, self._scheduled_refresh)
        self.root.after(DEADLINE_CHECK_INTERVAL_MS, self._scheduled_deadline_check)
        # DIST-04: однократная проверка обновлений через 30s после запуска (не блокируем startup)
        self.root.after(30_000, self._check_for_updates)

        # Начальное обновление overlay/tray
        self._refresh_ui()

        logger.info("WeeklyPlannerApp setup завершён (version=%s)", self.version)

    def _setup_unauthenticated_placeholder(self) -> None:
        """Минимальное окно-заглушка при отсутствии токена (Phase 3 scope).

        Overlay показывает empty state. Tray доступен с ограниченным меню.
        """
        # Создаём overlay с placeholder-state "empty"
        self.overlay = OverlayManager(
            self.root, self.settings_store, self.settings, self.theme,
        )
        # Клик по overlay логируется — login dialog реализуется в Phase 4+
        self.overlay.on_click = lambda: logger.info(
            "Placeholder overlay clicked — login dialog не реализован в Phase 3"
        )

        # Минимальный tray без sync/main_window callbacks
        callbacks = {
            "on_show":                      lambda: None,
            "on_hide":                      lambda: None,
            "on_add":                       lambda: None,
            "on_sync":                      lambda: None,
            "on_logout":                    self._handle_logout,
            "on_quit":                      self._handle_quit,
            "on_top_changed":               self._handle_top_changed_from_tray,
            "on_task_style_changed":        lambda s: None,
            "on_notifications_mode_changed": lambda m: None,
            "on_autostart_changed":         self._handle_autostart_changed,
            "is_autostart_enabled":         autostart_mod.is_autostart_enabled,
        }
        self.tray = TrayManager(
            self.root, self.settings_store, self.settings, self.theme, callbacks,
        )
        self.tray.start()
        self.tray.update_tooltip("Личный Еженедельник — нужна авторизация")

    # ---- Tray callbacks ----

    def _handle_show_main_window(self) -> None:
        """Открыть главное окно из tray."""
        if self.main_window is not None:
            self.main_window.show()

    def _handle_hide_main_window(self) -> None:
        """Скрыть главное окно из tray."""
        if self.main_window is not None:
            self.main_window.hide()

    def _handle_add_placeholder(self) -> None:
        """Phase 3 — открыть главное окно. Phase 4 — открыть add-task dialog."""
        if self.main_window is not None:
            self.main_window.show()

    def _handle_force_sync(self) -> None:
        """Принудительный sync из tray-меню."""
        if self.sync is not None:
            self.sync.force_sync()

    def _handle_logout(self) -> None:
        """Разлогиниться: остановить sync + очистить токены."""
        logger.info("Logout requested")
        try:
            if self.sync is not None:
                self.sync.stop()
            if self.auth is not None:
                self.auth.logout()
        except Exception as exc:
            logger.error("Logout cleanup failed: %s", exc)
        self._authenticated = False

    def _handle_quit(self) -> None:
        """Выход: остановить все компоненты + уничтожить root."""
        self._quit_requested = True
        logger.info("Quit requested")
        try:
            if self.pulse is not None:
                self.pulse.stop()
            if self.sync is not None:
                self.sync.stop()
            if self.tray is not None:
                self.tray.stop()
            if self.quick_capture is not None:
                try:
                    self.quick_capture.destroy()
                except Exception:
                    pass
            if self.overlay is not None:
                self.overlay.destroy()
            if self.main_window is not None:
                self.main_window.destroy()
        except Exception as exc:
            logger.error("Quit cleanup failed: %s", exc)
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def _handle_top_changed_from_tray(self, enabled: bool) -> None:
        """OVR-06: toggle 'поверх всех окон' из tray — применить к overlay И main window."""
        if self.overlay is not None:
            # Из tray — напрямую меняем атрибут, не вызываем overlay.set_always_on_top
            # (избегаем рекурсии через on_top_changed hook)
            self.settings.on_top = enabled
            try:
                self.overlay._overlay.attributes("-topmost", enabled)
            except Exception:
                pass
        if self.main_window is not None:
            self.main_window.set_always_on_top(enabled)

    def _handle_task_style_changed(self, style: str) -> None:
        """Phase 4: style changed → MainWindow перерисовывает task widgets."""
        if self.main_window is not None:
            self.main_window.handle_task_style_changed(style)
        else:
            logger.info("Task style изменён на %s (main_window отсутствует)", style)

    # ---- Phase 4: Quick capture ----

    def _on_overlay_right_click(self) -> None:
        """D-01: right-click на overlay → quick capture popup."""
        if self.quick_capture is None or self.overlay is None:
            return
        try:
            x, y = self.overlay.get_position()
        except Exception:
            x, y = 0, 0
        self.quick_capture.show_at_overlay(x, y, 56)

    def _handle_quick_capture_save(
        self, text: str, day_iso: str, time: Optional[str],
    ) -> None:
        """QuickCapturePopup.on_save → MainWindow → storage.add_task."""
        if self.main_window is None:
            return
        self.main_window.handle_quick_capture_save(text, day_iso, time)
        if self.sync is not None:
            try:
                self.sync.force_sync()
            except Exception as exc:
                logger.debug("force_sync after quick capture: %s", exc)
        try:
            self._refresh_ui()
        except Exception as exc:
            logger.debug("_refresh_ui after quick capture: %s", exc)

    def _trigger_quick_capture_centered(self) -> None:
        """D-30 Ctrl+Space: quick capture в центре main window."""
        if self.quick_capture is None or self.main_window is None:
            return
        try:
            mw_x = self.main_window._window.winfo_x()
            mw_y = self.main_window._window.winfo_y()
            mw_w = self.main_window._window.winfo_width()
            popup_x = mw_x + mw_w // 2 - 200
            popup_y = mw_y + 60
        except Exception:
            popup_x, popup_y = 200, 200
        self.quick_capture.show_centered(popup_x, popup_y)

    def _handle_notifications_mode_changed(self, mode: str) -> None:
        """Передать смену режима уведомлений в NotificationManager."""
        if self.notifications is not None:
            self.notifications.set_mode(mode)

    def _handle_autostart_changed(self, enabled: bool) -> None:
        """Включить/выключить автозапуск через winreg."""
        try:
            if enabled:
                autostart_mod.enable_autostart()
            else:
                autostart_mod.disable_autostart()
        except Exception as exc:
            logger.error("Autostart toggle failed: %s", exc)

    # ---- Schedulers ----

    def _scheduled_refresh(self) -> None:
        """Периодическое обновление overlay/tray badge + pulse start/stop (каждые 30с)."""
        if self._quit_requested:
            return
        try:
            self._refresh_ui()
        except Exception as exc:
            logger.error("Scheduled refresh failed: %s", exc)
        self.root.after(REFRESH_INTERVAL_MS, self._scheduled_refresh)

    def _scheduled_deadline_check(self) -> None:
        """Периодическая проверка дедлайнов + отправка toast уведомлений (каждые 60с)."""
        if self._quit_requested:
            return
        try:
            if self.notifications is not None and self.storage is not None:
                tasks = self.storage.get_visible_tasks()
                self.notifications.fire_scheduled_toasts(tasks)
        except Exception as exc:
            logger.error("Deadline check failed: %s", exc)
        self.root.after(DEADLINE_CHECK_INTERVAL_MS, self._scheduled_deadline_check)

    def _refresh_ui(self) -> None:
        """Обновить overlay/tray icon + (re)start/stop pulse по overdue state."""
        if self.storage is None:
            return
        counts = self._count_tasks()
        has_overdue = counts["overdue"] > 0

        state = "overdue" if has_overdue else ("default" if counts["today"] > 0 else "empty")

        # Overlay image (не-пульсирующая — pulse сам перерисует при active)
        if self.overlay is not None:
            if not has_overdue:
                self.overlay.refresh_image(
                    state=state,
                    task_count=counts["today"],
                    overdue_count=counts["overdue"],
                    pulse_t=0.0,
                )

        # Tray icon + tooltip
        if self.tray is not None:
            self.tray.update_icon(
                state=state,
                task_count=counts["today"],
                overdue_count=counts["overdue"],
            )
            if has_overdue:
                self.tray.update_tooltip(
                    f"Личный Еженедельник — {counts['overdue']} просрочено"
                )
            else:
                self.tray.update_tooltip(
                    f"Личный Еженедельник — {counts['today']} задач сегодня"
                )

        # Pulse управление (OVR-05)
        if self.pulse is not None:
            if has_overdue and not self.pulse.is_active():
                self.pulse.start()
            elif not has_overdue and self.pulse.is_active():
                self.pulse.stop()

    def _check_for_updates(self) -> None:
        """DIST-04: проверка /api/version. Если новая версия → UpdateBanner."""
        if self._quit_requested:
            return
        try:
            updater = UpdateManager(self.version)
            result = updater.check()
            if result is None:
                logger.debug("Update check: already on latest (%s)", self.version)
                return
            new_version, url, sha = result
            logger.info("UPDATE available: %s → %s", self.version, new_version)
            try:
                from client.ui.update_banner import UpdateBanner
                UpdateBanner(
                    self.root, self.theme, updater,
                    new_version=new_version, download_url=url, sha256=sha,
                )
            except Exception as exc:
                logger.error("UpdateBanner failed: %s", exc)
        except Exception as exc:
            logger.debug("Update check failed (non-fatal): %s", exc)

    def _count_tasks(self) -> dict:
        """Подсчитать задачи: today (не выполнены) + overdue."""
        from datetime import date
        today_iso = date.today().isoformat()
        tasks = self.storage.get_visible_tasks()
        today_count = sum(1 for t in tasks if t.day == today_iso and not t.done)
        overdue_count = sum(1 for t in tasks if t.is_overdue())
        return {"today": today_count, "overdue": overdue_count}

    # ---- Helpers ----

    @staticmethod
    def _resolve_app_icon_path() -> Optional[str]:
        """Найти абсолютный путь к иконке приложения (PITFALL 7: winotify требует абс. путь)."""
        candidate_paths = [
            Path(__file__).parent / "assets" / "icon.ico",
            Path(__file__).parent / "assets" / "icon.png",
        ]
        for p in candidate_paths:
            if p.exists():
                return str(p.resolve())
        return None
