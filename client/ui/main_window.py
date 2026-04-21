"""
MainWindow — главное окно планировщика. Phase 3 shell + Phase 4 content.

Phase 3 (сохранено):
  - Resizable CTkToplevel, min 320x320, default 460x600
  - Persistence window size+position через SettingsStore
  - Theme-aware через ThemeManager.subscribe
  - set_always_on_top (OVR-06)
  - WM_DELETE_WINDOW → hide (не destroy) — app живёт в tray

Phase 4 (новое):
  - WeekNavigation как header (Plan 04-05)
  - 7 DaySection через _rebuild_day_sections (Plan 04-04)
  - UndoToastManager в _root_frame (Plan 04-08)
  - DragController с register_drop_zone per DaySection (Plan 04-09)
  - EditDialog при TaskWidget.on_edit (Plan 04-07)
  - Ctrl+Space keyboard → QuickCapture (D-30)
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.core.storage import LocalStorage
from client.ui.day_section import DaySection
from client.ui.drag_controller import DragController, DropZone
from client.ui.edit_dialog import EditDialog  # deprecated, оставлен на будущее
from client.ui.inline_edit_panel import InlineEditPanel
from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import FONTS, ThemeManager
from client.ui.undo_toast import UndoToastManager
from client.ui.week_navigation import (
    WeekNavigation,
    get_current_week_monday,
    interpolate_palette,
)

logger = logging.getLogger(__name__)


class MainWindow:
    """Главное окно — Phase 3 shell + Phase 4 content."""

    MIN_SIZE = (320, 320)
    DEFAULT_SIZE = (460, 600)

    # UX-04: плавный fade show/hide (устраняет грубое мгновенное переключение).
    FADE_DURATION_MS = 150
    FADE_STEPS = 8

    def __init__(
        self,
        root: ctk.CTk,
        settings_store: SettingsStore,
        settings: UISettings,
        theme_manager: ThemeManager,
        storage: Optional[LocalStorage] = None,
        user_id: Optional[str] = None,
        quick_capture_trigger: Optional[Callable[[], None]] = None,
    ) -> None:
        self._root = root
        self._settings_store = settings_store
        self._settings = settings
        self._theme = theme_manager
        self._storage = storage
        self._user_id = user_id or ""
        self._quick_capture_trigger = quick_capture_trigger

        self._window = ctk.CTkToplevel(root)
        self._window.withdraw()
        self._window.title("Личный Еженедельник")
        self._window.minsize(*self.MIN_SIZE)
        self._window.resizable(True, True)

        w, h = self._resolve_initial_size()
        self._window.geometry(f"{w}x{h}")
        pos = self._settings.window_position
        if pos is not None and len(pos) == 2:
            try:
                x, y = int(pos[0]), int(pos[1])
                self._window.geometry(f"{w}x{h}+{x}+{y}")
            except (TypeError, ValueError):
                pass

        try:
            self._window.attributes("-topmost", self._settings.on_top)
        except tk.TclError:
            pass
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._day_sections: dict[date, DaySection] = {}
        self._drag_controller: Optional[DragController] = None
        self._undo_toast: Optional[UndoToastManager] = None
        self._week_nav: Optional[WeekNavigation] = None
        self._edit_panel: Optional[InlineEditPanel] = None

        self._build_ui()
        self._theme.subscribe(self._apply_theme)
        self._apply_theme({
            "bg_primary": self._theme.get("bg_primary"),
            "text_primary": self._theme.get("text_primary"),
            "bg_secondary": self._theme.get("bg_secondary"),
            "accent_brand": self._theme.get("accent_brand"),
            "border_window": self._theme.get("border_window"),
        })

        self._window.bind("<Configure>", self._on_configure)

        if self._quick_capture_trigger is not None:
            self._window.bind(
                "<Control-space>",
                lambda e: self._quick_capture_trigger(),
                add="+",
            )

        if self._storage is not None:
            self._refresh_tasks()

    # ---- Phase 3 Public API ----

    def show(self) -> None:
        """UX-04: fade-in 150мс через attributes('-alpha')."""
        # Устанавливаем alpha=0 ДО deiconify — иначе первый кадр виден непрозрачным
        # и только потом начинает гаснуть → мерцание.
        try:
            self._window.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self._window.deiconify()
        self._window.lift()
        self._fade(target=1.0, step=0)

    def hide(self) -> None:
        """UX-04: fade-out 150мс, затем withdraw."""
        try:
            if self._window.winfo_viewable() == 0:
                return
        except tk.TclError:
            return
        self._fade(target=0.0, step=0, on_complete=self._safe_withdraw)

    def _safe_withdraw(self) -> None:
        """Завершение fade-out: withdraw + восстановить alpha=1.0 для следующего show."""
        try:
            self._window.withdraw()
            self._window.attributes("-alpha", 1.0)
        except tk.TclError:
            pass

    def _fade(
        self,
        target: float,
        step: int,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """UX-04: плавное изменение alpha окна.

        Использует ease-out quadratic для естественного ощущения.
        На последнем шаге alpha устанавливается точно в target, чтобы не
        накапливать floating-point погрешность.

        Args:
            target: целевая alpha (0.0 = скрыть, 1.0 = показать)
            step: текущий шаг (0..FADE_STEPS-1)
            on_complete: вызов после завершения fade
        """
        current_step = step + 1
        progress = current_step / self.FADE_STEPS
        eased = 1.0 - (1.0 - progress) ** 2  # ease-out quadratic

        if target >= 0.5:  # fade-in: alpha от 0 к 1
            alpha = eased
        else:              # fade-out: alpha от 1 к 0
            alpha = 1.0 - eased

        try:
            self._window.attributes("-alpha", max(0.0, min(1.0, alpha)))
        except tk.TclError:
            return

        if current_step >= self.FADE_STEPS:
            # Финальный кадр — точное значение
            try:
                self._window.attributes("-alpha", target)
            except tk.TclError:
                pass
            if on_complete is not None:
                try:
                    on_complete()
                except Exception as exc:
                    logger.debug("fade on_complete failed: %s", exc)
            return

        delay_ms = max(1, int(self.FADE_DURATION_MS / self.FADE_STEPS))
        try:
            self._window.after(delay_ms, self._fade, target, current_step, on_complete)
        except tk.TclError:
            pass

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
        else:
            self.show()

    def is_visible(self) -> bool:
        try:
            return self._window.winfo_viewable() != 0
        except tk.TclError:
            return False

    def set_always_on_top(self, enabled: bool) -> None:
        try:
            self._window.attributes("-topmost", enabled)
        except tk.TclError:
            pass

    def destroy(self) -> None:
        if self._drag_controller is not None:
            try:
                self._drag_controller.destroy()
            except Exception:
                pass
        if self._undo_toast is not None:
            try:
                self._undo_toast.destroy()
            except Exception:
                pass
        for ds in list(self._day_sections.values()):
            try:
                ds.destroy()
            except Exception:
                pass
        self._day_sections.clear()
        try:
            self._window.destroy()
        except Exception as exc:
            logger.debug("MainWindow destroy: %s", exc)

    # ---- Phase 4: Public callbacks (used by WeeklyPlannerApp) ----

    def handle_task_style_changed(self, style: str) -> None:
        """Tray task_style toggle → перерисовать все TaskWidgets через rebuild."""
        self._rebuild_day_sections()
        self._refresh_tasks()

    def handle_quick_capture_save(
        self, text: str, day_iso: str, time: Optional[str],
    ) -> None:
        """WeeklyPlannerApp.quick_capture.on_save wire'ится сюда."""
        if self._storage is None:
            return
        task = Task.new(
            user_id=self._user_id, text=text, day=day_iso,
            time_deadline=time, position=0,
        )
        self._storage.add_task(task)
        self._refresh_tasks()

    def on_right_click_from_overlay(self, _event=None) -> None:
        if self._quick_capture_trigger is not None:
            self._quick_capture_trigger()

    # ---- Build ----

    def _build_ui(self) -> None:
        self._root_frame = ctk.CTkFrame(
            self._window,
            corner_radius=0,
            border_width=1,
            border_color=self._theme.get("border_window"),
        )
        self._root_frame.pack(fill="both", expand=True)

        self._week_nav = WeekNavigation(
            self._root_frame, self._window, self._theme,
            on_week_changed=self._on_week_changed,
            on_archive_changed=self._on_archive_changed,
        )
        self._week_nav.pack(fill="x", side="top")

        self._scroll = ctk.CTkScrollableFrame(self._root_frame)
        self._scroll.pack(fill="both", expand=True, padx=8, pady=4)

        self._undo_toast = UndoToastManager(
            self._root_frame, self._root, self._theme,
        )

        self._drag_controller = DragController(
            self._root, self._theme,
            on_task_moved=self._on_task_moved,
        )

        self._rebuild_day_sections()

    # ---- Week navigation callbacks ----

    def _on_week_changed(self, new_monday: date) -> None:
        """UX-01: лёгкий diff-update вместо heavy destroy+recreate — убирает мерцание."""
        self._update_week()
        self._refresh_tasks()

    def _on_archive_changed(self, is_archive: bool) -> None:
        """WEEK-06: archive mode на всех DaySection + DragController."""
        for ds in self._day_sections.values():
            ds.set_archive_mode(is_archive)
        if self._drag_controller:
            self._drag_controller.set_archive_mode(is_archive)
        if is_archive:
            base_palette = {
                "bg_primary": self._theme.get("bg_primary"),
                "bg_secondary": self._theme.get("bg_secondary"),
                "text_primary": self._theme.get("text_primary"),
                "accent_brand": self._theme.get("accent_brand"),
            }
            _ = interpolate_palette(base_palette, self._theme.get("bg_primary"), 0.3)

    # ---- Day sections rebuild ----

    def _rebuild_day_sections(self) -> None:
        """WEEK-01: пересоздать 7 DaySection для текущей выбранной недели."""
        for ds in list(self._day_sections.values()):
            try:
                ds.destroy()
            except Exception:
                pass
        self._day_sections.clear()
        if self._drag_controller:
            self._drag_controller.clear_drop_zones()

        if self._week_nav is None:
            return
        week_monday = self._week_nav.get_week_monday()
        today = date.today()

        task_style_map = {"card": "card", "line": "line", "minimal": "minimal"}
        style = task_style_map.get(self._settings.task_style, "card")

        for i in range(7):
            d = week_monday + timedelta(days=i)
            is_today = (d == today)
            ds = DaySection(
                self._scroll, d, is_today, self._theme, style, self._user_id,
                on_task_toggle=self._on_task_toggle,
                on_task_edit=self._on_task_edit,
                on_task_delete=self._on_task_delete,
                on_inline_add=self._on_inline_add,
            )
            ds.pack(fill="x", pady=4)
            self._day_sections[d] = ds

            if self._drag_controller:
                zone = DropZone(day_date=d, frame=ds.get_drop_frame())
                self._drag_controller.register_drop_zone(zone)

        if self._week_nav.is_current_archive():
            self._on_archive_changed(True)

    def _update_week(self) -> None:
        """UX-01: лёгкое обновление недели — diff-rebuild без пересоздания DaySection.

        Переиспользует существующие DaySection, только обновляет их даты и is_today
        через set_day_date. Устраняет визуальное мерцание при переключении недель.

        Fallback к _rebuild_day_sections если day_sections не инициализированы
        (первый вызов) или их количество != 7.
        """
        if self._week_nav is None:
            return
        if len(self._day_sections) != 7:
            self._rebuild_day_sections()
            return

        week_monday = self._week_nav.get_week_monday()
        today = date.today()
        new_dates = [week_monday + timedelta(days=i) for i in range(7)]

        # Словарь упорядочен по вставке — это текущие 7 секций в порядке дней недели
        old_sections_ordered = list(self._day_sections.values())
        new_map: dict[date, DaySection] = {}

        for i, d in enumerate(new_dates):
            ds = old_sections_ordered[i]
            ds.set_day_date(d, is_today=(d == today))
            new_map[d] = ds

        self._day_sections = new_map

        # Drop zones хранят day_date — нужно перерегистрировать на новые даты
        if self._drag_controller is not None:
            try:
                self._drag_controller.clear_drop_zones()
                for d, ds in self._day_sections.items():
                    zone = DropZone(day_date=d, frame=ds.get_drop_frame())
                    self._drag_controller.register_drop_zone(zone)
            except Exception as exc:
                logger.debug("_update_week drop zone refresh failed: %s", exc)

        # Archive mode обновить (если активен)
        if self._week_nav.is_current_archive():
            self._on_archive_changed(True)

    # ---- Refresh tasks ----

    def _refresh_tasks(self) -> None:
        """Get tasks from LocalStorage + распределить по DaySection."""
        if self._storage is None or self._week_nav is None:
            return
        all_tasks = self._storage.get_visible_tasks()
        by_day: dict[date, list[Task]] = {d: [] for d in self._day_sections.keys()}
        for t in all_tasks:
            try:
                td = date.fromisoformat(t.day)
            except (ValueError, TypeError):
                continue
            if td in by_day:
                by_day[td].append(t)

        for d, tasks in by_day.items():
            ds = self._day_sections[d]
            ds.render_tasks(tasks)
            if self._drag_controller:
                zone = None
                for z in self._drag_controller._drop_zones:
                    if z.day_date == d:
                        zone = z
                        break
                if zone:
                    for task_id, widget in ds._task_widgets.items():
                        try:
                            self._drag_controller.bind_task(
                                widget.get_body_frame(), task_id,
                                widget._task.text, zone,
                            )
                        except Exception:
                            pass

    # ---- CRUD callbacks ----

    def _on_task_toggle(self, task_id: str, new_done: bool) -> None:
        if self._storage:
            self._storage.update_task(task_id, done=new_done)
            self._refresh_tasks()

    def _on_task_edit(self, task_id: str) -> None:
        if self._storage is None:
            return
        task = self._storage.get_task(task_id)
        if task is None:
            return
        self._open_edit_panel(task)

    def _open_edit_panel(self, task: Task) -> None:
        """UX v2: открыть InlineEditPanel для задачи — закрыть предыдущую если есть."""
        if self._edit_panel is not None:
            try:
                self._edit_panel.destroy()
            except Exception:
                pass
            self._edit_panel = None
        self._edit_panel = InlineEditPanel(
            parent_frame=self._root_frame,
            root_window=self._window,
            task=task,
            theme_manager=self._theme,
            on_save=self._on_edit_save,
            on_delete=self._on_task_delete,
            on_close=self._close_edit_panel,
        )

    def _close_edit_panel(self) -> None:
        """Callback от InlineEditPanel после закрытия — очистить ref."""
        self._edit_panel = None

    def _on_edit_save(self, updated: Task) -> None:
        if self._storage is None:
            return
        self._storage.update_task(
            updated.id,
            text=updated.text,
            day=updated.day,
            time_deadline=updated.time_deadline,
            done=updated.done,
        )
        self._refresh_tasks()

    def _on_task_delete(self, task_id: str) -> None:
        self._delete_task_with_undo(task_id)

    def _delete_task_with_undo(self, task_id: str) -> None:
        """Оркестратор: storage.soft_delete → undo_toast.show с restore callback."""
        if self._storage is None or self._undo_toast is None:
            return
        task = self._storage.get_task(task_id)
        task_text = task.text if task else ""

        self._storage.soft_delete_task(task_id)
        self._refresh_tasks()

        def undo_restore():
            if self._storage:
                try:
                    with self._storage._lock:
                        for t in self._storage._data["tasks"]:
                            if t.get("id") == task_id:
                                t["deleted_at"] = None
                                break
                        from client.core.models import TaskChange
                        change = TaskChange(op="update", task_id=task_id)
                        self._storage._data["pending_changes"].append(change.to_dict())
                        self._storage._save_locked()
                except Exception as exc:
                    logger.error("Undo restore failed: %s", exc)
                self._refresh_tasks()

        self._undo_toast.show(task_id, task_text, undo_restore)

    def _on_inline_add(self, task: Task) -> None:
        if self._storage is None:
            return
        self._storage.add_task(task)
        self._refresh_tasks()

    def _on_task_moved(self, task_id: str, new_day: date) -> None:
        """DragController.on_task_moved → update_task(day=)."""
        if self._storage is None:
            return
        self._storage.update_task(task_id, day=new_day.isoformat())
        self._refresh_tasks()

    # ---- Phase 3 persistence ----

    def _resolve_initial_size(self) -> tuple[int, int]:
        ws = self._settings.window_size
        try:
            w, h = int(ws[0]), int(ws[1])
            if w >= self.MIN_SIZE[0] and h >= self.MIN_SIZE[1]:
                return (w, h)
        except (TypeError, ValueError, IndexError):
            pass
        return self.DEFAULT_SIZE

    def _on_configure(self, event) -> None:
        if event.widget is self._window:
            try:
                new_size = [self._window.winfo_width(), self._window.winfo_height()]
                new_pos = [self._window.winfo_x(), self._window.winfo_y()]
                if new_size != self._settings.window_size:
                    self._settings.window_size = new_size
                    self._settings.window_position = new_pos
            except tk.TclError:
                pass

    def _on_close(self) -> None:
        self._save_window_state()
        self.hide()

    def _save_window_state(self) -> None:
        try:
            self._settings.window_size = [
                self._window.winfo_width(),
                self._window.winfo_height(),
            ]
            self._settings.window_position = [
                self._window.winfo_x(),
                self._window.winfo_y(),
            ]
            self._settings_store.save(self._settings)
            logger.debug("MainWindow state saved: %s", self._settings.window_size)
        except tk.TclError as exc:
            logger.debug("_save_window_state skip: %s", exc)

    # ---- Theme ----

    def _apply_theme(self, palette: dict) -> None:
        bg = palette.get("bg_primary", "#F5EFE6")
        border = palette.get("border_window", "#8A7D6B")
        try:
            self._window.configure(fg_color=bg)
            if hasattr(self, "_root_frame"):
                self._root_frame.configure(fg_color=bg, border_color=border)
        except tk.TclError:
            pass
