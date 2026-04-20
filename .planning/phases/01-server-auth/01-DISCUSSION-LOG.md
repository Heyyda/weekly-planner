# Phase 1: Сервер и авторизация — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 01-server-auth
**Areas discussed:** Telegram-бот

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Telegram-бот | Один бот на всё или два разных | ✓ |
| Production URL | Прямой IP:порт или поддомен HTTPS | |
| Auth code UX | Длина, срок, single-use, rate-limit | |
| JWT lifetime | Access/refresh TTL | |

**User's choice:** Telegram-бот (единственная область для обсуждения; остальные оставлены на усмотрение Claude)
**Notes:** Владелец явно доверил стандартные решения по URL/code/JWT — требование скорости инициализации.

---

## Telegram-бот

### Q1: Один бот на всё или два разных?

| Option | Description | Selected |
|--------|-------------|----------|
| Один бот | В Фазе 1 шлёт auth-коды; в Фазе 5 получает /add, /week, /today. Одна иконка в Telegram, один token на VPS | ✓ |
| Два бота | @planner_auth_bot + @planner_bot. Разделение ответственности, но два token'а и systemd-юнита | |

**User's choice:** Один бот
**Notes:** Простота, одна иконка у владельца в чате, один ресурс на VPS.

### Q2: Есть ли уже бот которого переиспользуем или создать новый?

| Option | Description | Selected |
|--------|-------------|----------|
| Создать новый | Зарегистрировать в @BotFather | |
| Переиспользовать E-bot'овского | Усложнит E-bot | |
| У меня есть подходящий | Владелец расскажет | ✓ |

**User's choice:** У меня есть подходящий (`@Jazzways_bot`, токен `7752471809:AAH...vA0` передан в чате, нигде не используется)
**Notes:** Токен засвечен в чате — **требует ревока через `@BotFather` /revoke** при деплое. Решение зафиксировано как D-03 в CONTEXT.md.

### Q3: Переименовать бота?

| Option | Description | Selected |
|--------|-------------|----------|
| Оставить как есть | @Jazzways_bot — личный проект, имя неважно | ✓ |
| Переименовать | Через @BotFather /setname + /setusername | |

**User's choice:** Оставить как есть
**Notes:** Экономия времени, для личного проекта семантика имени не критична.

### Q4: Как бот присылает код авторизации?

| Option | Description | Selected |
|--------|-------------|----------|
| Только код | "123456 — код для входа" | |
| Код + контекст | Запрошен вход с устройства X в HH:MM. Код: 123456. Срок: 5 мин. Если это не ты — игнорируй. | ✓ |
| Код + инлайн-кнопка | Кнопка "Это не я" — дороже в реализации | |

**User's choice:** Код + контекст
**Notes:** Владелец выбрал форматированный сигнал с контекстом но без interactive-кнопки — баланс UX и сложности.

---

## Decision Gate: готов к CONTEXT.md?

| Option | Description | Selected |
|--------|-------------|----------|
| Готов к CONTEXT.md | Остальные gray areas отдать на усмотрение Claude (стандартные практики) | ✓ |
| Обсудить ещё | Production URL / Auth UX / JWT lifetime | |

**User's choice:** Готов к CONTEXT.md
**Notes:** Явно делегированные Claude'у области (D-06 до D-27) — с рационализацией в CONTEXT.md.

---

## Claude's Discretion

Владелец явно передал Claude следующие решения:
- Production URL и HTTPS-стратегия → поддомен `planner.heyda.ru` через reverse-proxy
- Длина auth-кода, TTL, single-use, rate-limit → 6 цифр, 5 мин, single-use, 1/мин и 5/час
- JWT access/refresh lifetimes → 15 мин access + 30 дней refresh (rolling)
- API версионирование → `/api/` prefix, без `/v1/`
- Error формат → простой JSON без RFC 7807
- БД путь, PRAGMA, таблицы → `/var/lib/planner/weekly_planner.db`, WAL + busy_timeout
- Systemd-юнит структура → `planner-api.service` + `planner-bot.service`
- Секреты → `/etc/planner/planner.env` с `EnvironmentFile` (600 права)
- Логирование → journalctl
- Библиотеки → PyJWT, aiogram 3.x, SQLAlchemy 2.x, Alembic, passlib[bcrypt], uvicorn

---

## Deferred Ideas

- Rate limiting на `/api/sync` — будем смотреть по факту в Фазе 2
- Multi-device named sessions (схема готова, UI — позже)
- JWT RS256 вместо HS256 — если появятся внешние интеграции
- Allow-list → таблица `allowed_users` с админ-флоу — при росте аудитории
- Закрытие `/api/docs` в продакшне — обсудим в Фазе 6
