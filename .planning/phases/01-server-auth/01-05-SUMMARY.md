---
phase: 01-server-auth
plan: 05
subsystem: server/auth
tags: [auth-codes, bcrypt, telegram, httpx, tdd]
dependency_graph:
  requires: ["01-02 (AuthCode model)", "01-03 (Settings с auth_code_ttl/length)"]
  provides: ["AuthCodeService (для Plan 06 endpoints)", "send_auth_code (для Plan 06 endpoints)"]
  affects: ["01-06 (auth endpoints используют эти классы)", "01-09 (bot handler дополнит chat_id)"]
tech_stack:
  added: ["bcrypt (напрямую, без passlib)", "httpx"]
  patterns: ["TDD red-green", "bcrypt.hashpw/checkpw вместо passlib (несовместимость 1.7.4 + bcrypt 5.x)", "Dependency injection client в send_auth_code для тестируемости", "explicit created_at для детерминированного порядка в БД"]
key_files:
  created:
    - server/auth/codes.py
    - server/auth/telegram.py
    - server/tests/test_codes.py
    - server/tests/test_telegram.py
  modified: []
decisions:
  - "bcrypt используется напрямую вместо passlib — passlib 1.7.4 несовместима с bcrypt 5.x (удалён __about__)"
  - "created_at устанавливается явно в request_code через Python UTC datetime для microsecond-precision порядка"
  - "expires_at timezone-handling: SQLite возвращает naive datetime, приводится к UTC через replace(tzinfo=utc)"
metrics:
  duration: "5 минут"
  completed_date: "2026-04-14"
  tasks_completed: 2
  files_created: 4
  files_modified: 0
  tests_added: 18
  tests_total: 60
---

# Phase 01 Plan 05: Auth Codes + Telegram Sender Summary

**One-liner:** bcrypt-хешированные 6-цифровые OTP с single-use верификацией и Telegram-отправкой через httpx с форматом D-05

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | AuthCodeService — генерация, bcrypt-hash, verify single-use | 01d63f8 | server/auth/codes.py, server/tests/test_codes.py |
| 2 | Telegram send_auth_code через httpx с форматом D-05 | 896a2d6 | server/auth/telegram.py, server/tests/test_telegram.py |

## What Was Built

### server/auth/codes.py — AuthCodeService

- `CodeRequestResult(NamedTuple)` — request_id + plaintext code (однократный, не логируется)
- `VerifyResult(Enum)` — OK / INVALID / EXPIRED / ALREADY_USED
- `AuthCodeService.request_code(username)` — генерирует `secrets.randbelow(10^6)`, хеширует bcrypt.hashpw, сохраняет в auth_codes с expires_at = now + 300s
- `AuthCodeService.verify_code(username, code)` — находит самый свежий неиспользованный код по username, проверяет TTL, bcrypt.checkpw, устанавливает used_at (single-use D-08)
- `AuthCodeService.cleanup_expired()` — housekeeping: DELETE WHERE expires_at < now

### server/auth/telegram.py — send_auth_code

- `TelegramSendError(Enum)` — OK / BOT_NOT_STARTED / API_ERROR / NETWORK_ERROR
- `send_auth_code(chat_id, code, hostname, msk_time_str, *, client)` — проверяет chat_id is None → BOT_NOT_STARTED, POST к api.telegram.org/bot{TOKEN}/sendMessage, обрабатывает httpx.RequestError → NETWORK_ERROR, status != 200 → API_ERROR, body.ok=False → API_ERROR
- `_format_message()` — формат D-05: 🔐 Запрошен вход в Личный Еженедельник / Код: **{code}** / Устройство / Время / Срок: 5 минут / "игнорируй"

## Test Results

```
18 passed (11 codes + 7 telegram) — новые
60 passed total (включая все предыдущие планы)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] passlib 1.7.4 несовместима с bcrypt 5.0.0**
- **Found during:** Task 1 GREEN phase
- **Issue:** `passlib.handlers.bcrypt` проверяет `_bcrypt.__about__.__version__` — атрибут удалён в bcrypt 5.x; вызывает ValueError при любой bcrypt операции
- **Fix:** Заменили `CryptContext(schemes=["bcrypt"])` на прямой `import bcrypt` + `bcrypt.hashpw/checkpw`
- **Files modified:** server/auth/codes.py
- **Commit:** 01d63f8

**2. [Rule 1 - Bug] SQLite возвращает naive datetime — несовместимо с aware UTC**
- **Found during:** Task 1 GREEN phase (test_verify_correct_code_ok)
- **Issue:** `record.expires_at` (из SQLite) — naive datetime. `_utcnow()` возвращает aware UTC. Сравнение вызывало `TypeError: can't compare offset-naive and offset-aware datetimes`
- **Fix:** В verify_code добавлена нормализация: `if expires_at.tzinfo is None: expires_at = expires_at.replace(tzinfo=timezone.utc)`
- **Files modified:** server/auth/codes.py
- **Commit:** 01d63f8

**3. [Rule 1 - Bug] created_at через server_default=func.now() даёт seconds-precision**
- **Found during:** Task 1 GREEN phase (test_verify_uses_most_recent_code)
- **Issue:** SQLite `func.now()` имеет секундную точность — два быстрых `request_code` давали одинаковый `created_at`, нарушая `ORDER BY created_at DESC`
- **Fix:** Передаём `created_at=now` (Python UTC datetime) явно в AuthCode constructor — microsecond precision
- **Files modified:** server/auth/codes.py
- **Commit:** 01d63f8

**4. [Rule 1 - Bug] BOT_TOKEN "token" слишком короткий для pydantic validator**
- **Found during:** Task 1 RED phase (fixture setup)
- **Issue:** Settings.bot_token имеет `min_length=10`; тест использовал `"token"` (5 символов)
- **Fix:** Изменено на `"test-token-12345"` в test fixture
- **Files modified:** server/tests/test_codes.py
- **Commit:** 01d63f8

## Known Stubs

Нет. `send_auth_code` не делает реальных вызовов в тестах (через mock client). В продакшене bot_token придёт из плановых переменных окружения. `telegram_chat_id` будет NULL до реализации Plan 09 (`/start` handler) — это ожидаемое поведение, документировано в BOT_NOT_STARTED error.

## Self-Check: PASSED

- server/auth/codes.py: FOUND
- server/auth/telegram.py: FOUND
- server/tests/test_codes.py: FOUND
- server/tests/test_telegram.py: FOUND
- Commit 01d63f8: FOUND (feat(01-05): AuthCodeService)
- Commit 896a2d6: FOUND (feat(01-05): send_auth_code)
- 18 tests green: VERIFIED
