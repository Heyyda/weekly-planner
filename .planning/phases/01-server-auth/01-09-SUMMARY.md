---
phase: "01-server-auth"
plan: "09"
subsystem: "bot"
tags: ["aiogram", "telegram", "auth", "chat_id"]
dependency_graph:
  requires: ["01-02 (User model)", "01-03 (db engine)"]
  provides: ["telegram_chat_id для auth-flow", "planner-bot entry point"]
  affects: ["01-10 (deploy — создаст planner-bot.service unit)"]
tech_stack:
  added: ["aiogram 3.x (long-polling bot)"]
  patterns: ["Router-based handler registration", "AsyncSessionLocal in standalone process (без FastAPI DI)"]
key_files:
  created:
    - "server/bot/handlers.py"
    - "server/bot/main.py"
    - "server/tests/test_bot_handlers.py"
  modified: []
decisions:
  - "object.__setattr__ для патчинга frozen aiogram Message в тестах (pydantic frozen model)"
  - "Long-polling (dp.start_polling) vs webhook: long-polling проще для VPS без публичного домена на момент Фазы 1"
  - "drop_pending_updates=True при старте — игнорировать накопившиеся /start во время простоя"
metrics:
  duration_seconds: 141
  completed_date: "2026-04-15"
  tasks_completed: 2
  files_created: 3
  files_modified: 0
---

# Phase 01 Plan 09: aiogram /start handler — Summary

**One-liner:** aiogram 3.x /start handler записывает telegram_chat_id в БД через AsyncSessionLocal — предпосылка для auth-flow без FastAPI DI.

## Что сделано

### Полный flow после этого плана

```
Пользователь → @Jazzways_bot /start
  → handle_start() проверяет username в ALLOWED_USERNAMES
  → если ОК: select/insert User, записывает telegram_chat_id
  → отвечает: "Привет! Я бот Личного Еженедельника. Теперь могу слать коды..."

Клиент → POST /api/auth/request-code {username}
  → auth_routes: ищет User.telegram_chat_id
  → если chat_id IS NOT NULL: отправляет код через bot.send_message(chat_id, code)
  → если chat_id IS NULL: возвращает ошибку "сначала напишите /start боту"
```

### Архитектура запуска

```
planner-bot.service (Plan 10 deploy создаст unit)
  ExecStart=/opt/planner/venv/bin/python -m server.bot.main
  EnvironmentFile=/etc/planner/planner.env
  Restart=always
  RestartSec=5s

Логирование: stdout → journalctl -u planner-bot -f
Формат: "%(asctime)s %(levelname)s %(name)s: %(message)s"
```

### Расширяемость (Фаза 5)

Фаза 5 только добавляет новые router'ы в `create_dispatcher()`:
```python
def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(start_router)      # Фаза 1 — уже есть
    dp.include_router(tasks_router)      # Фаза 5 — добавится
    dp.include_router(week_router)       # Фаза 5 — добавится
    return dp
```
`main.py` не меняется.

## Файлы

| Файл | Описание |
|------|----------|
| `server/bot/handlers.py` | Router + /start handler, allow-list check, DB write |
| `server/bot/main.py` | create_dispatcher(), create_bot(), main() long-polling |
| `server/tests/test_bot_handlers.py` | 5 unit тестов без реального Telegram API |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Frozen pydantic Model при патчинге message.answer**
- **Found during:** Task 2 (тесты)
- **Issue:** `aiogram.types.Message` является замороженной pydantic-моделью (`model_config = ConfigDict(frozen=True)`). Прямое присваивание `msg.answer = AsyncMock()` выбрасывает `ValidationError: Instance is frozen`.
- **Fix:** Заменил `msg.answer = AsyncMock()` на `object.__setattr__(msg, "answer", AsyncMock())` в `_make_message()`. Обходит pydantic freeze через Python low-level API.
- **Files modified:** `server/tests/test_bot_handlers.py`
- **Commit:** fb9e035

## Test Results

```
5 passed in 1.56s
- test_start_allowed_user_registers_chat_id  PASSED
- test_start_no_username                     PASSED
- test_start_not_allowed_user                PASSED
- test_start_idempotent_updates_chat_id      PASSED
- test_start_allowed_user_case_insensitive   PASSED
```

## Self-Check: PASSED

- server/bot/handlers.py: EXISTS
- server/bot/main.py: EXISTS
- server/tests/test_bot_handlers.py: EXISTS
- Commit e2843af (Task 1): EXISTS
- Commit fb9e035 (Task 2): EXISTS
- 5 tests: PASSED
