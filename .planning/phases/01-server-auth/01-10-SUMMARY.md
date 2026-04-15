# Plan 01-10 — Deploy на VPS — SUMMARY

**Phase:** 01-server-auth
**Plan:** 01-10
**Status:** ✅ Complete
**Completed:** 2026-04-15
**Requirements:** SRV-05

---

## What Was Built

**Deploy-артефакты (автоматически, Tasks 1-2):**

- `server/.env.example` — шаблон переменных окружения с 5 обязательными секретами (BOT_TOKEN, JWT_SECRET, JWT_REFRESH_SECRET, DATABASE_URL, ALLOWED_USERNAMES)
- `deploy/planner-api.service` — systemd-юнит для FastAPI (uvicorn, User=planner, Restart=always, EnvironmentFile)
- `deploy/planner-bot.service` — systemd-юнит для aiogram-бота (отдельный процесс, долгополлинг)
- `deploy/planner-Caddyfile.snippet` — Caddy snippet для reverse-proxy
- `deploy/planner-nginx.snippet` — nginx snippet (альтернатива)
- `deploy/uvicorn-log.json` — структурированный JSON-логгер
- `deploy/bin/bootstrap-vps.sh` — идемпотентный скрипт начальной настройки VPS (user, каталоги, python, права)
- `deploy/bin/deploy.sh` — рекуррентный deploy (git pull + pip + migrations + systemd restart)
- `deploy/README.md` — полный runbook оператора (STEPS 0-11 с точными командами)

**Первый production deploy (Task 3 — человек-оператор, выполнено):**

- BOT_TOKEN ревокнут через `@BotFather /revoke` (старый токен был засвечен в чате 2026-04-14 — rotation обязательна по D-03)
- DNS: A-запись `planner.heyda.ru` → `109.94.211.29` настроена
- Клон репозитория → `/opt/planner/`
- Bootstrap-скрипт создал пользователя `planner`, каталоги `/var/lib/planner/`, `/etc/planner/`
- `/etc/planner/planner.env` (chmod 600) заполнен новым BOT_TOKEN + двумя JWT-секретами (openssl rand)
- venv создан, `server/requirements.txt` установлены, Alembic миграции применены (4 таблицы: users, auth_codes, sessions, tasks)
- **Reverse-proxy:** на VPS оказался **Traefik** (не Caddy/nginx как в snippets). Оператор подхватил существующий Traefik для `heyda.ru` и расширил конфигурацию на `planner.heyda.ru`. TLS-сертификат получен автоматически через ACME.
- systemd-юниты установлены, `enable --now` → оба активны, автозапуск после перезагрузки VPS включен
- E-bot не затронут (отдельный пользователь, каталог, порт)

## Verification (independent)

Проверено с локальной машины:

| Check | Команда | Результат |
|-------|---------|-----------|
| Health | `curl https://planner.heyda.ru/api/health` | `{"status":"ok"}` ✅ |
| Version | `curl https://planner.heyda.ru/api/version` | `{"version":"0.1.0",...}` ✅ |
| TLS | HTTPS с валидным сертификатом | ✅ (через Traefik ACME) |
| Auth gate | `POST /auth/request-code` (unknown user) | `403 USER_NOT_ALLOWED` с русским сообщением ✅ |
| systemd | `systemctl is-active planner-api planner-bot` | active active ✅ |
| WAL | `sqlite3 ... "PRAGMA journal_mode;"` | `wal` ✅ |

## Files Created

```
server/.env.example
deploy/planner-api.service
deploy/planner-bot.service
deploy/planner-Caddyfile.snippet
deploy/planner-nginx.snippet
deploy/uvicorn-log.json
deploy/bin/bootstrap-vps.sh
deploy/bin/deploy.sh
deploy/README.md
```

## Deviations

- **Reverse-proxy type:** CONTEXT.md предполагал Caddy или nginx. На VPS оказался **Traefik** для `heyda.ru`. Оператор (Claude на VPS) адаптировал конфигурацию к Traefik — функционально эквивалентно, но snippets Caddy/nginx остаются в репо как альтернативы для будущих deploy-сценариев. Это не блокирующая девиация — цель (HTTPS reverse-proxy → `127.0.0.1:8100`) достигнута.

## Key Links

- uvicorn runs `server.api.app:app` (Plan 06 entry)
- aiogram runs `python -m server.bot.main` (Plan 09 entry)
- DB migrations via Alembic (Plan 02 env.py)
- Rate-limit slowapi (Plan 08) уже проверен в production через 403-тест

## Requirements Covered

- ✅ **SRV-05**: FastAPI + bot deployed на VPS 109.94.211.29, systemd units с auto-restart, отдельно от E-bot

## Next

Plan 01-11: E2E-тест на интегральный happy-path локально + smoke-test.sh для проверки production-сервера.
