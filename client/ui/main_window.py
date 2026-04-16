"""
MainWindow — главное окно планировщика (shell, Phase 3).

Scope Phase 3:
  - Resizable CTkToplevel, min 320x320, default 460x600 (UI-SPEC)
  - Navigation header: ← стрелка, "Неделя N", → стрелка, "Сегодня" кнопка
  - Аккордеон placeholder-дней Пн-Вс (без содержимого — Phase 4 добавит)
  - Today-indicator (D-07): синяя полоска 3px слева (accent_brand) + bold заголовок
  - Persistence window size+position через SettingsStore
  - Theme-aware через ThemeManager.subscribe (today-strip перекрашивается при смене темы)

Scope Phase 4:
  - Реальные task rendering
  - Навигация между неделями (работающая)
  - Add/edit/delete задач
  - Drag-and-drop

Wire-up (Plan 03-10):
  overlay.on_click = main_window.toggle
  overlay.on_top_changed = main_window.set_always_on_top
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import date, timedelta
from typing import Optional

import customtkinter as ctk

from client.ui.settings import SettingsStore, UISettings
from client.ui.themes import FONTS, ThemeManager

logger = logging.getLogger(__name__)

DAY_NAMES_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class MainWindow:
    """Главное окно — аккордеон дней + navigation header. См. 03-UI-SPEC §Main Window.

    Lifecycle:
        1. __init__ создаёт CTkToplevel, withdrawn (невидим).
        2. show() / hide() / toggle() управляют видимостью.
        3. set_always_on_top() проксирует OVR-06 toggle из OverlayManager.
        4. При close через крест (WM_DELETE_WINDOW) — hide, не destroy (app живёт в tray).
        5. destroy() — финальный cleanup при выходе приложения.
    """

    MIN_SIZE = (320, 320)
    DEFAULT_SIZE = (460, 600)
    TODAY_STRIP_WIDTH = 3  # D-07: синяя полоска 3px слева today-секции

    def __init__(
        self,
        root: ctk.CTk,
        settings_store: SettingsStore,
        settings: UISettings,
        theme_manager: ThemeManager,
    ) -> None:
        self._root = root
        self._settings_store = settings_store
        self._settings = settings
        self._theme = theme_manager

        # Создаём Toplevel как дочернее окно root (требуется CTkToplevel)
        self._window = ctk.CTkToplevel(root)
        self._window.withdraw()
        self._window.title("Личный Еженедельник")
        self._window.minsize(*self.MIN_SIZE)

        # Восстановить размер из settings
        w, h = self._resolve_initial_size()
        self._window.geometry(f"{w}x{h}")

        # Восстановить позицию (None = CTk автоцентрирует)
        pos = self._settings.window_position
        if pos is not None and len(pos) == 2:
            try:
                x, y = int(pos[0]), int(pos[1])
                self._window.geometry(f"{w}x{h}+{x}+{y}")
            except (TypeError, ValueError):
                pass

        # Always-on-top из settings
        try:
            self._window.attributes("-topmost", self._settings.on_top)
        except tk.TclError:
            pass

        # WM_DELETE_WINDOW → hide (не exit), реальный выход через tray
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        # D-07: reference к today-strip (CTkFrame 3px accent_brand). None если секция не today.
        self._today_strip: Optional[ctk.CTkFrame] = None
        # Карта i → strip (None для не-today дней), для проверки в тестах
        self._today_strip_map: dict[int, Optional[ctk.CTkFrame]] = {}
        self._day_sections: list[ctk.CTkFrame] = []

        self._build_ui()

        # Theme subscribe — получать уведомления при смене темы
        self._theme.subscribe(self._apply_theme)
        # Немедленно применяем текущую тему
        self._apply_theme({
            "bg_primary": self._theme.get("bg_primary"),
            "text_primary": self._theme.get("text_primary"),
            "bg_secondary": self._theme.get("bg_secondary"),
            "accent_brand": self._theme.get("accent_brand"),
        })

        # Сохранять размер при Configure events (resize, move)
        self._window.bind("<Configure>", self._on_configure)

    # ---- Public API ----

    def show(self) -> None:
        """Показать главное окно и поднять поверх остальных."""
        self._window.deiconify()
        self._window.lift()

    def hide(self) -> None:
        """Скрыть главное окно (не destroy — продолжает работать в tray)."""
        self._window.withdraw()

    def toggle(self) -> None:
        """Переключить видимость. Wired к overlay.on_click (Plan 03-10)."""
        if self.is_visible():
            self.hide()
        else:
            self.show()

    def is_visible(self) -> bool:
        """True если окно видимо (не withdrawn)."""
        try:
            return self._window.winfo_viewable() != 0
        except tk.TclError:
            return False

    def set_always_on_top(self, enabled: bool) -> None:
        """Применить OVR-06 always-on-top toggle. Вызывается из OverlayManager.on_top_changed."""
        try:
            self._window.attributes("-topmost", enabled)
        except tk.TclError:
            pass

    def destroy(self) -> None:
        """Финальный cleanup при выходе приложения."""
        try:
            self._window.destroy()
        except Exception as exc:
            logger.debug("MainWindow destroy: %s", exc)

    # ---- Theme ----

    def _apply_theme(self, palette: dict) -> None:
        """ThemeManager.subscribe callback — перекрасить контейнеры.

        D-07: today-strip (если есть) перекрашивается в palette['accent_brand'].
        """
        bg = palette.get("bg_primary", "#F5EFE6")
        bg_sec = palette.get("bg_secondary", bg)
        accent = palette.get("accent_brand", "#1E73E8")
        try:
            self._window.configure(fg_color=bg)
            if hasattr(self, "_root_frame"):
                self._root_frame.configure(fg_color=bg)
            for section in self._day_sections:
                try:
                    section.configure(fg_color=bg_sec)
                except tk.TclError:
                    pass
            # D-07: today-strip реагирует на смену темы
            if self._today_strip is not None:
                try:
                    self._today_strip.configure(fg_color=accent)
                except tk.TclError:
                    pass
        except tk.TclError:
            pass

    # ---- Layout ----

    def _build_ui(self) -> None:
        """Построить UI: navigation header + scrollable аккордеон 7 дней."""
        self._root_frame = ctk.CTkFrame(self._window, corner_radius=0)
        self._root_frame.pack(fill="both", expand=True)

        # Navigation header — placeholder кнопок ← Неделя N → Сегодня
        header = ctk.CTkFrame(self._root_frame, height=40, corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkButton(header, text="←", width=32, command=lambda: None).pack(
            side="left", padx=4, pady=4
        )
        ctk.CTkLabel(
            header,
            text="Неделя 16  14-20 апр",
            font=FONTS["h1"],
        ).pack(side="left", expand=True)
        ctk.CTkButton(header, text="Сегодня", width=72, command=lambda: None).pack(
            side="left", padx=4, pady=4
        )
        ctk.CTkButton(header, text="→", width=32, command=lambda: None).pack(
            side="left", padx=4, pady=4
        )

        # Scrollable аккордеон дней
        scroll = ctk.CTkScrollableFrame(self._root_frame)
        scroll.pack(fill="both", expand=True, padx=8, pady=4)

        # 7 placeholder-секций Пн–Вс
        today = date.today()
        monday = today - timedelta(days=today.weekday())  # weekday(): Пн=0..Вс=6

        for i in range(7):
            d = monday + timedelta(days=i)
            is_today = (d == today)
            section = self._build_day_section(scroll, DAY_NAMES_RU[i], d, is_today=is_today)
            self._day_sections.append(section)
            # Карта для тестирования: i → strip (или None)
            self._today_strip_map[i] = self._today_strip if is_today else None

    def _build_day_section(
        self,
        parent,
        day_name: str,
        d: date,
        is_today: bool,
    ) -> ctk.CTkFrame:
        """Placeholder-секция дня: заголовок + пустое тело. Phase 4 заменит task list.

        D-07 (today-specific): если is_today=True — добавить ДВА индикатора:
          (a) Синяя вертикальная полоска 3px слева (accent_brand color).
          (b) Bold font для заголовка + суффикс "• сегодня".
        Секции НЕ сегодня — обычный заголовок без strip.
        """
        section = ctk.CTkFrame(parent, corner_radius=6)
        section.pack(fill="x", pady=4)

        # Горизонтальный контейнер: [strip | header_content]
        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x")

        # D-07 (a): blue strip 3px слева — ТОЛЬКО для today-секции
        if is_today:
            accent = self._theme.get("accent_brand")
            strip = ctk.CTkFrame(
                row,
                width=self.TODAY_STRIP_WIDTH,
                fg_color=accent,
                corner_radius=0,
            )
            strip.pack(side="left", fill="y", padx=(0, 6))
            strip.pack_propagate(False)  # фиксируем ширину 3px
            self._today_strip = strip  # сохраняем reference для _apply_theme

        # Header content
        header_frame = ctk.CTkFrame(row, fg_color="transparent")
        header_frame.pack(side="left", fill="x", expand=True)

        # D-07 (b): bold font для today + суффикс "• сегодня"
        label_text = f"{day_name} {d.day}"
        if is_today:
            label_text += "  • сегодня"

        font = FONTS["body"]
        if is_today:
            # bold override: (family, size, "bold")
            font = (font[0], font[1], "bold")

        ctk.CTkLabel(header_frame, text=label_text, font=font).pack(
            side="left", padx=8, pady=6
        )
        # Placeholder счётчика задач
        ctk.CTkLabel(header_frame, text="(0)", font=FONTS["caption"]).pack(
            side="right", padx=8
        )

        return section

    # ---- Persistence ----

    def _resolve_initial_size(self) -> tuple[int, int]:
        """Получить размер окна из settings, с fallback на DEFAULT_SIZE."""
        ws = self._settings.window_size
        try:
            w, h = int(ws[0]), int(ws[1])
            if w >= self.MIN_SIZE[0] and h >= self.MIN_SIZE[1]:
                return (w, h)
        except (TypeError, ValueError, IndexError):
            pass
        return self.DEFAULT_SIZE

    def _on_configure(self, event) -> None:
        """Configure event (resize/move) — обновляем settings в памяти.

        Сохраняем на диск только при close, не на каждый пиксель.
        """
        if event.widget is self._window:
            try:
                new_size = [self._window.winfo_width(), self._window.winfo_height()]
                new_pos = [self._window.winfo_x(), self._window.winfo_y()]
                if new_size != self._settings.window_size:
                    self._settings.window_size = new_size
                    self._settings.window_position = new_pos
            except tk.TclError:
                pass

    def _on_close(self) -> None:
        """WM_DELETE_WINDOW — сохранить состояние и скрыть (не destroy).

        Приложение остаётся живым в system tray.
        """
        self._save_window_state()
        self.hide()

    def _save_window_state(self) -> None:
        """Сохранить размер и позицию окна в settings.json через SettingsStore."""
        try:
            self._settings.window_size = [
                self._window.winfo_width(),
                self._window.winfo_height(),
            ]
            self._settings.window_position = [
                self._window.winfo_x(),
                self._window.winfo_y(),
            ]
            self._settings_store.save(self._settings)
            logger.debug("MainWindow state saved: %s", self._settings.window_size)
        except tk.TclError as exc:
            logger.debug("_save_window_state skip: %s", exc)
