"""DragController — cross-day drag-and-drop. Phase 4 (TASK-05, TASK-06).

Approach 2 (04-RESEARCH-DND): custom mouse bindings + CTkToplevel ghost.
Critical: winfo-containing broken в CTkScrollableFrame → bbox hit-test.
Ghost pre-created (avoid alpha-flash от recreate).
"""
from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

logger = logging.getLogger(__name__)


@dataclass
class DropZone:
    """Зарегистрированная drop-зона."""
    day_date: date
    frame: ctk.CTkBaseClass
    is_archive: bool = False
    is_next_week: bool = False
    is_prev_week: bool = False

    def get_bbox(self) -> tuple[int, int, int, int]:
        w = self.frame
        try:
            return (
                w.winfo_rootx(),
                w.winfo_rooty(),
                w.winfo_rootx() + w.winfo_width(),
                w.winfo_rooty() + w.winfo_height(),
            )
        except tk.TclError:
            return (0, 0, 0, 0)

    def contains(self, x_root: int, y_root: int) -> bool:
        try:
            x1, y1, x2, y2 = self.get_bbox()
            if x2 <= x1 or y2 <= y1:
                return False
            return x1 <= x_root <= x2 and y1 <= y_root <= y2
        except TypeError:
            return False


class GhostWindow:
    """Полупрозрачное окно-призрак. Создаётся ОДНОМ экземпляре (избегаем alpha-flash)."""

    ALPHA = 0.6
    INIT_DELAY_MS = 100

    def __init__(self, root: ctk.CTk, theme_colors: dict) -> None:
        self._root = root
        self._colors = theme_colors
        self._width = 300
        self._height = 40

        self._window = ctk.CTkToplevel(root)
        self._window.withdraw()

        self._label = ctk.CTkLabel(
            self._window, text="", anchor="w",
            fg_color=theme_colors.get("bg_secondary", "#EDE6D9"),
            corner_radius=6,
        )
        self._label.pack(fill="both", expand=True, padx=4, pady=4)

        self._window.after(self.INIT_DELAY_MS, self._init_style)

    def _init_style(self) -> None:
        try:
            self._window.overrideredirect(True)
            self._window.attributes("-alpha", self.ALPHA)
            self._window.attributes("-topmost", True)
        except tk.TclError as exc:
            logger.debug("GhostWindow init style: %s", exc)

    def show(self, text: str, width: int, height: int, x: int, y: int) -> None:
        self._width = width
        self._height = height
        try:
            self._label.configure(text=text)
            self._window.geometry(f"{width}x{height}+{x}+{y}")
            self._window.deiconify()
            self._window.lift()
        except tk.TclError:
            pass

    def move(self, x: int, y: int) -> None:
        try:
            self._window.geometry(f"{self._width}x{self._height}+{x}+{y}")
        except tk.TclError:
            pass

    def hide(self) -> None:
        try:
            self._window.withdraw()
        except tk.TclError:
            pass

    def destroy(self) -> None:
        try:
            self._window.destroy()
        except Exception as exc:
            logger.debug("GhostWindow destroy: %s", exc)


class DragController:
    """Cross-day DnD controller."""

    DRAG_THRESHOLD_PX = 5

    def __init__(
        self,
        root: ctk.CTk,
        theme_manager,
        on_task_moved: Callable[[str, date], None],
        on_week_jump: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        self._root = root
        self._theme = theme_manager
        self._on_task_moved = on_task_moved
        self._on_week_jump = on_week_jump

        self._drop_zones: list[DropZone] = []

        self._dragging: bool = False
        self._source_task_id: Optional[str] = None
        self._source_task_text: str = ""
        self._source_widget = None
        self._source_zone: Optional[DropZone] = None
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._drag_offset_x: int = 0
        self._drag_offset_y: int = 0
        self._hovered_zone: Optional[DropZone] = None

        colors = {
            "bg_secondary": self._theme.get("bg_secondary"),
            "accent_brand": self._theme.get("accent_brand"),
        }
        self._ghost = GhostWindow(root, colors)

        self._theme.subscribe(self._on_theme_change)

    def register_drop_zone(self, zone: DropZone) -> None:
        self._drop_zones.append(zone)

    def clear_drop_zones(self) -> None:
        self._drop_zones.clear()

    def bind_task(
        self,
        task_body_frame,
        task_id: str,
        task_text: str,
        source_zone: DropZone,
    ) -> None:
        """D-22: bindings на task body + все children (CTkLabel перехватывает события)."""
        def on_press(event, tid=task_id, txt=task_text, sz=source_zone,
                     widget=task_body_frame):
            self._on_press(event, tid, txt, sz, widget)

        def _bind_recursive(w) -> None:
            try:
                w.bind("<ButtonPress-1>", on_press, add="+")
                w.bind("<B1-Motion>", self._on_motion, add="+")
                w.bind("<ButtonRelease-1>", self._on_release, add="+")
            except tk.TclError:
                pass
            try:
                for child in w.winfo_children():
                    # НЕ биндим на icons frame (edit/delete должны работать как клики)
                    name = str(child).lower()
                    if "icon" in name or "button" in name:
                        continue
                    _bind_recursive(child)
            except tk.TclError:
                pass

        try:
            _bind_recursive(task_body_frame)
        except tk.TclError as exc:
            logger.debug("bind_task: %s", exc)

    def set_archive_mode(self, is_archive: bool) -> None:
        for zone in self._drop_zones:
            zone.is_archive = is_archive

    def destroy(self) -> None:
        if self._ghost:
            self._ghost.destroy()

    def _on_press(self, event, task_id, task_text, source_zone, widget) -> None:
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._source_task_id = task_id
        self._source_task_text = task_text
        self._source_widget = widget
        self._source_zone = source_zone
        self._dragging = False
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y

    def _on_motion(self, event) -> None:
        if self._source_task_id is None:
            return
        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)

        if not self._dragging:
            if dx < self.DRAG_THRESHOLD_PX and dy < self.DRAG_THRESHOLD_PX:
                return
            self._start_drag(event)

        ghost_x = event.x_root - self._drag_offset_x
        ghost_y = event.y_root - self._drag_offset_y
        self._ghost.move(ghost_x, ghost_y)
        self._update_zone_highlights(event.x_root, event.y_root)

    def _on_release(self, event) -> None:
        if not self._dragging:
            self._reset_state()
            return

        target = self._find_drop_zone(event.x_root, event.y_root)
        if target is None or target.is_archive:
            self._cancel_drag()
            return

        # Cross-week jump имеет приоритет над same-day drop.
        if target.is_prev_week or target.is_next_week:
            direction = -1 if target.is_prev_week else 1
            task_id = self._source_task_id
            self._ghost.hide()
            self._clear_all_highlights()
            self._hide_week_jump_zones()
            try:
                if task_id and self._on_week_jump:
                    self._on_week_jump(direction, task_id)
            except Exception as exc:
                logger.error("on_week_jump failed: %s", exc)
            self._reset_state()
            return

        if target != self._source_zone:
            self._commit_drop(target)
        else:
            self._cancel_drag()

    def _start_drag(self, event) -> None:
        self._dragging = True

        ghost_x = event.x_root - self._drag_offset_x
        ghost_y = event.y_root - self._drag_offset_y
        try:
            widget_w = int(self._source_widget.winfo_width()) or 300
            widget_h = int(self._source_widget.winfo_height()) or 40
        except (tk.TclError, AttributeError, TypeError, ValueError):
            widget_w, widget_h = 300, 40
        self._ghost.show(self._source_task_text, widget_w, widget_h, ghost_x, ghost_y)

        # D-25: показать обе cross-week zones (prev + next).
        self._show_week_jump_zones()

    def _commit_drop(self, target: DropZone) -> None:
        """D-26: valid drop → callback."""
        self._ghost.hide()
        self._clear_all_highlights()
        self._hide_week_jump_zones()

        task_id = self._source_task_id
        try:
            if task_id and self._on_task_moved:
                self._on_task_moved(task_id, target.day_date)
        except Exception as exc:
            logger.error("on_task_moved failed: %s", exc)
        self._reset_state()

    def _cancel_drag(self) -> None:
        """D-26: invalid drop → hide, reset."""
        self._ghost.hide()
        self._clear_all_highlights()
        self._hide_week_jump_zones()
        self._reset_state()
        logger.debug("DnD cancelled")

    def _reset_state(self) -> None:
        self._dragging = False
        self._source_task_id = None
        self._source_task_text = ""
        self._source_widget = None
        self._source_zone = None
        self._hovered_zone = None

    def _find_drop_zone(self, x_root: int, y_root: int) -> Optional[DropZone]:
        """Bbox hit-test — НЕ winfo-containing (CTkScrollableFrame PITFALL)."""
        for zone in self._drop_zones:
            try:
                if not zone.frame.winfo_exists():
                    continue
            except (tk.TclError, AttributeError):
                continue
            if zone.contains(x_root, y_root):
                return zone
        return None

    def _update_zone_highlights(self, x_root: int, y_root: int) -> None:
        """D-24: active + adjacent highlights."""
        hovered = self._find_drop_zone(x_root, y_root)
        if hovered == self._hovered_zone:
            return

        if self._hovered_zone is not None and not (
            self._hovered_zone.is_prev_week or self._hovered_zone.is_next_week
        ):
            # Cross-week pills не тронуты в active-ветке — сбрасывать sage-цвет не нужно.
            self._set_zone_highlight(self._hovered_zone, "normal")

        if (
            hovered is not None
            and not hovered.is_archive
            and hovered != self._source_zone
        ):
            # Cross-week pills имеют собственный sage fg_color — не трогаем их подсветку.
            if not hovered.is_prev_week and not hovered.is_next_week:
                self._set_zone_highlight(hovered, "active")
            for zone in self._drop_zones:
                if (
                    zone is not hovered
                    and zone is not self._source_zone
                    and not zone.is_archive
                    and not zone.is_prev_week
                    and not zone.is_next_week
                ):
                    self._set_zone_highlight(zone, "adjacent")
        else:
            for zone in self._drop_zones:
                if (
                    zone is not self._source_zone
                    and not zone.is_prev_week
                    and not zone.is_next_week
                ):
                    self._set_zone_highlight(zone, "normal")
        self._hovered_zone = hovered

    def _set_zone_highlight(self, zone: DropZone, mode: str) -> None:
        try:
            if not zone.frame.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            return
        accent = self._theme.get("accent_brand")
        bg_primary = self._theme.get("bg_primary")
        try:
            if mode == "active":
                color = self._blend_hex(bg_primary, accent, 0.15)
                zone.frame.configure(fg_color=color)
            elif mode == "adjacent":
                color = self._blend_hex(bg_primary, accent, 0.05)
                zone.frame.configure(fg_color=color)
            else:
                zone.frame.configure(fg_color=bg_primary)
        except tk.TclError as exc:
            logger.debug("zone highlight: %s", exc)

    def _clear_all_highlights(self) -> None:
        for zone in self._drop_zones:
            # Не сбрасываем sage fg_color cross-week pills — для них normal == скрыто.
            if zone.is_prev_week or zone.is_next_week:
                continue
            self._set_zone_highlight(zone, "normal")

    def _show_week_jump_zones(self) -> None:
        """Показать обе pill-зоны (prev + next) при старте drag.

        Pack использует те же опции что и повторный pack в Tk — pack_forget
        сохраняет предыдущие опции, поэтому последующий pack() без аргументов
        восстановит предыдущий pack-контракт. Указываем опции явно чтобы
        гарантировать корректное позиционирование на первом показе.
        """
        for zone in self._drop_zones:
            if zone.is_prev_week:
                try:
                    zone.frame.pack(fill="x", padx=12, pady=(4, 4), side="top")
                    zone.frame.lift()
                except Exception:
                    pass
            elif zone.is_next_week:
                try:
                    zone.frame.pack(fill="x", padx=12, pady=(4, 4), side="bottom")
                    zone.frame.lift()
                except Exception:
                    pass

    def _hide_week_jump_zones(self) -> None:
        """Скрыть обе pill-зоны после drop/cancel."""
        for zone in self._drop_zones:
            if zone.is_prev_week or zone.is_next_week:
                try:
                    zone.frame.pack_forget()
                except Exception:
                    pass

    @staticmethod
    def _blend_hex(bg: str, fg: str, alpha: float) -> str:
        def parse(h: str) -> tuple:
            h = h.lstrip("#")
            if len(h) != 6:
                return (128, 128, 128)
            try:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            except ValueError:
                return (128, 128, 128)
        br, bg_, bb = parse(bg)
        fr, fg_, fb = parse(fg)
        r = int(br * (1 - alpha) + fr * alpha)
        g = int(bg_ * (1 - alpha) + fg_ * alpha)
        b = int(bb * (1 - alpha) + fb * alpha)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_theme_change(self, palette: dict) -> None:
        try:
            self._ghost._label.configure(
                fg_color=palette.get("bg_secondary", "#EDE6D9"))
        except Exception:
            pass
