"""
UpdateBanner — уведомление о доступном обновлении.

Показывается через app._show_update_banner когда check() находит новую версию.
CTkToplevel сверху-справа, без рамки, с accent-strip + icon + progress bar.

Quick 260422-tah: редизайн 340x96 → 420x170 с accent-strip, круглой иконкой,
progress bar (CTkProgressBar) и slide-down+fade-in анимацией.
"""
from __future__ import annotations

import logging
import sys
import threading
import tkinter as tk
from typing import Optional

import customtkinter as ctk

from client.ui.themes import FONTS, ThemeManager, _FONT_FAMILY
from client.utils.updater import UpdateManager

logger = logging.getLogger(__name__)


class UpdateBanner:
    """Всплывающий баннер обновления (420x170, accent-strip, progress bar)."""

    WIDTH = 420
    HEIGHT = 170
    EDGE_MARGIN = 24
    FADE_DURATION_MS = 200
    FADE_STEPS = 8
    SLIDE_FROM_Y = -20  # начальный y-offset относительно финального (выше экрана)

    def __init__(
        self,
        root: ctk.CTk,
        theme_manager: ThemeManager,
        updater: UpdateManager,
        new_version: str,
        download_url: str,
        sha256: str,
    ) -> None:
        self._root = root
        self._theme = theme_manager
        self._updater = updater
        self._new_version = new_version
        self._download_url = download_url
        self._sha256 = sha256
        self._downloading = False
        self._final_x = 0
        self._final_y = 0

        self._banner = ctk.CTkToplevel(root)
        self._banner.withdraw()
        self._banner.overrideredirect(True)
        try:
            self._banner.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._banner.geometry(f"{self.WIDTH}x{self.HEIGHT}")

        # ---- Токены палитры (читаем один раз — live-theme не требуется, баннер живёт недолго) ----
        bg_secondary = self._theme.get("bg_secondary")
        bg_tertiary = self._theme.get("bg_tertiary")
        text_primary = self._theme.get("text_primary")
        text_secondary = self._theme.get("text_secondary")
        accent_brand = self._theme.get("accent_brand")
        accent_brand_light = self._theme.get("accent_brand_light")
        border_window = self._theme.get("border_window")

        # ---- Root frame с рамкой ----
        self._frame = ctk.CTkFrame(
            self._banner,
            corner_radius=12,
            fg_color=bg_secondary,
            border_width=1,
            border_color=border_window,
        )
        self._frame.pack(fill="both", expand=True, padx=2, pady=2)

        # ---- Accent strip 4px слева (вертикальная цветная полоса) ----
        self._accent_strip = ctk.CTkFrame(
            self._frame, width=4, fg_color=accent_brand, corner_radius=0,
        )
        self._accent_strip.pack(side="left", fill="y")

        # ---- Content блок справа от strip ----
        content = ctk.CTkFrame(self._frame, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        # ---- Top row: иконка в круге + title + status ----
        top_row = ctk.CTkFrame(content, fg_color="transparent")
        top_row.pack(fill="x")

        # Круглая иконка 48x48 (corner_radius=24 делает её круглой)
        icon_frame = ctk.CTkFrame(
            top_row, width=48, height=48,
            corner_radius=24, fg_color=accent_brand,
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)
        icon_label = ctk.CTkLabel(
            icon_frame, text="⬇",
            font=(_FONT_FAMILY, 22, "bold"),
            text_color="#FFFFFF",
        )
        icon_label.pack(fill="both", expand=True)

        # Текстовая колонка справа от иконки
        text_col = ctk.CTkFrame(top_row, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True, padx=(12, 0))

        self._title = ctk.CTkLabel(
            text_col, text="Доступно обновление",
            font=FONTS["h1"], text_color=text_primary, anchor="w",
        )
        self._title.pack(fill="x")

        self._status = ctk.CTkLabel(
            text_col,
            text=f"v{self._updater.current_version} → v{new_version}",
            font=FONTS["body"], text_color=text_secondary, anchor="w",
        )
        self._status.pack(fill="x")

        # ---- Progress row (создан но НЕ pack'нут — появляется после клика "Обновить") ----
        self._progress_row = ctk.CTkFrame(content, fg_color="transparent")
        self._progress = ctk.CTkProgressBar(
            self._progress_row, width=280, height=8,
            progress_color=accent_brand,
            fg_color=bg_tertiary,
        )
        self._progress.pack(side="left", pady=(10, 0))
        self._progress.set(0)
        self._pct_label = ctk.CTkLabel(
            self._progress_row, text="0%",
            font=FONTS["caption"], text_color=text_secondary,
        )
        self._pct_label.pack(side="right", padx=(8, 0), pady=(10, 0))

        # ---- Button row ----
        self._btn_row = ctk.CTkFrame(content, fg_color="transparent")
        self._btn_row.pack(fill="x", pady=(10, 0))

        self._dismiss_btn = ctk.CTkButton(
            self._btn_row, text="Позже",
            width=80, height=32,
            fg_color="transparent", border_width=1,
            border_color=border_window,
            text_color=text_secondary,
            hover_color=self._theme.get("bg_tertiary"),
            command=self._dismiss,
        )
        self._dismiss_btn.pack(side="left")

        self._update_btn = ctk.CTkButton(
            self._btn_row, text="Обновить",
            width=140, height=32,
            fg_color=accent_brand,
            hover_color=accent_brand_light,
            text_color="#FFFFFF",
            command=self._on_update_click,
        )
        self._update_btn.pack(side="right")

        # Цвет для ошибок — кэшируем, чтобы не ходить в theme потом
        self._error_color = self._theme.get("accent_overdue")
        self._status_default_color = text_secondary

        # Reposition top-right с slide+fade анимацией (после того как root узнал размер экрана)
        self._banner.after(100, self._reposition_and_show)

    # ---- Animation ----

    def _reposition_and_show(self) -> None:
        """Поставить баннер в правый верхний угол и запустить slide-down+fade-in."""
        try:
            sw = self._banner.winfo_screenwidth()
            self._final_x = sw - self.WIDTH - self.EDGE_MARGIN
            self._final_y = self.EDGE_MARGIN
            # Стартовая позиция — выше финальной (slide-down эффект)
            start_y = self._final_y + self.SLIDE_FROM_Y
            self._banner.geometry(
                f"{self.WIDTH}x{self.HEIGHT}+{self._final_x}+{start_y}"
            )
            try:
                self._banner.attributes("-alpha", 0.0)
            except tk.TclError:
                pass
            self._banner.deiconify()
            self._banner.lift()
            self._animate_in(step=0)
        except tk.TclError as exc:
            logger.debug("UpdateBanner reposition: %s", exc)

    def _animate_in(self, step: int) -> None:
        """Ease-out квадратичный fade+slide кадр за кадром."""
        current_step = step + 1
        progress = current_step / self.FADE_STEPS
        eased = 1.0 - (1.0 - progress) ** 2  # ease-out quadratic
        alpha = eased
        start_y = self._final_y + self.SLIDE_FROM_Y
        y = int(start_y + (self._final_y - start_y) * eased)
        try:
            self._banner.attributes("-alpha", max(0.0, min(1.0, alpha)))
            self._banner.geometry(
                f"{self.WIDTH}x{self.HEIGHT}+{self._final_x}+{y}"
            )
        except tk.TclError:
            return
        if current_step >= self.FADE_STEPS:
            # Финальный кадр — точные значения (без накопления floating-point погрешности)
            try:
                self._banner.attributes("-alpha", 1.0)
                self._banner.geometry(
                    f"{self.WIDTH}x{self.HEIGHT}+{self._final_x}+{self._final_y}"
                )
            except tk.TclError:
                pass
            return
        delay = max(1, int(self.FADE_DURATION_MS / self.FADE_STEPS))
        try:
            self._banner.after(delay, self._animate_in, current_step)
        except tk.TclError:
            pass

    # ---- Progress ----

    def _update_progress(self, frac: float) -> None:
        """Обновить progress bar + процент (вызов из main thread через after)."""
        try:
            self._progress.set(max(0.0, min(1.0, frac)))
            self._pct_label.configure(text=f"{int(frac * 100)}%")
        except tk.TclError:
            pass

    # ---- Click handlers ----

    def _on_update_click(self) -> None:
        if self._downloading:
            return
        self._downloading = True
        self._update_btn.configure(state="disabled", text="Скачиваю...")
        self._dismiss_btn.configure(state="disabled")
        # Показать progress row ПЕРЕД btn_row (между top_row и btn_row)
        try:
            self._progress_row.pack(fill="x", before=self._btn_row)
        except tk.TclError:
            pass
        # Download в daemon thread — не блокируем UI
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self) -> None:
        def progress(done: int, total: int) -> None:
            if total > 0:
                frac = done / total
                self._root.after(0, self._update_progress, frac)

        try:
            tmp_path = self._updater.download_and_verify(
                self._download_url, self._sha256, progress_cb=progress,
            )
        except Exception as exc:
            logger.error("download_and_verify: %s", exc)
            tmp_path = None

        if tmp_path is None:
            self._root.after(0, self._on_download_failed)
            return

        self._root.after(0, lambda: self._apply_and_exit(tmp_path))

    def _on_download_failed(self) -> None:
        """Сбросить состояние + показать ошибку accent_overdue цветом."""
        self._downloading = False
        try:
            self._progress_row.pack_forget()
        except tk.TclError:
            pass
        self._update_btn.configure(state="normal", text="Повторить")
        self._dismiss_btn.configure(state="normal")
        self._status.configure(
            text="Ошибка. Проверь интернет.",
            text_color=self._error_color,
        )

    def _apply_and_exit(self, tmp_path: str) -> None:
        self._status.configure(
            text="Применяю обновление...",
            text_color=self._status_default_color,
        )
        ok = self._updater.apply_update(tmp_path)
        if not ok:
            # dev-mode или bat-start упал — fallback: открыть GitHub в браузере
            self._status.configure(text="Запусти новый .exe вручную")
            try:
                import webbrowser
                webbrowser.open(self._download_url)
            except Exception:
                pass
            return
        # Выходим — bat перехватит, заменит, перезапустит
        logger.info("Exiting for update bat to take over")
        try:
            self._banner.destroy()
        except tk.TclError:
            pass
        self._root.after(500, lambda: sys.exit(0))

    def _dismiss(self) -> None:
        try:
            self._banner.destroy()
        except tk.TclError:
            pass
