# Phase 2: Клиентское ядро — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 02-client-core
**Mode:** --auto (user sleeping; Claude picked recommended defaults for all areas)
**Areas auto-resolved:** Cache storage, Data model, Sync cadence, Operation queue, Retry & offline, Conflict resolution, Full resync, Tombstones, Keyring, Logging

---

## Cache storage format & location

| Option | Description | Selected |
|--------|-------------|----------|
| JSON file in AppData | Single file, human-readable, matches skeleton | ✓ (D-01..03) |
| SQLite local DB | More robust for large datasets | |
| Redis or memcached | Separate service | |

**Auto-decision:** JSON в `%APPDATA%/ЛичныйЕженедельник/cache.json` (+ `settings.json` separate)
**Rationale:** Simple, matches skeleton, sufficient for single-user + hundreds of tasks. SQLite overkill.

---

## Data model shape

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror server schema exactly | Single source of truth, minimal translation | ✓ (D-04..06) |
| Simplified local model | Easier to modify, drift risk | |
| Protobuf/MessagePack binary | Smaller files, harder debug | |

**Auto-decision:** `Task` dataclass identical to server (UUID, deleted_at, updated_at, position). JSON via `dataclasses.asdict`. `WeekPlan`/`DayPlan` computed, not stored.

---

## Sync cadence & triggers

| Option | Description | Selected |
|--------|-------------|----------|
| Interval polling only (60s) | Simple | |
| Hybrid: immediate push + 30s pull | Best UX | ✓ (D-07..09) |
| WebSocket / SSE push from server | Low latency, more infra | |

**Auto-decision:** 30-сек polling pull + immediate push через `threading.Event` wake при любом user change.

---

## Operation queue persistence

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory only | Simple, data loss on crash | |
| Persisted to cache.json | Survives crashes | ✓ (D-10..12) |
| Separate ops.log file | Append-only, replay-able | |

**Auto-decision:** Persisted в тот же cache.json под `threading.Lock`. Атомарный `drain_pending_changes()` метод.

---

## Retry semantics & offline detection

| Option | Description | Selected |
|--------|-------------|----------|
| Active health-check before each sync | Extra traffic | |
| Passive (exponential backoff на ошибках) | Minimal overhead | ✓ (D-13..15) |
| Fixed retry count, then give up | Bad for true offline | |

**Auto-decision:** Exponential backoff 1s→60s cap, infinite retries (offline-first). Detection passive через `requests.exceptions.ConnectionError` / `Timeout` / HTTP 5xx.

---

## Conflict resolution UX

| Option | Description | Selected |
|--------|-------------|----------|
| Silent server-wins | User not bothered | ✓ (D-16..18) |
| Toast notification on conflict | Transparent but noisy | |
| Modal "keep local / keep server" | User-empowering, annoying | |

**Auto-decision:** Silent server-wins (aligns Core Value). Log warning если pending_changes на этой же задаче — но перезаписываем.

---

## Full resync trigger (SYNC-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Time-based (>5min offline) | Automatic | ✓ (D-19..21) |
| Manual only (user clicks "full sync") | User control | |
| Session-based (every login) | Expensive | |

**Auto-decision:** Автоматически если последний sync > 5 минут назад. Push pending_changes ПЕРЕД full resync. `force_sync()` public для ручного триггера (tray-меню Phase 3).

---

## Tombstone handling (SYNC-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-delete locally, soft on server | Race — задача возродится | |
| Soft-delete (`deleted_at`), filter on display | Safe | ✓ (D-22..24) |
| Two-phase delete UI | Overkill | |

**Auto-decision:** Soft-delete локально + фильтрация по `deleted_at is None`. Физическое удаление после успешного push + через час idle (background cleanup).

---

## Keyring integration

| Option | Description | Selected |
|--------|-------------|----------|
| keyring Windows Credential Manager | Standard, skeleton предлагает | ✓ (D-25..26) |
| Encrypted file with passphrase | User must remember | |
| OS-specific other backends | Скоуп-creep | |

**Auto-decision:** `keyring` Windows backend. Service name `"ЛичныйЕженедельник"` (fallback ASCII если Cyrillic ломается в frozen exe). Access-token в RAM, refresh+username в keyring.

---

## Logging

| Option | Description | Selected |
|--------|-------------|----------|
| Python logging, rotating file | Standard | ✓ (D-27..29) |
| structlog JSON output | Для агрегации | |
| stdout only | Потеряется в frozen exe | |

**Auto-decision:** `logging.handlers.RotatingFileHandler` → `%APPDATA%/ЛичныйЕженедельник/logs/client.log` (1MB × 5 backups). INFO для sync-событий, DEBUG для details.

---

## Claude's Discretion (explicitly noted in CONTEXT.md)

- File structure in client/core/ (replace vs augment skeleton)
- Private method names
- TaskChange shape (NamedTuple / dataclass / dict)
- `threading.Event` vs `queue.Queue` for sync wake-up
- Exception classes for offline/auth differentiation
- Test file organization

---

## Deferred Ideas (explicit out-of-scope)

- Multi-device session display (→ Phase 3 tray or later)
- Sync status indicator in tray (→ Phase 3 UI)
- Manual conflict-resolution UI (→ v2 if silent causes issues)
- Encryption of cache.json at rest (→ v2 if shared with colleagues)
- Sync metrics / analytics (rejected as scope-creep)
