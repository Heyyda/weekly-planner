# Architecture Research

**Domain:** Personal multi-device task planner (desktop + Telegram bot + sync server)
**Researched:** 2026-04-14
**Confidence:** HIGH (stack pre-decided, architecture follows well-understood patterns for single-user local-first apps)

---

## Standard Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│  CLIENTS                                                                │
│                                                                         │
│  ┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐  │
│  │  Desktop PC #1   │    │  Desktop PC #2   │    │  Telegram Bot   │  │
│  │  (work, primary) │    │  (home, review)  │    │  (mobile quick) │  │
│  │                  │    │                  │    │                 │  │
│  │  CustomTkinter   │    │  CustomTkinter   │    │  python-        │  │
│  │  + LocalStorage  │    │  + LocalStorage  │    │  telegram-bot   │  │
│  │    cache.json    │    │    cache.json    │    │  (no local DB)  │  │
│  └────────┬─────────┘    └────────┬─────────┘    └───────┬─────────┘  │
│           │ REST/JSON             │ REST/JSON             │ REST/JSON  │
└───────────┼───────────────────────┼───────────────────────┼────────────┘
            │                       │                       │
            └───────────────────────┴───────────────────────┘
                                    │
                    ┌───────────────▼──────────────────┐
                    │       VPS 109.94.211.29           │
                    │                                   │
                    │  ┌──────────────────────────┐    │
                    │  │   FastAPI Server          │    │
                    │  │   port: 8100              │    │
                    │  │                           │    │
                    │  │  /auth   /tasks   /sync   │    │
                    │  │  /weeks  /health  /version│    │
                    │  └──────────┬───────────────┘    │
                    │             │                     │
                    │  ┌──────────▼───────────────┐    │
                    │  │  SQLite (WAL mode)        │    │
                    │  │  weekly_planner.db        │    │
                    │  │                           │    │
                    │  │  users / tasks / sessions │    │
                    │  └──────────────────────────┘    │
                    │                                   │
                    │  (also runs: E-bot device-manager │
                    │   on separate port/systemd unit)  │
                    └───────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Boundary |
|-----------|----------------|----------|
| **Desktop Client** | UI rendering, local-first task storage, optimistic updates, OS integration (tray, hotkey, overlay, autostart, notifications) | Owns local cache.json; never writes directly to DB |
| **LocalStorage (cache.json)** | Single offline source of truth per device; holds weeks data + pending_changes queue | Persists in %APPDATA%/ЛичныйЕженедельник/ |
| **SyncManager (background thread)** | Polls pending_changes every 30s, POSTs to /sync, merges server response back into cache | Runs as daemon thread; all network errors are silent |
| **FastAPI Server** | Auth provider, data repository, conflict resolver — thin API, no heavy business logic | Owns SQLite; is the canonical source of truth |
| **Telegram Bot** | Mobile quick-capture and read-only week view; stateless — reads from and writes to server directly, no local cache | Thin client; no cache; runs as separate long-polling process on VPS |

---

## Recommended Project Structure

The skeleton already laid out in the codebase is sound. Key additions needed:

```
server/
├── api.py                  # FastAPI app (current stub → real endpoints)
├── routes/
│   ├── auth.py             # POST /auth/telegram, POST /auth/refresh
│   ├── tasks.py            # GET/POST/PATCH/DELETE /tasks
│   └── sync.py             # POST /sync (batch upsert + response)
├── services/
│   └── sync_service.py     # Conflict resolution logic (server-wins merge)
├── db.py                   # SQLAlchemy models + WAL pragma on connect
├── models.py               # Pydantic schemas (request/response DTOs)
├── auth.py                 # JWT create/verify, Telegram code flow
└── config.py               # Env vars

bot/                         # NEW: Telegram bot process (separate from server)
├── bot.py                  # Main entry, long-polling setup
├── handlers.py             # Command handlers: /start /add /week /done
└── api_client.py           # HTTP calls to FastAPI (same as desktop client)
```

### Structure Rationale

- **server/routes/**: Split from monolithic api.py once endpoints exceed 5; prevents 500-line files
- **server/services/**: Keeps route handlers thin; sync_service owns the merge logic
- **bot/ as sibling to server/**: Bot is a separate process, not part of the FastAPI app — this avoids blocking the ASGI event loop with bot polling
- **bot/api_client.py**: Bot uses same REST API as desktop clients; no special bot-only endpoints needed (simplifies server)

---

## Architectural Patterns

### Pattern 1: Operation Queue (Pending Changes)

**What:** Client never calls individual REST endpoints per action. Instead, each mutation (create/update/delete) is appended as a JSON operation object to `pending_changes` in local cache. The SyncManager drains this queue in a single batch POST to `/sync`.

**When to use:** Always. This is the core of offline tolerance.

**Trade-offs:**
- Pro: Natural batching, works offline without code changes, single sync point
- Pro: Easy to reason about — all server writes go through one code path
- Con: Ordering matters — operations must be applied in sequence on server
- Con: If operation fails mid-queue, must replay from failure point (use server-side idempotency keys)

**Concrete implementation:**
```python
# client/core/storage.py
def add_pending_change(self, op: dict):
    # op = {"id": uuid4(), "op": "update_task", "data": {...}, "ts": utcnow()}
    self._data["pending_changes"].append(op)
    self._save()

# client/core/sync.py — SyncManager._do_sync()
def _do_sync(self):
    pending = self.storage.get_pending_changes()
    if not pending:
        return
    resp = self.session.post("/sync", json={"changes": pending}, timeout=10)
    # Server returns canonical week data to overwrite local state
    server_weeks = resp.json()["weeks"]
    self.storage.merge_from_server(server_weeks)
    self.storage.clear_pending_changes()
```

### Pattern 2: Last-Modified Delta Sync (for pull)

**What:** On each sync cycle, client sends its `last_sync_at` timestamp. Server returns only tasks modified after that timestamp. Client merges into local cache. This replaces full-state pull.

**When to use:** After initial first-sync; on reconnect after offline period; periodic background pull.

**Trade-offs:**
- Pro: Minimal bandwidth — only changed records transferred
- Pro: Fast on large task histories
- Con: Clock skew between client and server can miss records — mitigated by server always using its own `updated_at` timestamp, never trusting client clocks for comparison
- Con: Requires `updated_at` index on tasks table (add this from day one)

**Concrete implementation:**
```python
# GET /sync?since=2026-04-13T10:00:00Z
# Server: SELECT * FROM tasks WHERE user_id=? AND updated_at > ?
# Client merges response into cache, updates last_sync_at
```

### Pattern 3: Soft Deletes (Tombstones)

**What:** Tasks are never hard-deleted from SQLite. Instead, a `deleted_at` timestamp is set (NULL = alive, timestamp = deleted). Server includes recently-deleted records in delta sync responses so all clients learn about deletions.

**When to use:** Any time delete operations need to propagate across offline-capable clients.

**Why this matters:** Without tombstones, the following scenario corrupts state:
1. PC#1 creates task T1, syncs.
2. PC#2 goes offline. Knows about T1.
3. PC#1 deletes T1 (hard delete from server).
4. PC#2 comes online, syncs: server has no T1, but PC#2 still has it in cache.
5. PC#2's pending_changes includes no delete — server can't know if T1 was never received or intentionally kept.

**Tombstone cleanup:** Add a cron job or `/cleanup` endpoint to purge deleted_at records older than 90 days.

**Schema addition:**
```sql
-- tasks table
deleted_at TIMESTAMP NULL DEFAULT NULL
-- Query for "live" tasks: WHERE deleted_at IS NULL
-- Query for sync delta: WHERE updated_at > ? (includes tombstones)
```

### Pattern 4: Idempotent Operations (UUID client-generated IDs)

**What:** Task IDs are UUIDs generated on the client at creation time, not auto-increment integers from the server. Every operation carries the task's UUID.

**When to use:** Always, for any offline-capable write.

**Why:** If a "create task" operation is sent to server, server applies it, but network drops before client gets the response — client will retry on next sync. Server must be able to receive the same "create" operation twice without duplicating the task. UUID as primary key + `INSERT OR IGNORE` / `ON CONFLICT DO UPDATE` on server makes all operations naturally idempotent.

**Trade-offs:**
- Pro: No "duplicate task" bugs on retry
- Pro: No round-trip required to get an ID before showing task in UI
- Con: UUIDs are larger than integers (acceptable for this scale)

---

## Data Flow

### Task Creation (Optimistic)

```
User types task → presses Enter
    │
    ▼
TaskWidget created in UI immediately (Task dataclass with client UUID)
    │
    ▼
DayPlan.tasks.append(task)  [in-memory]
    │
    ▼
LocalStorage.add_pending_change({"op": "create", "task": task.to_dict()})
LocalStorage.save_week(week)  [cache.json updated]
    │
    ▼ (background, 30s later or on force_sync())
SyncManager._do_sync()
    │
    POST /sync {"changes": [...]}
    │
    ▼
Server validates JWT → applies operations to SQLite → returns updated weeks
    │
    ▼
Client: storage.merge_from_server(weeks) → storage.clear_pending_changes()
UI refreshes if current week changed
```

### Cross-Device Sync (Delta Pull)

```
PC#1 creates/edits tasks → syncs to server
     ↓
PC#2 wakes from sleep (or 30s timer fires)
     ↓
SyncManager: POST /sync {"since": "2026-04-14T09:00:00Z", "changes": []}
     ↓
Server: SELECT tasks WHERE user_id=? AND updated_at > '2026-04-14T09:00:00Z'
     ↓
Returns changed tasks (including tombstones)
     ↓
storage.merge_from_server() — upsert into cache, remove tombstoned tasks
UI refreshes
```

### Telegram Bot Flow (Stateless)

```
User sends /add "buy milk friday"
     ↓
Bot parses text → extracts task text + day
     ↓
bot/api_client.py: POST /tasks {"text": "buy milk", "day": "2026-04-17", ...}
  (with user JWT from bot's credential store)
     ↓
Server creates task in SQLite (returns task object)
     ↓
Bot replies: "Задача добавлена: buy milk (пятница)"
     ↓
Next time Desktop syncs: picks up new task via delta pull
```

### Auth Flow (Telegram Code)

```
First launch (no JWT in keyring)
     ↓
UI: show login screen → user enters Telegram username
     ↓
POST /auth/request {"telegram_username": "@nikita"}
     ↓
Server: Telegram Bot sends code "12345" to user via DM
     ↓
User sees code in Telegram → enters in app
     ↓
POST /auth/verify {"telegram_username": "@nikita", "code": "12345"}
     ↓
Server: creates/fetches User record, issues JWT + refresh_token
     ↓
Client: keyring.set_password("ЛичныйЕженедельник", "jwt", token)
     ↓
All subsequent requests: Authorization: Bearer <JWT>
```

---

## Data Model (Minimal, Planning-Level)

### Server SQLite Schema

```sql
-- Users
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id BIGINT  UNIQUE NOT NULL,
    username    TEXT    NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks (core table)
CREATE TABLE tasks (
    id          TEXT PRIMARY KEY,          -- UUID, client-generated
    user_id     INTEGER REFERENCES users(id),
    text        TEXT    NOT NULL,
    day         DATE    NOT NULL,          -- ISO: 2026-04-14
    done        BOOLEAN DEFAULT FALSE,
    deadline    TIMESTAMP NULL,            -- optional time within day
    position    INTEGER DEFAULT 0,         -- sort order within day
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMP NULL             -- tombstone; NULL = alive
);
CREATE INDEX idx_tasks_user_updated ON tasks(user_id, updated_at);
CREATE INDEX idx_tasks_user_day ON tasks(user_id, day, deleted_at);

-- Day notes (free-form per day)
CREATE TABLE day_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id),
    day         DATE    NOT NULL,
    content     TEXT    DEFAULT '',
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, day)
);

-- Auth sessions
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(id),
    refresh_token   TEXT UNIQUE NOT NULL,
    expires_at      TIMESTAMP NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Telegram auth codes (short-lived)
CREATE TABLE auth_codes (
    telegram_username TEXT PRIMARY KEY,
    code              TEXT NOT NULL,
    expires_at        TIMESTAMP NOT NULL
);
```

### Client Local Cache (cache.json structure)

```json
{
  "meta": {
    "user_id": 1,
    "last_sync_at": "2026-04-14T10:00:00Z",
    "cache_version": 1
  },
  "weeks": {
    "2026-04-14": {
      "tasks": [
        {"id": "uuid", "text": "...", "day": "2026-04-14", "done": false,
         "deadline": null, "position": 0, "updated_at": "..."}
      ],
      "notes": {"2026-04-14": "text...", "2026-04-15": ""}
    }
  },
  "pending_changes": [
    {"change_id": "uuid", "op": "create", "task": {...}, "ts": "..."},
    {"change_id": "uuid", "op": "update", "task_id": "uuid", "fields": {"done": true}, "ts": "..."},
    {"change_id": "uuid", "op": "delete", "task_id": "uuid", "ts": "..."}
  ]
}
```

---

## API Surface Sketch

```
POST /auth/request       {"telegram_username": str}             → 200 OK
POST /auth/verify        {"telegram_username": str, "code": str} → {"jwt": str, "refresh_token": str}
POST /auth/refresh       {"refresh_token": str}                 → {"jwt": str}

GET  /tasks?since=ISO    Auth required                          → {"tasks": [...], "server_time": ISO}
POST /tasks              Auth required + task payload           → {"task": {...}}
PATCH /tasks/{id}        Auth required + partial fields         → {"task": {...}}
DELETE /tasks/{id}       Auth required                          → 204 (sets deleted_at)

GET  /notes?week=ISO     Auth required                          → {"notes": {"date": "text"}}
PATCH /notes/{date}      Auth required + {"content": str}       → {"note": {...}}

POST /sync               Auth required + {"changes": [...], "since": ISO}
                         → {"tasks": [...], "notes": {...}, "server_time": ISO}

GET  /version            No auth                                → {"version": "1.0.0", "sha256": "..."}
GET  /health             No auth                                → {"status": "ok"}
```

**Key decision: /sync as primary endpoint.** Desktop clients use `/sync` exclusively (batch changes + delta pull in one round-trip). Individual CRUD endpoints (`/tasks`, `/notes`) are used only by the Telegram bot (which is always online and prefers simpler single-operation calls).

---

## Key Architectural Tradeoffs — Decisions

### Full State Replication vs Delta Sync

**Decision: Delta sync with `since` timestamp.**

Full state replication (send all tasks on every sync) is tempting for simplicity but fails with a year of history — a user with 1000 tasks would transmit all of them every 30 seconds. Delta sync using server's `updated_at > since` is simple to implement and correct for single-user data where no clock arbitration between clients is needed (server timestamp is the single clock).

**Confidence: HIGH** — standard pattern for personal sync apps (Things 3, Obsidian Sync use variants of this).

### Push Notifications (SSE vs Long Polling vs Nothing)

**Decision: Nothing for v1. 30-second polling is sufficient.**

SSE from server to desktop client requires keeping an HTTP connection open permanently. This adds complexity: reconnect logic, handling SSE with Python `requests` (not straightforward — requires `sseclient-py` or `httpx` with streaming), and a persistent connection per logged-in device. For a single-user personal planner where changes are infrequent, 30-second polling lag is imperceptible.

**When to reconsider:** If desktop-to-desktop sync latency becomes noticeable (e.g., task added on one PC not appearing on other PC within expected time). At that point, add SSE on top of existing polling — endpoints already exist.

**Confidence: HIGH** — SSE is technically available in FastAPI, but unnecessary complexity for v1.

### Telegram Bot: Long Polling vs Webhook

**Decision: Long polling.**

The VPS already has HTTPS (heyda.ru), so webhooks are technically feasible. However, long polling is simpler: no Telegram bot webhook registration/management, no path routing in nginx/FastAPI, no separate SSL cert concerns for the bot. The bot serves one user and handles ~5-20 interactions per day — long polling overhead is negligible. `python-telegram-bot`'s `Application.run_polling()` handles this in 3 lines.

**Webhook would be needed when:** Multiple concurrent users, response latency < 1s matters, or CPU/bandwidth of VPS becomes constrained by polling.

**Confidence: HIGH**

### Single SQLite with WAL vs Multiple DBs

**Decision: Single SQLite with WAL mode enabled.**

Only one user's data. SQLite in WAL mode allows concurrent reads while a write is in progress — the only write contention is the Telegram bot and desktop clients hitting the server simultaneously, which is rare. Set `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` on every new connection.

**No need for Postgres:** Postgres adds operational complexity (service management, connection strings, backups) that delivers no benefit at single-user scale. SQLite with WAL handles the load trivially.

**Confidence: HIGH** — confirmed by WAL documentation and FastAPI+SQLite production usage patterns.

### Business Logic Placement: Client-Heavy vs Server-Heavy

**Decision: Client-heavy with server as thin validator.**

The app must work fully offline. Therefore all business logic that affects what the user sees (overdue detection, week navigation, day aggregation, task sorting) lives on the client in `client/core/`. The server's only "business logic" is:
1. JWT validation
2. Idempotent upsert of tasks from pending_changes
3. Soft delete (set deleted_at)
4. Delta query (WHERE updated_at > since)

There is no server-side task processing, no computed fields, no server-generated notifications. This means the server can be replaced or restarted without data loss (client cache is sufficient for continued operation).

**Trade-off accepted:** If multiple users were ever added (currently out-of-scope), server-side logic would need to expand. For single-user, this is correct.

**Confidence: HIGH**

---

## Build Order (Recommended Implementation Sequence)

This sequence is dependency-driven: each phase enables the next.

```
Phase 1: Server Core
├── db.py: SQLite schema + WAL pragma + SQLAlchemy models
├── auth.py: Telegram code flow + JWT issuance
├── routes/auth.py: POST /auth/request + /auth/verify + /auth/refresh
├── routes/sync.py: POST /sync (accepts changes, returns delta)
└── Deployed to VPS, tested with curl

    WHY FIRST: Without a working server, desktop sync is untestable.
    Bot and desktop both depend on this.

Phase 2: Desktop Client — Core + Auth
├── client/core/auth.py: JWT keyring storage, login flow
├── client/core/storage.py: cache.json read/write, pending_changes queue
├── client/core/sync.py: Background thread, POST /sync, merge response
└── client/core/models.py: Task, DayPlan, WeekPlan dataclasses

    WHY SECOND: Local-first foundation. All UI depends on storage+models.
    Sync must be solid before building UI on top.

Phase 3: Desktop Client — UI
├── client/ui/themes.py: Color palettes
├── client/ui/sidebar.py: Overlay + slide animation (Win32)
├── client/ui/week_view.py: Week navigation
├── client/ui/day_panel.py: Collapsible days
├── client/ui/task_widget.py: Task rows + checkbox
└── client/app.py: Orchestration + tray + hotkey

    WHY THIRD: Depends on Phase 2 models/storage. UI-spec phase
    before this (use /gsd:ui-phase to produce UI-SPEC.md).

Phase 4: Telegram Bot
├── bot/bot.py: Long-polling setup
├── bot/handlers.py: /add /week /done commands
└── bot/api_client.py: Calls FastAPI server

    WHY FOURTH: Depends on Phase 1 server being stable.
    Bot is simpler than desktop — implement after desktop is working.

Phase 5: Distribution + Auto-Update
├── client/utils/updater.py: Version check + SHA256 + bat launcher pattern
├── build/build.bat: PyInstaller --onefile
└── Server: GET /version endpoint with sha256 of latest .exe

    WHY LAST: Polish layer. Depends on stable .exe output from Phases 2-3.
```

---

## Auto-Update Pattern (from E-bot, confirmed)

The E-bot codebase (`S:\Проекты\е-бот\mega.py`) implements this pattern in production:

1. On startup: background thread calls `GET /version` → compares `VERSION` constant
2. If server version > local: downloads new .exe to temp dir, verifies SHA256
3. Writes a `.bat` file to `%TEMP%` that: waits 2s, copies new .exe over old, launches new .exe, deletes bat
4. Runs bat via `subprocess.Popen` + immediately `sys.exit()` (releases file lock so bat can overwrite)
5. UAC elevation via `ShellExecute runas` if write to program directory is denied

**Windows-specific gotcha:** Running `.exe` cannot overwrite itself. The `.bat` intermediate is mandatory. This pattern already works in E-bot v1.11.1.

**SHA256 chain:** Server stores sha256 in `/version` response. Client verifies before applying. Prevents corrupted downloads from being applied.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Telegram Bot API | python-telegram-bot long polling from VPS | Same bot serves both auth codes and quick-capture commands |
| Windows Credential Manager | keyring library → `keyring.set_password()` | JWT + refresh token stored here; no plaintext on disk |
| Windows Registry | winreg via autostart.py | HKCU\Software\Microsoft\Windows\CurrentVersion\Run |
| Windows Toast Notifications | win10toast or winotify library | For overdue task alerts; optional / user-configurable |

### Internal Component Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| UI ↔ Core | Direct Python function calls (same process) | UI calls storage.get_week(), storage.add_pending_change() |
| Core ↔ Server | HTTP REST via requests library | Only SyncManager talks to server; UI never calls HTTP directly |
| Desktop ↔ Bot | No direct connection | Both sync independently to same server; server is the mediator |
| SyncManager ↔ UI | Tkinter `after()` callback on main thread | Sync runs in daemon thread; UI updates must be dispatched to main thread via app.after(0, callback) |
| Server ↔ SQLite | SQLAlchemy ORM with WAL pragma | Single connection pool, busy_timeout=5000ms |

---

## Anti-Patterns

### Anti-Pattern 1: UI Calls HTTP Directly

**What people do:** Task widget calls `requests.post("/tasks")` on button click.

**Why it's wrong:** Blocks the Tkinter main thread → UI freezes for 1-5 seconds on slow network or timeout. Offline clicks raise exceptions in UI code.

**Do this instead:** UI calls `storage.add_pending_change()` only. SyncManager handles all HTTP in its daemon thread.

### Anti-Pattern 2: Server Auto-Increment IDs as Task Identity

**What people do:** Client sends task without ID; server assigns `id=42`; client must wait for response to know the task's ID.

**Why it's wrong:** Breaks offline creation. Client can't reference the task in follow-up operations (update, delete) until server confirms the ID. Duplicates on retry.

**Do this instead:** Client generates UUID at creation time. Server uses `INSERT OR IGNORE` on conflict. Task exists in local cache with stable UUID immediately.

### Anti-Pattern 3: Hard Deleting Tasks

**What people do:** `DELETE FROM tasks WHERE id=?` on the server.

**Why it's wrong:** Offline client still has the task. On next sync, server has no record → client doesn't know if server never received it or it was deleted → client re-creates it.

**Do this instead:** `UPDATE tasks SET deleted_at=NOW()`. Delta sync returns tombstones. Client removes from cache when it receives `deleted_at IS NOT NULL`.

### Anti-Pattern 4: Sync on Every Keystroke

**What people do:** Send HTTP request on every task text change (debounced to 500ms).

**Why it's wrong:** Network traffic multiplies; offline text edits fail; sync logic becomes complex (partial text states pile up in pending_changes).

**Do this instead:** Sync on "task saved" event (Enter key, focus lost, explicit save). 30-second background sync handles the rest. Pending_changes accumulate locally; batch send.

### Anti-Pattern 5: Telegram Bot Inside the FastAPI Process

**What people do:** Register bot webhook handler as a FastAPI route; run bot in the same uvicorn process.

**Why it's wrong:** python-telegram-bot's long polling uses its own event loop and threading model. Running it inside FastAPI's ASGI event loop causes conflicts and complex async coordination.

**Do this instead:** Bot runs as a completely separate process (`bot/bot.py`), managed by its own systemd service unit on the VPS. It calls the same FastAPI endpoints as the desktop clients.

---

## Scaling Considerations

This is a single-user app. Scaling is not a concern for v1. For reference:

| Scale | Architecture Adjustment |
|-------|--------------------------|
| 1 user (current) | SQLite + single FastAPI process. No changes needed. |
| 10 users (colleagues) | SQLite still fine. Add per-user rate limiting. Row-level auth already in schema. |
| 100+ users | Migrate to Postgres. Keep FastAPI. SQLite becomes a bottleneck at concurrent writes. |

---

## Sources

- SQLite WAL mode: https://sqlite.org/wal.html
- FastAPI + SQLite concurrent writes: https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/
- Offline-first architecture patterns: https://rxdb.info/offline-first.html
- Telegram bot long polling vs webhook: https://grammy.dev/guide/deployment-types
- Soft deletes in sync (Couchbase Sync Gateway tombstones): https://docs.couchbase.com/sync-gateway/current/manage/managing-tombstones.html
- E-bot auto-update implementation (production reference): `S:\Проекты\е-бот\mega.py` lines 479-618
- FastAPI SSE (deferred to v2): https://fastapi.tiangolo.com/tutorial/server-sent-events/

---

*Architecture research for: Личный Еженедельник (personal multi-device task planner)*
*Researched: 2026-04-14*
