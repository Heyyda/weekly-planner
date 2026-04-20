"""
ThemeManager — 5 тем (light cream, dark warm, beige sepia, forest_light, forest_dark) + subscriber pattern.

Паттерн subscribe/notify избегает PITFALLS.md Pitfall 5: виджеты НЕ хардкодят цвета,
а получают палитру через callback при смене темы. Live-switching без рестарта.

Hex-токены light/dark/beige — verbatim из .planning/phases/03-overlay-system/03-UI-SPEC.md §Color Palette.
Hex-токены forest_light/forest_dark — из Forest refactor spec (Phase A, 260420-x69).
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

import customtkinter as ctk

logger = logging.getLogger(__name__)

# ---- Palettes (verbatim from UI-SPEC §Color Palette) ----

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg_primary": "#F5EFE6",
        "bg_secondary": "#EDE6D9",
        "bg_tertiary": "#E6DDC9",
        "text_primary": "#2B2420",
        "text_secondary": "#6B5E4E",
        "text_tertiary": "#9A8F7D",
        "accent_brand": "#1E73E8",
        "accent_brand_light": "#4EA1FF",
        "accent_done": "#38A169",
        "accent_overdue": "#E85A5A",
        "shadow_card": "rgba(70, 55, 40, 0.08)",
    },
    "dark": {
        "bg_primary": "#1F1B16",
        "bg_secondary": "#2B2620",
        "bg_tertiary": "#3A332C",
        "text_primary": "#F0E9DC",
        "text_secondary": "#B8AE9C",
        "text_tertiary": "#7A715F",
        "accent_brand": "#4EA1FF",
        "accent_brand_light": "#85BFFF",
        "accent_done": "#48B97D",
        "accent_overdue": "#F07272",
        "shadow_card": "rgba(0, 0, 0, 0.3)",
    },
    "beige": {
        "bg_primary": "#E8DDC4",
        "bg_secondary": "#D9CFB8",
        "bg_tertiary": "#C9BEA2",
        "text_primary": "#3D2F1F",
        "text_secondary": "#6E5F48",
        "text_tertiary": "#968769",
        "accent_brand": "#2966C4",
        "accent_brand_light": "#4E86DA",
        "accent_done": "#4A7A3D",
        "accent_overdue": "#C04B3C",
        "shadow_card": "rgba(80, 55, 30, 0.12)",
    },
    "forest_light": {
        "bg_primary": "#EEE9DC",
        "bg_secondary": "#F5F0E3",
        "bg_tertiary": "#E2E0D2",
        "text_primary": "#2E2B24",
        "text_secondary": "#6A6558",
        "text_tertiary": "#9A958A",
        "accent_brand": "#1E5239",
        "accent_brand_light": "#234E3A",
        "accent_done": "#1E5239",
        "accent_overdue": "#9E6A5A",
        "shadow_card": "rgba(30, 40, 32, 0.10)",
    },
    "forest_dark": {
        "bg_primary": "#161E1A",
        "bg_secondary": "#202A24",
        "bg_tertiary": "#1B2620",
        "text_primary": "#E6E3D5",
        "text_secondary": "#A5A89A",
        "text_tertiary": "#6E7168",
        "accent_brand": "#5E9E7A",
        "accent_brand_light": "#6BAF8A",
        "accent_done": "#5E9E7A",
        "accent_overdue": "#B87D6F",
        "shadow_card": "rgba(0, 0, 0, 0.35)",
    },
}

# ---- Fonts — Segoe UI (доступен Win7+ и на Win10, и на Win11).
# Ранее использовался Segoe-UI-Variable шрифт из Win11 — на Win10 tkinter
# silent fallback'ил на MS Sans Serif (Hotfix 260421-0jb).
_FONT_FAMILY = "Segoe UI"
_FONT_MONO = "Cascadia Mono"

FONTS: dict[str, tuple] = {
    "h1":      (_FONT_FAMILY, 16, "bold"),     # Week header
    "h2":      (_FONT_FAMILY, 14, "bold"),     # Day header
    "body":    (_FONT_FAMILY, 13, "normal"),   # Task text
    "body_m":  (_FONT_FAMILY, 13, "bold"),     # Emphasis
    "caption": (_FONT_FAMILY, 11, "normal"),   # Meta (counts, hints)
    "small":   (_FONT_FAMILY, 10, "normal"),   # Tiny labels
    "icon":    (_FONT_FAMILY, 24, "bold"),
    "mono":    (_FONT_MONO, 12, "normal"),     # Time display
}


class ThemeManager:
    """
    Держит текущую тему, оповещает подписчиков при set_theme.

    Canonical usage:
        tm = ThemeManager()
        tm.subscribe(lambda palette: widget.configure(fg_color=palette["bg_primary"]))
        tm.set_theme("dark")  # все подписчики вызываются
    """

    def __init__(self, initial: str = "forest_light") -> None:
        self._theme: str = initial if initial in PALETTES else "forest_light"
        self._callbacks: list[Callable[[dict[str, str]], None]] = []

    @property
    def current(self) -> str:
        """Текущая активная тема: 'light' | 'dark' | 'beige' | 'forest_light' | 'forest_dark'."""
        return self._theme

    def subscribe(self, callback: Callable[[dict[str, str]], None]) -> None:
        """Регистрация callback — каждый виджет/менеджер вызывает при старте."""
        self._callbacks.append(callback)

    def set_theme(self, theme: str) -> None:
        """
        Установить тему. Поддерживает 'system' — резолвит через detect_system_theme().
        Вызывает все callbacks с новой палитрой.
        """
        if theme == "system":
            theme = self.detect_system_theme()
        if theme not in PALETTES:
            logger.warning("Неизвестная тема %r — fallback на forest_light", theme)
            theme = "forest_light"
        self._theme = theme
        # CustomTkinter built-in mode (для стандартных CTk виджетов)
        try:
            ctk.set_appearance_mode("dark" if theme == "dark" else "light")
        except Exception as exc:
            logger.debug("CTk set_appearance_mode failed: %s", exc)
        palette = PALETTES[theme]
        for cb in self._callbacks:
            try:
                cb(palette)
            except Exception as exc:
                logger.error("Theme callback failed: %s", exc)

    def get(self, key: str) -> str:
        """Получить hex-цвет из текущей палитры. Fallback на #ffffff если key неизвестен."""
        return PALETTES[self._theme].get(key, "#ffffff")

    @staticmethod
    def detect_system_theme() -> str:
        """Reads HKCU\\...\\Themes\\Personalize\\AppsUseLightTheme. Returns 'light' or 'dark'."""
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if value else "dark"
        except Exception:
            return "light"
