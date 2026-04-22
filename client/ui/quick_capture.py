"""QuickCapturePopup — popup-input для мгновенного захвата задачи. Phase 4.

Интегрируется с parse_input.parse_quick_input (Plan 04-02).

Покрывает TASK-01 (speed-of-capture).
PITFALL 1: after(100) для overrideredirect
PITFALL 3: focus-out через after(50) delay
D-02: -toolwindow=1 hide from taskbar + edge-flip

Quick 260422-v1a: redesign 360×140 + accent strip + hint footer
+ screen-clamp позиционирование (popup никогда не выходит за край экрана).
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from shared.parse_input import parse_quick_input
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)


class QuickCapturePopup:
    """См. 04-UI-SPEC §Quick Capture. Quick 260422-v1a: 360×140 redesign."""

    POPUP_WIDTH = 360
    POPUP_HEIGHT = 140
    POPUP_GAP = 8
    ACCENT_STRIP_WIDTH = 4
    EDGE_MARGIN = 8  # отступ от края экрана (было 80 — избыточно)
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

    def show_at_overlay(self, overlay_x: int, overlay_y: int, overlay_size: int = 73) -> None:
        """D-02: показать popup рядом с overlay. Toggle если уже открыт.

        Quick 260422-v1a screen-clamp:
          X: сначала справа (overlay_x + overlay_size + gap); если не влезает →
             слева от overlay; fallback — центрировать по overlay, clamp к экрану.
          Y: по умолчанию = overlay_y; если не влезает снизу — прижать к низу экрана.
        """
        if self._visible:
            self.hide()
            return

        try:
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
        except tk.TclError:
            sw, sh = 1920, 1080

        # X positioning: prefer right → left → center+clamp
        x = overlay_x + overlay_size + self.POPUP_GAP
        if x + self.POPUP_WIDTH + self.EDGE_MARGIN > sw:
            x = overlay_x - self.POPUP_WIDTH - self.POPUP_GAP
        if x < self.EDGE_MARGIN:
            x = overlay_x + overlay_size // 2 - self.POPUP_WIDTH // 2
            x = max(self.EDGE_MARGIN, min(x, sw - self.POPUP_WIDTH - self.EDGE_MARGIN))

        # Y positioning: align with overlay top, clamp
        y = overlay_y
        if y + self.POPUP_HEIGHT + self.EDGE_MARGIN > sh:
            y = sh - self.POPUP_HEIGHT - self.EDGE_MARGIN
        if y < self.EDGE_MARGIN:
            y = self.EDGE_MARGIN

        self._create_popup(x, y)

    def show_centered(self, x: int, y: int) -> None:
        """D-30 Ctrl+Space alternate trigger. Quick 260422-v1a: clamp по обеим осям."""
        if self._visible:
            self.hide()
            return
        try:
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
        except tk.TclError:
            sw, sh = 1920, 1080
        x = max(self.EDGE_MARGIN, min(x, sw - self.POPUP_WIDTH - self.EDGE_MARGIN))
        y = max(self.EDGE_MARGIN, min(y, sh - self.POPUP_HEIGHT - self.EDGE_MARGIN))
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
        """Quick 260422-v1a: redesign — accent strip + caption label + hint footer."""
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
        bg = self._theme.get("bg_secondary")
        text_ter = self._theme.get("text_tertiary")
        border = self._blend_hex(bg, text_ter, 0.35)

        # Outer frame с border — визуально согласован с UpdateBanner/InlineEditPanel
        outer = ctk.CTkFrame(
            self._popup, fg_color=bg, corner_radius=10,
            border_width=1, border_color=border,
        )
        outer.pack(fill="both", expand=True)

        # Accent strip 4px слева (sage)
        strip = ctk.CTkFrame(
            outer, width=self.ACCENT_STRIP_WIDTH, fg_color=accent, corner_radius=0,
        )
        strip.pack(side="left", fill="y")
        strip.pack_propagate(False)

        # Content area
        content = ctk.CTkFrame(outer, fg_color=bg, corner_radius=0)
        content.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        # Caption label
        ctk.CTkLabel(
            content, text="Быстрая задача",
            font=FONTS["caption"], text_color=text_ter, anchor="w",
        ).pack(fill="x")

        # Entry
        self._entry = ctk.CTkEntry(
            content,
            placeholder_text="Что нужно сделать?",
            font=FONTS["body"],
            border_width=1,
            border_color=border,
            fg_color=bg,
            height=32,
            corner_radius=8,
        )
        self._entry.pack(fill="x", pady=(4, 6))

        # Hint footer
        ctk.CTkLabel(
            content, text="Enter — сохранить   ·   Esc — отмена",
            font=FONTS["caption"], text_color=text_ter, anchor="w",
        ).pack(fill="x")

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
        """D-05: red border 300ms → restore. Quick 260422-v1a: новый border = blend."""
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
                    bg = self._theme.get("bg_secondary")
                    text_ter = self._theme.get("text_tertiary")
                    border = self._blend_hex(bg, text_ter, 0.35)
                    self._entry.configure(border_color=border, border_width=1)
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
