# Phase 2: Клиентское ядро — Context

**Gathered:** 2026-04-16
**Status:** Ready for planning
**Mode:** auto-mode (user asleep; Claude picked recommended defaults for all gray areas)

<domain>
## Phase Boundary

Десктопный клиент Windows умеет хранить задачи локально (offline-first) и синхронизировать их с сервером `https://planner.heyda.ru/api` через `/api/sync` endpoint. **Без UI** — вся функциональность проверяется через логи и unit+integration тесты. Клиент — чистый Python модуль, импортируемый из `main.py` и (позднее, Phase 3) из overlay/week view.

Покрывает: SYNC-01..08 (локальный кеш, optimistic UI, фоновый sync, threading.Lock, server-wins, UUID client-side, full resync on reconnect, tombstones).

Авторизация (AUTH-01..05 из Phase 1) в этой фазе **используется, но не проектируется**: существующий `client/core/auth.py` skeleton уже содержит JWT request/verify/refresh паттерны — Phase 2 дописывает keyring-хранение и интегрирует с sync-потоком.

</domain>

<decisions>
## Implementation Decisions

### Cache storage format & location
- **D-01:** Локальный кеш — JSON-файл (не SQLite). Причина: простота, человекочитаемый, skeleton уже предполагает JSON (`client/core/storage.py` заглушка). Для single-user + десятки/сотни задач — достаточно.
- **D-02:** Путь: `%APPDATA%/ЛичныйЕженедельник/cache.json` (Windows `os.environ['APPDATA']`). Если Cyrillic-путь создаст проблемы — fallback на `%LOCALAPPDATA%` или английское имя папки (проверить в тесте).
- **D-03:** Настройки клиента — отдельный файл `settings.json` в той же папке (не смешиваем задачи и preferences).

### Data model (mirror server schema)
- **D-04:** Клиентский `Task` dataclass зеркалит server SQLAlchemy `Task`: `id` (UUID), `user_id`, `text`, `day` (ISO date), `time_deadline` (ISO datetime | None), `done` (bool), `position` (int), `created_at`, `updated_at`, `deleted_at` (None = живая). Минимум translation между wire-format и local.
- **D-05:** JSON-сериализация через `dataclasses.asdict()` + `json.dump()`. UUID → str, datetime → ISO 8601 с UTC timezone.
- **D-06:** Нет отдельной "Week" или "Day" сущности — они производные (`WeekPlan`, `DayPlan` создаются на лету через groupby по `day`). Хранится плоский `tasks: list[Task]`.

### Sync cadence & triggers
- **D-07:** Фоновый sync-поток (daemon thread) с **30-секундным интервалом** опроса сервера (pull delta). Стартует при первом успешном логине, останавливается при logout.
- **D-08:** **Immediate push** при любом локальном изменении: create/update/delete задачи → sync-поток немедленно разбужен через `threading.Event` или очередь → push применяется вне ожидания 30-сек интервала.
- **D-09:** При наступлении дедлайна задачи sync НЕ триггерится специально — пассивное ожидание обычного цикла (UI пульсация — забота Phase 3, не Phase 2).

### Operation queue & persistence
- **D-10:** Очередь `pending_changes: list[TaskChange]` — in-memory + **persisted в `cache.json`** (поле `pending_changes`). Причина: если приложение упадёт или юзер закроет до sync — изменения не теряются.
- **D-11:** После успешного push — `pending_changes` очищается (атомарно, под `threading.Lock`).
- **D-12:** `threading.Lock` (single) защищает весь `LocalStorage` state (tasks + pending_changes) — избежать race condition из PITFALLS Pattern 5. Простой lock без RLock (никаких nested-acquire).

### Retry semantics & offline handling
- **D-13:** Exponential backoff при сетевых ошибках: 1s, 2s, 4s, 8s, 16s, 32s, cap 60s. Повторяется бесконечно (offline-first — не сдаваемся).
- **D-14:** Online/offline detection — пассивное: ловим `requests.exceptions.ConnectionError` / `Timeout` / 5xx → переходим в "offline" состояние. Следующий retry через backoff. При успехе — сбрасываем backoff в 1s.
- **D-15:** **Нет активных health-check запросов** (не шлём отдельный GET /api/health для probe) — лишний трафик, HTTP-ошибка от основного sync уже информативна.

### Conflict resolution (server-wins)
- **D-16:** Server-wins: если сервер в ответе на sync вернул задачу с более поздним `updated_at`, чем у нас локально — **тихая перезапись** локальной копии. Никаких toast/уведомлений пользователю (Core Value: не отвлекать).
- **D-17:** Исключение: если у нас в `pending_changes` есть операция для этой же задачи — log warning (для диагностики), но применяем server version (server всегда прав). Локальная pending-операция **отбрасывается** (она бы всё равно переписала свои данные при следующем push → server'a).
- **D-18:** Client-side `updated_at` в CREATE/UPDATE операциях **не отправляется** (SRV-06: сервер ставит свой). Локально же поле обновляется по ответу сервера.

### Full resync on reconnect (SYNC-07)
- **D-19:** Детектор "долгое отключение": если последний успешный sync был больше **5 минут назад** (конфигурируемо) — при следующем успешном соединении выполняем **pull с since=None** (полный snapshot текущего состояния пользователя на сервере).
- **D-20:** Push очереди `pending_changes` происходит ПЕРЕД full resync (чтобы локальные изменения не потерялись при snapshot-перезаписи).
- **D-21:** `sync_manager.force_sync()` — публичный метод для ручного триггера (tray-меню в Phase 3 вызовет его).

### Tombstones (SYNC-08)
- **D-22:** Локально удалённая задача **не удаляется из `tasks`-списка сразу** — ставится `deleted_at = now()`, push в очередь. Отображение (Phase 3-4) фильтрует по `deleted_at is None`.
- **D-23:** После успешного push удалённой задачи (сервер принял tombstone) — локальная задача **может быть удалена физически** (cleanup). Но **не раньше** — иначе дубликаты при reconnect с другого устройства.
- **D-24:** Tombstone-задачи приходящие с сервера (deletion на другом устройстве) — помечаются локально `deleted_at`, при следующем cleanup (через час idle) физически удаляются.

### Keyring integration (для AUTH, переиспользуется)
- **D-25:** `keyring` — Windows Credential Manager backend — хранит три ключа: `access_token`, `refresh_token`, `telegram_username`. Service name: `"ЛичныйЕженедельник"` (сохраняем единообразие; если Cyrillic не сработает в frozen exe — fallback на ASCII `"WeeklyPlanner"`).
- **D-26:** При старте клиент: `keyring.get_password` → если есть refresh_token — попробовать `/auth/refresh` → если 401 → требовать новую авторизацию через Telegram-код. Access-token НЕ хранится в keyring (он короткий 15мин, всегда live в RAM).

### Logging & observability
- **D-27:** Python `logging` модуль, ротирующий файл-handler в `%APPDATA%/ЛичныйЕженедельник/logs/client.log` (RotatingFileHandler, maxBytes=1MB, backupCount=5).
- **D-28:** Уровни: INFO для sync-событий (push/pull/conflict), DEBUG для details, ERROR при network-timeout или server-5xx. Русские сообщения OK.
- **D-29:** НЕ логируем access/refresh tokens (даже DEBUG). Username — OK.

### Claude's Discretion
Всё выше — строгие решения. Claude сам решает:
- Конкретную структуру файлов `client/core/` (переписывать skeleton auth.py/storage.py/sync.py/models.py vs только дополнять)
- Имена приватных методов (`_save()`, `_load()`, `_do_sync()` и т.п.)
- Точный shape `TaskChange` (NamedTuple / dataclass / dict)
- Реализация `threading.Event` vs `queue.Queue` для wake-up sync-потока
- Exception classes для offline/auth-error differentiation
- Конкретная библиотека для UUID (`uuid.uuid4()` — стандартная; не переключать)
- Unit-тест vs integration-тест раскладка (как в Phase 1 — pytest + aiosqlite + httpx.MockTransport)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 — базовый API и контракты (уже работают в проде)
- `.planning/phases/01-server-auth/01-CONTEXT.md` — auth flow, JWT lifetimes, /api/sync contract
- `.planning/phases/01-server-auth/01-06-SUMMARY.md` — auth endpoints (request-code / verify / refresh / logout / me)
- `.planning/phases/01-server-auth/01-07-SUMMARY.md` — /api/sync endpoint shape (SyncIn/SyncOut/TaskChange)
- `server/api/sync_schemas.py` — эталонные pydantic схемы (клиентский Task + TaskChange должны матчиться)
- `server/api/auth_routes.py` — пример request/response JSON форматов
- `server/db/models.py` — схема задачи (id UUID, deleted_at, updated_at, position) — клиентский dataclass зеркалит

### Research — архитектурные паттерны
- `.planning/research/ARCHITECTURE.md` §Sync protocol — delta + since + tombstones обоснование
- `.planning/research/PITFALLS.md` Pitfall 4 (LocalStorage race condition — уже известна, закрывается D-12)
- `.planning/research/PITFALLS.md` Pitfall 7 (keyring в frozen exe — закрывается D-25, полный hidden-imports в Phase 6)
- `.planning/research/STACK.md` — библиотеки для клиента (requests, keyring — уже в requirements.txt скелета)

### Project vision & constraints
- `.planning/PROJECT.md` — Core Value (speed-of-capture), Validated Phase 1 (сервер работает)
- `.planning/REQUIREMENTS.md` §SYNC (8 требований, которые эта фаза закрывает)
- `.planning/ROADMAP.md` §Phase 2 — goal: "Клиент умеет хранить задачи локально и синхронизировать их с сервером — без UI, но проверяемо через логи"
- `CLAUDE.md` — стек клиента (CustomTkinter, keyring, requests), русские комментарии

### Existing skeleton (перепишется)
- `client/core/__init__.py` (empty)
- `client/core/auth.py` — 127 строк skeleton: JWT request/verify/refresh паттерны + keyring.set/get
- `client/core/storage.py` — 100 строк skeleton: LocalStorage класс с loads/saves
- `client/core/sync.py` — 103 строки skeleton: SyncManager + daemon thread
- `client/core/models.py` — 114 строк skeleton: Task/DayPlan/WeekPlan dataclasses

### Reference-проект (E-bot)
- `S:\Проекты\е-бот\` — паттерн keyring integration для JWT (если совпадает с AUTH-03)
- Автообновление с SHA256 — не в Phase 2, но паттерн пригодится в Phase 6

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `client/core/auth.py` (127 строк skeleton) — уже набросаны методы `request_code()`, `verify_code()`, `load_saved_token()`, `save_tokens()`. Plan должен **переиспользовать** сигнатуры где возможно, заменить скелет на production-реализацию с httpx/requests + keyring.
- `client/core/storage.py` (100 строк skeleton) — класс `LocalStorage` с `load()/save()`. Расширить: `pending_changes`, `threading.Lock`, `drain_pending_changes()` атомарный метод.
- `client/core/sync.py` (103 строки skeleton) — `SyncManager` с `start()/stop()`, `_sync_loop()` daemon thread. Дополнить: exponential backoff, `force_sync()`, `full_resync_if_stale()`, Event для immediate-push.
- `client/core/models.py` (114 строк skeleton) — `Task`, `DayPlan`, `WeekPlan` dataclasses. `WeekPlan` может быть computed property, а не stored.

### Established Patterns
- **Python 3.12 + dataclasses + type hints** — как в Phase 1 server
- **Русские docstrings/комментарии** (CLAUDE.md convention)
- **Private методы с `_`** — `_save()`, `_sync_loop()`, `_do_sync()` (см. client/app.py skeleton)
- **Singleton-подобный паттерн** (ThemeManager, SidebarManager в оригинальном CLAUDE.md) — LocalStorage и SyncManager будут такими же (создаются при старте app, живут весь lifecycle)
- **No `__all__`, import from full path** (`from client.core.sync import SyncManager`)

### Integration Points
- `main.py` → `WeeklyPlannerApp(version).run()` — приложение создаёт AuthManager → если auth OK, создаёт LocalStorage + SyncManager → запускает sync thread
- **Phase 3** будет импортировать `LocalStorage` для чтения задач в overlay/week view
- **Phase 3** вызовет `SyncManager.force_sync()` при клике "обновить" в tray-меню
- **Phase 5** (Telegram-бот) НЕ использует клиентский код — бот напрямую ходит в сервер API

### Skeleton — что НЕ трогать
- `main.py` — точка входа, Phase 2 использует его `WeeklyPlannerApp`-класс, но `app.py` сам UI-слой (Phase 3)
- `client/ui/*` — UI (Phase 3-4)
- `client/utils/*` — tray/hotkeys/updater (Phase 3-6)
- `server/*` — trogged by Phase 1, не трогать

</code_context>

<specifics>
## Specific Ideas

- **Offline-first принцип как в Things 3 / Bear / любых хороших native-apps**: сначала меняем локально, потом шлём. Пользователь никогда не ждёт сервера для любого действия.
- **"Тихая" синхронизация**: пользователь не видит модальных "синхронизация…" — она живёт в фоне. Если что-то не работает — максимум лог-запись + (в Phase 3) маленький indicator в tray-меню. Никаких pop-up.
- **Test strategy — как Phase 1**: pytest + fixtures. Mock httpx для sync-тестов (conftest уже умеет mock_telegram_send — аналогично сделать mock_sync_transport). Реальный сервер не требуется для тестов.
- **pending_changes queue design паттерн**: аналогично offline-first библиотекам (Dexie.js, RxDB, Realm). Но — проще, без CRDT, без vector clocks: single-user + server-wins = достаточно.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-device session display** (увидеть список активных устройств, revoke конкретное) — сервер уже поддерживает в `Session.device_name`, но UI для этого — Phase 3 tray-меню или Phase 4 settings-panel, не Phase 2.
- **"Show sync status" indicator** в tray — полезно, но UI-зависимо, откладываю в Phase 3.
- **Manual conflict-resolution UI** — если server-wins окажется агрессивным на практике, добавим в v2. Сейчас (D-16) — silent.
- **Encryption of cache.json at rest** — не требуется v1 (single-user, доверенный Windows-профиль). В v2 если проект масштабируется на коллег — рассмотрим `cryptography.fernet` + keyring.
- **Sync metrics / analytics** — сколько раз push/pull/conflicts. Полезно для debug, но не для Phase 2. В будущем — Prometheus-style endpoint на /api/metrics (нет, это scope-creep).

### Reviewed Todos (not folded)
(Cross_reference_todos вернул 0 совпадений — пусто)

</deferred>

---

*Phase: 02-client-core*
*Context gathered: 2026-04-16 (auto-mode, all gray areas auto-resolved to recommended defaults)*
