---
phase: 2
slug: client-core
status: refined
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-16
refined_by: planner
refined: 2026-04-16
---

# Phase 2 — Validation Strategy (refined)

> Per-phase validation contract. Per-task map populated by planner.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + requests-mock + pytest-timeout + pytest-mock |
| **Config file** | `client/pyproject.toml` (создаётся в Plan 02-01) |
| **Quick run command** | `python -m pytest client/tests -x --timeout=10` |
| **Full suite command** | `python -m pytest client/tests -v --timeout=60` |
| **Estimated runtime** | ~20-30 секунд (включая stress test SYNC-04 + threading-тесты) |

---

## Sampling Rate

- **After every task commit:** `python -m pytest client/tests -x --timeout=30`
- **After every plan wave:** `python -m pytest client/tests -v --timeout=60`
- **Before `/gsd:verify-work`:** Полный suite зелёный + `python -m pytest server/tests -x` (sanity)
- **Max feedback latency:** 30 секунд

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 02-01-T1 | 01 | 0 | infra | smoke | `pip install -r client/requirements-dev.txt && pytest client/tests --collect-only -q` | ⬜ pending |
| 02-01-T2 | 01 | 0 | infra | unit | `pytest client/tests/test_infrastructure.py -v` | ⬜ pending |
| 02-02-T1 | 02 | 1 | SYNC-06 | unit | `pytest client/tests/test_models.py -v` | ⬜ pending |
| 02-02-T2 | 02 | 1 | infra | unit | `pytest client/tests/test_paths.py -v` | ⬜ pending |
| 02-03-T1 | 03 | 1 | infra | unit | `pytest client/tests/test_logging.py -v` | ⬜ pending |
| 02-04-T1 | 04 | 2 | AUTH (foundation) | smoke | `python -c "from client.core.auth import AuthManager; AuthManager()"` | ⬜ pending |
| 02-04-T2 | 04 | 2 | AUTH | unit | `pytest client/tests/test_auth.py -v` | ⬜ pending |
| 02-05-T1 | 05 | 2 | SYNC-01,02,04,08 | smoke | `python -c "from client.core.storage import LocalStorage; LocalStorage()"` | ⬜ pending |
| 02-05-T2 | 05 | 2 | SYNC-01,02,04,08 | unit + stress | `pytest client/tests/test_storage.py -v --timeout=60` | ⬜ pending |
| 02-06-T1 | 06 | 3 | SYNC-06 | smoke | `python -c "from client.core.api_client import SyncApiClient"` | ⬜ pending |
| 02-06-T2 | 06 | 3 | SYNC-06 | unit | `pytest client/tests/test_api_client.py -v` | ⬜ pending |
| 02-07-T1 | 07 | 3 | SYNC-03,05,07 | smoke | `python -c "from client.core.sync import SyncManager"` | ⬜ pending |
| 02-07-T2 | 07 | 3 | SYNC-03,05,07 | unit + threading | `pytest client/tests/test_sync.py -v --timeout=30` | ⬜ pending |
| 02-08-T1 | 08 | 4 | SYNC-01..08 (E2E) | integration | `pytest client/tests/test_e2e_sync.py -v --timeout=60` | ⬜ pending |
| 02-08-T2 | 08 | 4 | D-29 (log safety) | integration | `pytest client/tests/test_logs_no_secrets.py -v` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (Test Infrastructure Setup)

- [ ] `client/tests/__init__.py` — empty package marker
- [ ] `client/tests/conftest.py` — fixtures: `tmp_appdata`, `mock_api`, `api_base`
- [ ] `client/requirements-dev.txt` — добавить `requests-mock>=1.12.0`, `pytest-mock>=3.14.0`, `pytest-timeout>=2.2.0`
- [ ] `client/pyproject.toml` — pytest config с `testpaths = ["client/tests"]`
- [ ] `client/tests/test_infrastructure.py` — маркер-тест что fixtures работают (3 теста)

---

## Observable vs Introspective Validation

### Observable (filesystem + log inspection)

| Requirement | Observable behavior | Test/Check |
|-------------|---------------------|-----------|
| **SYNC-01** | `cache.json` создан в `%APPDATA%/ЛичныйЕженедельник/cache.json` после первого save | `test_init_creates_dirs` + `test_save_and_load_roundtrip` |
| **SYNC-02** | Task added → видна в-памяти моментально + queued в pending_changes | `test_add_task_is_optimistic_and_queues_change` |
| **SYNC-05** | После sync с newer server updated_at, локальный task матчит сервер | `test_merge_server_wins_on_conflict` + e2e `test_server_wins_on_conflict` |
| **SYNC-08** | Task deleted локально → `deleted_at` установлен; не в `get_visible_tasks()` | `test_soft_delete_sets_tombstone` + e2e `test_tombstone_not_recreated_on_other_device` |
| **D-29** | client.log не содержит access_token/refresh_token после полного flow | `test_no_jwt_in_log_after_full_flow` |

### Introspective (white-box)

| Requirement | Introspective signal | Check |
|-------------|----------------------|-------|
| **SYNC-03** | Daemon thread "PlannerSync" started; `_attempt_sync` вызван при force_sync < 1s | `test_force_sync_wakes_immediately` + e2e `test_force_sync_in_running_thread` |
| **SYNC-04** | `threading.Lock` корректность при 50×100 concurrent ops | `test_concurrent_add_and_drain_is_race_free` (5000 ops) + e2e `test_concurrent_ui_writes_during_sync` |
| **SYNC-06** | Client-generated UUID4 в Task.id; idempotent через одинаковый task_id | `test_task_id_is_uuid` + `test_idempotent_create_preserves_uuid` |
| **SYNC-07** | After >5 min stale → next sync since=None (full resync) | `test_full_resync_on_stale` + e2e `test_full_resync_after_long_offline` |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|--------------|
| Real production /api/sync round-trip | All SYNC | Требует живой VPS + реальный Telegram-код | После Phase 2 верификации — `/gsd:verify-work` или ручной smoke на `https://planner.heyda.ru/api` |
| keyring на Cyrillic-username Windows-профиле | AUTH-03 | Требует Windows с кириллическим username | На реальной машине Никиты в Phase 6 bootstrap |
| keyring в frozen .exe | AUTH-03 / DIST-03 | Требует PyInstaller сборку | Отложено на Phase 6 |

---

## Validation Sign-Off

- [x] Все tasks имеют `<automated>` verify или Wave 0 dependency
- [x] Sampling continuity: нет 3 consecutive tasks без automated verify
- [x] Wave 0 покрывает все MISSING references (conftest + pyproject + requirements-dev)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ✅ refined by planner — готово к gsd-plan-checker / execution
