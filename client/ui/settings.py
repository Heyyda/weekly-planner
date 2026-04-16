"""
UISettings — dataclass-схема для settings.json (Phase 3).

Источник: 03-CONTEXT.md D-25 (LocalStorage.save_settings/load_settings как транспорт).
SettingsStore — тонкая обёртка: никакой новой I/O, только маршалинг dataclass ↔ dict.

Пороги настроек:
    theme: "light" | "dark" | "beige" | "system"
    task_style: "card" | "line" | "minimal"
    notifications_mode: "sound_pulse" | "pulse_only" | "silent"
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field, fields
from typing import Optional

from client.core.storage import LocalStorage

logger = logging.getLogger(__name__)

VALID_THEMES = {"light", "dark", "beige", "system"}
VALID_TASK_STYLES = {"card", "line", "minimal"}
VALID_NOTIFICATIONS = {"sound_pulse", "pulse_only", "silent"}


@dataclass
class UISettings:
    """Пользовательские настройки UI. Сохраняется в settings.json как dict."""
    theme: str = "light"
    task_style: str = "card"
    notifications_mode: str = "sound_pulse"
    on_top: bool = True
    autostart: bool = False
    overlay_position: list = field(default_factory=lambda: [100, 100])   # [x, y]
    window_size: list = field(default_factory=lambda: [460, 600])         # [w, h]
    window_position: Optional[list] = None                                 # [x, y] или None (центр)
    version: int = 1

    def to_dict(self) -> dict:
        """Сериализовать в dict для JSON (через dataclasses.asdict)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UISettings":
        """Backward/forward compat: игнорируем неизвестные ключи, подставляем defaults для отсутствующих."""
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in (data or {}).items() if k in known}
        return cls(**filtered)

    def validate(self) -> None:
        """Чистит невалидные значения на defaults. Вызывается после load()."""
        if self.theme not in VALID_THEMES:
            logger.warning("Неизвестная theme %r — reset на light", self.theme)
            self.theme = "light"
        if self.task_style not in VALID_TASK_STYLES:
            logger.warning("Неизвестный task_style %r — reset на card", self.task_style)
            self.task_style = "card"
        if self.notifications_mode not in VALID_NOTIFICATIONS:
            logger.warning(
                "Неизвестный notifications_mode %r — reset на sound_pulse",
                self.notifications_mode,
            )
            self.notifications_mode = "sound_pulse"


class SettingsStore:
    """Обёртка поверх LocalStorage.load_settings/save_settings."""

    def __init__(self, storage: LocalStorage) -> None:
        self._storage = storage

    def load(self) -> UISettings:
        """Load from settings.json или defaults если пусто/коррупция."""
        raw = self._storage.load_settings()
        settings = UISettings.from_dict(raw)
        settings.validate()
        return settings

    def save(self, settings: UISettings) -> None:
        """Atomic save через LocalStorage (tmp+os.replace)."""
        self._storage.save_settings(settings.to_dict())
