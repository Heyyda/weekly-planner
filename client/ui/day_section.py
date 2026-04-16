"""DaySection — секция одного дня в аккордеоне недели. Phase 4.

Покрывает WEEK-01 (7 секций рендерят задачи), TASK-07 (sorted by position).
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from shared.parse_input import parse_quick_input
from client.ui.task_widget import TaskWidget
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

DAY_NAMES_RU_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
TODAY_STRIP_WIDTH = 3


class DaySection:
    """Секция одного дня. См. 04-UI-SPEC §Day Section."""

    PLUS_SIZE = 24
    INLINE_ENTRY_HEIGHT = 32

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        day_date: date,
        is_today: bool,
        theme_manager: ThemeManager,
        task_style: str,
        user_id: str,
        on_task_toggle: Callable[[str, bool], None],
        on_task_edit: Callable[[str], None],
        on_task_delete: Callable[[str], None],
        on_inline_add: Callable[[Task], None],
    ) -> None:
        self._day_date = day_date
        self._is_today = is_today
        self._theme = theme_manager
        self._task_style = task_style
        self._user_id = user_id
        self._on_task_toggle = on_task_toggle
        self._on_task_edit = on_task_edit
        self._on_task_delete = on_task_delete
        self._on_inline_add = on_inline_add
        self._is_archive: bool = False
        self._destroyed: bool = False

        self._task_widgets: dict[str, TaskWidget] = {}
        self._tasks: list[Task] = []

        self._plus_label: Optional[ctk.CTkLabel] = None
        self._inline_entry: Optional[ctk.CTkEntry] = None
        self._inline_frame: Optional[ctk.CTkFrame] = None

        self._counter_label: Optional[ctk.CTkLabel] = None
        self._today_strip: Optional[ctk.CTkFrame] = None
        self._body_frame: Optional[ctk.CTkFrame] = None

        self.frame = ctk.CTkFrame(
            parent, corner_radius=6, fg_color=self._theme.get("bg_secondary"),
        )
        self._build()
        self._theme.subscribe(self._apply_theme)

    def pack(self, **kwargs) -> None:
        self.frame.pack(**kwargs)

    def render_tasks(self, tasks: list[Task]) -> None:
        """TASK-07: sort by position. PITFALL 4: partial update."""
        if self._destroyed:
            return
        sorted_tasks = sorted(tasks, key=lambda t: (t.position, t.created_at or ""))
        self._tasks = sorted_tasks

        new_ids = {t.id for t in sorted_tasks}
        for tid in list(self._task_widgets.keys()):
            if tid not in new_ids:
                try:
                    self._task_widgets[tid].destroy()
                except Exception:
                    pass
                del self._task_widgets[tid]

        for t in sorted_tasks:
            if t.id in self._task_widgets:
                self._task_widgets[t.id].update_task(t)
            else:
                w = TaskWidget(
                    self._body_frame, t, self._task_style, self._theme,
                    self._on_task_toggle, self._on_task_edit, self._on_task_delete,
                )
                w.pack(fill="x", pady=(0, 4))
                self._task_widgets[t.id] = w

        self._update_counter(len(sorted_tasks))
        self._update_empty_state(len(sorted_tasks) == 0)

    def get_body_frame(self) -> ctk.CTkFrame:
        """Target для DnD drop zone (Plan 04-09)."""
        return self._body_frame

    def get_day_date(self) -> date:
        return self._day_date

    def set_archive_mode(self, is_archive: bool) -> None:
        """WEEK-06: dim + disable inline add."""
        self._is_archive = is_archive
        self._update_empty_state(len(self._tasks) == 0)

    def destroy(self) -> None:
        self._destroyed = True
        for w in list(self._task_widgets.values()):
            try:
                w.destroy()
            except Exception:
                pass
        self._task_widgets.clear()
        try:
            self.frame.destroy()
        except Exception as exc:
            logger.debug("DaySection destroy: %s", exc)

    def _build(self) -> None:
        row = ctk.CTkFrame(self.frame, fg_color="transparent")
        row.pack(fill="x")

        if self._is_today:
            accent = self._theme.get("accent_brand")
            strip = ctk.CTkFrame(
                row, width=TODAY_STRIP_WIDTH, fg_color=accent, corner_radius=0,
            )
            strip.pack(side="left", fill="y", padx=(0, 6))
            strip.pack_propagate(False)
            self._today_strip = strip

        header = ctk.CTkFrame(row, fg_color="transparent")
        header.pack(side="left", fill="x", expand=True)

        day_name = DAY_NAMES_RU_SHORT[self._day_date.weekday()]
        label_text = f"{day_name} {self._day_date.day}"
        if self._is_today:
            label_text += "  • сегодня"
        font = FONTS["body"]
        if self._is_today:
            font = (font[0], font[1], "bold")
        ctk.CTkLabel(header, text=label_text, font=font).pack(
            side="left", padx=8, pady=6,
        )
        self._counter_label = ctk.CTkLabel(
            header, text="(0)", font=FONTS["caption"],
            text_color=self._theme.get("text_tertiary"),
        )
        self._counter_label.pack(side="right", padx=8)

        self._body_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self._body_frame.pack(fill="x", padx=8, pady=(0, 6))
        self._body_frame.bind("<Configure>", self._on_body_configure, add="+")

        self._plus_label = ctk.CTkLabel(
            self._body_frame,
            text="+",
            font=("Segoe UI Variable", self.PLUS_SIZE, "bold"),
            text_color=self._theme.get("text_tertiary"),
            cursor="hand2",
        )
        self._plus_label.pack(pady=8)
        self._plus_label.bind("<Button-1>", lambda e: self._show_inline_add())
        self._plus_label.bind("<Enter>", lambda e: self._on_plus_hover_enter())
        self._plus_label.bind("<Leave>", lambda e: self._on_plus_hover_leave())

    def _show_inline_add(self) -> None:
        """D-33: click '+' → CTkEntry inline."""
        if self._is_archive or self._destroyed:
            return
        if self._inline_entry is not None:
            return

        if self._plus_label is not None:
            self._plus_label.pack_forget()

        self._inline_frame = ctk.CTkFrame(self._body_frame, fg_color="transparent")
        self._inline_frame.pack(fill="x", pady=4)
        self._inline_entry = ctk.CTkEntry(
            self._inline_frame,
            placeholder_text="Новая задача...",
            height=self.INLINE_ENTRY_HEIGHT,
        )
        self._inline_entry.pack(fill="x")
        self._inline_entry.focus_set()
        self._inline_entry.bind("<Return>", self._on_inline_enter)
        self._inline_entry.bind("<Escape>", lambda e: self._hide_inline_add())
        self._inline_entry.bind(
            "<FocusOut>",
            lambda e: self.frame.after(100, self._maybe_hide_inline),
        )

    def _on_inline_enter(self, event=None) -> None:
        text = self._inline_entry.get().strip() if self._inline_entry else ""
        if not text:
            return
        parsed = parse_quick_input(text)
        task = Task.new(
            user_id=self._user_id,
            text=parsed["text"] or text,
            day=self._day_date.isoformat(),  # day принудительно — этот день
            time_deadline=parsed.get("time"),
            position=len(self._tasks),
        )
        try:
            self._on_inline_add(task)
        except Exception as exc:
            logger.error("on_inline_add callback failed: %s", exc)
        if self._inline_entry is not None:
            self._inline_entry.delete(0, "end")

    def _maybe_hide_inline(self) -> None:
        if self._destroyed or self._inline_entry is None:
            return
        try:
            focused = self._body_frame.focus_get()
            if focused is not self._inline_entry:
                self._hide_inline_add()
        except Exception:
            self._hide_inline_add()

    def _hide_inline_add(self, event=None) -> None:
        if self._inline_entry is not None:
            try:
                self._inline_entry.destroy()
            except Exception:
                pass
            self._inline_entry = None
        if self._inline_frame is not None:
            try:
                self._inline_frame.destroy()
            except Exception:
                pass
            self._inline_frame = None
        if len(self._tasks) == 0 and not self._is_archive and self._plus_label is not None:
            try:
                self._plus_label.pack(pady=8)
            except tk.TclError:
                pass

    def _update_empty_state(self, is_empty: bool) -> None:
        if self._plus_label is None:
            return
        if is_empty and not self._is_archive and self._inline_entry is None:
            try:
                self._plus_label.pack(pady=8)
            except tk.TclError:
                pass
        else:
            try:
                self._plus_label.pack_forget()
            except tk.TclError:
                pass

    def _update_counter(self, count: int) -> None:
        if self._counter_label is not None and self._counter_label.winfo_exists():
            try:
                self._counter_label.configure(text=f"({count})")
            except tk.TclError:
                pass

    def _on_plus_hover_enter(self) -> None:
        if self._plus_label and self._plus_label.winfo_exists():
            try:
                self._plus_label.configure(text_color=self._theme.get("accent_brand"))
            except tk.TclError:
                pass

    def _on_plus_hover_leave(self) -> None:
        if self._plus_label and self._plus_label.winfo_exists():
            try:
                self._plus_label.configure(text_color=self._theme.get("text_tertiary"))
            except tk.TclError:
                pass

    def _on_body_configure(self, event) -> None:
        """PITFALL 5: адаптивный wraplength при resize."""
        if self._destroyed:
            return
        try:
            new_wrap = max(100, int(event.width) - 80)
        except Exception:
            return
        for w in self._task_widgets.values():
            if w._text_label and w._text_label.winfo_exists():
                try:
                    w._text_label.configure(wraplength=new_wrap)
                except tk.TclError:
                    pass

    def _apply_theme(self, palette: dict) -> None:
        if self._destroyed:
            return
        try:
            self.frame.configure(fg_color=palette.get("bg_secondary"))
        except tk.TclError:
            pass
        if self._today_strip is not None and self._today_strip.winfo_exists():
            try:
                self._today_strip.configure(fg_color=palette.get("accent_brand"))
            except tk.TclError:
                pass
        if self._counter_label is not None and self._counter_label.winfo_exists():
            try:
                self._counter_label.configure(text_color=palette.get("text_tertiary"))
            except tk.TclError:
                pass
        if self._plus_label is not None and self._plus_label.winfo_exists():
            try:
                self._plus_label.configure(text_color=palette.get("text_tertiary"))
            except tk.TclError:
                pass
