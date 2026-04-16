"""EditDialog — модальный диалог редактирования. Phase 4 Plan 04-07.

Покрывает TASK-03. PITFALL 1: grab_set после deiconify + grab_release на всех exit.
PITFALL 2: CTkTextbox.get('1.0','end-1c').
"""
from __future__ import annotations

import logging
import re
import tkinter as tk
from datetime import date, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

_RE_HHMM = re.compile(r'^(\d{1,2}):(\d{2})$')

DAY_NAMES_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES_RU = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
                  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']


class EditDialog:
    DIALOG_WIDTH = 380
    DIALOG_HEIGHT = 360

    def __init__(
        self,
        parent_window: ctk.CTkBaseClass,
        task: Task,
        theme_manager: ThemeManager,
        on_save: Callable[[Task], None],
        on_delete: Callable[[str], None],
    ) -> None:
        self._parent = parent_window
        self._task = task
        self._theme = theme_manager
        self._on_save = on_save
        self._on_delete = on_delete
        self._closed = False

        self._text_box: Optional[ctk.CTkTextbox] = None
        self._day_var: Optional[ctk.StringVar] = None
        self._day_dropdown: Optional[ctk.CTkOptionMenu] = None
        self._time_var: Optional[tk.StringVar] = None
        self._time_entry: Optional[ctk.CTkEntry] = None
        self._done_var: Optional[tk.BooleanVar] = None
        self._save_btn: Optional[ctk.CTkButton] = None

        self._dialog = ctk.CTkToplevel(parent_window)
        self._dialog.withdraw()
        self._dialog.title("Задача")
        self._dialog.resizable(False, False)

        try:
            px = parent_window.winfo_x() + parent_window.winfo_width() // 2 - self.DIALOG_WIDTH // 2
            py = parent_window.winfo_y() + parent_window.winfo_height() // 2 - self.DIALOG_HEIGHT // 2
        except tk.TclError:
            px, py = 200, 200
        self._dialog.geometry(f"{self.DIALOG_WIDTH}x{self.DIALOG_HEIGHT}+{px}+{py}")

        self._build_ui()

        # PITFALL 1: deiconify ДО grab_set
        self._dialog.deiconify()
        try:
            self._dialog.grab_set()
        except tk.TclError as exc:
            logger.debug("grab_set failed: %s", exc)

        try:
            self._dialog.focus_set()
            if self._text_box:
                self._text_box.focus_set()
        except tk.TclError:
            pass

        self._dialog.bind("<Escape>", lambda e: self._cancel())
        self._dialog.bind("<Control-Return>", lambda e: self._save())
        self._dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._update_save_state()

    def _build_ui(self) -> None:
        frame = ctk.CTkFrame(self._dialog)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frame, text="Текст", anchor="w").pack(fill="x")
        self._text_box = ctk.CTkTextbox(frame, height=80, wrap="word")
        self._text_box.pack(fill="x", pady=(0, 8))
        self._text_box.insert("1.0", self._task.text)
        self._text_box.bind("<KeyRelease>", lambda e: self._update_save_state())

        ctk.CTkLabel(frame, text="День", anchor="w").pack(fill="x")
        day_options = self._build_day_options()
        self._day_var = ctk.StringVar(value=self._get_current_day_label())
        self._day_dropdown = ctk.CTkOptionMenu(
            frame, values=day_options, variable=self._day_var,
        )
        self._day_dropdown.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(frame, text="Время (HH:MM)", anchor="w").pack(fill="x")
        time_row = ctk.CTkFrame(frame, fg_color="transparent")
        time_row.pack(fill="x", pady=(0, 8))

        time_val = ""
        if self._task.time_deadline:
            time_val = self._task.time_deadline[:5] if len(
                self._task.time_deadline) >= 5 else self._task.time_deadline

        self._time_var = tk.StringVar(value=time_val)
        self._time_entry = ctk.CTkEntry(
            time_row, textvariable=self._time_var, width=100, font=FONTS["mono"],
        )
        self._time_entry.pack(side="left")

        ctk.CTkButton(
            time_row, text="✕", width=32,
            command=lambda: self._time_var.set(""),
        ).pack(side="left", padx=4)

        self._time_var.trace_add("write", self._on_time_changed)

        self._done_var = tk.BooleanVar(value=self._task.done)
        ctk.CTkCheckBox(
            frame, text="Выполнено", variable=self._done_var,
            command=self._update_save_state,
        ).pack(anchor="w", pady=(4, 12))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame, text="🗑 Удалить",
            fg_color=self._theme.get("accent_overdue"),
            hover_color="#cc3333",
            width=110,
            command=self._delete,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Отмена", width=80, command=self._cancel,
        ).pack(side="right", padx=(4, 0))

        self._save_btn = ctk.CTkButton(
            btn_frame, text="Сохранить", width=110, command=self._save,
        )
        self._save_btn.pack(side="right")

    def _build_day_options(self) -> list[str]:
        today = date.today()
        opts = ["Сегодня", "Завтра", "Послезавтра"]
        monday = today - timedelta(days=today.weekday())
        for i in range(7):
            d = monday + timedelta(days=i)
            if d in (today, today + timedelta(1), today + timedelta(2)):
                continue
            label = f"{DAY_NAMES_RU[i]} {d.day} {MONTH_NAMES_RU[d.month]}"
            opts.append(label)
        return opts

    def _get_current_day_label(self) -> str:
        today = date.today()
        try:
            d = date.fromisoformat(self._task.day)
        except (ValueError, TypeError):
            return "Сегодня"
        if d == today:
            return "Сегодня"
        if d == today + timedelta(1):
            return "Завтра"
        if d == today + timedelta(2):
            return "Послезавтра"
        return f"{DAY_NAMES_RU[d.weekday()]} {d.day} {MONTH_NAMES_RU[d.month]}"

    def _day_label_to_iso(self, label: str) -> str:
        today = date.today()
        if label == "Сегодня":
            return today.isoformat()
        if label == "Завтра":
            return (today + timedelta(1)).isoformat()
        if label == "Послезавтра":
            return (today + timedelta(2)).isoformat()
        parts = label.split()
        if len(parts) >= 2:
            try:
                day_num = int(parts[1])
                monday = today - timedelta(days=today.weekday())
                for i in range(7):
                    d = monday + timedelta(days=i)
                    if d.day == day_num:
                        return d.isoformat()
            except (ValueError, IndexError):
                pass
        return self._task.day

    def _on_time_changed(self, *_) -> None:
        val = self._time_var.get() if self._time_var else ""
        accent_overdue = self._theme.get("accent_overdue")
        accent_done = self._theme.get("accent_done")
        bg_sec = self._theme.get("bg_secondary")

        if not val:
            try:
                self._time_entry.configure(border_color=bg_sec)
            except (tk.TclError, AttributeError):
                pass
        elif self._is_valid_hhmm(val):
            try:
                self._time_entry.configure(border_color=accent_done)
            except (tk.TclError, AttributeError):
                pass
        else:
            try:
                self._time_entry.configure(border_color=accent_overdue)
            except (tk.TclError, AttributeError):
                pass
        self._update_save_state()

    @staticmethod
    def _is_valid_hhmm(val: str) -> bool:
        m = _RE_HHMM.match(val)
        if not m:
            return False
        try:
            h = int(m.group(1))
            mi = int(m.group(2))
            return 0 <= h <= 23 and 0 <= mi <= 59
        except ValueError:
            return False

    def _update_save_state(self) -> None:
        """D-17: disabled если empty text OR invalid HH:MM."""
        if self._save_btn is None or not self._save_btn.winfo_exists():
            return
        text_ok = False
        if self._text_box and self._text_box.winfo_exists():
            # PITFALL 2: end-1c убирает trailing newline
            text = self._text_box.get("1.0", "end-1c").strip()
            text_ok = bool(text)

        time_val = self._time_var.get() if self._time_var else ""
        time_ok = (not time_val) or self._is_valid_hhmm(time_val)

        try:
            self._save_btn.configure(state="normal" if (text_ok and time_ok) else "disabled")
        except tk.TclError:
            pass

    def _save(self) -> None:
        if self._closed:
            return
        text = ""
        if self._text_box:
            text = self._text_box.get("1.0", "end-1c").strip()
        if not text:
            return

        time_val = self._time_var.get().strip() if self._time_var else ""
        if time_val and not self._is_valid_hhmm(time_val):
            return

        day_iso = self._day_label_to_iso(self._day_var.get()) if self._day_var else self._task.day
        done = self._done_var.get() if self._done_var else self._task.done

        updated = Task(
            id=self._task.id,
            user_id=self._task.user_id,
            text=text,
            day=day_iso,
            time_deadline=time_val or None,
            done=done,
            position=self._task.position,
            created_at=self._task.created_at,
            updated_at=self._task.updated_at,
            deleted_at=self._task.deleted_at,
        )

        self._close_dialog()
        try:
            self._on_save(updated)
        except Exception as exc:
            logger.error("on_save callback failed: %s", exc)

    def _cancel(self) -> None:
        if self._closed:
            return
        self._close_dialog()

    def _delete(self) -> None:
        if self._closed:
            return
        task_id = self._task.id
        self._close_dialog()
        try:
            self._on_delete(task_id)
        except Exception as exc:
            logger.error("on_delete callback failed: %s", exc)

    def _close_dialog(self) -> None:
        """PITFALL 1: grab_release ОБЯЗАТЕЛЬНО перед destroy на всех exit paths."""
        if self._closed:
            return
        self._closed = True
        try:
            self._dialog.grab_release()
        except tk.TclError as exc:
            logger.debug("grab_release: %s", exc)
        try:
            self._dialog.destroy()
        except tk.TclError as exc:
            logger.debug("dialog destroy: %s", exc)

    def destroy(self) -> None:
        self._cancel()
