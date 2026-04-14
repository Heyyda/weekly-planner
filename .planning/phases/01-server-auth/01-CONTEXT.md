# Phase 1: Сервер и авторизация — Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Развернуть FastAPI-сервер на VPS 109.94.211.29 с SQLite-хранилищем (WAL + busy_timeout), реализовать Telegram JWT-авторизацию (username → код → access+refresh токены), опубликовать REST-эндпойнты `/api/auth/*`, `/api/sync`, `/api/health`, `/api/version`, запустить как systemd-юнит с автостартом. Клиентский код, UI, десктоп-интеграция, бот-команды для задач — вне скоупа этой фазы.

</domain>

<decisions>
## Implementation Decisions

### Telegram-бот (owned by user)
- **D-01:** Один бот на весь проект (единый `@Jazzways_bot`). В Фазе 1 — шлёт 6-значные коды авторизации. В Фазе 5 — тот же бот получает команды задач (`/add`, `/week`, `/today`). Не создавать второго.
- **D-02:** Username/название бота НЕ меняем — остаётся `@Jazzways_bot`. Семантика имени неважна для личного проекта; экономия на регистрации и переключении.
- **D-03:** Бот-токен владельца был передан в чате 2026-04-14 — **обязательно ревокнуть через `@BotFather` `/revoke`** при первом деплое и использовать новый. Старый токен считать скомпрометированным.
- **D-04:** Токен хранится на VPS в `/etc/planner/planner.env` (систем-`EnvironmentFile`, права `600`). В репозиторий не попадает. Клиент токен не знает — только сервер (сервер шлёт update-полл в Telegram API).

### Auth-код: UX
- **D-05:** Формат сообщения кода — расширенный контекст:
  ```
  🔐 Запрошен вход в Личный Еженедельник

  Код: 123456
  Устройство: <hostname или "рабочий PC">
  Время: 2026-04-14 14:23 MSK
  Срок: 5 минут

  Если это не ты — игнорируй это сообщение.
  ```
- **D-06:** Длина кода: **6 цифр** (стандарт OTP, удобно вводить, достаточно энтропии для 5-минутного окна) — *Claude discretion*
- **D-07:** Срок жизни кода: **5 минут** с момента отправки — *Claude discretion*
- **D-08:** Код **single-use** — после успешной `/auth/verify` помечается `used_at`, повторно не принимается — *Claude discretion*
- **D-09:** Rate limit на `/auth/request-code`: **1 запрос в минуту на username**, 5 запросов в час — защита от флуда и сценария "случайный повторный клик" — *Claude discretion*

### Production URL (Claude discretion)
- **D-10:** Эндпойнт клиента: `https://planner.heyda.ru/api/` через reverse-proxy (Caddy или nginx — уточнить что уже на VPS из E-bot setup) → backend на `127.0.0.1:8100`. Причины: TLS обязателен для credential-flow; домен `heyda.ru` уже у владельца (ссылка в скелете `server/api.py` на `https://heyda.ru/planner/download`); прямой IP:порт = certwarning в клиенте и хуже для keyring-миграции позже.
- **D-11:** Если поддомен ещё не настроен — создаётся в плане Фазы 1 отдельным deploy-таском.

### JWT lifetimes (Claude discretion)
- **D-12:** Access token TTL: **15 минут** (короткий — если утечёт, риск минимален; клиент сам рефрешит через `/auth/refresh`)
- **D-13:** Refresh token TTL: **30 дней** (с автоматическим продлением при активности — rolling refresh)
- **D-14:** Refresh token храниться в keyring и в server-side `Session` таблице (revokable); access — только в памяти клиента, не персистится
- **D-15:** При logout удаляется `Session` на сервере — все refresh-токены этого устройства инвалидируются

### API design (Claude discretion)
- **D-16:** Префикс `/api/` (как в скелете `server/api.py`) — без `/v1/`. Один пользователь, единая версия API — версионирование преждевременно.
- **D-17:** Эндпойнты v1:
  - `POST /api/auth/request-code` — вход: `{username}`, выход: `{request_id, expires_in}`
  - `POST /api/auth/verify` — вход: `{request_id, code}`, выход: `{access_token, refresh_token, expires_in, user_id}`
  - `POST /api/auth/refresh` — вход: `{refresh_token}`, выход: `{access_token, expires_in}` (+ опционально новый refresh)
  - `POST /api/auth/logout` — вход: Bearer access, action: revoke session
  - `GET /api/auth/me` — вход: Bearer access, выход: `{user_id, username, created_at}`
  - `POST /api/sync` — вход: Bearer + `{since, changes:[]}`, выход: `{server_timestamp, changes:[]}`
  - `GET /api/health` — {status: "ok"}
  - `GET /api/version` — {version, download_url, sha256}
- **D-18:** Формат ошибок: `{"error": {"code": "INVALID_CODE", "message": "Код истёк или неверен"}}` — простой, без RFC 7807 (излишне для single-user)

### Database (Claude discretion)
- **D-19:** SQLite файл: `/var/lib/planner/weekly_planner.db` (owner: `planner` user, права `600`). Каталог автосоздаётся systemd `ReadWritePaths`.
- **D-20:** PRAGMA при открытии: `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`, `synchronous=NORMAL`
- **D-21:** Таблицы (минимум для Фазы 1):
  - `users`: `id UUID, telegram_username TEXT UNIQUE, created_at, updated_at`
  - `auth_codes`: `id UUID, username TEXT, code_hash TEXT, expires_at, used_at NULL, created_at`
  - `sessions`: `id UUID, user_id, refresh_token_hash TEXT, device_name TEXT NULL, expires_at, revoked_at NULL, created_at, last_used_at`
  - `tasks`: `id UUID, user_id, text TEXT, day DATE, time_deadline TIMESTAMP NULL, done BOOLEAN, position INT, created_at, updated_at, deleted_at NULL` (поле `deleted_at` — tombstone для Фазы 2)
- **D-22:** Миграции — через Alembic (стандарт SQLAlchemy) с первой миграцией = стартовая схема

### Deployment (Claude discretion)
- **D-23:** Процесс как **`planner-api.service` systemd unit**, запущенный под непривилегированным пользователем `planner`. `Restart=always`, `RestartSec=5s`.
- **D-24:** Отдельный **`planner-bot.service`** systemd unit (aiogram 3.x long-polling или webhook — планировщик решит при реализации) — он владеет токеном бота, берёт задания из очереди (Redis, в памяти, или БД-поллинг) на отправку кодов. В Фазе 1 используется только для отправки кодов; команды задач добавятся в Фазе 5 в этот же unit без замены.
- **D-25:** **Reverse proxy** — переиспользовать существующий сервис (Caddy/nginx) который уже обрабатывает `heyda.ru`. Новый subdomain `planner.heyda.ru` → `127.0.0.1:8100`.
- **D-26:** Логирование — stdout/stderr → journalctl (через systemd). Структурированный JSON-формат (для возможного будущего агрегирования).
- **D-27:** **Секреты на VPS** в `/etc/planner/planner.env`:
  - `BOT_TOKEN` — новый токен после `/revoke`
  - `JWT_SECRET` — `openssl rand -hex 32`
  - `JWT_REFRESH_SECRET` — отдельный от access, тоже `openssl rand -hex 32`
  - `DATABASE_URL=sqlite:////var/lib/planner/weekly_planner.db`
  - `ALLOWED_USERNAMES=nikita_heyyda,...` (явный allow-list — чтобы случайные telegram-юзеры не могли спамить `/auth/request-code`)

### Claude's Discretion
Всё что помечено *Claude discretion* выше. Дополнительно:
- Конкретные библиотеки (`fastapi`, `sqlalchemy`, `alembic`, `pyjwt`, `aiogram`, `uvicorn`, `passlib[bcrypt]` — для code hash)
- Структура кода (roots `server/api/`, `server/auth/`, `server/db/`, `server/bot/`)
- Точный формат systemd-юнитов
- Health-check endpoint поведение
- OpenAPI схема автогенерится FastAPI — не переписываем вручную

### Folded Todos
Нет фолдед-тудов (cross_reference_todos вернул пусто).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level context
- `.planning/PROJECT.md` — Core Value (speed-of-capture), Key Decisions, Design-risk mitigation
- `.planning/REQUIREMENTS.md` §AUTH, §SRV — полные v1-требования этой фазы (AUTH-01..05, SRV-01..06)
- `.planning/ROADMAP.md` §Phase 1 — Goal, Success Criteria, Dependencies
- `CLAUDE.md` — архитектурные решения (JWT+Telegram, keyring, deployment patterns)

### Research (обязательно прочитать до планирования)
- `.planning/research/STACK.md` — корректировки стека: **PyJWT (не python-jose)**, aiogram 3.x, SQLite WAL + busy_timeout, версии всех библиотек
- `.planning/research/ARCHITECTURE.md` §Sync protocol, §API sketch — контракт `/sync`, server-as-validator, UUID client-side, tombstones
- `.planning/research/PITFALLS.md` Pitfall 6, 7, 11 — keyring в frozen exe (для Фазы 2-6, учесть заранее), SQLite concurrency, Cyrillic paths, auto-update rename trick (для Фазы 6)

### Codebase state
- `.planning/codebase/STACK.md` — актуальный скелет-стек
- `.planning/codebase/INTEGRATIONS.md` — планируемые интеграции
- `.planning/codebase/ARCHITECTURE.md` — текущая архитектура скелета
- `.planning/codebase/CONCERNS.md` — уже-идентифицированные технические долги в скелете
- `server/api.py`, `server/auth.py`, `server/config.py`, `server/db.py` — файлы-заглушки, которые фаза 1 заменяет реализацией

### Reference-проект (E-bot) — паттерны к переиспользованию
- `S:\Проекты\е-бот\device-manager.py` — работающий FastAPI-сервер на том же VPS (паттерн деплоя, systemd)
- `S:\Проекты\е-бот\mega.py` lines 479-618 — auto-update паттерн (понадобится в Фазе 6, учесть в БД через `/api/version`)
- `S:\Проекты\е-бот\` — паттерн Telegram-auth с кодом (если найдётся соответствующий модуль — читать; иначе writer-агенту спросить владельца)

### External secrets / indicators (память Никиты, не в репо)
- `S:\Obsidian\Claude\указатели-на-секреты.md` §Личный Еженедельник — где лежит bot-token и JWT-secrets после ротации

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FastAPI skeleton** (`server/api.py`) — `app = FastAPI(title=..., docs_url="/api/docs")` уже настроено. `/api/health` и `/api/version` заглушки есть — просто наполнить логикой.
- **SQLAlchemy skeleton** (`server/db.py`) — см. codebase/ARCHITECTURE.md, связи Base + session factory предполагаются. Уточнить при планировании.
- **JWT skeleton** (`server/auth.py`) — 2380 байт, видимо что-то уже набросано. Планировщик должен **сначала прочитать `server/auth.py`** и переиспользовать любую рабочую логику, остальное заменить на PyJWT.
- **Config skeleton** (`server/config.py`) — 876 байт, вероятно pydantic-settings. Прочитать при планировании.

### Established Patterns (из E-bot)
- **Reverse proxy уже работает** для `heyda.ru` — новый поддомен конфигурируется тем же сервисом (Caddy/nginx config на VPS)
- **systemd pattern** с `EnvironmentFile` и `Restart=always` — скопировать из E-bot unit-файла
- **Auto-update с SHA256** — E-bot использует это в проде, `/api/version` возвращает `{version, download_url, sha256}` (уже заглушка в `server/api.py`)

### Integration Points
- **VPS 109.94.211.29**: новый systemd-юнит рядом с существующими E-bot unit'ами. Не трогать их.
- **Telegram-бот `@Jazzways_bot`**: владение передано проекту. НЕ общий с E-bot.
- **Файловая система VPS**: `/var/lib/planner/` (данные), `/etc/planner/` (конфиг), `/var/log/planner/` (если журналить не только в journalctl)
- **Heyda.ru DNS**: требуется A-запись или CNAME `planner.heyda.ru` → существующий IP VPS; уточнить у владельца DNS-провайдера если нужно, или через Caddy `automatic_https`

</code_context>

<specifics>
## Specific Ideas

- **Auth-код сообщение**: владелец хочет расширенный контекст (не просто "123456"), но не кнопку "это не я" — форматированный текст с устройством, временем, сроком годности, подсказкой-"если не ты, игнорируй"
- **Бот `@Jazzways_bot`** уже существует у владельца, не используется нигде — переиспользуем. Название не переименовываем.
- **Токен бота был передан в чате** — ревокнуть первым делом при деплое.
- **E-bot на том же VPS** — не мешать и не ломать его работу при деплое (отдельные unit'ы, отдельный пользователь, отдельный SQLite-файл, отдельный порт)

</specifics>

<deferred>
## Deferred Ideas

- **Rate limiting на `/api/sync`** — не в Фазу 1; добавится если столкнёмся со спамом от клиента. В Фазу 2 при реализации sync-таймера.
- **Multi-device named sessions** (Фаза 2+): `sessions.device_name` позволит пользователю увидеть в tray-меню список активных устройств и revoke конкретное. В Фазу 1 схема поддерживает поле, но UI для него — позже.
- **OpenAPI публикация** на публичном URL — пока `/api/docs` включён (из скелета), но в прод можно закрыть auth'ом или отключить. Обсудим в Фазе 6 (dist).
- **JWT-алгоритм**: сейчас HS256 (symmetric). Если в v2 появятся внешние интеграции — перейти на RS256. Заложить в config, не хардкодить.
- **Allow-list переходит в многопользователь** — для коллег (потенциальных пользователей из PROJECT.md Context): в v1 whitelist в `.env`, в v2+ — таблица `allowed_users` с админ-флоу.

### Reviewed Todos (not folded)
(Cross_reference_todos вернул 0 совпадений — пусто)

</deferred>

---

*Phase: 01-server-auth*
*Context gathered: 2026-04-14*
