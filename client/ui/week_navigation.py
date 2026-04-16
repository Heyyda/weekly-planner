"""WeekNavigation — контроллер навигации недели. Phase 4.

Покрывает WEEK-02 (prev/next arrows), WEEK-03 (today button), WEEK-06 (archive).
D-29 header, D-30 keyboard shortcuts, D-31/D-32 archive semantics.
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, timedelta
from typing import Callable, Optional

import customtkinter as ctk

from client.ui.parse_input import format_date_range_ru
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)


# ==== Public helpers ====

def get_week_monday(d: date) -> date:
    """Понедельник недели для данной даты."""
    return d - timedelta(days=d.weekday())


def get_current_week_monday() -> date:
    return get_week_monday(date.today())


def get_iso_week_number(d: date) -> int:
    return d.isocalendar()[1]


def is_archive_week(week_monday: date) -> bool:
    """D-31: past = archive; D-32: current/future — не archive."""
    return week_monday < get_current_week_monday()


def format_week_header(week_monday: date) -> str:
    """'Неделя 16 • 14-20 апр' (D-29)."""
    week_num = get_iso_week_number(week_monday)
    sunday = week_monday + timedelta(days=6)
    return f"Неделя {week_num} • {format_date_range_ru(week_monday, sunday)}"


def interpolate_palette(palette: dict, bg_hex: str, factor: float) -> dict:
    """Blend each hex color with bg_hex by factor (0.0..1.0) — для archive dim."""
    def parse_hex(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        if len(h) != 6:
            return (128, 128, 128)
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            return (128, 128, 128)

    def blend(c1: str, c2: str, t: float) -> str:
        r1, g1, b1 = parse_hex(c1)
        r2, g2, b2 = parse_hex(c2)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    result: dict = {}
    for key, color in palette.items():
        if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
            result[key] = color
        else:
            result[key] = blend(color, bg_hex, factor)
    return result


# ==== Widget class ====

class WeekNavigation:
    """Header navigation + keyboard shortcuts + archive detection."""

    ARROW_WIDTH = 32
    TODAY_BTN_WIDTH = 80

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        window: ctk.CTkToplevel,
        theme_manager: ThemeManager,
        on_week_changed: Callable[[date], None],
        on_archive_changed: Callable[[bool], None],
    ) -> None:
        self._parent = parent
        self._window = window
        self._theme = theme_manager
        self._on_week_changed = on_week_changed
        self._on_archive_changed = on_archive_changed
        self._destroyed = False

        self._week_monday: date = get_current_week_monday()
        self._last_is_archive: bool = False

        self._header_frame: Optional[ctk.CTkFrame] = None
        self._prev_btn: Optional[ctk.CTkButton] = None
        self._next_btn: Optional[ctk.CTkButton] = None
        self._today_btn: Optional[ctk.CTkButton] = None
        self._header_label: Optional[ctk.CTkLabel] = None
        self._archive_banner: Optional[ctk.CTkFrame] = None

        self._build()
        self._bind_keyboard()
        self._theme.subscribe(self._apply_theme)
        self._update_header()

    def pack(self, **kwargs) -> None:
        if self._header_frame is not None:
            self._header_frame.pack(**kwargs)

    def get_week_monday(self) -> date:
        return self._week_monday

    def set_week_monday(self, monday: date) -> None:
        self._week_monday = get_week_monday(monday)
        self._update_header()
        self._notify_changes()

    def prev_week(self) -> None:
        self._week_monday = self._week_monday - timedelta(days=7)
        self._update_header()
        self._notify_changes()

    def next_week(self) -> None:
        self._week_monday = self._week_monday + timedelta(days=7)
        self._update_header()
        self._notify_changes()

    def today(self) -> None:
        self._week_monday = get_current_week_monday()
        self._update_header()
        self._notify_changes()

    def is_current_archive(self) -> bool:
        return is_archive_week(self._week_monday)

    def destroy(self) -> None:
        self._destroyed = True
        try:
            if self._header_frame is not None:
                self._header_frame.destroy()
        except Exception:
            pass

    def _build(self) -> None:
        self._header_frame = ctk.CTkFrame(
            self._parent, fg_color=self._theme.get("bg_primary"), corner_radius=0,
        )
        row = ctk.CTkFrame(self._header_frame, fg_color="transparent", height=40)
        row.pack(fill="x")
        row.pack_propagate(False)

        self._prev_btn = ctk.CTkButton(
            row, text="◀", width=self.ARROW_WIDTH, command=self.prev_week,
        )
        self._prev_btn.pack(side="left", padx=4, pady=4)

        self._header_label = ctk.CTkLabel(row, text="Неделя —", font=FONTS["h1"])
        self._header_label.pack(side="left", expand=True)

        self._today_btn = ctk.CTkButton(
            row, text="Сегодня", width=self.TODAY_BTN_WIDTH, command=self.today,
        )
        # Не pack по default — виден только для не-current

        self._next_btn = ctk.CTkButton(
            row, text="▶", width=self.ARROW_WIDTH, command=self.next_week,
        )
        self._next_btn.pack(side="right", padx=4, pady=4)

        # Archive banner
        self._archive_banner = ctk.CTkFrame(
            self._header_frame,
            fg_color=self._theme.get("bg_tertiary"),
            corner_radius=0,
            height=32,
        )
        ctk.CTkLabel(
            self._archive_banner, text="📦 Архив", font=FONTS["caption"],
        ).pack(side="left", padx=8, pady=6)
        ctk.CTkLabel(
            self._archive_banner,
            text="Вернуться →",
            font=FONTS["caption"],
            text_color=self._theme.get("accent_brand"),
            cursor="hand2",
        ).pack(side="right", padx=8)
        for child in self._archive_banner.winfo_children():
            try:
                child.bind("<Button-1>", lambda e: self.today())
            except tk.TclError:
                pass

    def _bind_keyboard(self) -> None:
        """D-30: Ctrl+Left/Right/T."""
        self._window.bind("<Control-Left>", lambda e: self.prev_week(), add="+")
        self._window.bind("<Control-Right>", lambda e: self.next_week(), add="+")
        self._window.bind("<Control-t>", lambda e: self.today(), add="+")
        self._window.bind("<Control-T>", lambda e: self.today(), add="+")

    def _update_header(self) -> None:
        if self._destroyed:
            return
        if self._header_label and self._header_label.winfo_exists():
            try:
                self._header_label.configure(text=format_week_header(self._week_monday))
            except tk.TclError:
                pass
        self._update_today_button_visibility()
        self._update_archive_banner()

    def _update_today_button_visibility(self) -> None:
        if self._today_btn is None:
            return
        is_current = self._week_monday == get_current_week_monday()
        try:
            if is_current:
                self._today_btn.pack_forget()
            else:
                self._today_btn.pack(side="right", padx=4, pady=4, before=self._next_btn)
        except tk.TclError:
            pass

    def _update_archive_banner(self) -> None:
        if self._archive_banner is None:
            return
        is_archive = self.is_current_archive()
        try:
            if is_archive:
                self._archive_banner.pack(fill="x")
            else:
                self._archive_banner.pack_forget()
        except tk.TclError:
            pass

    def _notify_changes(self) -> None:
        try:
            self._on_week_changed(self._week_monday)
        except Exception as exc:
            logger.error("on_week_changed failed: %s", exc)

        is_archive_now = self.is_current_archive()
        if is_archive_now != self._last_is_archive:
            self._last_is_archive = is_archive_now
            try:
                self._on_archive_changed(is_archive_now)
            except Exception as exc:
                logger.error("on_archive_changed failed: %s", exc)

    def _apply_theme(self, palette: dict) -> None:
        if self._destroyed:
            return
        try:
            if self._header_frame and self._header_frame.winfo_exists():
                self._header_frame.configure(fg_color=palette.get("bg_primary"))
            if self._archive_banner and self._archive_banner.winfo_exists():
                self._archive_banner.configure(fg_color=palette.get("bg_tertiary"))
        except tk.TclError:
            pass
