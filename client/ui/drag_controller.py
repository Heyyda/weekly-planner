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
    # Quick 260423-o8z: edge-drag cross-week navigation — расстояние в px от
    # края главного окна, внутри которого drag триггерит jump на ±7 дней.
    EDGE_JUMP_THRESHOLD_PX = 60

    def __init__(
        self,
        root: ctk.CTk,
        theme_manager,
        on_task_moved: Callable[[str, date], None],
        on_week_jump: Optional[Callable[[int, str], None]] = None,
        on_edge_zone_changed: Optional[Callable[[Optional[int]], None]] = None,
    ) -> None:
        self._root = root
        self._theme = theme_manager
        self._on_task_moved = on_task_moved
        self._on_week_jump = on_week_jump
        # Quick 260423-o8z: callback для main_window — показать/скрыть
        # sage edge-indicator на _left_edge_indicator / _right_edge_indicator.
        self._on_edge_zone_changed = on_edge_zone_changed

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
        # Quick 260423-o8z: None / -1 (prev-week) / +1 (next-week).
        self._edge_jump_direction: Optional[int] = None

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

        # Quick 260423-o8z: edge-drag detection относительно main window bounds.
        # Приоритет над day-zone highlights: если курсор у края → скрыть подсветку
        # дней, показать sage edge-indicator через on_edge_zone_changed callback.
        edge_direction: Optional[int] = None
        try:
            main_win = self._root  # CTk root — главное окно приложения
            win_x = main_win.winfo_rootx()
            win_w = main_win.winfo_width()
            distance_left = event.x_root - win_x
            distance_right = (win_x + win_w) - event.x_root
            if distance_left < self.EDGE_JUMP_THRESHOLD_PX:
                edge_direction = -1
            elif distance_right < self.EDGE_JUMP_THRESHOLD_PX:
                edge_direction = +1
        except (tk.TclError, AttributeError):
            edge_direction = None

        if edge_direction != self._edge_jump_direction:
            self._edge_jump_direction = edge_direction
            # Обновить ghost label внутри controller
            self._update_ghost_for_edge(edge_direction)
            # Нотифицировать main_window (показать/скрыть sage indicator)
            if self._on_edge_zone_changed is not None:
                try:
                    self._on_edge_zone_changed(edge_direction)
                except Exception as exc:
                    logger.error("on_edge_zone_changed failed: %s", exc)

        # День-зоны подсвечиваем ТОЛЬКО если edge не активен — чтобы не мигало.
        if self._edge_jump_direction is None:
            self._update_zone_highlights(event.x_root, event.y_root)
        else:
            # Сбросить подсветку дней (visual priority: edge mode)
            if self._hovered_zone is not None:
                self._set_zone_highlight(self._hovered_zone, "normal")
                self._hovered_zone = None

    def _update_ghost_for_edge(self, direction: Optional[int]) -> None:
        """Quick 260423-o8z: перекрасить ghost label для edge-jump режима.

        direction=-1 → "← Пред. неделя" + sage fg_color
        direction=+1 → "След. неделя →" + sage fg_color
        direction=None → восстановить original task text + bg_secondary
        """
        try:
            sage = self._theme.get("accent_brand")
            bg_sec = self._theme.get("bg_secondary")
            text_primary = self._theme.get("text_primary")
            if direction == -1:
                self._ghost._label.configure(
                    text="← Пред. неделя",
                    text_color="#FFFFFF",
                    fg_color=sage,
                )
            elif direction == +1:
                self._ghost._label.configure(
                    text="След. неделя →",
                    text_color="#FFFFFF",
                    fg_color=sage,
                )
            else:
                self._ghost._label.configure(
                    text=self._source_task_text,
                    text_color=text_primary,
                    fg_color=bg_sec,
                )
        except Exception as exc:
            logger.debug("_update_ghost_for_edge failed: %s", exc)

    def _on_release(self, event) -> None:
        if not self._dragging:
            self._reset_state()
            return

        # Quick 260423-o8z: edge-jump имеет приоритет над drop-zones.
        if self._edge_jump_direction is not None:
            direction = self._edge_jump_direction
            task_id = self._source_task_id
            self._ghost.hide()
            self._clear_all_highlights()
            # Скрыть edge indicators через callback (direction=None)
            if self._on_edge_zone_changed is not None:
                try:
                    self._on_edge_zone_changed(None)
                except Exception as exc:
                    logger.debug("on_edge_zone_changed(None) failed: %s", exc)
            try:
                if task_id and self._on_week_jump:
                    self._on_week_jump(direction, task_id)
            except Exception as exc:
                logger.error("on_week_jump failed: %s", exc)
            self._reset_state()
            return

        target = self._find_drop_zone(event.x_root, event.y_root)
        if target is None or target.is_archive:
            self._cancel_drag()
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
        # Quick 260423-o8z: pill-frames больше не показываются на drag start —
        # cross-week jump триггерится через edge-drag (EDGE_JUMP_THRESHOLD_PX).

    def _commit_drop(self, target: DropZone) -> None:
        """D-26: valid drop → callback."""
        self._ghost.hide()
        self._clear_all_highlights()

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
        # Quick 260423-o8z: скрыть edge indicator если был показан
        if self._on_edge_zone_changed is not None:
            try:
                self._on_edge_zone_changed(None)
            except Exception:
                pass
        self._reset_state()
        logger.debug("DnD cancelled")

    def _reset_state(self) -> None:
        self._dragging = False
        self._source_task_id = None
        self._source_task_text = ""
        self._source_widget = None
        self._source_zone = None
        self._hovered_zone = None
        # Quick 260423-o8z: сброс edge-jump state
        self._edge_jump_direction = None

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
        """D-24: active + adjacent highlights.

        Quick 260423-o8z: упрощено — pill cross-week zones удалены,
        остался только archive guard.
        """
        hovered = self._find_drop_zone(x_root, y_root)
        if hovered == self._hovered_zone:
            return

        if self._hovered_zone is not None:
            self._set_zone_highlight(self._hovered_zone, "normal")

        if (
            hovered is not None
            and not hovered.is_archive
            and hovered != self._source_zone
        ):
            self._set_zone_highlight(hovered, "active")
            for zone in self._drop_zones:
                if (
                    zone is not hovered
                    and zone is not self._source_zone
                    and not zone.is_archive
                ):
                    self._set_zone_highlight(zone, "adjacent")
        else:
            for zone in self._drop_zones:
                if zone is not self._source_zone:
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
        """Quick 260423-o8z: сбросить подсветку всех зон (pill cross-week удалены)."""
        for zone in self._drop_zones:
            self._set_zone_highlight(zone, "normal")

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
