"""DaySection — компактная секция одного дня в аккордеоне недели.

v0.4.0 redesign:
- Header row = ОДНА строка 28px: strip | Пн 20  • сегодня | tasks N | +
- Пустой день collapsed до 36px (одна header-строка + отступ)
- Плюс в правом верхнем углу header (не по центру body)
- Rounded corners везде r=10
- Соседи с неактивным днём — минимальный фон

Forest Phase D (260421-183):
- Inline edit-card: TaskWidget заменяется на TaskEditCard при enter_edit_mode
- `_editing_task_id` трекает текущую редактируемую задачу (одна за раз)
- Открытие второй edit-mode автосохраняет первую (flow-friendly)
- `on_task_update(task_id, fields)` callback для MainWindow → storage.update_task
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from shared.parse_input import parse_quick_input
from client.ui.task_edit_card import TaskEditCard
from client.ui.task_widget import TaskWidget
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

DAY_NAMES_RU_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAY_NAMES_RU_LONG = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
TODAY_STRIP_WIDTH = 3
CORNER_RADIUS = 12
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
        on_task_update: Optional[Callable[[str, dict], None]] = None,
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
        self._on_task_update = on_task_update
        self._is_archive: bool = False
        self._destroyed: bool = False

        self._task_widgets: dict[str, TaskWidget] = {}
        self._tasks: list[Task] = []

        # Forest Phase D: inline edit state.
        self._editing_task_id: Optional[str] = None
        self._edit_card: Optional[TaskEditCard] = None

        self._plus_btn: Optional[ctk.CTkLabel] = None
        self._inline_entry: Optional[ctk.CTkEntry] = None
        self._inline_frame: Optional[ctk.CTkFrame] = None
        self._counter_label: Optional[ctk.CTkLabel] = None
        self._today_strip: Optional[ctk.CTkFrame] = None
        self._body_frame: Optional[ctk.CTkFrame] = None
        self._header_row: Optional[ctk.CTkFrame] = None
        self._divider: Optional[ctk.CTkFrame] = None

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
                # Forest Phase B: force transparent 'line' style for all task rows
                w = TaskWidget(
                    self._body_frame, t, "line", self._theme,
                    self._on_task_toggle, self._on_task_edit, self._on_task_delete,
                )
                w.pack(fill="x", pady=(0, 3))
                self._task_widgets[t.id] = w

        self._update_counter(len(sorted_tasks))
        self._update_body_visibility()

    def get_body_frame(self) -> ctk.CTkFrame:
        return self._body_frame

    def get_day_date(self) -> date:
        return self._day_date

    def set_archive_mode(self, is_archive: bool) -> None:
        self._is_archive = is_archive
        self._update_body_visibility()

    def destroy(self) -> None:
        self._destroyed = True
        # Phase D: tear down edit card first если открыта.
        if self._edit_card is not None:
            try:
                self._edit_card.destroy()
            except Exception:
                pass
            self._edit_card = None
        self._editing_task_id = None
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

    # ---- Forest Phase D: Inline edit-mode ----

    def enter_edit_mode(self, task_id: str) -> None:
        """Развернуть TaskEditCard на месте TaskWidget указанной задачи.

        Если другая задача уже редактируется — сначала автосохраняем её,
        потом открываем новую (flow-friendly UX).
        """
        if self._destroyed or self._is_archive:
            return
        # Auto-save предыдущую карточку если открыта другая задача.
        if self._editing_task_id is not None and self._editing_task_id != task_id:
            self.exit_edit_mode(save=True)
        # Если уже редактируем эту же задачу — фокус и выход.
        if self._editing_task_id == task_id and self._edit_card is not None:
            self._edit_card.focus()
            return

        task = next((t for t in self._tasks if t.id == task_id), None)
        if task is None:
            return

        widget = self._task_widgets.get(task_id)
        before_ref = None
        if widget is not None:
            try:
                before_ref = widget.frame
                widget.frame.pack_forget()
            except tk.TclError:
                before_ref = None

        # week_monday = Monday текущей секции (независимо от ее day_date).
        week_monday = self._day_date - timedelta(days=self._day_date.weekday())

        self._edit_card = TaskEditCard(
            self._body_frame, task, week_monday, self._theme,
            on_save=lambda fields, tid=task_id: self._handle_edit_save(tid, fields),
            on_cancel=lambda: self.exit_edit_mode(save=False),
            on_delete=lambda tid=task_id: self._handle_edit_delete(tid),
        )
        pack_kwargs = {"fill": "x", "pady": (0, 3)}
        if before_ref is not None:
            try:
                self._edit_card.pack(before=before_ref, **pack_kwargs)
            except tk.TclError:
                self._edit_card.pack(**pack_kwargs)
        else:
            self._edit_card.pack(**pack_kwargs)

        self._editing_task_id = task_id
        self._update_body_visibility()
        try:
            self._edit_card.focus()
        except tk.TclError:
            pass

    def exit_edit_mode(self, save: bool) -> None:
        """Закрыть edit-card. Если save=True — передать текущие поля через
        on_task_update callback перед teardown."""
        if self._edit_card is None:
            return
        if save and self._on_task_update and self._editing_task_id:
            try:
                fields = self._edit_card.collect_fields()
            except Exception as exc:
                logger.error("collect_fields failed: %s", exc)
                fields = None
            if fields is not None:
                try:
                    self._on_task_update(self._editing_task_id, fields)
                except Exception as exc:
                    logger.error("on_task_update failed: %s", exc)
        self._teardown_edit_mode()

    def _handle_edit_save(self, task_id: str, fields: dict) -> None:
        """Callback для кнопки 'Сохранить' / Ctrl+Enter внутри карточки."""
        if self._on_task_update:
            try:
                self._on_task_update(task_id, fields)
            except Exception as exc:
                logger.error("on_task_update failed: %s", exc)
        self._teardown_edit_mode()

    def _handle_edit_delete(self, task_id: str) -> None:
        """Callback для кнопки '🗑 Удалить' внутри карточки.

        Сначала teardown edit-mode, потом вызов существующего on_task_delete —
        порядок важен: undo-toast ждёт что UI не держит ссылок на задачу.
        """
        self._teardown_edit_mode()
        try:
            self._on_task_delete(task_id)
        except Exception as exc:
            logger.error("on_task_delete failed: %s", exc)

    def _teardown_edit_mode(self) -> None:
        task_id = self._editing_task_id
        if self._edit_card is not None:
            try:
                self._edit_card.destroy()
            except Exception:
                pass
            self._edit_card = None
        self._editing_task_id = None
        # Вернуть TaskWidget на место (если задача всё ещё в списке).
        if task_id:
            widget = self._task_widgets.get(task_id)
            if widget is not None:
                try:
                    widget.frame.pack(fill="x", pady=(0, 3))
                except tk.TclError:
                    pass
        self._update_body_visibility()

    # ---- Build ----

    def _day_bg_color(self) -> str:
        # Forest Phase B: today → bg_tertiary (forest-tint), regular days → transparent (сливаются с bg_primary окна)
        return self._theme.get("bg_tertiary") if self._is_today else "transparent"

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

        # Forest Phase B: subtle 1px divider снизу каждой секции (bg_tertiary).
        # На bg_primary (regular days) даёт tint-линию ~4% контраста — structure без карточек.
        self._divider = ctk.CTkFrame(
            self.frame, height=1,
            fg_color=self._theme.get("bg_tertiary"),
            corner_radius=0,
        )
        self._divider.pack(side="bottom", fill="x", padx=0, pady=0)

    def _update_body_visibility(self) -> None:
        """Пустой день + no inline-add + no edit-card → body скрыт."""
        if self._destroyed or self._body_frame is None:
            return
        should_show = (
            len(self._tasks) > 0
            or self._inline_entry is not None
            or self._edit_card is not None
        )
        # Forest Phase B: today-секция получает более щедрый padding 14×12 (spec 4.4).
        if self._is_today:
            body_padx, body_pady = 14, (2, 12)
        else:
            body_padx, body_pady = 10, (2, 6)
        try:
            if should_show:
                self._body_frame.pack(fill="x", padx=body_padx, pady=body_pady)
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
        # Forest Phase B: frame bg обновляется из свежей палитры
        # (today → bg_tertiary, regular → transparent).
        new_bg = palette.get("bg_tertiary") if self._is_today else "transparent"
        try:
            self.frame.configure(fg_color=new_bg)
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
        # Forest Phase B: divider цвета bg_tertiary обновляется при смене темы.
        if self._divider is not None and self._divider.winfo_exists():
            try:
                self._divider.configure(fg_color=palette.get("bg_tertiary"))
            except tk.TclError:
                pass
