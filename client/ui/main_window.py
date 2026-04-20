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

Forest Phase F (260421-1ya) — dark-parity audit:
  - _root_frame и _scroll получили явный fg_color через палитру при создании
    (до этого CTk выбирал дефолтный ctk.ThemeManager цвет — в forest_dark мог
    давать серый оттенок не совпадающий с bg_primary).
  - _apply_theme теперь обновляет и _scroll.configure(fg_color=bg) чтобы
    скролл-фрейм перекрашивался при live-switching.
  - Hardcoded fallback "#F5EFE6" (bg_primary из light-темы) заменён на резолв
    через self._theme.get("bg_primary") — корректен для любой активной темы.
"""
from __future__ import annotations

import ctypes
import logging
import tkinter as tk
from datetime import date, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.core.storage import LocalStorage
from client.ui.day_section import DaySection
from client.ui.drag_controller import DragController, DropZone
from client.ui.edit_dialog import EditDialog
from client.ui.settings import SettingsStore, UISettings
from client.ui.color_tween import ColorTween
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

    # Frameless + custom title bar (Plan 260421-06u)
    TITLE_BAR_HEIGHT = 28
    ACCENT_STRIP_WIDTH = 3
    FRAMELESS_INIT_DELAY_MS = 100   # Pitfall 1: Win11 DWM timing — копия паттерна из overlay.py
    DWM_CORNER_DELAY_MS = 150       # Дополнительная задержка перед region-вызовом
    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMWCP_ROUND = 2

    # Rounded corners (hotfix 260421-0jb): GDI SetWindowRgn работает Win7+,
    # в отличие от DWM Win11-only API. Radius 12px — современный Forest-look.
    WINDOW_CORNER_RADIUS = 12
    RGN_REAPPLY_DEBOUNCE_MS = 50    # Дебаунс re-apply региона при resize

    # Phase G: DWM drop-shadow — после SetWindowRgn ждём 50ms и вызываем
    # DwmExtendFrameIntoClientArea с MARGINS(0,0,0,1). Win10/11 DWM требует
    # "extended frame" >=1px для показа системной тени под frameless окном.
    DWM_SHADOW_DELAY_MS = 50
    CLOSE_BTN_TWEEN_MS = 150

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

        # Drag-state (для кастомной шапки — см. _on_title_drag_*)
        self._title_drag_offset_x = 0
        self._title_drag_offset_y = 0

        # Ссылки на виджеты шапки (заполняются в _build_title_bar, используются в _apply_theme)
        self._title_bar: Optional[ctk.CTkFrame] = None
        self._title_accent_strip: Optional[ctk.CTkFrame] = None
        self._title_label: Optional[ctk.CTkLabel] = None
        self._title_close_btn: Optional[ctk.CTkLabel] = None
        self._title_separator: Optional[ctk.CTkFrame] = None
        # Phase F: _scroll exposed для _apply_theme
        self._scroll: Optional[ctk.CTkScrollableFrame] = None

        self._day_sections: dict[date, DaySection] = {}
        self._drag_controller: Optional[DragController] = None
        self._undo_toast: Optional[UndoToastManager] = None
        self._week_nav: Optional[WeekNavigation] = None

        # Debounce handle для re-apply rounded-region при resize (hotfix 260421-0jb)
        self._rgn_reapply_job: Optional[str] = None

        self._build_ui()
        self._theme.subscribe(self._apply_theme)
        self._apply_theme({
            "bg_primary": self._theme.get("bg_primary"),
            "text_primary": self._theme.get("text_primary"),
            "bg_secondary": self._theme.get("bg_secondary"),
            "accent_brand": self._theme.get("accent_brand"),
        })

        self._window.bind("<Configure>", self._on_configure)

        if self._quick_capture_trigger is not None:
            self._window.bind(
                "<Control-space>",
                lambda e: self._quick_capture_trigger(),
                add="+",
            )

        # Frameless: overrideredirect + DWM rounded corners (Pitfall 1 — after delay)
        self._window.after(self.FRAMELESS_INIT_DELAY_MS, self._init_frameless_style)

        if self._storage is not None:
            self._refresh_tasks()

    # ---- Phase 3 Public API ----

    def show(self) -> None:
        self._window.deiconify()
        self._window.lift()

    def hide(self) -> None:
        self._window.withdraw()

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
        # Phase G: отменить in-flight close-btn tween перед teardown.
        if self._title_close_btn is not None:
            try:
                ColorTween.cancel_all(self._title_close_btn)
            except Exception:
                pass
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
        # Phase F: явный fg_color — избегаем CTk-дефолта (в forest_dark ctk.ThemeManager
        # подбирает серо-синий который не совпадает с bg_primary).
        bg_primary = self._theme.get("bg_primary")
        self._root_frame = ctk.CTkFrame(
            self._window, corner_radius=0, fg_color=bg_primary,
        )
        self._root_frame.pack(fill="both", expand=True)

        self._build_title_bar(self._root_frame)

        self._week_nav = WeekNavigation(
            self._root_frame, self._window, self._theme,
            on_week_changed=self._on_week_changed,
            on_archive_changed=self._on_archive_changed,
        )
        self._week_nav.pack(fill="x", side="top")

        # Phase F: fg_color для CTkScrollableFrame — по умолчанию CTk рисует
        # в серо-синем ("gray17"/"gray86"), что в forest_dark выглядит чужеродно.
        self._scroll = ctk.CTkScrollableFrame(
            self._root_frame, fg_color=bg_primary,
        )
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
        self._rebuild_day_sections()
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
                on_task_update=self._on_task_update,
            )
            ds.pack(fill="x", pady=4)
            self._day_sections[d] = ds

            if self._drag_controller:
                zone = DropZone(day_date=d, frame=ds.get_body_frame())
                self._drag_controller.register_drop_zone(zone)

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
        """Forest Phase D: route to inline TaskEditCard через DaySection.enter_edit_mode.
        Fallback на модальный EditDialog когда секция не найдена (старая задача в
        другой неделе — edge case)."""
        if self._storage is None:
            return
        task = self._storage.get_task(task_id)
        if task is None:
            return
        # Находим DaySection, содержащую задачу.
        try:
            task_day = date.fromisoformat(task.day)
        except (ValueError, TypeError):
            task_day = None
        section = self._day_sections.get(task_day) if task_day else None
        if section is not None:
            section.enter_edit_mode(task_id)
            return
        # Fallback: модальный EditDialog (задача вне текущей недели).
        EditDialog(
            self._window, task, self._theme,
            on_save=self._on_edit_save,
            on_delete=self._on_task_delete,
        )

    def _on_task_update(self, task_id: str, fields: dict) -> None:
        """Forest Phase D: inline edit save → применить к storage + refresh UI."""
        if self._storage is None:
            return
        allowed = {'text', 'day', 'time_deadline', 'done', 'position'}
        payload = {k: v for k, v in fields.items() if k in allowed}
        if not payload:
            return
        self._storage.update_task(task_id, **payload)
        self._refresh_tasks()

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
            # Debounced re-apply rounded region — resize drag генерит десятки <Configure>,
            # SetWindowRgn привязан к конкретным размерам окна (hotfix 260421-0jb).
            if self._rgn_reapply_job is not None:
                try:
                    self._window.after_cancel(self._rgn_reapply_job)
                except Exception:
                    pass
            try:
                self._rgn_reapply_job = self._window.after(
                    self.RGN_REAPPLY_DEBOUNCE_MS,
                    self._apply_window_region_rounded,
                )
            except tk.TclError:
                self._rgn_reapply_job = None

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
        # Phase F: fallback через self._theme.get — убран light-only хардкод "#F5EFE6"
        # (был палитра light темы, в forest_dark давал светлый оттенок при частичном
        # palette-dict из __init__).
        bg = palette.get("bg_primary") or self._theme.get("bg_primary")
        try:
            self._window.configure(fg_color=bg)
            if hasattr(self, "_root_frame"):
                self._root_frame.configure(fg_color=bg)
            # Phase F: скролл-фрейм тоже перекрашиваем под bg_primary
            if self._scroll is not None and self._scroll.winfo_exists():
                self._scroll.configure(fg_color=bg)
        except tk.TclError:
            pass
        # Title bar перекрашивание (Plan 260421-06u).
        # Fallback через ThemeManager.get — частичный palette dict может не содержать
        # всех нужных ключей (см. __init__ где передаётся только 4 ключа).
        def _col(key: str) -> str:
            val = palette.get(key)
            if val is None:
                val = self._theme.get(key)
            return val
        try:
            if self._title_bar is not None and self._title_bar.winfo_exists():
                self._title_bar.configure(fg_color=_col("bg_primary"))
            if (
                self._title_accent_strip is not None
                and self._title_accent_strip.winfo_exists()
            ):
                self._title_accent_strip.configure(fg_color=_col("accent_brand"))
            if self._title_label is not None and self._title_label.winfo_exists():
                self._title_label.configure(text_color=_col("text_secondary"))
            if (
                self._title_close_btn is not None
                and self._title_close_btn.winfo_exists()
            ):
                self._title_close_btn.configure(text_color=_col("text_tertiary"))
            if (
                self._title_separator is not None
                and self._title_separator.winfo_exists()
            ):
                self._title_separator.configure(fg_color=_col("bg_tertiary"))
        except tk.TclError:
            pass

    # ---- Frameless + custom title bar (Plan 260421-06u) ----

    def _init_frameless_style(self) -> None:
        """Pitfall 1: Win11 DWM требует overrideredirect через after(100, ...).

        Копия паттерна из OverlayManager._init_overlay_style (без импорта — cross-phase
        coupling избегаем умышленно).
        """
        try:
            self._window.overrideredirect(True)
        except tk.TclError as exc:
            logger.debug("overrideredirect failed: %s", exc)
            return
        # Переприменить topmost (overrideredirect может сбросить)
        try:
            self._window.attributes("-topmost", self._settings.on_top)
        except tk.TclError:
            pass
        # Rounded corners через GDI SetWindowRgn — Win7+, работает и Win10 и Win11.
        # Hotfix 260421-0jb: DWM Win11-only API не работал на Win10 → углы были квадратные.
        self._window.after(
            self.DWM_CORNER_DELAY_MS, self._apply_window_region_rounded,
        )

    def _apply_window_region_rounded(self) -> None:
        """Win7+: GDI SetWindowRgn для rounded corners.

        Работает на Win10/Win11 одинаково (в отличие от DWMWCP_ROUND который
        Win11-only). Silent fail — окно останется прямоугольным.

        SetWindowRgn takes ownership of HRGN — вручную DeleteObject НЕ нужен.
        Координаты `w+1`/`h+1` в CreateRoundRectRgn — exclusive-coordinate quirk:
        без +1 правый/нижний край обрезается на 1px.
        """
        try:
            hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())
            w = self._window.winfo_width()
            h = self._window.winfo_height()
            if w <= 1 or h <= 1:
                # Окно ещё не получило размеры — повторим после idle
                self._window.after_idle(self._apply_window_region_rounded)
                return
            r = self.WINDOW_CORNER_RADIUS
            # CreateRoundRectRgn(x1, y1, x2, y2, cornerWidth, cornerHeight)
            rgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, w + 1, h + 1, r, r,
            )
            # SetWindowRgn(hwnd, hrgn, bRedraw=True)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
            logger.debug(
                "MainWindow rounded corners applied via SetWindowRgn "
                "(w=%d, h=%d, r=%d)", w, h, r,
            )
        except Exception as exc:
            logger.debug("SetWindowRgn failed (non-Windows?): %s", exc)
        # Phase G: после SetWindowRgn ждём DWM_SHADOW_DELAY_MS и включаем
        # системную drop-shadow. Планируется на КАЖДЫЙ re-apply региона
        # (включая debounced resize) — DWM трактует recompute margins как no-op
        # если hwnd уже имеет extended frame.
        try:
            self._window.after(self.DWM_SHADOW_DELAY_MS, self._apply_dwm_shadow)
        except tk.TclError:
            pass

    def _build_title_bar(self, parent: ctk.CTkFrame) -> None:
        """Кастомная шапка 28px: 3px forest-полоса, заголовок 'Еженедельник', ✕.

        Drag-логика привязывается к self._title_bar и self._title_label (но НЕ к ✕).
        ✕ → self._on_close (тот же путь что WM_DELETE_WINDOW).
        """
        palette_bg = self._theme.get("bg_primary")
        palette_sep = self._theme.get("bg_tertiary")
        palette_accent = self._theme.get("accent_brand")
        palette_text = self._theme.get("text_secondary")
        palette_close = self._theme.get("text_tertiary")

        # Контейнер шапки
        self._title_bar = ctk.CTkFrame(
            parent, height=self.TITLE_BAR_HEIGHT,
            fg_color=palette_bg, corner_radius=0,
        )
        self._title_bar.pack(fill="x", side="top")
        self._title_bar.pack_propagate(False)

        # 3px accent strip слева
        self._title_accent_strip = ctk.CTkFrame(
            self._title_bar, width=self.ACCENT_STRIP_WIDTH,
            fg_color=palette_accent, corner_radius=0,
        )
        self._title_accent_strip.pack(side="left", fill="y")
        self._title_accent_strip.pack_propagate(False)

        # ✕ кнопка (пакается ПЕРВОЙ справа — до title_label — чтобы label занял оставшееся)
        self._title_close_btn = ctk.CTkLabel(
            self._title_bar, text="✕", width=self.TITLE_BAR_HEIGHT,
            height=self.TITLE_BAR_HEIGHT,
            fg_color="transparent", text_color=palette_close,
            cursor="hand2", font=FONTS["caption"],
        )
        self._title_close_btn.pack(side="right")
        self._title_close_btn.bind("<Button-1>", lambda e: self._on_close())
        # Phase G: hover — ColorTween на text_color (tertiary -> accent_overdue).
        # fg_color остаётся instant — CTkLabel.fg_color с "transparent"/hex смесями
        # tween'ить нельзя (transparent не hex). 150ms ease-out.
        self._close_btn_last_color: str = palette_close
        self._title_close_btn.bind(
            "<Enter>", lambda e: self._on_close_hover(True),
        )
        self._title_close_btn.bind(
            "<Leave>", lambda e: self._on_close_hover(False),
        )

        # Заголовок (анкор left с отступом 10px от accent strip)
        self._title_label = ctk.CTkLabel(
            self._title_bar, text="Еженедельник",
            fg_color="transparent", text_color=palette_text,
            font=FONTS["caption"], anchor="w",
        )
        self._title_label.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # 1px separator border-bottom
        self._title_separator = ctk.CTkFrame(
            parent, height=1, fg_color=palette_sep, corner_radius=0,
        )
        self._title_separator.pack(fill="x", side="top")

        # Drag bindings: на контейнер шапки И заголовок (НЕ на ✕ — он свой обработчик имеет)
        for w in (self._title_bar, self._title_label, self._title_accent_strip):
            w.bind("<ButtonPress-1>", self._on_title_drag_start)
            w.bind("<B1-Motion>", self._on_title_drag_motion)
            w.bind("<ButtonRelease-1>", self._on_title_drag_end)

    def _on_title_drag_start(self, event) -> None:
        """Запомнить offset курсор→левый-верхний-угол окна."""
        try:
            self._title_drag_offset_x = event.x_root - self._window.winfo_x()
            self._title_drag_offset_y = event.y_root - self._window.winfo_y()
        except tk.TclError:
            pass

    def _on_title_drag_motion(self, event) -> None:
        """Переместить окно за курсором. Не зажимаем в bounds — окно большое,
        virtual desktop clamp тут излишен (overlay это оправданно 56px).
        """
        try:
            new_x = event.x_root - self._title_drag_offset_x
            new_y = event.y_root - self._title_drag_offset_y
            self._window.geometry(f"+{new_x}+{new_y}")
        except tk.TclError:
            pass

    def _on_title_drag_end(self, event) -> None:
        """Persist позицию через SettingsStore — тот же путь что _save_window_state."""
        self._save_window_state()

    # ---- Phase G: close button hover tween ----

    def _on_close_hover(self, entering: bool) -> None:
        """ColorTween на text_color + мгновенный swap fg_color (transparent не hex)."""
        btn = self._title_close_btn
        if btn is None or not btn.winfo_exists():
            return
        if entering:
            target_text = self._theme.get("accent_overdue")
            target_fg = self._theme.get("bg_secondary")
        else:
            target_text = self._theme.get("text_tertiary")
            target_fg = "transparent"
        current = getattr(self, "_close_btn_last_color", target_text)
        self._close_btn_last_color = target_text
        try:
            ColorTween.tween(
                btn, "text_color", current, target_text,
                duration_ms=self.CLOSE_BTN_TWEEN_MS, easing="ease-out",
            )
        except Exception as exc:
            logger.debug("close-btn tween failed: %s", exc)
            try:
                btn.configure(text_color=target_text)
            except tk.TclError:
                pass
        # fg_color — мгновенно (transparent <-> hex несовместимы с RGB-tween).
        try:
            btn.configure(fg_color=target_fg)
        except tk.TclError:
            pass

    # ---- Phase G: DWM drop shadow ----

    def _apply_dwm_shadow(self) -> None:
        """Win10/11: DwmExtendFrameIntoClientArea(MARGINS(0,0,0,1)) -> системная
        тень под frameless-окном. Работает когда DWM composition активен
        (на Win7/Win8 без Aero — silent fallback).

        Порядок вызовов строго:
            overrideredirect(True) -> SetWindowRgn(rounded) -> DwmExtendFrameIntoClientArea

        MARGINS(0,0,0,1): 1px "extended frame" снизу — минимум чтобы DWM показал
        тень, не ломая визуальную высоту контента.
        """
        try:
            hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())

            class _MARGINS(ctypes.Structure):
                _fields_ = [
                    ("cxLeftWidth", ctypes.c_int),
                    ("cxRightWidth", ctypes.c_int),
                    ("cyTopHeight", ctypes.c_int),
                    ("cyBottomHeight", ctypes.c_int),
                ]

            margins = _MARGINS(0, 0, 0, 1)
            hr = ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
                hwnd, ctypes.byref(margins),
            )
            logger.debug("DwmExtendFrameIntoClientArea -> hr=%s", hr)
        except Exception as exc:
            # DWM composition может быть отключен (Classic theme) или dwmapi.dll
            # недоступен (не-Windows) — тихо live-без-тени.
            logger.debug("DWM shadow failed (non-Windows / no DWM): %s", exc)
