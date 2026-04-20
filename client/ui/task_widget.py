"""TaskWidget — виджет одной задачи. v0.4.0 redesign.

Улучшения:
- Checkbox 22×22 с плавной галочкой (smooth=True)
- Иконки-символы (✎ pencil, 🗑 trash) всегда видны, dim при отсутствии hover
- Компактный padding (5-6 px)
- Rounded corners r=10
- Overdue state: ярко-красный checkbox border + текст

Forest Phase G (260421-2a1):
- Hover на иконки ✎ / 🗑 через ColorTween (150ms ease-out) вместо мгновенного
  configure(text_color=...). Отслеживаем `_icon_last_color[btn]` чтобы знать
  from_hex для следующего tween (cget на CTkLabel может вернуть tuple вместо
  hex — опираемся на собственный трекинг).
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, datetime
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.ui.color_tween import ColorTween
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

VALID_STYLES = {"card", "line", "minimal"}

# Phase G: стандартная длительность hover-tween по всему приложению.
ICON_TWEEN_MS = 150
ICON_TWEEN_EASING = "ease-out"


class TaskWidget:
    CHECKBOX_SIZE = 22
    CHECKBOX_RADIUS = 4
    ICON_PAD = 4
    CORNER_RADIUS = 10

    _PADDING = {"card": (10, 7), "line": (8, 5), "minimal": (6, 4)}

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
        self._row: Optional[ctk.CTkFrame] = None

        # Phase G: трекинг последнего применённого text_color для ColorTween.
        # CTkLabel.cget("text_color") в некоторых версиях CTk возвращает tuple
        # (light_color, dark_color), а не hex — ColorTween работает только с
        # hex, поэтому помним сами.
        self._icon_last_color: dict[int, str] = {}

        fg = self._bg_color()
        self.frame = ctk.CTkFrame(
            parent,
            corner_radius=self.CORNER_RADIUS if style != "line" else 0,
            fg_color=fg,
        )

        self._build()
        self._theme.subscribe(self._apply_theme)

    def pack(self, **kwargs) -> None:
        self.frame.pack(**kwargs)

    def get_body_frame(self) -> ctk.CTkFrame:
        """Frame тела задачи — target для DnD bindings."""
        return self._body_frame

    def update_task(self, task: Task) -> None:
        self._task = task
        if self._text_label is not None and self._text_label.winfo_exists():
            try:
                self._text_label.configure(text=task.text)
            except tk.TclError:
                pass
        self._render_checkbox()
        self._update_time_label()
        self._update_text_decoration()

    def destroy(self) -> None:
        self._destroyed = True
        # Phase G: отменить in-flight hover-твины на наших иконках перед destroy.
        for btn in (self._edit_btn, self._del_btn):
            if btn is not None:
                try:
                    ColorTween.cancel_all(btn)
                except Exception:
                    pass
        try:
            self.frame.destroy()
        except Exception as exc:
            logger.debug("TaskWidget destroy: %s", exc)

    # ---- Build ----

    def _bg_color(self) -> str:
        if self._style == "card":
            return self._theme.get("bg_secondary")
        return "transparent"

    def _build(self) -> None:
        padx, pady = self._PADDING[self._style]
        self._row = ctk.CTkFrame(self.frame, fg_color="transparent")
        self._row.pack(fill="x", padx=padx, pady=pady)

        # Checkbox — custom tk.Canvas (плавная галочка)
        self._cb_canvas = tk.Canvas(
            self._row,
            width=self.CHECKBOX_SIZE,
            height=self.CHECKBOX_SIZE,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
            bg=self._bg_color() if self._bg_color() != "transparent" else self._theme.get("bg_primary"),
        )
        self._cb_canvas.pack(side="left", padx=(0, 10))
        self._cb_canvas.bind("<Button-1>", self._on_checkbox_click)

        # Body frame — holds text + time; used as DnD target
        self._body_frame = ctk.CTkFrame(self._row, fg_color="transparent", cursor="fleur")
        self._body_frame.pack(side="left", fill="x", expand=True)

        self._text_label = ctk.CTkLabel(
            self._body_frame,
            text=self._task.text,
            anchor="w",
            justify="left",
            wraplength=0,
            font=FONTS["body"],
            text_color=self._theme.get("text_primary"),
        )
        self._text_label.pack(side="left", fill="x", expand=True)

        # Time label (всегда создаём — показываем/прячем по наличию time_deadline)
        self._time_label = ctk.CTkLabel(
            self._body_frame, text="", font=FONTS["mono"],
            text_color=self._theme.get("text_secondary"),
        )
        self._time_label.pack(side="left", padx=(6, 0))
        # visibility toggled in _update_time_label

        # Icons frame — right side
        icons_frame = ctk.CTkFrame(self._row, fg_color="transparent")
        icons_frame.pack(side="right", padx=(6, 0))

        tertiary = self._theme.get("text_tertiary")

        self._edit_btn = ctk.CTkLabel(
            icons_frame, text="✎", width=18, cursor="hand2",
            font=(FONTS["body"][0], 16, "normal"),
            text_color=tertiary,
        )
        self._edit_btn.pack(side="left", padx=(0, self.ICON_PAD))
        self._edit_btn.bind("<Button-1>", lambda e: self._on_edit(self._task.id))
        self._edit_btn.bind("<Enter>", lambda e: self._icon_hover(self._edit_btn, True))
        self._edit_btn.bind("<Leave>", lambda e: self._icon_hover(self._edit_btn, False))
        self._icon_last_color[id(self._edit_btn)] = tertiary

        self._del_btn = ctk.CTkLabel(
            icons_frame, text="🗑", width=18, cursor="hand2",
            font=(FONTS["body"][0], 14, "normal"),
            text_color=tertiary,
        )
        self._del_btn.pack(side="left")
        self._del_btn.bind("<Button-1>", lambda e: self._on_delete(self._task.id))
        self._del_btn.bind("<Enter>", lambda e: self._icon_hover(self._del_btn, True))
        self._del_btn.bind("<Leave>", lambda e: self._icon_hover(self._del_btn, False))
        self._icon_last_color[id(self._del_btn)] = tertiary

        # Hover on row — раскрашиваем иконки (они ВСЕГДА видны, но темнее когда no hover)
        for w in (self.frame, self._row, self._body_frame, self._text_label, self._time_label):
            try:
                w.bind("<Enter>", self._on_hover_enter, add="+")
                w.bind("<Leave>", self._on_hover_leave, add="+")
            except tk.TclError:
                pass

        self._render_checkbox()
        self._update_time_label()
        self._update_text_decoration()

    # ---- Checkbox ----

    def _render_checkbox(self) -> None:
        c = self._cb_canvas
        if c is None or not c.winfo_exists():
            return
        c.delete("all")
        s = self.CHECKBOX_SIZE
        pad = 2

        if self._task.done:
            fill = self._theme.get("accent_done")
            # Rounded fill via oval+rect approximation
            c.create_rectangle(pad, pad, s - pad, s - pad, fill=fill, outline="", width=0)
            # Forest Phase B: чекмарк берёт цвет из палитры (bg_primary), не захардкожен "white".
            # В forest_light → #EEE9DC (cream) на forest-fill #1E5239 — высокий контраст.
            # В forest_dark → #161E1A (тёмный) на lifted forest #5E9E7A — высокий контраст.
            checkmark_color = self._theme.get("bg_primary")
            pts = [s * 0.25, s * 0.52, s * 0.42, s * 0.70, s * 0.75, s * 0.32]
            c.create_line(pts, fill=checkmark_color, width=2, smooth=True, capstyle="round")
        elif self._task.is_overdue():
            border = self._theme.get("accent_overdue")
            c.create_rectangle(pad, pad, s - pad, s - pad, fill="", outline=border, width=2)
        else:
            border = self._theme.get("text_tertiary")
            c.create_rectangle(pad, pad, s - pad, s - pad, fill="", outline=border, width=1)

    def _on_checkbox_click(self, event=None) -> None:
        """Optimistic UI: toggle локально + callback → storage."""
        if self._destroyed:
            return
        new_done = not self._task.done
        self._task.done = new_done
        self._render_checkbox()
        self._update_text_decoration()
        self._update_time_label()
        try:
            self._on_toggle(self._task.id, new_done)
        except Exception as exc:
            logger.error("on_toggle: %s", exc)

    # ---- Time label ----

    def _update_time_label(self) -> None:
        if self._time_label is None or not self._time_label.winfo_exists():
            return
        if not self._task.time_deadline:
            try:
                self._time_label.pack_forget()
            except tk.TclError:
                pass
            return
        try:
            self._time_label.configure(text=self._extract_hhmm(self._task.time_deadline))
            self._time_label.pack(side="left", padx=(6, 0))
        except tk.TclError:
            pass
        if self._task.done:
            color = self._theme.get("text_tertiary")
        elif self._task.is_overdue():
            color = self._theme.get("accent_overdue")
        else:
            color = self._theme.get("text_secondary")
        try:
            self._time_label.configure(text_color=color)
        except tk.TclError:
            pass

    def _update_text_decoration(self) -> None:
        """Strikethrough для выполненных + dim цвет."""
        if self._text_label is None or not self._text_label.winfo_exists():
            return
        family, size, _weight = FONTS["body"]
        if self._task.done:
            try:
                self._text_label.configure(
                    font=(family, size, "overstrike"),
                    text_color=self._theme.get("text_tertiary"),
                )
            except tk.TclError:
                pass
        else:
            color = self._theme.get("accent_overdue") if self._task.is_overdue() else self._theme.get("text_primary")
            try:
                self._text_label.configure(
                    font=FONTS["body"],
                    text_color=color,
                )
            except tk.TclError:
                pass

    # ---- Hover ----

    def _on_hover_enter(self, event=None) -> None:
        if self._destroyed or self._hover:
            return
        self._hover = True
        self._refresh_icon_visibility()

    def _on_hover_leave(self, event=None) -> None:
        if self._destroyed:
            return
        # Debounce: check actual cursor position to avoid flicker when mouse enters child
        try:
            mx = self.frame.winfo_pointerx()
            my = self.frame.winfo_pointery()
            fx = self.frame.winfo_rootx()
            fy = self.frame.winfo_rooty()
            fw = self.frame.winfo_width()
            fh = self.frame.winfo_height()
            if fx <= mx <= fx + fw and fy <= my <= fy + fh:
                return  # ещё внутри frame
        except tk.TclError:
            pass
        self._hover = False
        self._refresh_icon_visibility()

    def _refresh_icon_visibility(self) -> None:
        """Phase G: плавный tween icon color вместо мгновенного configure."""
        target = self._theme.get("text_secondary") if self._hover else self._theme.get("text_tertiary")
        for btn in (self._edit_btn, self._del_btn):
            if btn is None or not btn.winfo_exists():
                continue
            self._tween_icon(btn, target)

    def _icon_hover(self, btn: ctk.CTkLabel, entering: bool) -> None:
        """Phase G: hover на конкретную иконку — tween к brand/overdue/dim-цвету."""
        if self._destroyed or btn is None or not btn.winfo_exists():
            return
        if entering:
            # Forest Phase B: hover на 🗑 → accent_overdue (clay),
            # на ✎ (и прочих) → accent_brand (forest). Семантика «delete = красный».
            target = (
                self._theme.get("accent_overdue")
                if btn is self._del_btn
                else self._theme.get("accent_brand")
            )
        else:
            target = (
                self._theme.get("text_secondary")
                if self._hover
                else self._theme.get("text_tertiary")
            )
        self._tween_icon(btn, target)

    def _tween_icon(self, btn: ctk.CTkLabel, target_hex: str) -> None:
        """Общий helper: ColorTween на text_color c учётом _icon_last_color."""
        if self._destroyed or btn is None or not btn.winfo_exists():
            return
        key = id(btn)
        current = self._icon_last_color.get(key, target_hex)
        self._icon_last_color[key] = target_hex
        try:
            ColorTween.tween(
                btn, "text_color", current, target_hex,
                duration_ms=ICON_TWEEN_MS, easing=ICON_TWEEN_EASING,
            )
        except Exception as exc:
            logger.debug("icon tween failed: %s", exc)
            try:
                btn.configure(text_color=target_hex)
            except tk.TclError:
                pass

    # ---- Theme ----

    def _apply_theme(self, palette: dict) -> None:
        if self._destroyed:
            return
        try:
            self.frame.configure(fg_color=self._bg_color())
        except tk.TclError:
            pass
        if self._text_label is not None and self._text_label.winfo_exists():
            self._update_text_decoration()
        self._render_checkbox()
        self._update_time_label()
        # Phase G: при смене темы сбрасываем _icon_last_color на новый tertiary
        # и перекрашиваем иконки мгновенно (тема-switch — не анимируемая операция).
        new_tertiary = palette.get("text_tertiary") or self._theme.get("text_tertiary")
        for btn in (self._edit_btn, self._del_btn):
            if btn is None or not btn.winfo_exists():
                continue
            try:
                ColorTween.cancel(btn, "text_color")
            except Exception:
                pass
            self._icon_last_color[id(btn)] = (
                palette.get("text_secondary") if self._hover else new_tertiary
            ) or new_tertiary
            try:
                btn.configure(
                    text_color=palette.get("text_secondary") if self._hover else new_tertiary
                )
            except tk.TclError:
                pass

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
