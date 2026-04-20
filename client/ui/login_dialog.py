"""
LoginDialog — модальный диалог авторизации через Telegram. Phase 7 (post-v1).

Двухшаговый flow:
  1. Ввод Telegram username → request_code → код уходит в @Jazzways_bot
  2. Ввод 6-значного кода → verify_code → JWT в keyring → close

Вызывается из WeeklyPlannerApp._setup() если нет saved token. Показывается через
root.wait_window(dialog), поэтому _setup блокируется до завершения auth.

Forest Phase E (260421-1jo):
  Primary buttons ("Запросить код", "Войти") — forest fill (accent_brand) с
  cream text (bg_primary). Back button — ghost. Error статус — clay через
  palette["accent_overdue"] вместо хардкодного error-hex. Theme-subscription
  для live-switching.

Forest Phase F (260421-1ya) — dark-parity audit:
  CTkEntry (username, code) теперь получают явные fg_color, border_color,
  text_color, placeholder_text_color из палитры. Без явных указаний CTk
  применяет дефолтный серо-синий — в forest_dark entry выглядит чужеродно.
  _apply_theme теперь обновляет и entry-колоры (live-switching пока диалог
  открыт — редкий сценарий, но покрыт).
"""
from __future__ import annotations

import logging
import socket
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from client.core.auth import AuthManager
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)


class LoginDialog:
    """Модалка авторизации. Запускается на _setup если keyring пустой."""

    WIDTH = 380
    HEIGHT = 280

    def __init__(
        self,
        root: ctk.CTk,
        theme_manager: ThemeManager,
        auth_manager: AuthManager,
        on_success: Optional[Callable[[], None]] = None,
    ) -> None:
        self._root = root
        self._theme = theme_manager
        self._auth = auth_manager
        self._on_success = on_success

        self._request_id: Optional[str] = None
        self._success: bool = False
        self._destroyed = False
        self._last_status_error: bool = False
        self._hostname = socket.gethostname()

        self._dialog = ctk.CTkToplevel(root)
        self._dialog.title("Вход — Личный Еженедельник")
        self._dialog.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self._dialog.resizable(False, False)

        # Центрировать относительно экрана
        self._dialog.update_idletasks()
        sw = self._dialog.winfo_screenwidth()
        sh = self._dialog.winfo_screenheight()
        x = (sw - self.WIDTH) // 2
        y = (sh - self.HEIGHT) // 2
        self._dialog.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        self._dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._content: Optional[ctk.CTkFrame] = None
        self._username_entry: Optional[ctk.CTkEntry] = None
        self._code_entry: Optional[ctk.CTkEntry] = None
        self._status_label: Optional[ctk.CTkLabel] = None
        self._primary_btn: Optional[ctk.CTkButton] = None
        self._back_btn: Optional[ctk.CTkButton] = None
        self._title_label: Optional[ctk.CTkLabel] = None
        self._desc_label: Optional[ctk.CTkLabel] = None

        self._build_username_step()

        # grab_set после deiconify (PITFALL из Plan 04-07)
        try:
            self._dialog.after(100, self._dialog.grab_set)
        except Exception as exc:
            logger.debug("grab_set failed: %s", exc)

        # Live theme switching
        try:
            self._theme.subscribe(self._apply_theme)
        except Exception as exc:
            logger.debug("LoginDialog theme subscribe: %s", exc)

    # ---- Public ----

    def wait(self) -> bool:
        """Блокирует вызывающий поток до закрытия диалога. Возвращает success."""
        self._root.wait_window(self._dialog)
        return self._success

    # ---- Forest styling helpers ----

    def _style_primary_button(self, btn: ctk.CTkButton) -> None:
        """Forest primary: accent_brand fill, cream text, accent_light hover."""
        try:
            btn.configure(
                fg_color=self._theme.get("accent_brand"),
                hover_color=self._theme.get("accent_brand_light"),
                text_color=self._theme.get("bg_primary"),
                font=FONTS["body_m"],
            )
        except tk.TclError:
            pass

    def _style_ghost_button(self, btn: ctk.CTkButton) -> None:
        """Ghost: transparent fill + border text_tertiary, text_secondary colour."""
        try:
            btn.configure(
                fg_color="transparent",
                border_width=1,
                border_color=self._theme.get("text_tertiary"),
                text_color=self._theme.get("text_secondary"),
                hover_color=self._theme.get("bg_tertiary"),
                font=FONTS["body"],
            )
        except tk.TclError:
            pass

    def _style_entry(self, entry: ctk.CTkEntry) -> None:
        """Forest entry: bg_secondary fill, bg_tertiary border, text_primary text
        (Phase F — без explicit set CTk подбирает дефолтный серо-синий)."""
        try:
            entry.configure(
                fg_color=self._theme.get("bg_secondary"),
                border_color=self._theme.get("bg_tertiary"),
                text_color=self._theme.get("text_primary"),
                placeholder_text_color=self._theme.get("text_tertiary"),
            )
        except tk.TclError:
            pass

    # ---- UI: Step 1 — username ----

    def _build_username_step(self) -> None:
        self._clear_content()
        bg = self._theme.get("bg_primary")
        text_primary = self._theme.get("text_primary")
        text_secondary = self._theme.get("text_secondary")

        self._dialog.configure(fg_color=bg)
        self._content = ctk.CTkFrame(self._dialog, fg_color=bg, corner_radius=0)
        self._content.pack(fill="both", expand=True, padx=24, pady=20)

        self._title_label = ctk.CTkLabel(
            self._content, text="Вход через Telegram",
            text_color=text_primary, font=FONTS["h1"],
        )
        self._title_label.pack(anchor="w", pady=(0, 4))

        self._desc_label = ctk.CTkLabel(
            self._content,
            text="Введи свой Telegram username — пришлём код в @Jazzways_bot",
            text_color=text_secondary, font=FONTS["caption"], wraplength=320, justify="left",
        )
        self._desc_label.pack(anchor="w", pady=(0, 12))

        self._username_entry = ctk.CTkEntry(
            self._content, placeholder_text="username (без @)",
            width=320, height=36, font=FONTS["body"],
        )
        self._username_entry.pack(pady=(0, 8))
        self._style_entry(self._username_entry)
        self._username_entry.bind("<Return>", lambda e: self._on_request_code())
        self._username_entry.focus_set()

        self._status_label = ctk.CTkLabel(
            self._content, text="", text_color=text_secondary, font=FONTS["caption"],
        )
        self._status_label.pack(pady=(0, 8))

        self._primary_btn = ctk.CTkButton(
            self._content, text="Запросить код",
            width=320, height=36, command=self._on_request_code,
        )
        self._primary_btn.pack()
        self._style_primary_button(self._primary_btn)
        self._back_btn = None

    # ---- UI: Step 2 — code ----

    def _build_code_step(self) -> None:
        self._clear_content()
        bg = self._theme.get("bg_primary")
        text_primary = self._theme.get("text_primary")
        text_secondary = self._theme.get("text_secondary")

        self._dialog.configure(fg_color=bg)
        self._content = ctk.CTkFrame(self._dialog, fg_color=bg, corner_radius=0)
        self._content.pack(fill="both", expand=True, padx=24, pady=20)

        self._title_label = ctk.CTkLabel(
            self._content, text="Код из Telegram",
            text_color=text_primary, font=FONTS["h1"],
        )
        self._title_label.pack(anchor="w", pady=(0, 4))

        self._desc_label = ctk.CTkLabel(
            self._content,
            text="Зайди в чат с @Jazzways_bot — там 6-значный код",
            text_color=text_secondary, font=FONTS["caption"], wraplength=320, justify="left",
        )
        self._desc_label.pack(anchor="w", pady=(0, 12))

        self._code_entry = ctk.CTkEntry(
            self._content, placeholder_text="123456",
            width=320, height=36, font=FONTS["body"], justify="center",
        )
        self._code_entry.pack(pady=(0, 8))
        self._style_entry(self._code_entry)
        self._code_entry.bind("<Return>", lambda e: self._on_verify_code())
        self._code_entry.focus_set()

        self._status_label = ctk.CTkLabel(
            self._content, text="", text_color=text_secondary, font=FONTS["caption"],
        )
        self._status_label.pack(pady=(0, 8))

        btn_row = ctk.CTkFrame(self._content, fg_color="transparent")
        btn_row.pack(fill="x")

        self._back_btn = ctk.CTkButton(
            btn_row, text="← Назад", width=100, height=36,
            command=self._build_username_step,
        )
        self._back_btn.pack(side="left")
        self._style_ghost_button(self._back_btn)

        self._primary_btn = ctk.CTkButton(
            btn_row, text="Войти", width=210, height=36,
            command=self._on_verify_code,
        )
        self._primary_btn.pack(side="right")
        self._style_primary_button(self._primary_btn)

    # ---- Handlers ----

    def _on_request_code(self) -> None:
        username = (self._username_entry.get() if self._username_entry else "").strip().lstrip("@")
        if not username:
            self._set_status("Введи username", error=True)
            return
        self._set_status("Запрашиваю код...", error=False)
        self._set_busy(True)
        self._dialog.update_idletasks()

        try:
            request_id = self._auth.request_code(username=username, hostname=self._hostname)
        except Exception as exc:
            logger.error("request_code: %s", exc)
            self._set_status(f"Ошибка: {exc}", error=True)
            self._set_busy(False)
            return

        self._request_id = request_id
        self._set_busy(False)
        self._build_code_step()

    def _on_verify_code(self) -> None:
        code = (self._code_entry.get() if self._code_entry else "").strip()
        if not code.isdigit() or len(code) != 6:
            self._set_status("Код — 6 цифр", error=True)
            return
        if self._request_id is None:
            self._set_status("request_id потерян, вернись назад", error=True)
            return
        self._set_status("Проверяю...", error=False)
        self._set_busy(True)
        self._dialog.update_idletasks()

        try:
            ok = self._auth.verify_code(
                request_id=self._request_id, code=code, device_name=self._hostname,
            )
        except Exception as exc:
            logger.error("verify_code: %s", exc)
            self._set_status(f"Ошибка: {exc}", error=True)
            self._set_busy(False)
            return

        if not ok:
            self._set_status("Код не принят. Проверь цифры.", error=True)
            self._set_busy(False)
            return

        self._success = True
        self._set_status("Успех!", error=False)
        if self._on_success is not None:
            try:
                self._on_success()
            except Exception as exc:
                logger.debug("on_success: %s", exc)
        self._close_dialog()

    # ---- Helpers ----

    def _set_status(self, text: str, error: bool = False) -> None:
        """Error → accent_overdue (clay); success/info → accent_brand (forest).

        Forest Phase E: старый error-hex удалён — цвета строго через палитру.
        """
        if self._status_label is None:
            return
        self._last_status_error = error
        color = self._theme.get("accent_overdue") if error else self._theme.get("accent_brand")
        try:
            self._status_label.configure(text=text, text_color=color)
        except tk.TclError:
            pass

    def _set_busy(self, busy: bool) -> None:
        if self._primary_btn is not None:
            try:
                self._primary_btn.configure(state="disabled" if busy else "normal")
            except tk.TclError:
                pass

    def _apply_theme(self, palette: dict) -> None:
        """Live-update при смене темы — dialog, labels, buttons, entries, status color."""
        if self._destroyed:
            return
        bg = palette.get("bg_primary")
        text_primary = palette.get("text_primary")
        text_secondary = palette.get("text_secondary")
        try:
            self._dialog.configure(fg_color=bg)
        except tk.TclError:
            return
        try:
            if self._content is not None and self._content.winfo_exists():
                self._content.configure(fg_color=bg)
        except tk.TclError:
            pass
        try:
            if self._title_label is not None and self._title_label.winfo_exists():
                self._title_label.configure(text_color=text_primary)
            if self._desc_label is not None and self._desc_label.winfo_exists():
                self._desc_label.configure(text_color=text_secondary)
        except tk.TclError:
            pass
        # Phase F: entries — палитра применяется через _style_entry (учитывает все 4 цвета).
        try:
            if (
                self._username_entry is not None
                and self._username_entry.winfo_exists()
            ):
                self._style_entry(self._username_entry)
            if (
                self._code_entry is not None
                and self._code_entry.winfo_exists()
            ):
                self._style_entry(self._code_entry)
        except tk.TclError:
            pass
        if self._primary_btn is not None:
            self._style_primary_button(self._primary_btn)
        if self._back_btn is not None:
            self._style_ghost_button(self._back_btn)
        # Refresh status color according to last error-state
        if self._status_label is not None:
            try:
                if self._status_label.winfo_exists():
                    color = (
                        palette.get("accent_overdue")
                        if self._last_status_error
                        else palette.get("accent_brand")
                    )
                    self._status_label.configure(text_color=color)
            except tk.TclError:
                pass

    def _clear_content(self) -> None:
        if self._content is not None:
            try:
                self._content.destroy()
            except tk.TclError:
                pass
        self._content = None
        self._username_entry = None
        self._code_entry = None
        self._status_label = None
        self._primary_btn = None
        self._back_btn = None
        self._title_label = None
        self._desc_label = None

    def _on_close(self) -> None:
        """Закрытие окна через крест — считаем как cancel."""
        self._success = False
        self._close_dialog()

    def _close_dialog(self) -> None:
        self._destroyed = True
        try:
            self._dialog.grab_release()
        except tk.TclError:
            pass
        try:
            self._dialog.destroy()
        except tk.TclError:
            pass
