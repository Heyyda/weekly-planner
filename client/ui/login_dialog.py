"""
LoginDialog — модальный диалог авторизации через Telegram. Phase 7 (post-v1).

Двухшаговый flow:
  1. Ввод Telegram username → request_code → код уходит в @Jazzways_bot
  2. Ввод 6-значного кода → verify_code → JWT в keyring → close

Вызывается из WeeklyPlannerApp._setup() если нет saved token. Показывается через
root.wait_window(dialog), поэтому _setup блокируется до завершения auth.
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

        self._build_username_step()

        # grab_set после deiconify (PITFALL из Plan 04-07)
        try:
            self._dialog.after(100, self._dialog.grab_set)
        except Exception as exc:
            logger.debug("grab_set failed: %s", exc)

    # ---- Public ----

    def wait(self) -> bool:
        """Блокирует вызывающий поток до закрытия диалога. Возвращает success."""
        self._root.wait_window(self._dialog)
        return self._success

    # ---- UI: Step 1 — username ----

    def _build_username_step(self) -> None:
        self._clear_content()
        bg = self._theme.get("bg_primary")
        text_primary = self._theme.get("text_primary")

        self._dialog.configure(fg_color=bg)
        self._content = ctk.CTkFrame(self._dialog, fg_color=bg, corner_radius=0)
        self._content.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            self._content, text="Вход через Telegram",
            text_color=text_primary, font=FONTS["h1"],
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            self._content,
            text="Введи свой Telegram username — пришлём код в @Jazzways_bot",
            text_color=text_primary, font=FONTS["caption"], wraplength=320, justify="left",
        ).pack(anchor="w", pady=(0, 12))

        self._username_entry = ctk.CTkEntry(
            self._content, placeholder_text="username (без @)",
            width=320, height=36, font=FONTS["body"],
        )
        self._username_entry.pack(pady=(0, 8))
        self._username_entry.bind("<Return>", lambda e: self._on_request_code())
        self._username_entry.focus_set()

        self._status_label = ctk.CTkLabel(
            self._content, text="", text_color=text_primary, font=FONTS["caption"],
        )
        self._status_label.pack(pady=(0, 8))

        self._primary_btn = ctk.CTkButton(
            self._content, text="Запросить код",
            width=320, height=36, command=self._on_request_code,
        )
        self._primary_btn.pack()

    # ---- UI: Step 2 — code ----

    def _build_code_step(self) -> None:
        self._clear_content()
        bg = self._theme.get("bg_primary")
        text_primary = self._theme.get("text_primary")

        self._dialog.configure(fg_color=bg)
        self._content = ctk.CTkFrame(self._dialog, fg_color=bg, corner_radius=0)
        self._content.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            self._content, text="Код из Telegram",
            text_color=text_primary, font=FONTS["h1"],
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            self._content,
            text="Зайди в чат с @Jazzways_bot — там 6-значный код",
            text_color=text_primary, font=FONTS["caption"], wraplength=320, justify="left",
        ).pack(anchor="w", pady=(0, 12))

        self._code_entry = ctk.CTkEntry(
            self._content, placeholder_text="123456",
            width=320, height=36, font=FONTS["body"], justify="center",
        )
        self._code_entry.pack(pady=(0, 8))
        self._code_entry.bind("<Return>", lambda e: self._on_verify_code())
        self._code_entry.focus_set()

        self._status_label = ctk.CTkLabel(
            self._content, text="", text_color=text_primary, font=FONTS["caption"],
        )
        self._status_label.pack(pady=(0, 8))

        btn_row = ctk.CTkFrame(self._content, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(
            btn_row, text="← Назад", width=100, height=36,
            fg_color="transparent", border_width=1,
            text_color=text_primary, hover_color=self._theme.get("bg_secondary"),
            command=self._build_username_step,
        ).pack(side="left")

        self._primary_btn = ctk.CTkButton(
            btn_row, text="Войти", width=210, height=36,
            command=self._on_verify_code,
        )
        self._primary_btn.pack(side="right")

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
        if self._status_label is None:
            return
        color = "#C94A4A" if error else self._theme.get("accent_brand")
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

    def _on_close(self) -> None:
        """Закрытие окна через крест — считаем как cancel."""
        self._success = False
        self._close_dialog()

    def _close_dialog(self) -> None:
        try:
            self._dialog.grab_release()
        except tk.TclError:
            pass
        try:
            self._dialog.destroy()
        except tk.TclError:
            pass
