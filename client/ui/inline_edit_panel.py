"""InlineEditPanel — inline-редактирование задачи. UX v2.

Заменяет EditDialog popup: панель появляется slide-down внутри главного окна,
поверх scroll area через place(). Быстрее и органичнее чем modal Toplevel.
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.core.models import Task
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

DAY_NAMES_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES_RU = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн',
                  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
HH_OPTIONS = ["—"] + [f"{h:02d}" for h in range(24)]
MM_OPTIONS = ["—"] + [f"{m:02d}" for m in range(0, 60, 5)]


class InlineEditPanel:
    """Slide-down панель редактирования задачи, живёт внутри main_window._root_frame."""

    PANEL_HEIGHT = 280
    ANIM_DURATION_MS = 150
    ANIM_STEPS = 8

    def __init__(
        self,
        parent_frame: ctk.CTkFrame,
        root_window: ctk.CTkToplevel,
        task: Task,
        theme_manager: ThemeManager,
        on_save: Callable[[Task], None],
        on_delete: Callable[[str], None],
        on_close: Callable[[], None],
    ) -> None:
        self._parent = parent_frame
        self._root_window = root_window
        self._task = task
        self._theme = theme_manager
        self._on_save = on_save
        self._on_delete = on_delete
        self._on_close = on_close
        self._closed = False
        self._animating = False

        self._text_box: Optional[ctk.CTkTextbox] = None
        self._day_var: Optional[ctk.StringVar] = None
        self._hh_var: Optional[ctk.StringVar] = None
        self._mm_var: Optional[ctk.StringVar] = None
        self._time_enabled_var: Optional[tk.BooleanVar] = None
        self._recurrence_var: Optional[tk.BooleanVar] = None
        self._save_btn: Optional[ctk.CTkButton] = None
        self._hh_menu: Optional[ctk.CTkOptionMenu] = None
        self._mm_menu: Optional[ctk.CTkOptionMenu] = None

        bg = self._theme.get("bg_secondary")
        border = self._blend_hex(
            self._theme.get("bg_secondary"),
            self._theme.get("text_tertiary"),
            0.35,
        )

        self._frame = ctk.CTkFrame(
            parent_frame,
            fg_color=bg,
            corner_radius=12,
            border_width=1,
            border_color=border,
            height=self.PANEL_HEIGHT,
        )
        self._build_ui()

        # Start hidden above the viewport: y = -PANEL_HEIGHT
        self._frame.place(
            relx=0.5, rely=0, x=0, y=-self.PANEL_HEIGHT,
            anchor="n", relwidth=0.94,
        )
        self._frame.lift()

        # Bindings
        self._frame.bind("<Escape>", lambda e: self._cancel())
        self._root_window.bind("<Escape>", lambda e: self._cancel(), add="+")
        self._root_window.bind("<Control-Return>", lambda e: self._save(), add="+")

        # Начать анимацию slide-down
        self._slide(target_y=20, step=0)

        # Focus textbox
        try:
            if self._text_box:
                self._text_box.focus_set()
        except tk.TclError:
            pass
        self._update_save_state()

    def _build_ui(self) -> None:
        bg = self._theme.get("bg_secondary")
        text_primary = self._theme.get("text_primary")
        text_sec = self._theme.get("text_secondary")

        content = ctk.CTkFrame(self._frame, fg_color=bg, corner_radius=0)
        content.pack(fill="both", expand=True, padx=14, pady=12)

        # Задача (textbox)
        ctk.CTkLabel(
            content, text="Задача", font=FONTS["caption"],
            text_color=text_sec, anchor="w",
        ).pack(fill="x")
        self._text_box = ctk.CTkTextbox(
            content, height=54, wrap="word", corner_radius=10, font=FONTS["body"],
        )
        self._text_box.pack(fill="x", pady=(2, 10))
        self._text_box.insert("1.0", self._task.text)
        self._text_box.bind("<KeyRelease>", lambda e: self._update_save_state())

        # Day + Time row
        grid = ctk.CTkFrame(content, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 10))

        day_col = ctk.CTkFrame(grid, fg_color="transparent")
        day_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            day_col, text="День", font=FONTS["caption"],
            text_color=text_sec, anchor="w",
        ).pack(fill="x")
        self._day_var = ctk.StringVar(value=self._get_current_day_label())
        ctk.CTkOptionMenu(
            day_col, values=self._build_day_options(), variable=self._day_var,
            corner_radius=10, font=FONTS["body"], height=30,
            fg_color=self._theme.get("accent_brand"),
            button_color=self._theme.get("accent_brand"),
            button_hover_color=self._theme.get("accent_brand_light"),
            dropdown_fg_color=self._theme.get("bg_secondary"),
            dropdown_text_color=self._theme.get("text_primary"),
            text_color="#FFFFFF",
        ).pack(fill="x", pady=(2, 0))

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
        # Quick 260422-v1a: placeholder '—' вместо '09:00' когда время не задано
        self._hh_var = ctk.StringVar(value=cur_hh if has_time else "—")
        self._mm_var = ctk.StringVar(value=cur_mm if has_time else "—")

        self._hh_menu = ctk.CTkOptionMenu(
            time_row, values=HH_OPTIONS, variable=self._hh_var,
            width=60, corner_radius=10, font=FONTS["mono"], height=30,
            command=lambda *_: self._on_time_enabled_implicit(True),
            fg_color=self._theme.get("accent_brand"),
            button_color=self._theme.get("accent_brand"),
            button_hover_color=self._theme.get("accent_brand_light"),
            dropdown_fg_color=self._theme.get("bg_secondary"),
            dropdown_text_color=self._theme.get("text_primary"),
            text_color="#FFFFFF",
        )
        self._hh_menu.pack(side="left")
        ctk.CTkLabel(time_row, text=":", font=FONTS["mono"],
                     text_color=text_primary).pack(side="left", padx=3)
        self._mm_menu = ctk.CTkOptionMenu(
            time_row, values=MM_OPTIONS, variable=self._mm_var,
            width=60, corner_radius=10, font=FONTS["mono"], height=30,
            command=lambda *_: self._on_time_enabled_implicit(True),
            fg_color=self._theme.get("accent_brand"),
            button_color=self._theme.get("accent_brand"),
            button_hover_color=self._theme.get("accent_brand_light"),
            dropdown_fg_color=self._theme.get("bg_secondary"),
            dropdown_text_color=self._theme.get("text_primary"),
            text_color="#FFFFFF",
        )
        self._mm_menu.pack(side="left")
        ctk.CTkButton(
            time_row, text="✕", width=26, height=30, corner_radius=10,
            fg_color="transparent", border_width=1, text_color=text_sec,
            hover_color=self._theme.get("bg_tertiary"),
            command=self._clear_time,
        ).pack(side="left", padx=(6, 0))
        # Quick 260422-v1a: '—' placeholder сам визуально показывает отсутствие
        # времени — дополнительный dim через _set_time_menus_dim не нужен.

        # Recurrence toggle — еженедельное повторение (Quick 260422-v1a).
        # Заменяет бывший Done checkbox — done управляется кликом по чекбоксу
        # в TaskWidget, дублирование в edit-панели убрано.
        self._recurrence_var = tk.BooleanVar(
            value=(getattr(self._task, "recurrence", None) == "weekly")
        )
        ctk.CTkCheckBox(
            content, text="Повторять каждую неделю", variable=self._recurrence_var,
            command=self._update_save_state, font=FONTS["body"],
            corner_radius=4, checkbox_width=20, checkbox_height=20,
        ).pack(anchor="w", pady=(0, 10))

        # Buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")
        ctk.CTkButton(
            btn_frame, text="Удалить",
            fg_color="transparent", border_width=1,
            border_color=self._theme.get("accent_overdue"),
            text_color=self._theme.get("accent_overdue"),
            hover_color=self._theme.get("bg_tertiary"),
            width=90, height=30, corner_radius=10,
            font=FONTS["body"], command=self._delete,
        ).pack(side="left")
        ctk.CTkButton(
            btn_frame, text="Отмена",
            fg_color="transparent", border_width=1,
            text_color=text_primary,
            hover_color=self._theme.get("bg_tertiary"),
            width=80, height=30, corner_radius=10,
            font=FONTS["body"], command=self._cancel,
        ).pack(side="right", padx=(6, 0))
        self._save_btn = ctk.CTkButton(
            btn_frame, text="Сохранить", width=110, height=30, corner_radius=10,
            font=FONTS["body_m"], command=self._save,
            fg_color=self._theme.get("accent_brand"),
            hover_color=self._theme.get("accent_brand_light"),
            text_color="#FFFFFF",
        )
        self._save_btn.pack(side="right")

    # ---- Animation ----

    def _slide(self, target_y: int, step: int,
               on_complete: Optional[Callable[[], None]] = None) -> None:
        """Slide панели по y от current к target с ease-out quadratic."""
        self._animating = True
        current_step = step + 1
        progress = current_step / self.ANIM_STEPS
        eased = 1.0 - (1.0 - progress) ** 2

        # Интерполяция от start к target
        if not hasattr(self, "_anim_start_y"):
            # первый кадр — захватить start
            try:
                start_raw = self._frame.place_info().get("y", -self.PANEL_HEIGHT)
                self._anim_start_y = int(start_raw)
            except (tk.TclError, ValueError, TypeError):
                self._anim_start_y = -self.PANEL_HEIGHT
            self._anim_target_y = target_y

        start = self._anim_start_y
        end = self._anim_target_y
        y = int(start + (end - start) * eased)
        try:
            self._frame.place_configure(y=y)
        except tk.TclError:
            self._animating = False
            return

        if current_step >= self.ANIM_STEPS:
            try:
                self._frame.place_configure(y=end)
            except tk.TclError:
                pass
            self._animating = False
            # Очистить анимационное состояние для возможного повторного использования
            if hasattr(self, "_anim_start_y"):
                del self._anim_start_y
            if hasattr(self, "_anim_target_y"):
                del self._anim_target_y
            if on_complete:
                try:
                    on_complete()
                except Exception as exc:
                    logger.debug("slide on_complete: %s", exc)
            return

        delay_ms = max(1, int(self.ANIM_DURATION_MS / self.ANIM_STEPS))
        try:
            self._frame.after(delay_ms, self._slide, target_y, current_step, on_complete)
        except tk.TclError:
            self._animating = False

    # ---- Time helpers (скопировано из EditDialog) ----

    def _current_time_parts(self) -> tuple[str, str, bool]:
        from datetime import datetime
        td = self._task.time_deadline
        if not td:
            return ("09", "00", False)
        try:
            if "T" in td:
                dt = datetime.fromisoformat(td.replace("Z", "+00:00"))
                return (dt.strftime("%H"), dt.strftime("%M"), True)
            parts = td.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return (f"{int(parts[0]):02d}", f"{int(parts[1]):02d}", True)
        except (ValueError, TypeError):
            pass
        return ("09", "00", False)

    def _clear_time(self) -> None:
        """Сброс времени через ✕: выключить enabled + оба dropdown на '—'."""
        if self._time_enabled_var is not None:
            self._time_enabled_var.set(False)
        if self._hh_var is not None:
            self._hh_var.set("—")
        if self._mm_var is not None:
            self._mm_var.set("—")

    def _on_time_enabled_implicit(self, enabled: bool) -> None:
        """Callback OptionMenu: выбор '—' в любом dropdown → выключить time_enabled."""
        if self._hh_var and self._mm_var:
            hh = self._hh_var.get()
            mm = self._mm_var.get()
            if hh == "—" or mm == "—":
                if self._time_enabled_var is not None:
                    self._time_enabled_var.set(False)
                return
        if self._time_enabled_var is not None:
            self._time_enabled_var.set(enabled)

    def _set_time_menus_dim(self, dim: bool) -> None:
        """Quick 260422-v1a: '—' placeholder сам показывает отсутствие времени,
        дополнительный dim text_color больше не нужен. Оставлен как no-op, чтобы
        не ломать возможные внешние вызовы.
        """
        return

    # ---- Day helpers (скопировано из EditDialog) ----

    def _build_day_options(self) -> list[str]:
        today = date.today()
        opts = ["Сегодня", "Завтра", "Послезавтра"]
        monday = today - timedelta(days=today.weekday())
        for i in range(7):
            d = monday + timedelta(days=i)
            if d in (today, today + timedelta(1), today + timedelta(2)):
                continue
            opts.append(f"{DAY_NAMES_RU[i]} {d.day} {MONTH_NAMES_RU[d.month]}")
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

    # ---- Validation / save ----

    def _update_save_state(self) -> None:
        if self._save_btn is None or not self._save_btn.winfo_exists():
            return
        ok = False
        if self._text_box and self._text_box.winfo_exists():
            ok = bool(self._text_box.get("1.0", "end-1c").strip())
        try:
            self._save_btn.configure(state="normal" if ok else "disabled")
        except tk.TclError:
            pass

    def _save(self) -> None:
        if self._closed:
            return
        text = self._text_box.get("1.0", "end-1c").strip() if self._text_box else ""
        if not text:
            return
        day_iso = self._day_label_to_iso(self._day_var.get()) if self._day_var else self._task.day
        # Quick 260422-v1a: double-guard — time_val=None если ЛЮБОЙ из dropdown
        # на '—' или time_enabled выключен.
        time_val: Optional[str] = None
        if self._time_enabled_var and self._time_enabled_var.get():
            hh = self._hh_var.get() if self._hh_var else "—"
            mm = self._mm_var.get() if self._mm_var else "—"
            if hh != "—" and mm != "—":
                time_val = f"{hh}:{mm}"

        # Quick 260422-v1a: done сохраняем как был (toggle теперь только через
        # чекбокс в TaskWidget); recurrence читаем из нового чекбокса.
        recurrence_val = "weekly" if (self._recurrence_var and self._recurrence_var.get()) else None

        updated = Task(
            id=self._task.id, user_id=self._task.user_id, text=text,
            day=day_iso, time_deadline=time_val,
            done=self._task.done,
            position=self._task.position,
            created_at=self._task.created_at, updated_at=self._task.updated_at,
            deleted_at=self._task.deleted_at,
            recurrence=recurrence_val,
        )
        self._close_with_callback(lambda: self._on_save(updated))

    def _cancel(self) -> None:
        if self._closed:
            return
        self._close_with_callback(None)

    def _delete(self) -> None:
        if self._closed:
            return
        task_id = self._task.id
        self._close_with_callback(lambda: self._on_delete(task_id))

    def _close_with_callback(self, cb: Optional[Callable[[], None]]) -> None:
        if self._closed:
            return
        self._closed = True

        def finalize() -> None:
            try:
                self._frame.destroy()
            except tk.TclError:
                pass
            try:
                self._on_close()
            except Exception as exc:
                logger.debug("on_close: %s", exc)
            if cb is not None:
                try:
                    cb()
                except Exception as exc:
                    logger.error("close callback failed: %s", exc)

        # Slide-up анимация
        if hasattr(self, "_anim_start_y"):
            del self._anim_start_y
        if hasattr(self, "_anim_target_y"):
            del self._anim_target_y
        self._slide(target_y=-self.PANEL_HEIGHT, step=0, on_complete=finalize)

    def destroy(self) -> None:
        """Немедленное уничтожение без анимации (для replace случая)."""
        self._closed = True
        try:
            self._frame.destroy()
        except tk.TclError:
            pass

    @staticmethod
    def _blend_hex(a: str, b: str, t: float) -> str:
        """Линейный блендинг двух hex-цветов. t=0 → a, t=1 → b."""
        def _parse(h: str) -> tuple[int, int, int]:
            h = h.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        ar, ag, ab = _parse(a)
        br, bg, bb = _parse(b)
        r = int(ar + (br - ar) * t)
        g = int(ag + (bg - ag) * t)
        bl = int(ab + (bb - ab) * t)
        return f"#{r:02X}{g:02X}{bl:02X}"
