"""
UpdateBanner — уведомление о доступном обновлении.

Показывается через app._show_update_banner когда check() находит новую версию.
CTkToplevel сверху-справа, без рамки, с двумя кнопками ("Позже" ghost + "Обновить" primary).

Forest Phase E (260421-1jo):
  Обе кнопки теперь через palette keys (accent_brand forest primary, ghost-стиль
  secondary). Banner фон — bg_primary с 1px border по bg_tertiary. Подписка на
  ThemeManager позволяет live-switching тем пока banner открыт.
"""
from __future__ import annotations

import logging
import sys
import threading
import tkinter as tk
from typing import Optional

import customtkinter as ctk

from client.ui.themes import FONTS, ThemeManager
from client.utils.updater import UpdateManager

logger = logging.getLogger(__name__)


class UpdateBanner:
    """Всплывающий баннер обновления."""

    WIDTH = 340
    HEIGHT = 96
    EDGE_MARGIN = 24

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
        self._destroyed = False

        self._banner = ctk.CTkToplevel(root)
        self._banner.withdraw()
        self._banner.overrideredirect(True)
        try:
            self._banner.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._banner.geometry(f"{self.WIDTH}x{self.HEIGHT}")

        # Forest: banner background = bg_primary (как диалог), 1px border через bg_tertiary
        bg_primary = self._theme.get("bg_primary")
        bg_tertiary = self._theme.get("bg_tertiary")
        text_primary = self._theme.get("text_primary")
        text_secondary = self._theme.get("text_secondary")
        text_tertiary = self._theme.get("text_tertiary")
        accent = self._theme.get("accent_brand")
        accent_light = self._theme.get("accent_brand_light")

        self._frame = ctk.CTkFrame(
            self._banner,
            corner_radius=10,
            fg_color=bg_primary,
            border_width=1,
            border_color=bg_tertiary,
        )
        self._frame.pack(fill="both", expand=True, padx=2, pady=2)

        content = ctk.CTkFrame(self._frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=10)

        self._title = ctk.CTkLabel(
            content, text=f"Доступна версия {new_version}",
            text_color=text_primary, font=FONTS["h2"], anchor="w",
        )
        self._title.pack(fill="x")

        self._status = ctk.CTkLabel(
            content, text=f"Текущая {self._updater.current_version}",
            text_color=text_secondary, font=FONTS["caption"], anchor="w",
        )
        self._status.pack(fill="x", pady=(0, 6))

        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack(fill="x")

        # "Позже" — ghost: transparent fill + border, secondary text
        self._dismiss_btn = ctk.CTkButton(
            btn_row, text="Позже", width=80, height=28,
            fg_color="transparent",
            border_width=1,
            border_color=text_tertiary,
            text_color=text_secondary,
            hover_color=bg_tertiary,
            font=FONTS["body"],
            command=self._dismiss,
        )
        self._dismiss_btn.pack(side="left")

        # "Обновить" — forest primary: accent_brand fill, cream text (bg_primary)
        self._update_btn = ctk.CTkButton(
            btn_row, text="Обновить", width=140, height=28,
            fg_color=accent,
            hover_color=accent_light,
            text_color=bg_primary,
            font=FONTS["body_m"],
            command=self._on_update_click,
        )
        self._update_btn.pack(side="right")

        # Live theme switching
        try:
            self._theme.subscribe(self._apply_theme)
        except Exception as exc:
            logger.debug("UpdateBanner theme subscribe: %s", exc)

        # Reposition top-right (после того как root узнал размер экрана)
        self._banner.after(100, self._reposition_and_show)

    def _apply_theme(self, palette: dict) -> None:
        """Live-update всех элементов banner при смене темы."""
        if self._destroyed:
            return
        bg_primary = palette.get("bg_primary")
        bg_tertiary = palette.get("bg_tertiary")
        text_primary = palette.get("text_primary")
        text_secondary = palette.get("text_secondary")
        text_tertiary = palette.get("text_tertiary")
        accent = palette.get("accent_brand")
        accent_light = palette.get("accent_brand_light")
        try:
            if self._frame.winfo_exists():
                self._frame.configure(fg_color=bg_primary, border_color=bg_tertiary)
        except tk.TclError:
            return
        try:
            self._title.configure(text_color=text_primary)
            self._status.configure(text_color=text_secondary)
            self._dismiss_btn.configure(
                border_color=text_tertiary,
                text_color=text_secondary,
                hover_color=bg_tertiary,
            )
            self._update_btn.configure(
                fg_color=accent,
                hover_color=accent_light,
                text_color=bg_primary,
            )
        except tk.TclError:
            pass

    def _reposition_and_show(self) -> None:
        try:
            sw = self._banner.winfo_screenwidth()
            x = sw - self.WIDTH - self.EDGE_MARGIN
            y = self.EDGE_MARGIN
            self._banner.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
            self._banner.deiconify()
            self._banner.lift()
        except tk.TclError as exc:
            logger.debug("UpdateBanner reposition: %s", exc)

    def _on_update_click(self) -> None:
        if self._downloading:
            return
        self._downloading = True
        self._update_btn.configure(state="disabled", text="Скачиваю...")
        self._dismiss_btn.configure(state="disabled")
        # Download в daemon thread — не блокируем UI
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self) -> None:
        def progress(done: int, total: int) -> None:
            if total > 0:
                pct = int(done * 100 / total)
                self._root.after(0, lambda p=pct: self._status.configure(text=f"Скачано {p}%"))

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
        self._downloading = False
        self._update_btn.configure(state="normal", text="Повторить")
        self._dismiss_btn.configure(state="normal")
        self._status.configure(
            text="Ошибка скачивания. Проверь интернет или SHA256.",
        )

    def _apply_and_exit(self, tmp_path: str) -> None:
        self._status.configure(text="Применяю обновление...")
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
            self._destroyed = True
            self._banner.destroy()
        except tk.TclError:
            pass
        self._root.after(500, lambda: sys.exit(0))

    def _dismiss(self) -> None:
        self._destroyed = True
        try:
            self._banner.destroy()
        except tk.TclError:
            pass
