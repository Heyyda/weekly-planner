---
phase: 02-client-core
plan: "04"
subsystem: client-auth
tags: [auth, keyring, jwt, threading, requests-mock]
dependency_graph:
  requires: ["02-01", "02-02", "02-03"]
  provides: ["AuthManager", "AuthError hierarchy", "bearer_header", "refresh_access rotation"]
  affects: ["02-06-sync", "02-07-sync-tests"]
tech_stack:
  added: []
  patterns:
    - "threading.Lock on access_token (read/write from sync daemon thread)"
    - "keyring ASCII service name WeeklyPlanner (D-25 frozen-exe safety)"
    - "AuthExpiredError caught in load_saved_token → returns False (not re-raised)"
    - "requests.Session reuse across all auth calls"
    - "fake_keyring in-memory dict fixture isolates tests from Windows Credential Manager"
key_files:
  created:
    - client/tests/test_auth.py
  modified:
    - client/core/auth.py
decisions:
  - "access_token stays in RAM only — never written to keyring (D-26 confirmed)"
  - "refresh_token rotation on /auth/refresh — saved to keyring immediately (D-13)"
  - "AuthExpiredError from refresh_access is caught by load_saved_token → returns False"
  - "logout is best-effort — network errors logged and ignored, keyring always cleared"
metrics:
  duration_seconds: 116
  completed_date: "2026-04-15"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 02 Plan 04: AuthManager Rewrite Summary

**One-liner:** Full rewrite of AuthManager with correct server endpoints (`/auth/request-code`, `request_id`-based verify), keyring refresh-token rotation (D-13), RAM-only access_token (D-26), and threading.Lock for sync-thread safety.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | AuthManager rewrite — правильные endpoints + keyring rotation | c8e87cc | client/core/auth.py |
| 2 | test_auth.py — 15 unit-тестов AuthManager | 0e64810 | client/tests/test_auth.py |

## What Was Built

### client/core/auth.py (full rewrite, 244 LOC)

The skeleton `auth.py` had four critical bugs fixed:

1. **Wrong endpoint** — `/auth/request` → `/auth/request-code`
2. **Wrong verify body** — `{username, code}` → `{request_id, code, device_name}` (request_id returned by /request-code, passed to /verify)
3. **access_token in keyring** — removed entirely; access_token lives only in RAM (D-26)
4. **No refresh rotation** — server returns new `refresh_token` on `/auth/refresh`; client now saves it immediately (D-13)
5. **Cyrillic service name** — `"ЛичныйЕженедельник"` → `config.KEYRING_SERVICE` = `"WeeklyPlanner"` (ASCII, D-25)

Added:
- `threading.Lock` wrapping all `access_token` reads/writes (thread-safe for SyncManager)
- 5 typed exceptions: `AuthError`, `AuthNetworkError`, `AuthRateLimitError`, `AuthInvalidCodeError`, `AuthExpiredError`
- `bearer_header()` raises `AuthError` if not authenticated (vs returning empty dict)
- `_extract_error_message()` parses `{"error": {"message": "..."}}` server error format
- `is_authenticated()` thread-safe property
- keyring errors logged via `logger.error` but never re-raised (graceful degradation)

### client/tests/test_auth.py (15 tests, 239 LOC)

Full coverage of all auth flows:

| Test | Covers |
|------|--------|
| `test_request_code_happy` | 200 → request_id returned, username stored |
| `test_request_code_rate_limit` | 429 → AuthRateLimitError |
| `test_request_code_network_error` | ConnectionError → AuthNetworkError |
| `test_verify_code_happy_saves_to_keyring` | D-26: access NOT in keyring, refresh IS |
| `test_verify_code_invalid` | 400 → AuthInvalidCodeError |
| `test_refresh_access_rotates_keyring` | D-13: new refresh saved to keyring |
| `test_refresh_access_401_raises_expired` | 401 → AuthExpiredError + state cleared |
| `test_refresh_access_network_error_returns_false` | offline-tolerant: returns False not raises |
| `test_load_saved_token_empty_keyring` | empty keyring → False |
| `test_load_saved_token_with_refresh` | refresh in keyring + server 200 → True |
| `test_load_saved_token_refresh_expired` | 401 from server → False (AuthExpiredError caught) |
| `test_logout_clears_keyring_and_state` | keyring cleared, all fields None |
| `test_bearer_header_unauthenticated_raises` | AuthError when no token |
| `test_bearer_header_with_token` | returns correct Authorization header |
| `test_get_access_token_thread_safe` | 5 readers + 5 writers, 100 ops each — no errors |

**Result:** 15 passed in 0.12s. Full suite: 42 passed in 0.17s.

## Verification

```
python -m pytest client/tests/test_auth.py -v --timeout=10
# → 15 passed in 0.12s

python -m pytest client/tests -v --timeout=10
# → 42 passed in 0.17s
```

All acceptance criteria met:
- `grep -c "auth/request-code" client/core/auth.py` = 2
- `grep -c "auth/request[^-]" client/core/auth.py` = 0
- `grep -c "request_id" client/core/auth.py` = 7
- `grep -c "device_name" client/core/auth.py` = 2
- `grep -c '"WeeklyPlanner"' client/core/auth.py` = 0 (uses config.KEYRING_SERVICE)
- `grep -c "config.KEYRING_SERVICE" client/core/auth.py` = 5
- `grep -c "threading.Lock" client/core/auth.py` = 1
- `grep -c "class Auth" client/core/auth.py` = 6 (AuthManager + 5 exceptions)

## Deviations from Plan

None — plan executed exactly as written. The test count is 15 (not 11 as in task description, not 14 as in success criteria) because the plan body listed 13 behaviors in `<behavior>` but also specified `bearer_header_with_token` as a separate case. All behaviors from the plan are covered.

## Known Stubs

None. `AuthManager` is fully wired — all methods make real HTTP requests (mocked in tests) and real keyring calls (mocked in tests via `fake_keyring` fixture).

## Self-Check: PASSED

Files created/modified:
- `client/core/auth.py` — FOUND (244 LOC, imports cleanly)
- `client/tests/test_auth.py` — FOUND (239 LOC, 15 tests)

Commits:
- `c8e87cc` — FOUND (feat(02-04): AuthManager rewrite)
- `0e64810` — FOUND (test(02-04): unit-тесты AuthManager)
