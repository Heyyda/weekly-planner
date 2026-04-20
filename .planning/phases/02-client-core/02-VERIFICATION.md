---
phase: 02-client-core
verified: 2026-04-16T12:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
human_verification:
  - test: "Реальный production /api/sync round-trip"
    expected: "Задача созданная оффлайн появляется через /tasks API на живом сервере planner.heyda.ru"
    why_human: "Требует реального прохождения Telegram-авторизации (бот → 6-значный код) и живого VPS. Покрыто requests-mock E2E тестами — production human-UAT отложен согласно Phase 1 HUMAN-UAT pattern."
---

# Phase 2: Клиентское ядро — Verification Report

**Phase Goal:** Десктопный клиент умеет хранить задачи локально и синхронизировать их с сервером — без UI, но проверяемо через логи
**Verified:** 2026-04-16T12:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Задача, созданная в `cache.json` offline, автоматически появляется на сервере при восстановлении сети | VERIFIED | `test_full_happy_path` + `test_offline_50_tasks_no_loss_after_reconnect` в `test_e2e_sync.py` — FakeServer stateful mock подтверждает доставку через `_attempt_sync` |
| 2 | 50 задач, созданных подряд при отключённой сети, все доходят до сервера после reconnect — без потерь и дублей | VERIFIED | `test_offline_50_tasks_no_loss_after_reconnect`: 50 Task.new + 3 failed attempts + server.online=True + `assert len(server.tasks) == 50` + `assert set(server.tasks.keys()) == set(task_ids)` |
| 3 | Задача, удалённая на одном устройстве, не воссоздаётся при синхронизации с другого (tombstone работает) | VERIFIED | `test_tombstone_not_recreated_on_other_device`: device B storage получает tombstone через merge_from_server, `get_visible_tasks() == []` |
| 4 | `threading.Lock` защищает `pending_changes` — нет race condition при одновременном добавлении из UI и сбросе sync-потоком | VERIFIED | `test_concurrent_add_and_drain_is_race_free`: 50 adder-потоков × 100 ops + 50 drainer-потоков — 5000 unique changes без потерь и дубликатов, 0 ошибок |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `client/core/models.py` | Task, TaskChange, utcnow_iso + wire-format | VERIFIED | 185 строк; `class Task`, `class TaskChange`, `def to_wire`, `uuid.uuid4`, `deleted_at` — все поля зеркалят server TaskState |
| `client/core/config.py` | Централизованные константы (API_BASE, KEYRING_SERVICE, интервалы) | VERIFIED | `API_BASE="https://planner.heyda.ru/api"`, `KEYRING_SERVICE="WeeklyPlanner"`, `SYNC_INTERVAL_SECONDS=30.0`, `STALE_THRESHOLD_SECONDS=300`, `BACKOFF_CAP=60.0` |
| `client/core/paths.py` | AppPaths с APPDATA→LOCALAPPDATA→cwd fallback | VERIFIED | `class AppPaths`, `def ensure`, `_resolve_appdata_root` с тремя fallback-ветками |
| `client/core/logging_setup.py` | setup_client_logging + SecretFilter (D-29) | VERIFIED | `RotatingFileHandler`, `class SecretFilter`, `_SETUP_MARKER` для идемпотентности; Bearer/access_token/refresh_token маскируются |
| `client/core/auth.py` | AuthManager с правильными endpoints + keyring rotation | VERIFIED | `/auth/request-code` (не `/auth/request`), `request_id` в verify_code body, `threading.Lock`, все 5 exception-классов |
| `client/core/storage.py` | LocalStorage с Lock + atomic write + drain + soft-delete + merge | VERIFIED | `threading.Lock`, `os.replace` × 2, `drain_pending_changes`, `soft_delete_task`, `merge_from_server`, `cleanup_tombstones`; RLock = 0 |
| `client/core/api_client.py` | SyncApiClient с 401-refresh-retry + exponential backoff | VERIFIED | `class SyncApiClient`, `class ApiResult`, `refresh_access` в 401-retry, `_bump_backoff`, `BACKOFF_CAP` cap 60s |
| `client/core/sync.py` | SyncManager с Event wake + stale detection | VERIFIED | `threading.Event` × 2, time.sleep = 0, `_wake_event.wait`, `drain_pending_changes`, `restore_pending_changes`, `merge_from_server`, `_is_stale`, `cleanup_tombstones`, auth_expired stop |
| `client/tests/conftest.py` | tmp_appdata + mock_api + api_base fixtures | VERIFIED | 3 fixtures; `monkeypatch.setenv("APPDATA", ...)` + `monkeypatch.setenv("LOCALAPPDATA", ...)` |
| `client/pyproject.toml` | pytest config с testpaths=client/tests | VERIFIED | `testpaths = ["client/tests"]`, `--strict-markers`, `--timeout=10` |
| `client/tests/test_infrastructure.py` | 3 маркер-теста fixtures | VERIFIED | 3 теста зелёные |
| `client/tests/test_models.py` | 11 unit-тестов | VERIFIED | 11 passed |
| `client/tests/test_paths.py` | 7 unit-тестов paths + config | VERIFIED | 7 passed |
| `client/tests/test_logging.py` | 6 unit-тестов logging + SecretFilter | VERIFIED | 6 passed |
| `client/tests/test_auth.py` | 14+ unit-тестов AuthManager | VERIFIED | 15 passed (план предполагал 14, реализовано 15) |
| `client/tests/test_storage.py` | 23 unit-тестов + stress test | VERIFIED | 23 passed; stress test 5000 ops прошёл |
| `client/tests/test_api_client.py` | 11 unit-тестов wire-format, backoff | VERIFIED | 11 passed |
| `client/tests/test_sync.py` | 16+ unit-тестов SyncManager | VERIFIED | 20 passed (больше чем ожидалось) |
| `client/tests/test_e2e_sync.py` | 7 E2E интеграционных тестов | VERIFIED | 7 passed |
| `client/tests/test_logs_no_secrets.py` | 2 log-safety теста | VERIFIED | 2 passed |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `Task.new()` | client-generated UUID | `uuid.uuid4()` в `models.py:52` | WIRED | UUID строка 36 символов, идемпотентный CREATE |
| `TaskChange.to_wire()` | server `sync_schemas.TaskChange` | JSON-совместимый dict с `op`, `task_id` | WIRED | partial UPDATE (только не-None), minimal DELETE |
| `LocalStorage._save_locked` | `cache.json` на диске | `os.replace(tmp, cache_file)` в `storage.py:93` | WIRED | atomic write через .tmp файл |
| `add_pending_change / drain_pending_changes` | `self._lock` | `with self._lock` в каждой публичной мутации | WIRED | 10+ `with self._lock` конструкций в storage.py |
| `SyncApiClient.post_sync` | `POST /api/sync` | JSON body `{since, changes: [to_wire()]}` + `Bearer` header | WIRED | `_do_post_sync` в `api_client.py:277` |
| `SyncApiClient on 401` | `AuthManager.refresh_access()` | `self._auth.refresh_access()` + один retry | WIRED | `api_client.py:265-275` |
| `SyncManager.force_sync()` | `_sync_loop` | `self._wake_event.set()` пробуждает `Event.wait()` | WIRED | `sync.py:124` → `sync.py:162` |
| `_attempt_sync` on success | `storage.merge_from_server` | `payload.get("changes")` + `payload.get("server_timestamp")` | WIRED | `sync.py:219` |
| `_attempt_sync` on failure | `storage.restore_pending_changes` | `if drained: storage.restore_pending_changes(drained)` | WIRED | `sync.py:234-235` |
| `setup_client_logging` | SecretFilter на root logger | `addFilter(SecretFilter())` на RotatingFileHandler | WIRED | `logging_setup.py:197`; bearer_header() логирует через logger, фильтр перехватывает |
| `AuthManager._save_refresh_to_keyring` | Windows Credential Manager | `keyring.set_password(KEYRING_SERVICE, KEYRING_REFRESH_KEY, ...)` | WIRED | access_token в keyring НЕ пишется — только refresh_token (D-26) |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| SYNC-01 | 02-05 | Локальный кеш в `cache.json` в AppData | SATISFIED | `test_init_creates_dirs` + `test_save_and_load_roundtrip`; atomic write via os.replace |
| SYNC-02 | 02-05 | Optimistic UI: операции применяются мгновенно + pending queue | SATISFIED | `test_add_task_is_optimistic_and_queues_change`; `add_task` → in-memory + pending одновременно |
| SYNC-03 | 02-07 | Фоновый sync-поток с periodic + immediate wake | SATISFIED | `test_force_sync_wakes_immediately`; Event.wait(30) + force_sync() → wake < 1s |
| SYNC-04 | 02-05 | `threading.Lock` на `pending_changes` (no race condition) | SATISFIED | `test_concurrent_add_and_drain_is_race_free`: 50×100 ops = 5000, 0 потерь |
| SYNC-05 | 02-07 | Server-wins при конфликте (`server updated_at` wins) | SATISFIED | `test_merge_server_wins_on_conflict`; `test_server_wins_on_conflict` (E2E) |
| SYNC-06 | 02-02, 02-06 | UUID генерируются на клиенте — CREATE идемпотентен | SATISFIED | `test_task_id_is_uuid`; `test_idempotent_create_preserves_uuid` — тот же task_id при повторной отправке |
| SYNC-07 | 02-07 | Автоматический full resync при восстановлении после оффлайн | SATISFIED | `test_full_resync_on_stale`: last_sync > 5 мин → since=None; `test_full_resync_after_long_offline` (E2E) |
| SYNC-08 | 02-05 | Tombstone для удалений — не воссоздавать на другом устройстве | SATISFIED | `test_soft_delete_sets_tombstone`; `test_server_tombstone_not_recreated`; `test_tombstone_not_recreated_on_other_device` (E2E) |

All 8 SYNC requirements satisfied with double coverage (unit + integration).

---

### Anti-Patterns Found

No blocking anti-patterns found. Searched all `client/core/*.py` files for:
- TODO/FIXME/PLACEHOLDER → 0 matches
- Empty implementations (`return {}`, `return []`, `return null`) → 0 stub cases (all returns are data-producing)
- Hardcoded empty initial state without fetch → `_empty_data()` correctly populates from file on `_load()`
- `time.sleep` in sync.py → 0 (correctly uses `Event.wait`)
- `RLock` → 0 (correctly uses `Lock` per D-12)

---

### Human Verification Required

#### 1. Production /api/sync round-trip

**Test:** Запустить клиент на реальной машине с рабочим VPS. Ввести Telegram username → получить код от бота → ввести код → создать задачу в UI → проверить через `GET /api/tasks` или прямой запрос к SQLite на VPS.
**Expected:** Задача появляется на сервере в течение 30 секунд (один sync-цикл)
**Why human:** Требует полного Telegram-авторизационного flow (бот должен быть активен и иметь рабочий token), а также живого VPS на 109.94.211.29:8100. Все component-level контракты проверены через requests-mock. Human-UAT отложен согласно паттерну Phase 1 (smoke-test.sh существует для сервера, аналогичный клиентский тест требует собранного .exe — Phase 6).

---

### Test Suite Summary

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_infrastructure.py` | 3 | All passed |
| `test_models.py` | 11 | All passed |
| `test_paths.py` | 7 | All passed |
| `test_logging.py` | 6 | All passed |
| `test_auth.py` | 15 | All passed |
| `test_storage.py` | 23 | All passed (incl. stress 5000 ops) |
| `test_api_client.py` | 11 | All passed |
| `test_sync.py` | 20 | All passed |
| `test_e2e_sync.py` | 7 | All passed |
| `test_logs_no_secrets.py` | 2 | All passed |
| **TOTAL** | **106** | **106 passed, 0 failed** |

Cross-phase sanity: `server/tests` — 92 passed, 0 failed (Phase 1 regression-free).

**Runtime:** 8.15 seconds (well within 60s budget, stress test included)

---

### Gaps Summary

No gaps. All 4 ROADMAP Success Criteria for Phase 2 are automatically verified by the test suite without requiring real server access.

The one human_verification item (production round-trip) is correctly classified as not-a-gap per the verification instructions: "Real production /api/sync round-trip is `human_needed` (requires Phase 1 real auth flow with Telegram, which is already deferred per Phase 1 HUMAN-UAT). Not a gap — covered by requests-mock E2E."

---

*Verified: 2026-04-16T12:00:00Z*
*Verifier: Claude (gsd-verifier)*
