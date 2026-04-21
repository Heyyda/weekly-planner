"""DaySection — компактная секция одного дня в аккордеоне недели.

v0.4.0 redesign:
- Header row = ОДНА строка 28px: strip | Пн 20  • сегодня | tasks N | +
- Пустой день collapsed до 36px (одна header-строка + отступ)
- Плюс в правом верхнем углу header (не по центру body)
- Rounded corners везде r=10
- Соседи с неактивным днём — минимальный фон
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
DAY_NAMES_RU_LONG = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
TODAY_STRIP_WIDTH = 3
CORNER_RADIUS = 10
HEADER_HEIGHT = 34
INLINE_ENTRY_HEIGHT = 30


class DaySection:
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

        self._plus_btn: Optional[ctk.CTkLabel] = None
        self._inline_entry: Optional[ctk.CTkEntry] = None
        self._inline_frame: Optional[ctk.CTkFrame] = None
        self._counter_label: Optional[ctk.CTkLabel] = None
        self._today_strip: Optional[ctk.CTkFrame] = None
        self._body_frame: Optional[ctk.CTkFrame] = None
        self._header_row: Optional[ctk.CTkFrame] = None

        self.frame = ctk.CTkFrame(
            parent, corner_radius=CORNER_RADIUS,
            fg_color=self._day_bg_color(),
        )
        self._build()
        self._theme.subscribe(self._apply_theme)

    def pack(self, **kwargs) -> None:
        self.frame.pack(**kwargs)

    def render_tasks(self, tasks: list[Task]) -> None:
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
                w.pack(fill="x", pady=(0, 3))
                self._task_widgets[t.id] = w

        self._update_counter(len(sorted_tasks))
        self._update_body_visibility()

    def get_body_frame(self) -> ctk.CTkFrame:
        return self._body_frame

    def get_drop_frame(self) -> ctk.CTkFrame:
        """Фрейм для регистрации DropZone — вся секция дня (header + body).

        Используется вместо get_body_frame(), потому что _body_frame может быть
        скрыт через pack_forget() при пустом дне (см. _update_body_visibility).
        Корневой self.frame упакован в main_window всегда, поэтому имеет
        ненулевой bbox — DnD на пустой день работает корректно.
        """
        return self.frame

    def get_day_date(self) -> date:
        return self._day_date

    def set_archive_mode(self, is_archive: bool) -> None:
        self._is_archive = is_archive
        self._update_body_visibility()

    def set_day_date(self, new_date: date, is_today: bool) -> None:
        """Обновить день без пересоздания виджета (diff-rebuild).

        UX-01: устраняет мерцание при смене недели — переиспользуем один и тот же
        DaySection, меняя только дату/цвет/strip/label.

        Args:
            new_date: новая дата дня
            is_today: является ли этот день сегодняшним
        """
        if self._destroyed:
            return
        old_is_today = self._is_today
        self._day_date = new_date
        self._is_today = is_today

        # 1) Фон рамки
        try:
            self.frame.configure(fg_color=self._day_bg_color())
        except tk.TclError:
            pass

        # 2) today_strip transition
        if is_today and not old_is_today:
            self._swap_to_today_strip()
        elif not is_today and old_is_today:
            self._swap_to_spacer()

        # 3) Label текст + шрифт
        day_label = self._find_day_label()
        if day_label is not None:
            day_name_short = DAY_NAMES_RU_SHORT[new_date.weekday()]
            day_name_long = DAY_NAMES_RU_LONG[new_date.weekday()]
            if is_today:
                label_text = f"{day_name_long}, {new_date.day}"
                font = FONTS["h2"]
            else:
                label_text = f"{day_name_short} {new_date.day}"
                font = FONTS["body"]
            try:
                day_label.configure(text=label_text, font=font)
            except tk.TclError:
                pass

    def _find_day_label(self) -> Optional[ctk.CTkLabel]:
        """Найти day_label в _header_row — первый CTkLabel (после strip/spacer)."""
        if self._header_row is None:
            return None
        try:
            for child in self._header_row.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    return child
        except tk.TclError:
            pass
        return None

    def _swap_to_today_strip(self) -> None:
        """not-today → today: удалить spacer → создать today_strip первым."""
        if self._header_row is None:
            return
        try:
            children = list(self._header_row.winfo_children())
        except tk.TclError:
            return
        # Первый child — spacer (transparent frame). Удаляем.
        if children and isinstance(children[0], ctk.CTkFrame):
            try:
                children[0].destroy()
            except Exception:
                pass

        try:
            self._today_strip = ctk.CTkFrame(
                self._header_row, width=TODAY_STRIP_WIDTH,
                fg_color=self._theme.get("accent_brand"), corner_radius=0,
            )
            remaining = list(self._header_row.winfo_children())
            # Находим первого ещё-живого child, КРОМЕ только что созданного strip.
            first_existing = None
            for child in remaining:
                if child is not self._today_strip:
                    first_existing = child
                    break
            if first_existing is not None:
                self._today_strip.pack(
                    side="left", fill="y", padx=(0, 8), before=first_existing,
                )
            else:
                self._today_strip.pack(side="left", fill="y", padx=(0, 8))
            self._today_strip.pack_propagate(False)
        except tk.TclError:
            pass

    def _swap_to_spacer(self) -> None:
        """today → not-today: destroy strip → создать spacer первым."""
        if self._today_strip is not None:
            try:
                self._today_strip.destroy()
            except Exception:
                pass
            self._today_strip = None
        if self._header_row is None:
            return
        try:
            spacer = ctk.CTkFrame(
                self._header_row, width=TODAY_STRIP_WIDTH + 8, fg_color="transparent",
            )
            remaining = list(self._header_row.winfo_children())
            # Найти первого живого child, отличного от spacer
            first_existing = None
            for child in remaining:
                if child is not spacer:
                    first_existing = child
                    break
            if first_existing is not None:
                spacer.pack(side="left", before=first_existing)
            else:
                spacer.pack(side="left")
        except tk.TclError:
            pass

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

    # ---- Build ----

    def _day_bg_color(self) -> str:
        return self._theme.get("bg_secondary") if self._is_today else self._theme.get("bg_primary")

    def _build(self) -> None:
        # Header row — single line, 34px
        self._header_row = ctk.CTkFrame(self.frame, fg_color="transparent", height=HEADER_HEIGHT)
        self._header_row.pack(fill="x", padx=0, pady=0)
        self._header_row.pack_propagate(False)

        if self._is_today:
            self._today_strip = ctk.CTkFrame(
                self._header_row, width=TODAY_STRIP_WIDTH,
                fg_color=self._theme.get("accent_brand"), corner_radius=0,
            )
            self._today_strip.pack(side="left", fill="y", padx=(0, 8))
            self._today_strip.pack_propagate(False)
        else:
            # Отступ вместо strip
            spacer = ctk.CTkFrame(self._header_row, width=TODAY_STRIP_WIDTH + 8, fg_color="transparent")
            spacer.pack(side="left")

        day_name = DAY_NAMES_RU_SHORT[self._day_date.weekday()]
        label_text = f"{day_name} {self._day_date.day}"
        if self._is_today:
            label_text = f"{DAY_NAMES_RU_LONG[self._day_date.weekday()]}, {self._day_date.day}"
        font = FONTS["h2"] if self._is_today else FONTS["body"]

        day_label = ctk.CTkLabel(
            self._header_row, text=label_text, font=font,
            text_color=self._theme.get("text_primary"),
        )
        day_label.pack(side="left", pady=4)

        # Right side: counter + plus
        right = ctk.CTkFrame(self._header_row, fg_color="transparent")
        right.pack(side="right", padx=(0, 8))

        self._counter_label = ctk.CTkLabel(
            right, text="", font=FONTS["caption"],
            text_color=self._theme.get("text_tertiary"),
        )
        self._counter_label.pack(side="left", padx=(0, 6))

        self._plus_btn = ctk.CTkLabel(
            right, text="＋", font=(FONTS["body"][0], 18, "normal"),
            text_color=self._theme.get("text_tertiary"),
            cursor="hand2", width=22,
        )
        self._plus_btn.pack(side="left")
        self._plus_btn.bind("<Button-1>", lambda e: self._show_inline_add())
        self._plus_btn.bind("<Enter>", lambda e: self._plus_btn.configure(text_color=self._theme.get("accent_brand")))
        self._plus_btn.bind("<Leave>", lambda e: self._plus_btn.configure(text_color=self._theme.get("text_tertiary")))

        # Body frame — hidden until tasks exist or inline-add opened
        self._body_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self._body_frame.bind("<Configure>", self._on_body_configure, add="+")
        # Don't pack yet — visibility controlled in _update_body_visibility

    def _update_body_visibility(self) -> None:
        """Пустой день + no inline-add → body скрыт (только header = 34px)."""
        if self._destroyed or self._body_frame is None:
            return
        should_show = len(self._tasks) > 0 or self._inline_entry is not None
        try:
            if should_show:
                self._body_frame.pack(fill="x", padx=10, pady=(2, 6))
            else:
                self._body_frame.pack_forget()
        except tk.TclError:
            pass

    def _update_counter(self, count: int) -> None:
        if self._counter_label is not None and self._counter_label.winfo_exists():
            try:
                text = "" if count == 0 else f"{count}"
                self._counter_label.configure(text=text)
            except tk.TclError:
                pass

    # ---- Inline add ----

    def _show_inline_add(self) -> None:
        if self._is_archive or self._destroyed:
            return
        if self._inline_entry is not None:
            try:
                self._inline_entry.focus_set()
            except tk.TclError:
                pass
            return

        self._inline_frame = ctk.CTkFrame(self._body_frame, fg_color="transparent")
        self._inline_frame.pack(fill="x", pady=(0, 3))
        self._inline_entry = ctk.CTkEntry(
            self._inline_frame,
            placeholder_text="Новая задача...",
            height=INLINE_ENTRY_HEIGHT,
            corner_radius=CORNER_RADIUS,
            font=FONTS["body"],
        )
        self._inline_entry.pack(fill="x")
        self._update_body_visibility()
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
            day=self._day_date.isoformat(),
            time_deadline=parsed.get("time"),
            position=len(self._tasks),
        )
        try:
            self._on_inline_add(task)
        except Exception as exc:
            logger.error("on_inline_add: %s", exc)
        if self._inline_entry is not None:
            try:
                self._inline_entry.delete(0, "end")
            except tk.TclError:
                pass

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
        self._update_body_visibility()

    def _on_body_configure(self, event) -> None:
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
            self.frame.configure(fg_color=self._day_bg_color())
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
        if self._plus_btn is not None and self._plus_btn.winfo_exists():
            try:
                self._plus_btn.configure(text_color=palette.get("text_tertiary"))
            except tk.TclError:
                pass
