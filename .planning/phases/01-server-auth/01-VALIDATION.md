---
phase: 1
slug: server-auth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Will be refined by the planner with per-task verification mappings.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + httpx (async FastAPI client) + pytest-asyncio + aiosqlite |
| **Config file** | `server/pyproject.toml` (pytest section) + `server/tests/conftest.py` |
| **Quick run command** | `cd server && pytest -x --timeout=10` |
| **Full suite command** | `cd server && pytest --cov=. --cov-report=term-missing` |
| **Estimated runtime** | ~15-30 seconds for full suite |

---

## Sampling Rate

- **After every task commit:** Run `cd server && pytest -x --timeout=10` (fail on first error, 10s per-test cap)
- **After every plan wave:** Run `cd server && pytest -v` (full suite)
- **Before `/gsd:verify-work`:** Full suite must be green + `curl https://planner.heyda.ru/api/health` returns 200
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Populated by planner during plan generation. Each plan task should reference either an automated test, a curl-verifiable endpoint, or explicit Wave 0 dependency.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| *TBD* | *planner fills* | *planner fills* | *planner fills* | *planner fills* | *planner fills* | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (Test Infrastructure Setup)

Before any task tests can exist, these must be created first:

- [ ] `server/tests/conftest.py` — shared fixtures: async SQLite in-memory engine, httpx AsyncClient, override Settings, mock Telegram Bot API calls
- [ ] `server/tests/__init__.py` — empty, marks tests as package
- [ ] `server/pyproject.toml` §[tool.pytest.ini_options] — pytest config: `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- [ ] `server/requirements-dev.txt` — pytest, pytest-asyncio, pytest-cov, httpx, aiosqlite

---

## Observable vs Introspective Validation

### Observable (verifiable from outside the process — curl, HTTP responses)

| Requirement | Observable behavior | Test command |
|-------------|--------------------|--------------|
| **SRV-01** | `POST /api/auth/request-code` returns `{request_id, expires_in}` given valid username | `curl -X POST .../api/auth/request-code -d '{"username":"test"}'` |
| **AUTH-02** | `POST /api/auth/verify` returns JWT pair given valid request_id + code | `curl -X POST .../api/auth/verify -d '{"request_id":"...","code":"123456"}'` |
| **AUTH-04** | `POST /api/auth/refresh` returns new access token given valid refresh | `curl -X POST .../api/auth/refresh -d '{"refresh_token":"..."}'` |
| **SRV-05** | `GET /api/health` returns 200 on `https://planner.heyda.ru` | `curl -fsS https://planner.heyda.ru/api/health` |
| **SRV-02** | `POST /api/sync` with valid Bearer returns changes delta | `curl -X POST .../api/sync -H 'Authorization: Bearer $TOKEN' -d '{"since":"2026-01-01T00:00:00Z","changes":[]}'` |
| **SRV-05** | Systemd unit auto-restarts after kill | `sudo kill -9 $(pgrep -f uvicorn); sleep 6; systemctl status planner-api` |

### Introspective (requires looking inside the system — logs, DB queries)

| Requirement | Introspective signal | Check command |
|-------------|----------------------|---------------|
| **SRV-03** | SQLite in WAL mode; two concurrent writes don't fail | `sqlite3 /var/lib/planner/weekly_planner.db "PRAGMA journal_mode;"` returns `wal` |
| **SRV-04** | `auth_codes` table contains hash, not plaintext | `sqlite3 ... "SELECT code_hash FROM auth_codes LIMIT 1"` — bcrypt/argon prefix visible |
| **AUTH-03** | JWT refresh session recorded with `revoked_at NULL` initially | `sqlite3 ... "SELECT revoked_at FROM sessions WHERE id = '...';"` |
| **SRV-06** | Server `updated_at` is authoritative (server ignores client updated_at) | pytest integration test that submits task with past updated_at and verifies server overwrites |
| **AUTH-05** | Logout revokes the session (sets `revoked_at`) | pytest integration test |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram bot actually delivers code to user's chat | AUTH-01 | Requires real Telegram API + real account + user must have `/start`-ed the bot | (1) deploy server; (2) from owner's Telegram chat with @Jazzways_bot send `/start`; (3) `curl /api/auth/request-code -d '{"username":"nikita_heyyda"}'`; (4) verify message arrives in Telegram with 6-digit code |
| Reverse proxy TLS works with real browser | SRV-05 | Certificate auto-provisioning (Caddy) requires real DNS + CA challenge | Visit `https://planner.heyda.ru/api/health` in browser — should show 200 OK with valid cert |
| Deployment via git-pull + systemd restart works end-to-end | SRV-05 | Requires SSH access to VPS; untestable in CI | Documented in phase plan; executor runs the deploy script manually the first time |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (filled by planner)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (conftest.py + pyproject pytest config)
- [ ] No watch-mode flags (only fail-fast `-x`)
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter after planner refines per-task map

**Approval:** pending (planner refines, then gsd-plan-checker validates)
