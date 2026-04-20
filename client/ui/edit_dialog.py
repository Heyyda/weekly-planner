"""EditDialog — модальный компактный диалог (fallback для задач вне текущей недели).

Changes vs v0.3.x:
- Горизонтальные ряды с label слева + input справа (компактно)
- Time picker = 2 CTkOptionMenu (HH 00-23, MM в 5-минутных шагах)
- Уменьшённые padding-ы, крупные шрифты
- Rounded corners везде r=10
- modal-like через transient + topmost-flash + focus_force

Forest Phase F (260421-1ya) — dark-parity audit:
- Save button получил явный forest-fill (был дефолтный CTk синий — Phase A3 bug тут
  не закрылся, т.к. файл использовался только как fallback).
- Delete button — clay ghost (accent_overdue border+text). Отмена — neutral ghost.
- CTkTextbox: явные fg_color/text_color/border_color через палитру.
- CTkOptionMenu (day/hh/mm): forest-фон, бейзовые цвета через палитру.
- CTkCheckBox: аналогично task_edit_card — accent_brand fill + text_primary text.
- Все цвета резолвятся в _build_ui из `self._theme.get(...)` — при пересоздании
  диалога (каждый EditDialog — одноразовый) подхватывается актуальная тема.
"""
from __future__ import annotations

import logging
import re
import tkinter as tk
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

_RE_HHMM = re.compile(r'^(\d{1,2}):(\d{2})$')

DAY_NAMES_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES_RU = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
                  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

HH_OPTIONS = [f"{h:02d}" for h in range(24)]
MM_OPTIONS = [f"{m:02d}" for m in range(0, 60, 5)]


class EditDialog:
    DIALOG_WIDTH = 420
    DIALOG_HEIGHT = 320

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
        self._hh_var: Optional[ctk.StringVar] = None
        self._mm_var: Optional[ctk.StringVar] = None
        self._time_enabled_var: Optional[tk.BooleanVar] = None
        self._done_var: Optional[tk.BooleanVar] = None
        self._save_btn: Optional[ctk.CTkButton] = None

        self._dialog = ctk.CTkToplevel(parent_window)
        self._dialog.withdraw()
        self._dialog.title("Задача")
        self._dialog.resizable(False, False)
        self._dialog.configure(fg_color=self._theme.get("bg_primary"))

        try:
            self._dialog.transient(parent_window)
        except tk.TclError:
            pass
        try:
            self._dialog.attributes("-toolwindow", True)
        except tk.TclError:
            pass

        try:
            px = parent_window.winfo_x() + parent_window.winfo_width() // 2 - self.DIALOG_WIDTH // 2
            py = parent_window.winfo_y() + parent_window.winfo_height() // 2 - self.DIALOG_HEIGHT // 2
        except tk.TclError:
            px, py = 200, 200
        self._dialog.geometry(f"{self.DIALOG_WIDTH}x{self.DIALOG_HEIGHT}+{px}+{py}")

        self._build_ui()

        self._dialog.deiconify()
        try:
            self._dialog.lift()
            self._dialog.attributes("-topmost", True)
            self._dialog.after(200, lambda: self._dialog.attributes("-topmost", False))
        except tk.TclError:
            pass
        try:
            self._dialog.grab_set()
        except tk.TclError:
            pass
        try:
            self._dialog.focus_force()
            if self._text_box:
                self._text_box.focus_set()
        except tk.TclError:
            pass

        self._dialog.bind("<Escape>", lambda e: self._cancel())
        self._dialog.bind("<Control-Return>", lambda e: self._save())
        self._dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._update_save_state()

    def _build_ui(self) -> None:
        # ---- Palette keys (Forest Phase F) ----
        bg = self._theme.get("bg_primary")
        bg_sec = self._theme.get("bg_secondary")
        bg_tert = self._theme.get("bg_tertiary")
        text_primary = self._theme.get("text_primary")
        text_sec = self._theme.get("text_secondary")
        text_tert = self._theme.get("text_tertiary")
        accent_brand = self._theme.get("accent_brand")
        accent_brand_light = self._theme.get("accent_brand_light")
        accent_overdue = self._theme.get("accent_overdue")

        content = ctk.CTkFrame(self._dialog, fg_color=bg, corner_radius=0)
        content.pack(fill="both", expand=True, padx=16, pady=14)

        # --- Text ---
        ctk.CTkLabel(
            content, text="Задача", font=FONTS["caption"],
            text_color=text_sec, anchor="w",
        ).pack(fill="x")
        self._text_box = ctk.CTkTextbox(
            content, height=60, wrap="word", corner_radius=10,
            font=FONTS["body"],
            fg_color=bg_sec,
            text_color=text_primary,
            border_width=1,
            border_color=bg_tert,
        )
        self._text_box.pack(fill="x", pady=(2, 10))
        self._text_box.insert("1.0", self._task.text)
        self._text_box.bind("<KeyRelease>", lambda e: self._update_save_state())

        # --- Day + Time row ---
        grid = ctk.CTkFrame(content, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 10))

        day_col = ctk.CTkFrame(grid, fg_color="transparent")
        day_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            day_col, text="День", font=FONTS["caption"],
            text_color=text_sec, anchor="w",
        ).pack(fill="x")
        day_options = self._build_day_options()
        self._day_var = ctk.StringVar(value=self._get_current_day_label())
        self._day_dropdown = ctk.CTkOptionMenu(
            day_col, values=day_options, variable=self._day_var,
            corner_radius=10, font=FONTS["body"], height=32,
            fg_color=bg_sec,
            button_color=bg_tert,
            button_hover_color=accent_brand,
            text_color=text_primary,
            dropdown_fg_color=bg_sec,
            dropdown_text_color=text_primary,
            dropdown_hover_color=bg_tert,
            dropdown_font=FONTS["body"],
        )
        self._day_dropdown.pack(fill="x", pady=(2, 0))

        time_col = ctk.CTkFrame(grid, fg_color="transparent")
        time_col.pack(side="right", padx=(12, 0))

        ctk.CTkLabel(
            time_col, text="Время", font=FONTS["caption"],
            text_color=text_sec, anchor="w",
        ).pack(fill="x")

        time_row = ctk.CTkFrame(time_col, fg_color="transparent")
        time_row.pack(fill="x", pady=(2, 0))

        cur_hh, cur_mm, has_time = self._current_time_parts()
        self._time_enabled_var = tk.BooleanVar(value=has_time)
        self._hh_var = ctk.StringVar(value=cur_hh if has_time else "09")
        self._mm_var = ctk.StringVar(value=cur_mm if has_time else "00")

        self._hh_menu = ctk.CTkOptionMenu(
            time_row, values=HH_OPTIONS, variable=self._hh_var,
            width=62, corner_radius=10, font=FONTS["mono"], height=32,
            fg_color=bg_sec,
            button_color=bg_tert,
            button_hover_color=accent_brand,
            text_color=text_primary,
            dropdown_fg_color=bg_sec,
            dropdown_text_color=text_primary,
            dropdown_hover_color=bg_tert,
            dropdown_font=FONTS["mono"],
            command=lambda *_: self._on_time_enabled_implicit(True),
        )
        self._hh_menu.pack(side="left")
        ctk.CTkLabel(
            time_row, text=":", font=FONTS["mono"], text_color=text_primary,
        ).pack(side="left", padx=3)
        self._mm_menu = ctk.CTkOptionMenu(
            time_row, values=MM_OPTIONS, variable=self._mm_var,
            width=62, corner_radius=10, font=FONTS["mono"], height=32,
            fg_color=bg_sec,
            button_color=bg_tert,
            button_hover_color=accent_brand,
            text_color=text_primary,
            dropdown_fg_color=bg_sec,
            dropdown_text_color=text_primary,
            dropdown_hover_color=bg_tert,
            dropdown_font=FONTS["mono"],
            command=lambda *_: self._on_time_enabled_implicit(True),
        )
        self._mm_menu.pack(side="left")

        self._time_clear_btn = ctk.CTkButton(
            time_row, text="✕", width=26, height=32, corner_radius=10,
            fg_color="transparent", border_width=1,
            border_color=bg_tert,
            text_color=text_sec,
            hover_color=bg_sec,
            font=FONTS["body"],
            command=self._clear_time,
        )
        self._time_clear_btn.pack(side="left", padx=(6, 0))

        if not has_time:
            self._set_time_menus_dim(True)

        # --- Done checkbox ---
        self._done_var = tk.BooleanVar(value=self._task.done)
        ctk.CTkCheckBox(
            content, text="Выполнено", variable=self._done_var,
            command=self._update_save_state, font=FONTS["body"],
            corner_radius=4, checkbox_width=20, checkbox_height=20,
            text_color=text_primary,
            fg_color=accent_brand,
            hover_color=accent_brand_light,
            border_color=text_tert,
        ).pack(anchor="w", pady=(0, 12))

        # --- Buttons row ---
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")

        # Удалить — clay ghost: transparent fill + accent_overdue border/text.
        ctk.CTkButton(
            btn_frame, text="Удалить",
            fg_color="transparent", border_width=1,
            border_color=accent_overdue,
            text_color=accent_overdue,
            hover_color=bg_sec,
            width=90, height=32, corner_radius=10,
            font=FONTS["body"], command=self._delete,
        ).pack(side="left")

        # Отмена — neutral ghost: transparent + text_secondary.
        ctk.CTkButton(
            btn_frame, text="Отмена",
            fg_color="transparent", border_width=1,
            border_color=bg_tert,
            text_color=text_sec,
            hover_color=bg_sec,
            width=80, height=32, corner_radius=10,
            font=FONTS["body"], command=self._cancel,
        ).pack(side="right", padx=(6, 0))

        # Сохранить — Forest primary fill. Phase F: убран дефолтный CTk синий
        # (fg_color/hover_color/text_color отсутствовали → CTk подбирал blue).
        self._save_btn = ctk.CTkButton(
            btn_frame, text="Сохранить",
            width=110, height=32, corner_radius=10,
            fg_color=accent_brand,
            hover_color=accent_brand_light,
            text_color=bg,  # cream на forest-fill — высокий контраст
            font=FONTS["body_m"], command=self._save,
        )
        self._save_btn.pack(side="right")

    # ---- Time helpers ----

    def _current_time_parts(self) -> tuple[str, str, bool]:
        td = self._task.time_deadline
        if not td:
            return ("09", "00", False)
        try:
            if "T" in td:
                dt = datetime.fromisoformat(td.replace("Z", "+00:00"))
                return (dt.strftime("%H"), dt.strftime("%M"), True)
            parts = td.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                hh = f"{int(parts[0]):02d}"
                mm = f"{int(parts[1]):02d}"
                return (hh, mm, True)
        except (ValueError, TypeError):
            pass
        return ("09", "00", False)

    def _clear_time(self) -> None:
        if self._time_enabled_var is not None:
            self._time_enabled_var.set(False)
        self._set_time_menus_dim(True)

    def _on_time_enabled_implicit(self, enabled: bool) -> None:
        if self._time_enabled_var is not None:
            self._time_enabled_var.set(enabled)
        self._set_time_menus_dim(not enabled)

    def _set_time_menus_dim(self, dim: bool) -> None:
        """Визуально показать что время отключено."""
        color = self._theme.get("text_tertiary") if dim else self._theme.get("text_primary")
        for menu in (self._hh_menu, self._mm_menu):
            try:
                menu.configure(text_color=color)
            except (tk.TclError, AttributeError):
                pass

    # ---- Day helpers ----

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

    # ---- Validation ----

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
        if self._save_btn is None or not self._save_btn.winfo_exists():
            return
        text_ok = False
        if self._text_box and self._text_box.winfo_exists():
            text = self._text_box.get("1.0", "end-1c").strip()
            text_ok = bool(text)
        try:
            self._save_btn.configure(state="normal" if text_ok else "disabled")
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

        day_iso = self._day_label_to_iso(self._day_var.get()) if self._day_var else self._task.day
        done = self._done_var.get() if self._done_var else self._task.done

        time_val: Optional[str] = None
        if self._time_enabled_var and self._time_enabled_var.get():
            hh = self._hh_var.get() if self._hh_var else "09"
            mm = self._mm_var.get() if self._mm_var else "00"
            time_val = f"{hh}:{mm}"

        updated = Task(
            id=self._task.id,
            user_id=self._task.user_id,
            text=text,
            day=day_iso,
            time_deadline=time_val,
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
            logger.error("on_save: %s", exc)

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
            logger.error("on_delete: %s", exc)

    def _close_dialog(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._dialog.grab_release()
        except tk.TclError:
            pass
        try:
            self._dialog.destroy()
        except tk.TclError:
            pass

    def destroy(self) -> None:
        self._cancel()
