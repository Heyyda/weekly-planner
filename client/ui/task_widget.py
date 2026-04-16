"""TaskWidget — виджет одной задачи. Phase 4.

3 стиля рендеринга (D-07/08/09), custom Canvas checkbox (D-11),
hover icons (D-13), theme-aware через ThemeManager.subscribe.

Покрывает:
  WEEK-04: overdue visual (accent_overdue border)
  WEEK-05: 3 стиля через style param
  TASK-02: on_toggle callback при checkbox click
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, datetime
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

VALID_STYLES = {"card", "line", "minimal"}


class TaskWidget:
    """Виджет одной задачи. См. 04-UI-SPEC §Task Block."""

    CHECKBOX_SIZE = 18        # D-11
    CHECKBOX_RADIUS = 3       # D-11
    ICON_SIZE = 14            # D-13

    _PADDING = {"card": (12, 10), "line": (10, 8), "minimal": (6, 6)}
    _CORNER_RADIUS = {"card": 8, "line": 0, "minimal": 6}

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        task: Task,
        style: str,
        theme_manager: ThemeManager,
        on_toggle: Callable[[str, bool], None],
        on_edit: Callable[[str], None],
        on_delete: Callable[[str], None],
    ) -> None:
        if style not in VALID_STYLES:
            logger.warning("Неизвестный style=%r — fallback 'card'", style)
            style = "card"

        self._task = task
        self._style = style
        self._theme = theme_manager
        self._on_toggle = on_toggle
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._hover: bool = False
        self._destroyed: bool = False

        self._cb_canvas: Optional[tk.Canvas] = None
        self._text_label: Optional[ctk.CTkLabel] = None
        self._time_label: Optional[ctk.CTkLabel] = None
        self._edit_btn: Optional[ctk.CTkLabel] = None
        self._del_btn: Optional[ctk.CTkLabel] = None
        self._body_frame: Optional[ctk.CTkFrame] = None

        fg = self._theme.get("bg_secondary") if style == "card" else "transparent"
        self.frame = ctk.CTkFrame(
            parent,
            corner_radius=self._CORNER_RADIUS[style],
            fg_color=fg,
        )

        self._build()
        self._theme.subscribe(self._apply_theme)

    def pack(self, **kwargs) -> None:
        self.frame.pack(**kwargs)

    def get_body_frame(self) -> ctk.CTkFrame:
        """Frame тела задачи — target для DnD bindings (Plan 04-09, D-22)."""
        return self._body_frame

    def update_task(self, task: Task) -> None:
        """Partial update без пересоздания виджетов (PITFALL 4 — scroll preserved)."""
        self._task = task
        if self._text_label is not None and self._text_label.winfo_exists():
            self._text_label.configure(text=task.text)
        self._render_checkbox()
        self._update_time_label()

    def destroy(self) -> None:
        self._destroyed = True
        try:
            self.frame.destroy()
        except Exception as exc:
            logger.debug("TaskWidget destroy: %s", exc)

    def _build(self) -> None:
        padx, pady = self._PADDING[self._style]
        row = ctk.CTkFrame(self.frame, fg_color="transparent")
        row.pack(fill="x", padx=padx, pady=pady)

        self._cb_canvas = tk.Canvas(
            row,
            width=self.CHECKBOX_SIZE,
            height=self.CHECKBOX_SIZE,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
            bg=self._theme.get("bg_secondary" if self._style == "card" else "bg_primary"),
        )
        self._cb_canvas.pack(side="left", padx=(0, 8))
        self._cb_canvas.bind("<Button-1>", self._on_checkbox_click)

        self._body_frame = ctk.CTkFrame(row, fg_color="transparent", cursor="fleur")
        self._body_frame.pack(side="left", fill="x", expand=True)

        self._text_label = ctk.CTkLabel(
            self._body_frame,
            text=self._task.text,
            anchor="w",
            justify="left",
            wraplength=0,
            font=FONTS["body"],
        )
        self._text_label.pack(side="left", fill="x", expand=True)

        if self._task.time_deadline:
            hhmm = self._extract_hhmm(self._task.time_deadline)
            self._time_label = ctk.CTkLabel(self._body_frame, text=hhmm, font=FONTS["mono"])
            self._time_label.pack(side="left", padx=(4, 0))

        icons_frame = ctk.CTkFrame(row, fg_color="transparent")
        icons_frame.pack(side="right", padx=(4, 0))

        self._edit_btn = ctk.CTkLabel(
            icons_frame, text="✏", width=self.ICON_SIZE + 6, cursor="hand2",
            font=FONTS["caption"],
        )
        self._edit_btn.pack(side="left")
        self._edit_btn.bind("<Button-1>", lambda e: self._on_edit(self._task.id))

        self._del_btn = ctk.CTkLabel(
            icons_frame, text="🗑", width=self.ICON_SIZE + 6, cursor="hand2",
            font=FONTS["caption"],
        )
        self._del_btn.pack(side="left")
        self._del_btn.bind("<Button-1>", lambda e: self._on_delete(self._task.id))

        for w in (self.frame, row, self._body_frame, self._text_label):
            try:
                w.bind("<Enter>", self._on_hover_enter, add="+")
                w.bind("<Leave>", self._on_hover_leave, add="+")
            except tk.TclError:
                pass

        self._render_checkbox()
        self._update_time_label()
        self._set_icons_visible(False)

    def _render_checkbox(self) -> None:
        c = self._cb_canvas
        if c is None or not c.winfo_exists():
            return
        c.delete("all")
        s = self.CHECKBOX_SIZE
        r = self.CHECKBOX_RADIUS

        if self._task.done:
            fill = self._theme.get("accent_done")
            c.create_rectangle(r, r, s - r, s - r, fill=fill, outline="", tags="box")
            pts = [s * 0.22, s * 0.55, s * 0.43, s * 0.73, s * 0.78, s * 0.28]
            c.create_line(pts, fill="white", width=2, smooth=False, tags="check")
        elif self._task.is_overdue():
            border = self._theme.get("accent_overdue")
            c.create_rectangle(r, r, s - r, s - r, fill="", outline=border, width=2, tags="box")
        else:
            border = self._theme.get("text_secondary")
            c.create_rectangle(r, r, s - r, s - r, fill="", outline=border, width=1, tags="box")

    def _update_time_label(self) -> None:
        if self._time_label is None or not self._time_label.winfo_exists():
            return
        if self._task.time_deadline:
            self._time_label.configure(text=self._extract_hhmm(self._task.time_deadline))

        if self._task.done:
            color = self._theme.get("text_tertiary")
        elif self._task.is_overdue() or self._is_time_overdue():
            color = self._theme.get("accent_overdue")
        else:
            color = self._theme.get("text_secondary")
        try:
            self._time_label.configure(text_color=color)
        except tk.TclError:
            pass

    def _is_time_overdue(self) -> bool:
        if not self._task.time_deadline or self._task.done:
            return False
        try:
            if "T" in self._task.time_deadline:
                try:
                    dl = datetime.fromisoformat(
                        self._task.time_deadline.replace("Z", "+00:00"))
                    return dl < datetime.now(dl.tzinfo or None)
                except (ValueError, TypeError):
                    return False
            if self._task.day != date.today().isoformat():
                return False
            hhmm = self._task.time_deadline[:5]
            now_hm = datetime.now().strftime("%H:%M")
            return hhmm < now_hm
        except Exception:
            return False

    @staticmethod
    def _extract_hhmm(value: str) -> str:
        if not value:
            return ""
        if len(value) >= 5 and value[2] == ":":
            return value[:5]
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except (ValueError, TypeError):
            return value[:5]

    def _on_hover_enter(self, event=None) -> None:
        if self._destroyed:
            return
        self._hover = True
        if self._style == "minimal":
            try:
                self.frame.configure(fg_color=self._theme.get("bg_secondary"))
            except tk.TclError:
                pass
        self._set_icons_visible(True)

    def _on_hover_leave(self, event=None) -> None:
        if self._destroyed:
            return
        self._hover = False
        if self._style == "minimal":
            try:
                self.frame.configure(fg_color="transparent")
            except tk.TclError:
                pass
        self._set_icons_visible(False)

    def _set_icons_visible(self, visible: bool) -> None:
        """PITFALL 6: 'invisible' color = current bg (пересчитываем при theme switch)."""
        color = self._theme.get("text_secondary") if visible else self._theme.get(
            "bg_secondary" if self._style == "card" else "bg_primary")
        for btn in (self._edit_btn, self._del_btn):
            if btn is not None:
                try:
                    btn.configure(text_color=color)
                except tk.TclError:
                    pass

    def _on_checkbox_click(self, event=None) -> None:
        """Toggle done + callback (optimistic UI)."""
        if self._destroyed:
            return
        new_done = not self._task.done
        self._task.done = new_done
        self._render_checkbox()
        self._update_time_label()
        try:
            self._on_toggle(self._task.id, new_done)
        except Exception as exc:
            logger.error("on_toggle callback failed: %s", exc)

    def _apply_theme(self, palette: dict) -> None:
        """ThemeManager callback — перекрасить всё (PITFALL 6)."""
        if self._destroyed:
            return
        try:
            if self._style == "card":
                self.frame.configure(fg_color=palette.get("bg_secondary"))
            if self._cb_canvas and self._cb_canvas.winfo_exists():
                self._cb_canvas.configure(
                    bg=palette.get("bg_secondary" if self._style == "card" else "bg_primary"))
        except tk.TclError:
            pass
        self._render_checkbox()
        self._update_time_label()
        self._set_icons_visible(self._hover)
