"""QuickCapturePopup — popup-input для мгновенного захвата задачи. Phase 4.

Интегрируется с parse_input.parse_quick_input (Plan 04-02).

Покрывает TASK-01 (speed-of-capture).
PITFALL 1: after(100) для overrideredirect
PITFALL 3: focus-out через after(50) delay
D-02: -toolwindow=1 hide from taskbar + edge-flip
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from client.ui.parse_input import parse_quick_input
from client.ui.themes import ThemeManager

logger = logging.getLogger(__name__)


class QuickCapturePopup:
    """См. 04-UI-SPEC §Quick Capture."""

    POPUP_WIDTH = 400
    POPUP_HEIGHT = 40
    POPUP_GAP = 8
    EDGE_MARGIN = 80
    FOCUS_CHECK_DELAY_MS = 50
    INIT_DELAY_MS = 100
    EMPTY_FLASH_MS = 300

    def __init__(
        self,
        root: ctk.CTk,
        theme_manager: ThemeManager,
        on_save: Callable[[str, str, Optional[str]], None],
    ) -> None:
        self._root = root
        self._theme = theme_manager
        self._on_save = on_save

        self._popup: Optional[ctk.CTkToplevel] = None
        self._entry: Optional[ctk.CTkEntry] = None
        self._visible: bool = False

    def is_visible(self) -> bool:
        return self._visible and self._popup is not None

    def show_at_overlay(self, overlay_x: int, overlay_y: int, overlay_size: int = 56) -> None:
        """D-02: показать popup под overlay. Toggle если уже открыт."""
        if self._visible:
            self.hide()
            return

        try:
            screen_h = self._root.winfo_screenheight()
        except tk.TclError:
            screen_h = 1080

        needed_below = overlay_y + overlay_size + self.POPUP_GAP + self.POPUP_HEIGHT + self.EDGE_MARGIN
        if needed_below > screen_h:
            popup_y = overlay_y - self.POPUP_HEIGHT - self.POPUP_GAP
        else:
            popup_y = overlay_y + overlay_size + self.POPUP_GAP

        popup_x = overlay_x + overlay_size // 2 - self.POPUP_WIDTH // 2
        self._create_popup(popup_x, popup_y)

    def show_centered(self, x: int, y: int) -> None:
        """D-30 Ctrl+Space alternate trigger."""
        if self._visible:
            self.hide()
            return
        self._create_popup(x, y)

    def hide(self) -> None:
        self._visible = False
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception as exc:
                logger.debug("QuickCapture hide: %s", exc)
            self._popup = None
            self._entry = None

    def destroy(self) -> None:
        self.hide()

    def _create_popup(self, x: int, y: int) -> None:
        """PITFALL 1: overrideredirect через after(100)."""
        self._popup = ctk.CTkToplevel(self._root)
        self._popup.withdraw()
        self._popup.geometry(f"{self.POPUP_WIDTH}x{self.POPUP_HEIGHT}+{x}+{y}")
        self._popup.after(self.INIT_DELAY_MS, self._init_popup_style)

    def _init_popup_style(self) -> None:
        if self._popup is None:
            return
        try:
            self._popup.overrideredirect(True)
            self._popup.attributes("-topmost", True)
        except tk.TclError as exc:
            logger.debug("overrideredirect init: %s", exc)

        try:
            self._popup.wm_attributes("-toolwindow", 1)
        except tk.TclError:
            pass

        accent = self._theme.get("accent_brand")
        frame = ctk.CTkFrame(
            self._popup, fg_color=self._theme.get("bg_secondary"), corner_radius=0,
        )
        frame.pack(fill="both", expand=True)

        strip = ctk.CTkFrame(frame, width=3, fg_color=accent, corner_radius=0)
        strip.pack(side="left", fill="y")
        strip.pack_propagate(False)

        self._entry = ctk.CTkEntry(
            frame,
            placeholder_text="Новая задача на сегодня...",
            border_width=0,
            fg_color=self._theme.get("bg_secondary"),
        )
        self._entry.pack(side="left", fill="both", expand=True, padx=(4, 4), pady=2)

        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Escape>", lambda e: self.hide())
        self._popup.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<FocusOut>", self._on_focus_out)

        self._popup.deiconify()
        try:
            self._popup.focus_force()
            self._entry.focus_set()
        except tk.TclError:
            pass
        self._visible = True

    def _on_enter(self, event=None) -> None:
        """D-05: save если не пусто; multi-add clear."""
        if self._entry is None:
            return
        text = self._entry.get().strip()
        if not text:
            self._flash_empty_border()
            return

        try:
            parsed = parse_quick_input(text)
        except Exception as exc:
            logger.error("parse_quick_input failed: %s", exc)
            parsed = {"text": text, "day": date.today().isoformat(), "time": None}

        try:
            self._on_save(parsed["text"] or text, parsed["day"], parsed.get("time"))
        except Exception as exc:
            logger.error("on_save callback failed: %s", exc)

        try:
            self._entry.delete(0, "end")
            self._entry.focus_set()
        except tk.TclError:
            pass

    def _flash_empty_border(self) -> None:
        """D-05: red border 300ms → restore."""
        if self._entry is None or not self._entry.winfo_exists():
            return
        accent_overdue = self._theme.get("accent_overdue")
        try:
            self._entry.configure(border_color=accent_overdue, border_width=2)
        except tk.TclError:
            return

        def restore():
            if self._entry and self._entry.winfo_exists():
                try:
                    self._entry.configure(
                        border_color=self._theme.get("bg_secondary"),
                        border_width=0,
                    )
                except tk.TclError:
                    pass

        self._root.after(self.EMPTY_FLASH_MS, restore)

    def _on_focus_out(self, event=None) -> None:
        """PITFALL 3: delay + check_focus."""
        if self._popup is None:
            return
        self._popup.after(self.FOCUS_CHECK_DELAY_MS, self._check_focus)

    def _check_focus(self) -> None:
        if self._popup is None:
            return
        try:
            focused = self._root.focus_get()
            if focused is self._popup or focused is self._entry:
                return
            if focused is not None:
                try:
                    parent = focused
                    while parent:
                        if parent is self._popup:
                            return
                        parent = parent.master
                except Exception:
                    pass
            self.hide()
        except (tk.TclError, AttributeError):
            self.hide()
