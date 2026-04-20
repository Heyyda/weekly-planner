"""
REST API — FastAPI приложение.

Endpoints:
  POST /api/auth/request     — запросить код подтверждения
  POST /api/auth/verify      — подтвердить код, получить JWT
  POST /api/auth/refresh     — обновить access token
  GET  /api/auth/me          — информация о текущем пользователе

  GET  /api/weeks/{start}    — получить неделю с задачами
  POST /api/sync             — отправить изменения, получить актуальные данные
  GET  /api/overdue          — все просроченные задачи

  GET  /api/categories       — список категорий
  POST /api/categories       — создать категорию

  GET  /api/templates        — повторяющиеся шаблоны
  POST /api/templates        — создать шаблон

  GET  /api/version          — текущая версия + download URL + SHA256

Запуск: uvicorn server.api:app --host 0.0.0.0 --port 8100
"""

from fastapi import FastAPI

app = FastAPI(
    title="Личный Еженедельник API",
    version="0.1.0",
    docs_url="/api/docs",
)


# TODO: Реализовать роуты
# Порядок реализации:
# 1. /api/version — самый простой, для проверки что сервер работает
# 2. /api/auth/* — авторизация
# 3. /api/weeks/{start} — чтение недели
# 4. /api/sync — запись изменений
# 5. /api/overdue — просроченные задачи
# 6. /api/categories, /api/templates — вспомогательные


@app.get("/api/version")
async def get_version():
    return {
        "version": "0.1.0",
        "download_url": "https://heyda.ru/planner/download",
        "sha256": "",
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}
