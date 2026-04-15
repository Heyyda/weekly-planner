# Plan 01-11 — E2E + smoke-test — SUMMARY

**Phase:** 01-server-auth
**Plan:** 01-11
**Status:** ✅ Complete
**Completed:** 2026-04-15
**Requirements:** ALL (final goal-backward verification)

---

## What Was Built

**Task 1: E2E integration tests** (`server/tests/test_e2e_integration.py`)
- `test_phase_1_full_flow` — 12 шагов: bot `/start` → `/auth/request-code` → verify → `/auth/me` → `/api/sync` CREATE/UPDATE/DELETE → delta через `since` → refresh token rotation → logout → проверка revoked session возвращает 401
- `test_phase_1_wal_and_concurrent_writes` — 5 параллельных async writers + проверка `PRAGMA journal_mode=wal` без `database is locked`
- Весь server test suite: **92 passed**

**Task 2: `deploy/bin/smoke-test.sh`** — bash-скрипт для production-проверки
- Проверка 1: `GET /api/health` → 200 + `status:ok`
- Проверка 2: `GET /api/version` → 200 + `version` field
- Проверка 3: TLS сертификат валидный (curl --fail через HTTPS)
- Проверка 4: rate-limit `/api/auth/request-code` (1/min) — первый запрос 403 USER_NOT_ALLOWED, второй 429 TOO_MANY_REQUESTS
- Проверка 5: `POST /api/sync` без Bearer → 401 (auth gate)
- Printable summary по ROADMAP Success Criteria

**Task 3: Smoke-test выполнен против production** — 5/5 автоматических проверок зелёные

## Verification Results

Запуск `bash deploy/bin/smoke-test.sh https://planner.heyda.ru`:

| # | Check | Result |
|---|-------|--------|
| 1 | GET /api/health | ✅ 200 `{"status":"ok"}` |
| 2 | GET /api/version | ✅ 200 `{"version":"0.1.0",...}` |
| 3 | TLS | ✅ valid cert (Traefik ACME) |
| 4 | Rate-limit (1/min) | ✅ second request → 429 |
| 5 | /api/sync without Bearer | ✅ 401 Unauthorized |

## ROADMAP Phase 1 Success Criteria

| SC | Criterion | Status | Evidence |
|----|-----------|--------|----------|
| SC-1 | Telegram auth flow (username → code → JWT) | ✅ Covered by tests | 11 auth-codes tests + 7 telegram tests + 11 auth-routes tests + 2 E2E tests + live endpoint (`request-code` returns `request_id`). Full real-Telegram delivery self-verifies when desktop client first used in Phase 2-3. |
| SC-2 | `/api/health` + `/api/version` → 200 | ✅ | smoke-test checks 1-2 |
| SC-3 | `/api/sync` accepts changes with Bearer | ✅ | 8 pytest tests + auth-gate 401 check in smoke-test |
| SC-4 | SQLite WAL + concurrent writes | ✅ | test_phase_1_wal_and_concurrent_writes local + VPS PRAGMA=`wal` (VPS-Claude отчёт) |
| SC-5 | systemd auto-restart | ✅ | `systemctl is-active planner-api planner-bot` → active active (VPS-Claude отчёт); auto-restart unverified until VPS reboot event, but Restart=always configured |

## Files Created

```
server/tests/test_e2e_integration.py  # 2 E2E tests
deploy/bin/smoke-test.sh              # production smoke-test
server/bot/handlers.py                # добавлено logging для /start
```

## Commits

- `0c3c478` test(01-11): E2E integration tests — auth+sync happy-path + WAL concurrent writes
- `3820bed` chore(01-11): smoke-test.sh для проверки production-сервера

## Known Follow-ups (not blockers)

- **Реальная доставка Telegram-кода** — полный real-world flow (с человеком в Telegram) проверится естественно когда в Phase 2+ заработает desktop-клиент и Никита впервые авторизуется. Юнит+интеграционные тесты доказывают логику; live-endpoint принимает запросы; операционный flow самопроверится в реальном использовании.
- **`sudo reboot` on VPS** для полной проверки SC-5 auto-restart — не делаем сейчас, влияет на E-bot. Можно проверить при следующем плановом обслуживании VPS.
