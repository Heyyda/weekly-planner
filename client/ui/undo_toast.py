"""UndoToastManager — floating toasts внизу main window. Phase 4 (TASK-04).

Gmail-pattern undo-flow: "⟲ Задача удалена • Отменить" с 5-second countdown.
Max 3 stacked vertically.

CTkFrame + place() (НЕ CTkToplevel per research anti-pattern).

Forest Phase E (260421-1jo):
  _apply_theme теперь обновляет не только bg, но и accent (undo-label text_color
  + bar_canvas bg). Палитра — forest-compatible (accent_brand = forest).
"""
from __future__ import annotations

import logging
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional

import customtkinter as ctk

from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)


@dataclass
class ToastEntry:
    task_id: str
    task_text: str
    undo_callback: Callable[[], None]


class UndoToastManager:
    MAX_TOASTS = 3
    TOAST_DURATION_MS = 5000
    TOAST_WIDTH = 280
    TOAST_HEIGHT = 44
    TOAST_BOTTOM_MARGIN = 8
    TOAST_GAP = 4
    COUNTDOWN_INTERVAL_MS = 50

    def __init__(
        self,
        parent: ctk.CTkFrame,
        root: ctk.CTk,
        theme_manager: ThemeManager,
    ) -> None:
        self._parent = parent
        self._root = root
        self._theme = theme_manager
        self._destroyed = False

        self._queue: list[ToastEntry] = []
        self._frames: list[ctk.CTkFrame] = []
        self._canvases: list[tk.Canvas] = []
        self._undo_labels: list[ctk.CTkLabel] = []
        self._start_ms_list: list[int] = []

        theme_manager.subscribe(self._apply_theme)

    def show(
        self,
        task_id: str,
        task_text: str,
        undo_callback: Callable[[], None],
    ) -> None:
        """D-21: max 3 — вытесняем самый старый."""
        if self._destroyed:
            return

        if len(self._queue) >= self.MAX_TOASTS:
            self._dismiss_at(0)

        entry = ToastEntry(
            task_id=task_id,
            task_text=task_text,
            undo_callback=undo_callback,
        )
        self._queue.append(entry)
        self._build_toast(entry)
        self._reposition_all()

        start_ms = int(time.monotonic() * 1000)
        self._start_ms_list.append(start_ms)
        self._root.after(
            self.TOAST_DURATION_MS,
            lambda tid=task_id: self._auto_dismiss(tid),
        )

    def hide_all(self) -> None:
        for i in range(len(self._queue) - 1, -1, -1):
            self._dismiss_at(i)

    def destroy(self) -> None:
        self._destroyed = True
        self.hide_all()

    def _build_toast(self, entry: ToastEntry) -> None:
        bg = self._theme.get("bg_secondary")
        text_primary = self._theme.get("text_primary")
        accent = self._theme.get("accent_brand")

        toast = ctk.CTkFrame(
            self._parent,
            width=self.TOAST_WIDTH,
            height=self.TOAST_HEIGHT,
            corner_radius=8,
            fg_color=bg,
        )
        toast.pack_propagate(False)

        content = ctk.CTkFrame(toast, fg_color="transparent")
        content.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            content,
            text="⟲ Задача удалена",
            text_color=text_primary,
            font=FONTS["body"],
            anchor="w",
        ).pack(side="left")

        undo_lbl = ctk.CTkLabel(
            content,
            text="Отменить",
            text_color=accent,
            cursor="hand2",
            font=FONTS["body"],
        )
        undo_lbl.pack(side="right")
        undo_lbl.bind(
            "<Button-1>",
            lambda e, tid=entry.task_id: self._undo(tid),
        )

        bar_canvas = tk.Canvas(
            toast,
            width=self.TOAST_WIDTH,
            height=2,
            bg=accent,
            highlightthickness=0,
            borderwidth=0,
        )
        bar_canvas.place(x=0, rely=1.0, anchor="sw")

        self._frames.append(toast)
        self._canvases.append(bar_canvas)
        self._undo_labels.append(undo_lbl)

        start_ms = int(time.monotonic() * 1000)
        self._root.after(
            self.COUNTDOWN_INTERVAL_MS,
            lambda: self._animate_bar(bar_canvas, start_ms),
        )

    def _animate_bar(self, canvas: tk.Canvas, start_ms: int) -> None:
        if self._destroyed:
            return
        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return

        elapsed = int(time.monotonic() * 1000) - start_ms
        if elapsed >= self.TOAST_DURATION_MS:
            try:
                canvas.configure(width=0)
            except tk.TclError:
                pass
            return

        ratio = 1.0 - (elapsed / self.TOAST_DURATION_MS)
        new_width = max(0, int(self.TOAST_WIDTH * ratio))
        try:
            canvas.configure(width=new_width)
        except tk.TclError:
            return

        self._root.after(
            self.COUNTDOWN_INTERVAL_MS,
            lambda: self._animate_bar(canvas, start_ms),
        )

    def _reposition_all(self) -> None:
        try:
            pw = self._parent.winfo_width() or 460
        except tk.TclError:
            pw = 460
        if pw < 100:
            pw = 460

        for i, frame in enumerate(self._frames):
            if not frame.winfo_exists():
                continue
            y_offset = self.TOAST_BOTTOM_MARGIN + i * (self.TOAST_HEIGHT + self.TOAST_GAP)
            x = (pw - self.TOAST_WIDTH) // 2
            try:
                frame.place(x=x, rely=1.0, anchor="sw", y=-y_offset)
            except tk.TclError:
                pass

    def _undo(self, task_id: str) -> None:
        """D-20: click 'Отменить' → undo_callback + hide."""
        idx = self._find_index(task_id)
        if idx is None:
            return
        entry = self._queue[idx]
        try:
            entry.undo_callback()
        except Exception as exc:
            logger.error("undo_callback failed: %s", exc)
        self._dismiss_at(idx)

    def _auto_dismiss(self, task_id: str) -> None:
        """D-19: после 5s — hide (НЕ undo)."""
        idx = self._find_index(task_id)
        if idx is None:
            return
        self._dismiss_at(idx)

    def _dismiss_at(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._queue):
            return
        self._queue.pop(idx)
        frame = self._frames.pop(idx)
        if idx < len(self._canvases):
            self._canvases.pop(idx)
        if idx < len(self._undo_labels):
            self._undo_labels.pop(idx)
        if idx < len(self._start_ms_list):
            self._start_ms_list.pop(idx)
        try:
            frame.place_forget()
            frame.destroy()
        except tk.TclError:
            pass
        self._reposition_all()

    def _find_index(self, task_id: str) -> Optional[int]:
        for i, e in enumerate(self._queue):
            if e.task_id == task_id:
                return i
        return None

    def _apply_theme(self, palette: dict) -> None:
        """Live-update всех живых тостов: bg, accent на undo-labels + canvas bars."""
        if self._destroyed:
            return
        bg = palette.get("bg_secondary")
        accent = palette.get("accent_brand")
        for frame in self._frames:
            try:
                if frame.winfo_exists():
                    frame.configure(fg_color=bg)
            except tk.TclError:
                pass
        for lbl in self._undo_labels:
            try:
                if lbl.winfo_exists():
                    lbl.configure(text_color=accent)
            except tk.TclError:
                pass
        for canvas in self._canvases:
            try:
                if canvas.winfo_exists():
                    canvas.configure(bg=accent)
            except tk.TclError:
                pass
