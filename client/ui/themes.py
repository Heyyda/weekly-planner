"""
Theme Manager — тёмная и светлая темы.

Цветовая палитра минималистичная, приятная для глаз.
Вдохновение: Notion sidebar, Todoist, Linear.
"""


# Тёмная тема
DARK = {
    "bg_primary": "#1a1a2e",       # фон панели
    "bg_secondary": "#16213e",     # фон секций
    "bg_hover": "#1f2b47",         # при наведении
    "bg_today": "#1a2744",         # подсветка сегодня
    "text_primary": "#e0e0e0",     # основной текст
    "text_secondary": "#8a8a9a",   # приглушённый текст
    "text_done": "#555566",        # зачёркнутый текст
    "accent": "#4a9eff",           # акцентный синий
    "accent_hover": "#6ab4ff",
    "priority_high": "#ff4757",    # красный (приоритет 1)
    "priority_low": "#747d8c",     # серый (приоритет 3)
    "overdue_bg": "#2d1b1b",       # фон просроченной задачи
    "overdue_dot": "#ff6b6b",      # индикатор просрочки
    "border": "#2a2a3e",           # разделители
    "scrollbar": "#333355",
    "trigger_strip": "#4a9eff",    # полоска-триггер sidebar
}

# Светлая тема
LIGHT = {
    "bg_primary": "#ffffff",
    "bg_secondary": "#f8f9fa",
    "bg_hover": "#f0f1f3",
    "bg_today": "#eef4ff",
    "text_primary": "#1a1a2e",
    "text_secondary": "#6c757d",
    "text_done": "#adb5bd",
    "accent": "#2563eb",
    "accent_hover": "#3b82f6",
    "priority_high": "#dc2626",
    "priority_low": "#9ca3af",
    "overdue_bg": "#fef2f2",
    "overdue_dot": "#ef4444",
    "border": "#e5e7eb",
    "scrollbar": "#d1d5db",
    "trigger_strip": "#2563eb",
}

# Шрифты
FONTS = {
    "heading": ("Segoe UI", 14, "bold"),   # заголовки дней
    "task": ("Segoe UI", 13),              # текст задач
    "task_done": ("Segoe UI", 13),         # + overstrike
    "small": ("Segoe UI", 11),             # мета-информация
    "stats": ("Segoe UI", 12, "bold"),     # статистика
    "nav": ("Segoe UI", 13, "bold"),       # навигация по неделям
    "notes": ("Consolas", 12),             # заметки (моно)
}


class ThemeManager:
    """
    Переключение тем и применение цветов к виджетам.
    """

    def __init__(self, mode: str = "dark"):
        self.mode = mode
        self.colors = DARK if mode == "dark" else LIGHT

    def toggle(self):
        """Переключить тему."""
        self.mode = "light" if self.mode == "dark" else "dark"
        self.colors = DARK if self.mode == "dark" else LIGHT
        # TODO: применить ко всем виджетам

    def get(self, key: str) -> str:
        """Получить цвет по ключу."""
        return self.colors.get(key, "#ffffff")
