---
phase: 2
slug: client-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 2 — Validation Strategy

> Per-phase validation contract. Planner refines per-task map during plan generation.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + requests-mock (or responses) + tmp_path for filesystem |
| **Config file** | `client/pyproject.toml` OR extend `server/pyproject.toml` to include `client/tests` — planner decides |
| **Quick run command** | `python -m pytest client/tests -x --timeout=10` |
| **Full suite command** | `python -m pytest client/tests -v --tb=short` |
| **Estimated runtime** | ~10-20 seconds (no bcrypt here — fast) |

---

## Sampling Rate

- **After every task commit:** `python -m pytest client/tests -x --timeout=10`
- **After every plan wave:** Full client suite + sanity-check server suite doesn't break (`python -m pytest server/tests -x`)
- **Before `/gsd:verify-work`:** Full suite green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

> Populated by planner. Every task must reference either automated test, inline Python check, or explicit Wave 0 dependency.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| *TBD* | *planner fills* | *planner fills* | *planner fills* | *planner fills* | *planner fills* | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (Test Infrastructure Setup)

- [ ] `client/tests/conftest.py` — shared fixtures: tmp_path cache.json factory, mock Settings with APPDATA override, mock authenticated HTTP session
- [ ] `client/tests/__init__.py` — empty package marker
- [ ] `client/requirements-dev.txt` OR extend existing — add `requests-mock` (or `responses`)
- [ ] pytest config inclusion — either new `client/pyproject.toml` or update root / server one to include `client/tests` testpath
- [ ] `client/core/__init__.py` uses sufficient re-exports so tests `from client.core import LocalStorage, SyncManager, AuthManager` works cleanly

---

## Observable vs Introspective Validation

### Observable (filesystem + log inspection — user-facing effect verifiable)

| Requirement | Observable behavior | Test/Check |
|-------------|---------------------|-----------|
| **SYNC-01** | `cache.json` created at `%APPDATA%/ЛичныйЕженедельник/cache.json` on first task persist | `test_cache_file_created_in_appdata` + `tmp_path` fixture override |
| **SYNC-02** | Task added → visible in-memory immediately + queued in `pending_changes` | `test_add_task_is_optimistic_and_queues_change` |
| **SYNC-05** | After sync response with newer `updated_at`, local task fields match server | `test_server_wins_on_conflict` |
| **SYNC-08** | Task deleted locally → `deleted_at` set; task not in `get_visible_tasks()` | `test_soft_delete_hides_task_but_keeps_tombstone` |

### Introspective (internal state — requires white-box)

| Requirement | Introspective signal | Check |
|-------------|----------------------|-------|
| **SYNC-03** | Daemon sync thread started; `_sync_loop()` called at intervals | `test_sync_thread_wakes_on_interval_and_event` + inspect thread state |
| **SYNC-04** | `threading.Lock` used correctly — no race on rapid adds | `test_concurrent_add_and_drain_is_race_free` (100 threads × 10 ops) |
| **SYNC-06** | Client-generated UUID4 in `Task.id` — idempotent, no server round-trip for ID | `test_task_id_generated_locally_no_server_roundtrip` |
| **SYNC-07** | After >5min offline, next online → full resync triggered (since=None) | `test_long_offline_triggers_full_resync` — mock clock/time |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|--------------|
| Real production /api/sync round-trip | All SYNC | Requires live server + real auth (SC-1 from Phase 1) | Run E2E test module against `https://planner.heyda.ru/api/` once real Telegram auth done; defer to Phase 2 verifier gate |
| keyring on Cyrillic path Windows profile | SYNC-adjacent (auth persistence) | Requires Windows with Cyrillic username profile | Install on Никита's actual work laptop in Phase 6 bootstrapping |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner fills)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (conftest + pyproject)
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter after planner refines per-task map

**Approval:** pending (planner refines, then gsd-plan-checker validates)
