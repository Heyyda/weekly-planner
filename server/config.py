"""
Серверная конфигурация.

Деплоится на VPS 109.94.211.29 рядом с E-bot device-manager.py.
Порт: 8100 (E-bot занимает 8000, N8N — 5678).
"""

import os

# Сервер
HOST = "0.0.0.0"
PORT = 8100

# База данных
DB_PATH = os.environ.get("PLANNER_DB", "/opt/planner/weekly_planner.db")

# JWT
JWT_SECRET = os.environ.get("PLANNER_JWT_SECRET", "CHANGE_ME_IN_PRODUCTION")
JWT_ACCESS_EXPIRE_DAYS = 7
JWT_REFRESH_EXPIRE_DAYS = 30
JWT_ALGORITHM = "HS256"

# Telegram бот (для авторизации)
TELEGRAM_BOT_TOKEN = os.environ.get("PLANNER_TG_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("PLANNER_TG_ADMIN_CHAT", "")

# Обновления
EXE_PATH = os.environ.get("PLANNER_EXE_PATH", "/opt/planner/Личный Еженедельник.exe")
DOWNLOAD_URL = "https://heyda.ru/planner/download"
