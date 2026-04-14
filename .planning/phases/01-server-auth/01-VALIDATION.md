---
phase: 1
slug: server-auth
status: refined
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-14
refined: 2026-04-14
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Refined by planner with per-task verification mapping.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + httpx (async FastAPI client) + pytest-asyncio + aiosqlite |
| **Config file** | `server/pyproject.toml` (pytest section) + `server/tests/conftest.py` |
| **Quick run command** | `cd server && pytest -x --timeout=10` |
| **Full suite command** | `cd server && pytest -v --tb=short` |
| **Estimated runtime** | ~30-45 seconds for full suite (bcrypt делает тесты кодов медленнее) |

---

## Sampling Rate

- **After every task commit:** Run `cd server && pytest -x --timeout=10` (fail on first error, 10s per-test cap)
- **After every plan wave:** Run `cd server && pytest -v` (full suite)
- **Before `/gsd:verify-work`:** Full suite green + `curl https://planner.heyda.ru/api/health` returns 200
- **Max feedback latency:** 45 seconds (bcrypt медленный)

---

## Per-Task Verification Map

> Каждый task в Plans 01-11 имеет автоматизированный verify. В таблице ниже task ID = `{plan}.{task}`.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 01.1 | 01-01 | 0 | Infrastructure | unit | `python -c "import tomllib; tomllib.load(open('server/pyproject.toml','rb'))"` | ⬜ pending |
| 01.2 | 01-01 | 0 | Infrastructure | unit | `test -f server/tests/conftest.py && python -c "import ast; ast.parse(open('server/tests/conftest.py').read())"` | ⬜ pending |
| 01.3 | 01-01 | 0 | Infrastructure | integration | `cd server && pytest tests/test_infrastructure.py -x -v` → 3 passed | ⬜ pending |
| 02.1 | 01-02 | 1 | SRV-04, SRV-06 | unit | `cd server && pytest tests/test_models.py -x -v` → 6 passed | ⬜ pending |
| 02.2 | 01-02 | 1 | SRV-04 | integration | `cd server && rm -f test.db && DATABASE_URL=sqlite:///./test.db alembic upgrade head && sqlite3 test.db ".tables"` — 4 tables | ⬜ pending |
| 03.1 | 01-03 | 1 | Infrastructure | unit | `cd server && pytest tests/test_config.py -x -v` → 6 passed | ⬜ pending |
| 03.2 | 01-03 | 1 | SRV-03 | integration | `cd server && pytest tests/test_engine.py -x -v` → 6 passed (includes test_wal_pragmas_applied + test_concurrent_writes_no_lock) | ⬜ pending |
| 04.1 | 01-04 | 2 | AUTH-02, AUTH-03 | unit | `cd server && pytest tests/test_jwt.py -x -v` → 7 passed | ⬜ pending |
| 04.2 | 01-04 | 2 | AUTH-04, AUTH-05 | integration | `cd server && pytest tests/test_sessions.py -x -v` → 7 passed | ⬜ pending |
| 04.3 | 01-04 | 2 | AUTH-02, AUTH-05 | integration | `cd server && pytest tests/test_dependencies.py -x -v` → 5 passed | ⬜ pending |
| 05.1 | 01-05 | 2 | AUTH-01, SRV-01 | integration | `cd server && pytest tests/test_codes.py -x -v` → 11 passed | ⬜ pending |
| 05.2 | 01-05 | 2 | AUTH-01 | unit | `cd server && pytest tests/test_telegram.py -x -v` → 7 passed | ⬜ pending |
| 06.1 | 01-06 | 3 | SRV-01 | unit | Python inline check: schemas import + errors hit all code paths | ⬜ pending |
| 06.2 | 01-06 | 3 | SRV-01 | unit | Python inline check: app.routes contains all 5 auth paths | ⬜ pending |
| 06.3 | 01-06 | 3 | AUTH-01..05, SRV-01 | integration | `cd server && pytest tests/test_auth_routes.py -x -v` → 10 passed | ⬜ pending |
| 07.1 | 01-07 | 3 | SRV-02 | unit | Python inline check: SyncIn + TaskChange parse correctly | ⬜ pending |
| 07.2 | 01-07 | 3 | SRV-02 | unit | Python inline check: /api/sync in app.routes | ⬜ pending |
| 07.3 | 01-07 | 3 | SRV-02, SRV-06 | integration | `cd server && pytest tests/test_sync_routes.py -x -v` → 7+ passed | ⬜ pending |
| 08.1 | 01-08 | 3 | Infrastructure | unit | Python inline check: /api/health и /api/version в app.routes | ⬜ pending |
| 08.2 | 01-08 | 3 | SRV-01 | unit | Python check: app.state.limiter установлен + request_code имеет Request в signature | ⬜ pending |
| 08.3 | 01-08 | 3 | SRV-01 | integration | `cd server && pytest tests/test_health_version.py tests/test_rate_limit.py -x -v` → 5 passed | ⬜ pending |
| 09.1 | 01-09 | 4 | AUTH-01 | unit | Python inline: create_dispatcher() возвращает валидный Dispatcher | ⬜ pending |
| 09.2 | 01-09 | 4 | AUTH-01 | integration | `cd server && pytest tests/test_bot_handlers.py -x -v` → 5 passed | ⬜ pending |
| 10.1 | 01-10 | 5 | SRV-05 | unit | Файлы deploy/*.service, .env.example, snippets существуют, JSON валиден | ⬜ pending |
| 10.2 | 01-10 | 5 | SRV-05 | unit | `bash -n deploy/bin/*.sh` — syntax OK; grep на ключевые строки | ⬜ pending |
| 10.3 | 01-10 | 5 | SRV-05 | **human-action** | Checkpoint: оператор выполняет README шаги и возвращается с "deployed" | ⬜ pending |
| 11.1 | 01-11 | 5 | ALL | integration | `cd server && pytest tests/test_e2e_integration.py -x -v` → 2 passed | ⬜ pending |
| 11.2 | 01-11 | 5 | ALL | unit | `bash -n deploy/bin/smoke-test.sh` + grep на success criteria | ⬜ pending |
| 11.3 | 01-11 | 5 | ALL | **human-verify** | Checkpoint: smoke-test.sh против https://planner.heyda.ru/ passes + все 5 ROADMAP criteria подтверждены | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (Test Infrastructure Setup) — закрывается Plan 01-01

- [ ] `server/tests/conftest.py` — shared fixtures: async SQLite in-memory engine, httpx AsyncClient, override Settings, mock Telegram Bot API calls
- [ ] `server/tests/__init__.py` — empty, marks tests as package
- [ ] `server/pyproject.toml` §[tool.pytest.ini_options] — `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- [ ] `server/requirements-dev.txt` — pytest, pytest-asyncio, pytest-cov, httpx, aiosqlite
- [ ] `server/requirements.txt` — production deps
- [ ] `server/{api,auth,db,bot}/__init__.py` — пустые subpackage markers

---

## Observable vs Introspective Validation

### Observable (verifiable from outside the process — curl, HTTP responses)

| Requirement | Observable behavior | Test command |
|-------------|--------------------|--------------|
| **SRV-01** | `POST /api/auth/request-code` returns `{request_id, expires_in}` given valid username | `curl -X POST .../api/auth/request-code -d '{"username":"nikita_heyyda","hostname":"test"}'` |
| **AUTH-02** | `POST /api/auth/verify` returns JWT pair given valid request_id + code | `curl -X POST .../api/auth/verify -d '{"request_id":"...","code":"123456"}'` |
| **AUTH-04** | `POST /api/auth/refresh` returns new access token + rotates refresh | `curl -X POST .../api/auth/refresh -d '{"refresh_token":"..."}'` |
| **AUTH-05** | `POST /api/auth/logout` + последующий refresh → 401 | tests/test_auth_routes.py::test_logout_revokes_session |
| **SRV-05** | `GET /api/health` returns 200 on `https://planner.heyda.ru` | `curl -fsS https://planner.heyda.ru/api/health` |
| **SRV-02** | `POST /api/sync` with valid Bearer returns changes delta | `curl -X POST .../api/sync -H 'Authorization: Bearer $TOKEN' -d '{"since":"2026-01-01T00:00:00Z","changes":[]}'` |
| **SRV-05** | Systemd unit auto-restarts after kill / reboot | `sudo reboot; sleep 60; systemctl is-active planner-api planner-bot` |

### Introspective (requires looking inside the system — logs, DB queries)

| Requirement | Introspective signal | Check command |
|-------------|----------------------|---------------|
| **SRV-03** | SQLite in WAL mode; two concurrent writes don't fail | `sqlite3 /var/lib/planner/weekly_planner.db "PRAGMA journal_mode;"` returns `wal` |
| **SRV-04** | `auth_codes` table contains bcrypt hash, not plaintext | tests/test_codes.py::test_request_code_stores_hash_not_plaintext + `sqlite3 ... "SELECT code_hash FROM auth_codes LIMIT 1"` — prefix `$2` |
| **AUTH-03** | JWT refresh session recorded with `revoked_at NULL` initially | tests/test_sessions.py::test_create_session + DB inspect |
| **SRV-06** | Server `updated_at` is authoritative (server ignores client updated_at) | tests/test_sync_routes.py::test_sync_create_task (проверяет updated_at server-side) |
| **AUTH-05** | Logout revokes the session (sets `revoked_at`) | tests/test_sessions.py::test_revoke_sets_revoked_at |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram bot actually delivers code to user's chat | AUTH-01 | Requires real Telegram API + real account + user must have `/start`-ed the bot | (1) deploy server; (2) from owner's Telegram chat with @Jazzways_bot send `/start`; (3) `curl /api/auth/request-code -d '{"username":"nikita_heyyda"}'`; (4) verify message arrives in Telegram with 6-digit code |
| Reverse proxy TLS works with real browser | SRV-05 | Certificate auto-provisioning (Caddy Let's Encrypt) requires real DNS + CA challenge | Visit `https://planner.heyda.ru/api/health` in browser — should show 200 OK with valid cert |
| Deployment via git-pull + systemd works end-to-end | SRV-05 | Requires SSH access to VPS; untestable in CI | Plan 01-10 Task 3 checkpoint — оператор выполняет deploy/README.md, возвращается с "deployed" |
| Reboot survival | SRV-05 #5 | Требует SSH + reboot | Plan 01-11 Task 3 checkpoint — `sudo reboot` + `systemctl is-active` после |
| BotFather token revoke | D-03 security | Действие в Telegram UI | Plan 01-10 Task 3 checkpoint — первый шаг runbook, не shortcut-able |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or explicit Wave 0/human-checkpoint dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (все tasks auto, кроме 2 explicit checkpoint'ов)
- [x] Wave 0 covers all MISSING references (conftest.py + pyproject pytest config в Plan 01-01)
- [x] No watch-mode flags (только fail-fast `-x`)
- [x] Feedback latency < 45s (bcrypt медленный — 5 sec на tests/test_codes.py; суммарно suite ~30-45 sec)
- [x] `nyquist_compliant: true` set in frontmatter after refinement

**Total tests after all plans:**
- Plan 01-01: 3 (infrastructure)
- Plan 01-02: 6 (models)
- Plan 01-03: 6 (config) + 6 (engine) = 12
- Plan 01-04: 7 (jwt) + 7 (sessions) + 5 (deps) = 19
- Plan 01-05: 11 (codes) + 7 (telegram) = 18
- Plan 01-06: 10 (auth routes)
- Plan 01-07: 7+ (sync routes)
- Plan 01-08: 3 (health+version) + 2 (rate-limit) = 5
- Plan 01-09: 5 (bot handlers)
- Plan 01-10: 0 (deploy — ручной checkpoint)
- Plan 01-11: 2 (e2e integration)
- **Total: ~88 automated tests**

**Approval:** refined by planner; ready for gsd-plan-checker.
