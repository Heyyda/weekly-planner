# Phase 2: Клиентское ядро — Research

**Researched:** 2026-04-16
**Domain:** Python client-side offline-first storage + threading + HTTP sync
**Confidence:** HIGH (все технические решения заблокированы CONTEXT.md; паттерны верифицированы по коду Phase 1, ARCHITECTURE.md, PITFALLS.md)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01**: Локальный кеш — JSON-файл (не SQLite). Один файл `cache.json`.
- **D-02**: Путь `%APPDATA%/ЛичныйЕженедельник/cache.json`. Fallback: `%LOCALAPPDATA%` или ASCII-имя папки.
- **D-03**: Настройки — отдельный `settings.json` в той же папке.
- **D-04**: Клиентский `Task` dataclass зеркалит server schema: `id (UUID), user_id, text, day (ISO date), time_deadline (ISO datetime | None), done (bool), position (int), created_at, updated_at, deleted_at (None = живая)`.
- **D-05**: JSON-сериализация через `dataclasses.asdict()` + `json.dump()`. UUID → str, datetime → ISO 8601 UTC.
- **D-06**: Хранится плоский `tasks: list[Task]`. WeekPlan/DayPlan — computed, не stored.
- **D-07**: Фоновый sync-поток с 30-секундным интервалом. Стартует при логине, останавливается при logout.
- **D-08**: Immediate push при любом локальном изменении: `threading.Event` пробуждает sync-поток.
- **D-09**: Sync не триггерится при наступлении дедлайна.
- **D-10**: `pending_changes: list[TaskChange]` — in-memory + persisted в `cache.json["pending_changes"]`.
- **D-11**: После успешного push — `pending_changes` очищается атомарно под Lock.
- **D-12**: Один `threading.Lock` защищает весь `LocalStorage` state. Без RLock, без вложенных acquire.
- **D-13**: Exponential backoff: 1s→2s→4s→8s→16s→32s→cap 60s. Бесконечные retries.
- **D-14**: Offline detection пассивная: ловим `ConnectionError/Timeout/5xx` → offline state. При успехе — reset backoff.
- **D-15**: Нет активных health-check запросов.
- **D-16**: Server-wins: серверный `updated_at` позднее → тихая перезапись локальной копии. Никаких toast.
- **D-17**: Если pending для той же задачи — log warning, но применяем server version. Pending-операция отбрасывается.
- **D-18**: Client-side `updated_at` в CREATE/UPDATE операциях НЕ отправляется.
- **D-19**: Full resync если последний sync > 5 минут назад (конфигурируемо) — pull с `since=None`.
- **D-20**: Push pending ПЕРЕД full resync.
- **D-21**: `sync_manager.force_sync()` — публичный метод.
- **D-22**: Удалённая задача не удаляется из `tasks` — ставится `deleted_at = now()`, push в очередь.
- **D-23**: Физическое удаление только после успешного push tombstone.
- **D-24**: Tombstones с сервера → пометить локально `deleted_at`, cleanup через час idle.
- **D-25**: Keyring service name: `"ЛичныйЕженедельник"` (fallback ASCII `"WeeklyPlanner"` если Cyrillic ломается в frozen exe).
- **D-26**: Старт: `keyring.get_password` → refresh-token → `/auth/refresh` → если 401 → новый Telegram-код. Access-token только в RAM.
- **D-27**: `RotatingFileHandler` в `%APPDATA%/.../logs/client.log`, maxBytes=1MB, backupCount=5.
- **D-28**: INFO для sync-событий, DEBUG для деталей, ERROR при network-timeout/5xx.
- **D-29**: НЕ логировать access/refresh tokens.

### Claude's Discretion
- Структура файлов `client/core/` (переписывать skeleton vs только дополнять)
- Имена приватных методов (`_save()`, `_load()`, `_do_sync()` и т.п.)
- Точный shape `TaskChange` (NamedTuple / dataclass / dict)
- Реализация `threading.Event` vs `queue.Queue` для wake-up sync-потока
- Exception classes для offline/auth-error differentiation
- `uuid.uuid4()` — стандартная; не переключать
- Unit-тест vs integration-тест раскладка

### Deferred Ideas (OUT OF SCOPE)
- Multi-device session display в UI
- "Show sync status" indicator в tray (Phase 3)
- Manual conflict-resolution UI (v2)
- Encryption of cache.json at rest (v2)
- Sync metrics/analytics
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SYNC-01 | Локальный кеш задач в JSON-файле `cache.json` в AppData (оффлайн-работа) | LocalStorage с atomic write через `os.replace()` + tmp file; wire format в §Wire Format |
| SYNC-02 | Optimistic UI: операции применяются к кешу мгновенно, ставятся в очередь `pending_changes` | `add_pending_change()` + `save()` атомарно под Lock; `threading.Event` wake |
| SYNC-03 | Фоновый sync-поток периодически отправляет `pending_changes` и забирает delta с сервера | `threading.Event.wait(timeout=30)` паттерн в §Threading Pattern; backoff в §Backoff |
| SYNC-04 | `threading.Lock` на доступ к `pending_changes` из UI- и sync-потоков | `drain_pending_changes()` — единственный safe паттерн; в §Thread Safety |
| SYNC-05 | При конфликте server-wins (серверный `updated_at` переопределяет локальный) | `merge_from_server()` сравнивает `updated_at` ISO строки; в §Merge Logic |
| SYNC-06 | UUID ID генерируются на клиенте — CREATE идемпотентен, не ждёт сервер | `str(uuid.uuid4())` при создании Task; server handles idempotent create |
| SYNC-07 | При восстановлении сети — автоматический full resync накопленных изменений | `full_resync_if_stale()` проверяет `last_sync_at`; push pending first, then pull since=None |
| SYNC-08 | Tombstone для удалений (`deleted_at`) — не создавать задачу заново на другом устройстве | `deleted_at = utcnow()` + push "delete" op; cleanup после confirmed push |
</phase_requirements>

---

## Summary

Phase 2 строит клиентское ядро — три модуля: `LocalStorage` (персистентность), `SyncManager` (фоновая синхронизация), `AuthManager` (JWT + keyring). Всё написано "поверх" существующих 444 LOC skeleton-файлов: скелет содержит правильные сигнатуры, но тела нужно переписать — отсутствует threading.Lock, exponential backoff, tombstone логика, правильный wire format для `/api/sync`.

Ключевой технический вопрос — маппинг между клиентским `TaskChange` и серверным `SyncIn/SyncOut`. Сервер уже задеплоен на `https://planner.heyda.ru/api`. `POST /api/sync` принимает `{"since": datetime|null, "changes": [{"op": "create"|"update"|"delete", "task_id": "uuid", ...}]}` и возвращает `{"server_timestamp": datetime, "changes": [TaskState...]}`. Клиентский `Task` dataclass должен зеркалить `TaskState` (без `priority`, без `category_id` — они out-of-scope v1).

**Primary recommendation:** Полная перезапись тел skeleton-методов при сохранении публичных сигнатур. `threading.Event` как wake-up механизм. `os.replace()` для atomic JSON write. Keyring service name в ASCII fallback константе.

---

## Standard Stack

### Core (уже в requirements.txt)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | >=2.32.0 | HTTP client для sync | Уже в стеке; synchronous — правильный выбор для daemon thread (не async) |
| `keyring` | >=25.7.0 | JWT в Windows Credential Manager | Production-proven в E-bot; WinCred backend |
| `threading` | stdlib | Lock + Event для sync thread | Стандартная библиотека; никакого дополнительного пакета |
| `uuid` | stdlib | Client-generated UUID для Task.id | stdlib; SYNC-06 |
| `json` | stdlib | cache.json сериализация | stdlib |
| `dataclasses` | stdlib | Task/TaskChange model | Уже в skeleton |
| `pathlib` | stdlib | Пути к AppData | Уже в skeleton |
| `logging` | stdlib | RotatingFileHandler | D-27/D-28 |

### Testing
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | >=8.0 | Unit + integration тесты | Всегда |
| `requests-mock` | >=1.12.0 | Mock HTTP requests в тестах sync | Проще чем `responses`; thread-safe |
| `pytest-mock` | >=3.14 | `monkeypatch` и `MagicMock` | Уже есть в server tests |
| `tmp_path` | pytest fixture | Временный AppData для storage тестов | Встроен в pytest |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` | `httpx` (sync) | httpx нет в requirements; requests достаточен для sync daemon thread |
| `threading.Event` | `queue.Queue` | Queue сложнее; Event проще для "wake or timeout" паттерна |
| `json` + `os.replace()` | SQLite | SQLite избыточен для single-user; JSON = human-readable, совместим со skeleton |

**Installation (dev dependencies):**
```bash
pip install requests-mock pytest-mock
```

---

## Wire Format Reference

### /api/sync Request (SyncIn)
Источник: `server/api/sync_schemas.py` (задеплоен на prod, неизменен)

```python
# Клиент отправляет:
{
    "since": "2026-04-15T09:30:00.000000Z",  # или null для full resync
    "changes": [
        # CREATE
        {"op": "create", "task_id": "uuid-str", "text": "купить молоко",
         "day": "2026-04-14", "done": false, "position": 0,
         "time_deadline": null},
        # UPDATE (partial — только изменённые поля)
        {"op": "update", "task_id": "uuid-str", "done": true},
        # DELETE (tombstone)
        {"op": "delete", "task_id": "uuid-str"}
    ]
}
```

**Критично:** `updated_at` клиент НЕ отправляет (SRV-06: server-side). `user_id` НЕ отправляется (берётся из JWT). `task_id` = UUID string, сгенерированный клиентом (SYNC-06).

### /api/sync Response (SyncOut)
```python
{
    "server_timestamp": "2026-04-15T09:30:00.123456Z",  # клиент сохраняет как новый since
    "changes": [
        {
            "task_id": "uuid-str",
            "text": "купить молоко",
            "day": "2026-04-14",
            "time_deadline": null,
            "done": false,
            "position": 0,
            "created_at": "2026-04-15T09:30:00.123456Z",
            "updated_at": "2026-04-15T09:30:00.123456Z",  # source of truth
            "deleted_at": null  # non-null = tombstone
        }
    ]
}
```

### /api/auth endpoints (из auth_routes.py)
```python
# POST /api/auth/request-code
Request: {"username": "nikita_heyyda", "hostname": "WORK-PC"}
Response: {"request_id": "uuid", "expires_in": 300}

# POST /api/auth/verify
Request: {"request_id": "uuid", "code": "123456", "device_name": "WORK-PC"}
Response: {"access_token": "jwt...", "refresh_token": "...", "expires_in": 900,
           "user_id": "uuid", "token_type": "bearer"}

# POST /api/auth/refresh
Request: {"refresh_token": "..."}
Response: {"access_token": "jwt...", "refresh_token": "...", "expires_in": 900, "token_type": "bearer"}

# GET /api/auth/me  (Bearer required)
Response: {"user_id": "uuid", "username": "nikita_heyyda", "created_at": "2026-..."}
```

**Важно:** skeleton `auth.py` использует неправильные endpoint URLs (`/auth/request` вместо `/auth/request-code`, `/auth/verify` принимает `username+code` вместо `request_id+code`). Нужна корректировка при переписке.

---

## Architecture Patterns

### Рекомендуемая структура client/core/

```
client/core/
├── __init__.py          # пустой
├── models.py            # Task dataclass (переписать: убрать priority/category, добавить deleted_at)
├── storage.py           # LocalStorage (переписать тела: добавить Lock, atomic write, drain)
├── sync.py              # SyncManager (переписать тела: Event, backoff, merge, full resync)
├── auth.py              # AuthManager (переписать тела: fix endpoints, fix keyring keys, add refresh logic)
└── config.py            # NEW: API_BASE = "https://planner.heyda.ru/api", SYNC_INTERVAL=30, STALE_THRESHOLD=300
```

### Pattern 1: threading.Event wake-up (SYNC-03, D-08)

**What:** Daemon sync thread спит с таймаутом через `Event.wait(timeout=30)`. При изменении вызывается `Event.set()` → поток просыпается немедленно и делает sync.

**When to use:** Всегда. Это замена `time.sleep(30)` из текущего skeleton.

```python
# client/core/sync.py
import threading

class SyncManager:
    def __init__(self, storage, auth_manager):
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._sync_loop, daemon=True, name="SyncThread")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._wake_event.set()  # разбудить чтобы не ждать 30 сек

    def force_sync(self):
        """Вызывается из UI при каждом изменении (D-08)."""
        self._wake_event.set()

    def _sync_loop(self):
        while not self._stop_event.is_set():
            self._wake_event.wait(timeout=30)  # sleep 30s OR wake on set()
            self._wake_event.clear()
            if self._stop_event.is_set():
                break
            self._do_sync()
```

**Confidence:** HIGH (stdlib threading.Event — стандартный паттерн)

### Pattern 2: drain_pending_changes — единственный safe способ (SYNC-04, D-12)

**What:** Атомарное изъятие всей очереди под Lock. Sync thread берёт snapshot, UI может продолжать добавлять новые операции без ожидания.

```python
# client/core/storage.py
import threading

class LocalStorage:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict = {}

    def add_pending_change(self, change: dict) -> None:
        """Вызывается из UI thread (optimistic, D-10)."""
        with self._lock:
            self._data.setdefault("pending_changes", []).append(change)
            self._save_locked()  # сохранить под уже захваченным lock

    def drain_pending_changes(self) -> list:
        """Атомарно изъять всю очередь (SYNC-04). Вызывается из sync thread."""
        with self._lock:
            changes = list(self._data.get("pending_changes", []))
            self._data["pending_changes"] = []
            # НЕ сохраняем здесь — сохраним после confirmed push
        return changes

    def restore_pending_changes(self, changes: list) -> None:
        """Вернуть в очередь если push не удался."""
        with self._lock:
            existing = self._data.get("pending_changes", [])
            self._data["pending_changes"] = changes + existing  # вернуть в начало
            self._save_locked()

    def _save_locked(self) -> None:
        """Atomic write через tmp + os.replace(). Вызывается только под _lock."""
        import os, tempfile, json
        tmp = self.cache_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.cache_file)  # атомарная замена на Windows
```

**Warning:** `os.replace()` атомарен в пределах одного тома/диска. Для cache.json в %APPDATA% это всегда выполняется. НЕ использовать `f.write()` прямо в cache_file — при крэше файл будет повреждён.

**Confidence:** HIGH (os.replace — documented atomic operation, Python docs)

### Pattern 3: Exponential backoff (D-13)

**What:** Inline без библиотек. Счётчик ошибок → delay. Cap 60s.

```python
# client/core/sync.py — inline в _sync_loop

_BACKOFF_BASE = 1.0   # секунд
_BACKOFF_CAP = 60.0   # секунд

class SyncManager:
    def __init__(self, ...):
        self._backoff_delay = _BACKOFF_BASE
        self._consecutive_errors = 0

    def _do_sync(self) -> bool:
        try:
            result = self._attempt_sync()
            self._backoff_delay = _BACKOFF_BASE  # reset при успехе
            self._consecutive_errors = 0
            return True
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exc:
            self._consecutive_errors += 1
            self._backoff_delay = min(self._backoff_delay * 2, _BACKOFF_CAP)
            logging.getLogger(__name__).error(
                "Sync offline error #%d, backoff %.0fs: %s",
                self._consecutive_errors, self._backoff_delay, exc
            )
            return False

    def _sync_loop(self):
        while not self._stop_event.is_set():
            ok = self._do_sync()
            # После ошибки ждём backoff; после успеха — стандартные 30s
            wait_time = self._backoff_delay if not ok else 30.0
            self._wake_event.wait(timeout=wait_time)
            self._wake_event.clear()
```

**Confidence:** HIGH (паттерн стандартный, без внешних библиотек)

### Pattern 4: merge_from_server — server-wins (SYNC-05)

**What:** Для каждого TaskState из ответа сервера: найти в локальном `tasks` по `task_id`, сравнить `updated_at`, перезаписать если сервер новее (или задача не существует локально). Задачи с `deleted_at != null` → применить tombstone.

```python
# client/core/storage.py

def merge_from_server(self, server_changes: list[dict], server_timestamp: str) -> None:
    """
    Применить delta от сервера (D-16, D-17, SYNC-05).

    server_changes: list TaskState dicts из SyncOut.changes
    server_timestamp: сохраняется как last_sync_at (новый since)
    """
    with self._lock:
        tasks_by_id: dict[str, dict] = {
            t["id"]: t for t in self._data.get("tasks", [])
        }
        pending_ids: set[str] = {
            c.get("task_id") for c in self._data.get("pending_changes", [])
        }

        for server_task in server_changes:
            tid = server_task["task_id"]
            # Переименовываем task_id → id для локального формата
            local_task = {**server_task, "id": tid}
            local_task.pop("task_id", None)

            if tid in pending_ids:
                # D-17: логируем но применяем серверную версию
                logging.getLogger(__name__).warning(
                    "Конфликт: task %s в pending_changes перезаписана сервером", tid
                )

            existing = tasks_by_id.get(tid)
            if existing is None:
                # Новая задача от сервера
                tasks_by_id[tid] = local_task
            else:
                # Server-wins: сравниваем updated_at (ISO strings)
                server_ts = server_task.get("updated_at", "")
                local_ts = existing.get("updated_at", "")
                if server_ts >= local_ts:
                    tasks_by_id[tid] = local_task

        self._data["tasks"] = list(tasks_by_id.values())
        self._data.setdefault("meta", {})["last_sync_at"] = server_timestamp
        self._save_locked()
```

**Note:** ISO 8601 strings сравниваются лексикографически — это корректно только если все timestamps UTC с одним форматом. Сервер возвращает `"2026-04-15T09:30:00.123456Z"` — всегда UTC, всегда "Z" suffix. Клиент должен хранить в том же формате.

**Confidence:** HIGH (confirmed from server sync_schemas.py и 01-07-SUMMARY.md)

### Pattern 5: full_resync_if_stale (SYNC-07, D-19, D-20)

```python
# client/core/sync.py

STALE_THRESHOLD_SECS = 300  # 5 минут

def _do_sync(self) -> bool:
    last_sync_at = self.storage.get_meta("last_sync_at")  # ISO str or None
    is_stale = self._is_stale(last_sync_at)

    # D-20: push pending ПЕРЕД full resync
    pending = self.storage.drain_pending_changes()
    if pending:
        success = self._push_changes(pending, since=last_sync_at)
        if not success:
            self.storage.restore_pending_changes(pending)
            return False  # offline — не идём дальше

    # Pull delta (since=None для full resync при stale)
    since = None if is_stale else last_sync_at
    return self._pull_delta(since)

def _is_stale(self, last_sync_at: str | None) -> bool:
    if last_sync_at is None:
        return True  # никогда не синхронизировались
    from datetime import datetime, timezone
    try:
        last = datetime.fromisoformat(last_sync_at.replace("Z", "+00:00"))
        delta = (datetime.now(timezone.utc) - last).total_seconds()
        return delta > STALE_THRESHOLD_SECS
    except (ValueError, TypeError):
        return True
```

### Pattern 6: keyring integration (D-25, D-26)

**Текущая проблема в skeleton `auth.py`:**
- Service name: `"ЛичныйЕженедельник"` — потенциально сломан в frozen exe (PITFALLS.md Pitfall 7)
- Keyring keys: `"jwt"`, `"refresh"`, `"username"` — нужно заменить на `"access_token"`, `"refresh_token"`, `"username"` (D-26 говорит access-token НЕ в keyring, только refresh + username)
- Endpoints: `/auth/request` вместо `/auth/request-code`, `username+code` вместо `request_id+code`

**Правильная реализация:**

```python
# client/core/auth.py

import keyring
import logging

SERVICE_NAME = "WeeklyPlanner"   # ASCII fallback (D-25: Cyrillic может сломаться в frozen)
# Если тестируем и Cyrillic работает — можно дополнить логику попытки с Cyrillic

KEYRING_REFRESH = "refresh_token"
KEYRING_USERNAME = "username"

class AuthManager:
    def __init__(self, api_base: str):
        self._api_base = api_base
        self.access_token: str | None = None   # только в RAM (D-26)
        self._refresh_token: str | None = None
        self.username: str | None = None
        self._user_id: str | None = None

    def load_saved_token(self) -> bool:
        """Попытка автологина из keyring (D-26)."""
        try:
            refresh = keyring.get_password(SERVICE_NAME, KEYRING_REFRESH)
            username = keyring.get_password(SERVICE_NAME, KEYRING_USERNAME)
            if refresh:
                self._refresh_token = refresh
                self.username = username
                return self._refresh_access()
        except Exception as exc:
            logging.getLogger(__name__).error("Keyring read error: %s", exc)
        return False

    def _save_refresh_to_keyring(self) -> None:
        """Сохранить refresh_token и username (access — только RAM)."""
        try:
            keyring.set_password(SERVICE_NAME, KEYRING_REFRESH, self._refresh_token or "")
            keyring.set_password(SERVICE_NAME, KEYRING_USERNAME, self.username or "")
        except Exception as exc:
            logging.getLogger(__name__).error("Keyring write error: %s", exc)
```

**Confidence:** MEDIUM для Cyrillic service name в frozen exe — PITFALLS.md Pitfall 7 подтверждает проблему, конкретный fallback механизм выбран на основе STACK.md §Gotcha 6.

### Anti-Patterns to Avoid
- **`time.sleep(SYNC_INTERVAL)` в _sync_loop:** блокирует поток; нельзя graceful shutdown; нельзя immediate wake. Использовать `Event.wait(timeout=...)`.
- **`list.clear()` после итерации pending:** race condition (Pitfall 5 из PITFALLS.md). Использовать только `drain_pending_changes()`.
- **Прямая запись в cache_file без tmp:** при крэше файл повреждён. Всегда `tmp + os.replace()`.
- **`except Exception: pass` в keyring/network:** PITFALLS.md Security Mistakes таблица. Всегда логировать ошибки.
- **Сравнение `updated_at` через `.timestamp()` с локальным clock:** CONTEXT.md D-18. Только ISO string compare.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | Custom file locking | `os.replace(tmp, dst)` | OS-гарантированная атомарность; один вызов |
| UUID generation | Custom ID scheme | `str(uuid.uuid4())` | SYNC-06; стандарт; сервер ожидает UUID format |
| HTTP retry | Custom retry loop | Inline backoff в sync_loop | tenacity избыточна; простой счётчик достаточен |
| JWT decode (клиент) | Decode и проверить exp | НЕ нужно | Клиент не декодирует JWT — просто хранит и посылает. Refresh по 401 |
| Thread-safe queue | `collections.deque` + Lock | `threading.Lock` + list | Drain-pattern проще и нагляднее; Queue сложнее для "restore on failure" |

---

## Skeleton — Что Переписывать

### models.py (114 LOC) — ПЕРЕПИСАТЬ ТЕЛА

Текущее состояние скелета содержит неверный `Task` dataclass: лишние поля `priority`, `category_id` (out-of-scope v1), отсутствует `deleted_at` (SYNC-08), отсутствует `user_id` (D-04), `created_at`/`updated_at` — строки вместо datetime.

**Что сохранить:**
- `DayPlan`, `WeekPlan` вычисляемые классы — только computed, не stored (D-06)
- `AppState` dataclass — используется settings

**Что заменить:**
```python
# Новый Task — зеркалит server TaskState (sync_schemas.py)
@dataclass
class Task:
    id: str                                # UUID str от клиента
    user_id: str                           # UUID str пользователя
    text: str
    day: str                               # ISO date "2026-04-14"
    time_deadline: Optional[str] = None    # ISO datetime или None
    done: bool = False
    position: int = 0
    created_at: str = ""                   # ISO datetime UTC
    updated_at: str = ""                   # ISO datetime UTC (source: server)
    deleted_at: Optional[str] = None       # None = жива; str = tombstone
```

**Что удалить из skeleton:**
- `Priority(IntEnum)` — v2
- `Category` dataclass — v2
- `RecurringTemplate` dataclass — v2

### storage.py (100 LOC) — ПЕРЕПИСАТЬ ТЕЛА

Скелет содержит правильные сигнатуры (`get_week`, `save_week`, `add_pending_change`, `clear_pending_changes`). Нужно:
1. Добавить `threading.Lock` (Pitfall 5 — Critical)
2. Заменить прямую запись в файл на `os.replace(tmp, dst)` паттерн
3. Добавить `drain_pending_changes()` вместо `get_pending_changes() + clear_pending_changes()`
4. Добавить `merge_from_server()`, `get_meta()`, `set_meta()`
5. Переключить от "weekly" storage (`weeks` dict) к плоскому `tasks` list (D-06)

### sync.py (103 LOC) — ПЕРЕПИСАТЬ ТЕЛА

Скелет использует `time.sleep(30)` — заменить на `threading.Event`. Отсутствуют: backoff, full resync, `force_sync` через Event, `drain_pending_changes`, `restore_pending_changes`, merge.

### auth.py (127 LOC) — ПЕРЕПИСАТЬ ТЕЛА + исправить URL/keys

Скелет содержит неверные endpoint URLs и keyring keys. Нужно исправить endpoint пути (D-17 из Phase 1 CONTEXT), исправить flow (request_id теперь в /verify), убрать access_token из keyring.

---

## Common Pitfalls

### Pitfall 1: skeleton auth.py использует устаревший API контракт
**What goes wrong:** `/auth/request` → нет такого endpoint; правильный — `/auth/request-code`. `/auth/verify` принимает `{username, code}` в скелете, но реальный endpoint принимает `{request_id, code, device_name}`.
**Why it happens:** Skeleton написан до финализации Phase 1 API.
**How to avoid:** При переписке auth.py сверить с `server/api/auth_routes.py` и `01-06-SUMMARY.md`.
**Warning signs:** 404 на `/api/auth/request`, 422 Unprocessable Entity на `/api/auth/verify`.

### Pitfall 2: ISO timestamp compare — naive vs aware datetime
**What goes wrong:** `datetime.fromisoformat("2026-04-15T09:30:00.123456Z")` в Python < 3.11 не понимает "Z" суффикс → `ValueError`.
**Why it happens:** В Python 3.11+ "Z" воспринимается, в 3.10 — нет. Проект требует 3.12+ (CLAUDE.md), но на практике безопаснее нормализовать.
**How to avoid:** `ts.replace("Z", "+00:00")` перед `fromisoformat()`. Аналогично в Phase 1 коде (01-07-SUMMARY.md "Deviations #1").

### Pitfall 3: pending_changes отдаётся на push, но push падает — изменения теряются
**What goes wrong:** `drain_pending_changes()` очищает очередь (в памяти) → push fails → изменения потеряны.
**Why it happens:** drain = destructive operation.
**How to avoid:** `restore_pending_changes(changes)` при любой ошибке push. Схема: drain → try push → on success: flush file; on fail: restore.

### Pitfall 4: keyring Cyrillic service name в frozen exe
**What goes wrong:** `keyring.get_password("ЛичныйЕженедельник", ...)` может вернуть `NoKeyringError` или неверные данные при PyInstaller --onefile (PITFALLS.md Pitfall 7).
**Why it happens:** WinCred UTF-16, entry_points не собраны PyInstaller.
**How to avoid:** ASCII service name `"WeeklyPlanner"` (D-25). Phase 6 добавит `hiddenimports=['keyring.backends.Windows']`.
**Warning signs:** После упаковки в exe пользователь должен логиниться каждый раз.

### Pitfall 5: merge_from_server обновляет задачу у которой есть pending update
**What goes wrong:** Пользователь изменил задачу → в pending есть update → сервер вернул старое состояние (delta по since) → merge перезаписывает свежее локальное изменение.
**Why it happens:** D-17 решил: server-wins + log warning. Но реализация merge должна проверять pending_ids ПЕРЕД перезаписью.
**How to avoid:** В `merge_from_server()` собирать `pending_ids` из текущего `pending_changes` и логировать (не блокировать) конфликт.

### Pitfall 6: settings.json и cache.json в одном flush
**What goes wrong:** Вызов `save()` при каждом `add_pending_change()` записывает весь `_data` включая weeks (потенциально большой). При 10+ задачах rapid-input → UI microfreezes (PITFALLS.md Performance Traps таблица).
**How to avoid:** Отдельный `_save_locked()` только для `pending_changes` и `meta`; полный flush при выходе и успешном sync. Или debounce: накапливать изменения, flush через `after(500, save)`.

---

## Code Examples

### TaskChange — рекомендованный shape (Claude's discretion)

```python
# client/core/models.py

from dataclasses import dataclass, field
from typing import Optional, Literal
import uuid
from datetime import datetime, timezone

def utcnow_iso() -> str:
    """UTC timestamp в ISO 8601 формате совместимым с сервером."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

@dataclass
class TaskChange:
    """Операция в pending_changes queue. Зеркалит server TaskChange."""
    op: Literal["create", "update", "delete"]
    task_id: str
    # CREATE/UPDATE fields (all optional; omit for DELETE)
    text: Optional[str] = None
    day: Optional[str] = None
    time_deadline: Optional[str] = None
    done: Optional[bool] = None
    position: Optional[int] = None
    # Internal metadata (not sent to server)
    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=utcnow_iso)

    def to_wire(self) -> dict:
        """Serialize для отправки на /api/sync (без change_id и ts)."""
        d = {"op": self.op, "task_id": self.task_id}
        for key in ("text", "day", "time_deadline", "done", "position"):
            v = getattr(self, key)
            if v is not None:
                d[key] = v
        return d
```

### LocalStorage init + atomic write

```python
# client/core/storage.py

import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_VERSION = 1

class LocalStorage:
    APP_DIR = "ЛичныйЕженедельник"  # display; не используется в keyring

    def __init__(self):
        appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA", ".")
        self.base_path = Path(appdata) / self.APP_DIR
        self.cache_file = self.base_path / "cache.json"
        self.settings_file = self.base_path / "settings.json"
        self.logs_dir = self.base_path / "logs"
        self._lock = threading.Lock()
        self._data: dict = {}

    def init(self) -> None:
        """Инициализация: создать директории, загрузить кеш, настроить логирование."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._setup_logging()
        self._load()

    def _load(self) -> None:
        """Загрузить cache.json; при ошибке — начать с пустого кеша."""
        if not self.cache_file.exists():
            self._data = {"meta": {"cache_version": _CACHE_VERSION}, "tasks": [], "pending_changes": []}
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            # schema migration placeholder
            if self._data.get("meta", {}).get("cache_version") != _CACHE_VERSION:
                logger.warning("Версия кеша изменилась — рекомендован full resync")
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Не удалось загрузить cache.json: %s. Начинаю с пустого кеша.", exc)
            self._data = {"meta": {"cache_version": _CACHE_VERSION}, "tasks": [], "pending_changes": []}

    def _save_locked(self) -> None:
        """Atomic write через tmp + os.replace(). Вызывается только под _lock."""
        tmp = self.cache_file.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.cache_file)
        except OSError as exc:
            logger.error("Не удалось сохранить cache.json: %s", exc)
            tmp.unlink(missing_ok=True)

    def _setup_logging(self) -> None:
        """RotatingFileHandler (D-27)."""
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(
            self.logs_dir / "client.log",
            maxBytes=1 * 1024 * 1024,  # 1MB
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
```

### SyncManager._attempt_sync — полный happy-path

```python
# client/core/sync.py — key method

def _attempt_sync(self) -> bool:
    """Одна попытка sync: push pending + pull delta. Возвращает True при успехе."""
    from datetime import datetime, timezone
    import requests

    last_sync_at = self.storage.get_meta("last_sync_at")
    is_stale = self._is_stale(last_sync_at)

    # Push pending (D-20: ПЕРЕД full resync)
    pending = self.storage.drain_pending_changes()
    if pending or is_stale:
        since = None if is_stale else last_sync_at
        wire_changes = [c.to_wire() if hasattr(c, "to_wire") else c for c in pending]
        payload = {
            "since": since,
            "changes": wire_changes,
        }
        try:
            resp = self._session.post(
                f"{self._api_base}/sync",
                json=payload,
                headers=self._auth_headers(),
                timeout=10,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Sync network error: %s", exc)
            self.storage.restore_pending_changes(pending)
            return False

        if resp.status_code == 401:
            logger.warning("Sync 401 — попытка refresh токена")
            if self._auth_manager.refresh_access():
                self.storage.restore_pending_changes(pending)
                return False  # retry на следующем цикле с новым токеном
            logger.error("Refresh не удался — требуется повторный логин")
            return False

        if resp.status_code != 200:
            logger.error("Sync HTTP %d: %s", resp.status_code, resp.text[:200])
            self.storage.restore_pending_changes(pending)
            return False

        data = resp.json()
        self.storage.merge_from_server(
            server_changes=data.get("changes", []),
            server_timestamp=data["server_timestamp"],
        )
        logger.info("Sync OK: push %d ops, recv %d changes", len(pending), len(data.get("changes", [])))
    return True
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 (уже установлен — server/requirements-dev.txt) |
| Config file | `client/pyproject.toml` (создать Wave 0) |
| Quick run command | `python -m pytest client/tests/ -x -q` |
| Full suite command | `python -m pytest client/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| SYNC-01 | cache.json создаётся в %APPDATA%/ЛичныйЕженедельник/ | unit | `python -m pytest client/tests/test_storage.py::test_init_creates_cache_file -x` | Wave 0 |
| SYNC-01 | Загрузка corrupted cache.json не крашит — начинает с пустого | unit | `python -m pytest client/tests/test_storage.py::test_corrupted_cache_recovery -x` | Wave 0 |
| SYNC-02 | add_pending_change добавляет в pending_changes и персистирует | unit | `python -m pytest client/tests/test_storage.py::test_add_pending_change_persisted -x` | Wave 0 |
| SYNC-03 | force_sync() немедленно будит sync thread (< 1s) | unit | `python -m pytest client/tests/test_sync.py::test_force_sync_wakes_immediately -x` | Wave 0 |
| SYNC-03 | Sync thread при сетевой ошибке применяет backoff | unit (mock) | `python -m pytest client/tests/test_sync.py::test_backoff_on_network_error -x` | Wave 0 |
| SYNC-03 | 50 offline задач достигают сервера после reconnect | integration | `python -m pytest client/tests/test_sync.py::test_offline_queue_50_tasks -x` | Wave 0 |
| SYNC-04 | drain_pending_changes под Lock — нет race condition | unit | `python -m pytest client/tests/test_storage.py::test_concurrent_add_and_drain -x` | Wave 0 |
| SYNC-05 | merge_from_server перезаписывает локальную если server_updated_at новее | unit | `python -m pytest client/tests/test_storage.py::test_server_wins_on_conflict -x` | Wave 0 |
| SYNC-05 | merge логирует warning при конфликте с pending | unit | `python -m pytest client/tests/test_storage.py::test_conflict_logged -x` | Wave 0 |
| SYNC-06 | Task.id = uuid4() генерируется до отправки на сервер | unit | `python -m pytest client/tests/test_models.py::test_task_id_is_uuid -x` | Wave 0 |
| SYNC-07 | full resync если last_sync_at > 5 min ago (since=None) | unit (mock) | `python -m pytest client/tests/test_sync.py::test_full_resync_on_stale -x` | Wave 0 |
| SYNC-07 | push pending ПЕРЕД full resync | unit (mock) | `python -m pytest client/tests/test_sync.py::test_push_before_full_resync -x` | Wave 0 |
| SYNC-08 | delete task → deleted_at установлен, задача не удалена из tasks | unit | `python -m pytest client/tests/test_storage.py::test_soft_delete_sets_tombstone -x` | Wave 0 |
| SYNC-08 | tombstone от сервера → задача не воссоздаётся при следующей merge | unit | `python -m pytest client/tests/test_storage.py::test_server_tombstone_not_recreated -x` | Wave 0 |
| AUTH | load_saved_token возвращает True если refresh успешен | unit (mock) | `python -m pytest client/tests/test_auth.py::test_load_saved_token_refresh -x` | Wave 0 |
| AUTH | load_saved_token возвращает False если keyring пустой | unit | `python -m pytest client/tests/test_auth.py::test_load_saved_token_empty_keyring -x` | Wave 0 |
| AUTH | keyring ошибка логируется (не raise) | unit | `python -m pytest client/tests/test_auth.py::test_keyring_error_logged -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest client/tests/ -x -q` (только быстрые unit тесты, < 10s)
- **Per wave merge:** `python -m pytest client/tests/ -v` (полный client suite)
- **Phase gate:** Полный suite зелёный + integration тест с mock server

### Wave 0 Gaps (нужно создать)
- [ ] `client/tests/__init__.py`
- [ ] `client/tests/conftest.py` — fixtures: `tmp_appdata`, `mock_api` (requests-mock)
- [ ] `client/tests/test_storage.py` — unit тесты LocalStorage
- [ ] `client/tests/test_sync.py` — unit тесты SyncManager
- [ ] `client/tests/test_models.py` — unit тесты Task/TaskChange dataclasses
- [ ] `client/tests/test_auth.py` — unit тесты AuthManager
- [ ] `client/pyproject.toml` — pytest config (asyncio_mode не нужен — client sync)
- [ ] Framework install: `pip install requests-mock pytest-mock` (добавить в server/requirements-dev.txt или создать client/requirements-dev.txt)

### conftest.py для client/tests/

```python
# client/tests/conftest.py

import pytest
import requests_mock as req_mock_module
from pathlib import Path

@pytest.fixture
def tmp_appdata(tmp_path, monkeypatch):
    """Подменяет APPDATA на tmp директорию — изолирует тесты от реального AppData."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path

@pytest.fixture
def storage(tmp_appdata):
    """Инициализированный LocalStorage в tmp директории."""
    from client.core.storage import LocalStorage
    s = LocalStorage()
    s.init()
    return s

@pytest.fixture
def mock_api():
    """requests_mock.Mocker для тестов SyncManager и AuthManager."""
    with req_mock_module.Mocker() as m:
        yield m
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `time.sleep(N)` в sync loop | `threading.Event.wait(timeout=N)` | Standard Python pattern | Graceful shutdown + immediate wake |
| `file.write()` прямо в dst | `os.replace(tmp, dst)` | Python 3.3+ | Atomic: нет риска corruption |
| Direct list mutation в threads | `drain_pending_changes()` паттерн | Известный паттерн | Thread-safe TOCTOU-free |
| python-jose для JWT | PyJWT>=2.9.0 | Phase 1 решение (STATE.md) | Клиент НЕ декодирует JWT; irrelevant для Phase 2 |

**Deprecated/outdated в skeleton:**
- `time.sleep(30)` в `_sync_loop` — заменить на Event.wait
- `get_pending_changes() + clear_pending_changes()` — заменить на `drain_pending_changes()`
- Прямое `json.dump()` в cache_file — заменить на tmp + os.replace
- Keyring key `"jwt"` для access_token — убрать (access только в RAM)
- Endpoint `/api/auth/request` → `/api/auth/request-code`

---

## Open Questions

1. **Cyrillic service name в keyring — проверить заранее или оставить на Phase 6?**
   - Что мы знаем: PITFALLS.md Pitfall 7 говорит, что Cyrillic имена ломаются в frozen exe. STACK.md Gotcha 6 говорит о UTF-16 encoding в WinCred.
   - Что неясно: в dev-режиме (python main.py) Cyrillic в service name может работать — тогда тест на не-frozen exe не выявит проблему.
   - Рекомендация: **Использовать ASCII service name `"WeeklyPlanner"` с самого начала** (D-25 это разрешает). Избегает проблему полностью, не создавая migration issue позже.

2. **Tombstone cleanup через час idle — кто триггерит?**
   - Что мы знаем: D-24 — cleanup через час idle в sync thread.
   - Что неясно: "час idle" = 2 успешных sync-цикла без changes? Или реальный таймер?
   - Рекомендация: Sync thread проверяет tombstone-задачи у которых `deleted_at` старше 1 часа И для которых нет pending op. Cleanup opportunistic — при каждом успешном pull.

3. **settings.json — где хранить API_BASE?**
   - Что мы знаем: skeleton хардкодит `API_BASE` в двух местах (`auth.py`, `sync.py`). PITFALLS.md Technical Debt говорит это нужно централизовать.
   - Рекомендация: Создать `client/core/config.py` с `API_BASE = "https://planner.heyda.ru/api"` как module-level константу. Не в `settings.json` (UI-настройка для пользователя) и не хардкод в нескольких файлах.

---

## Sources

### Primary (HIGH confidence)
- `server/api/sync_schemas.py` — точный wire format SyncIn/SyncOut/TaskChange/TaskState (verified in code)
- `server/api/auth_routes.py` — точные endpoints и request/response shapes (verified in code)
- `server/db/models.py` — Task schema (UUID, deleted_at, updated_at server-side) (verified in code)
- `.planning/phases/01-server-auth/01-07-SUMMARY.md` — sync endpoint design decisions + curl examples
- `.planning/research/PITFALLS.md` — Pitfalls 4, 5, 7 (LocalStorage race, keyring frozen exe)
- `.planning/research/ARCHITECTURE.md` — sync protocol patterns (delta + since + tombstones)
- `.planning/phases/02-client-core/02-CONTEXT.md` — 29 locked decisions (D-01 to D-29)
- `client/core/*.py` (все 4 skeleton файла) — публичные сигнатуры, что переиспользовать

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md` §Gotcha 6 — keyring WinCred character limits + Cyrillic UTF-16
- Python docs `os.replace()` — atomic rename on POSIX and Windows (same volume)
- Python docs `threading.Event` — wait(timeout) semantics

### Tertiary (LOW confidence)
- Сравнение ISO 8601 strings лексикографически — корректно только при одинаковом формате (требует тестирования)

---

## Metadata

**Confidence breakdown:**
- Wire format: HIGH — verified against deployed server code
- Thread safety patterns: HIGH — stdlib, well-documented
- keyring Cyrillic: MEDIUM — problem confirmed in Pitfall 7, specific behavior in non-frozen context not tested
- Skeleton salvageability: HIGH — код прочитан полностью

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (стабильный стек; сервер не меняется)
