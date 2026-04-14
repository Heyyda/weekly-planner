"""
Главный класс приложения.
Управляет окном, sidebar-поведением, навигацией между экранами.
"""

import customtkinter as ctk

from client.ui.sidebar import SidebarManager
from client.ui.week_view import WeekView
from client.ui.themes import ThemeManager
from client.core.storage import LocalStorage
from client.core.models import AppState


class WeeklyPlannerApp:
    """
    Основное окно приложения.

    Жизненный цикл:
    1. Инициализация окна (overrideredirect, topmost)
    2. Проверка авторизации → если нет, показать экран логина
    3. Загрузка локального кеша → отрисовка текущей недели
    4. Фоновая синхронизация с сервером
    5. Запуск system tray иконки
    6. Запуск слушателя глобальных хоткеев
    """

    # Размеры панели
    PANEL_WIDTH = 360          # ширина развёрнутой панели
    PANEL_COLLAPSED_WIDTH = 6  # видимая полоска в свёрнутом состоянии
    ANIMATION_STEP = 20        # пикселей за кадр
    ANIMATION_DELAY = 12       # мс между кадрами

    def __init__(self, version: str = "0.1.0"):
        self.version = version
        self.state = AppState()

        # CustomTkinter настройки
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Личный Еженедельник")
        self.root.overrideredirect(True)  # без рамки
        self.root.attributes("-topmost", True)

        # Компоненты (инициализируются в _setup)
        self.sidebar: SidebarManager = None
        self.week_view: WeekView = None
        self.theme: ThemeManager = None
        self.storage: LocalStorage = None

    def _setup(self):
        """Инициализация всех компонентов после создания окна."""
        # TODO: Реализовать
        # 1. ThemeManager — загрузить сохранённую тему
        # 2. SidebarManager — настроить позицию, анимацию, события мыши
        # 3. LocalStorage — загрузить кеш
        # 4. Auth check — проверить JWT в keyring
        # 5. WeekView — отрисовать текущую неделю
        # 6. System tray — запустить иконку
        # 7. Hotkeys — зарегистрировать глобальный хоткей
        # 8. Sync — запустить фоновую синхронизацию
        # 9. Notifications — проверить просроченные задачи
        pass

    def run(self):
        """Запуск основного цикла приложения."""
        self._setup()
        self.root.mainloop()

    def destroy(self):
        """Корректное завершение."""
        # TODO: сохранить состояние, остановить sync, убрать tray
        self.root.destroy()
