---
phase: 01-server-auth
plan: "06"
subsystem: server/api
tags: [fastapi, pydantic, auth, endpoints, integration-tests]
dependency_graph:
  requires: ["01-04", "01-05"]
  provides: ["server.api.app:app", "server.api.auth_routes:router", "server.api.schemas", "server.api.errors"]
  affects: ["01-07", "01-08", "01-09", "01-10", "01-11"]
tech_stack:
  added: []
  patterns:
    - "FastAPI APIRouter с prefix=/api/auth"
    - "Pydantic v2 field_validator для нормализации username и валидации кода"
    - "dependency_overrides + ASGITransport для integration тестов без реального HTTP"
    - "monkeypatch send_auth_code для изоляции от Telegram API в тестах"
    - "Rolling refresh: revoke старой session + создание новой в одном вызове"
key_files:
  created:
    - server/api/schemas.py
    - server/api/errors.py
    - server/api/auth_routes.py
    - server/api/app.py
    - server/tests/test_auth_routes.py
  modified:
    - server/requirements.txt  # добавлен tzdata для ZoneInfo на Windows
decisions:
  - "tzdata добавлен в requirements.txt: ZoneInfo('Europe/Moscow') на Windows требует этот пакет"
  - "11 тестов вместо 10 (план говорил 10+): добавлен тест test_logout_with_specific_refresh_token для полноты покрытия AUTH-05"
metrics:
  duration_seconds: 263
  completed_date: "2026-04-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 1
  tests_added: 11
  tests_total: 71
---

# Phase 01 Plan 06: Auth API Endpoints Summary

**One-liner:** 5 FastAPI auth endpoints с Pydantic v2 схемами и 11 integration тестами через httpx AsyncClient

## What Was Built

### server/api/schemas.py
Pydantic v2 request/response модели для всех 5 auth endpoints:

- **RequestCodeIn** — username (нормализация: `@Nikita` → `nikita`), hostname (default "неизвестно")
- **VerifyCodeIn** — request_id, code (валидация: строго 6 цифр), device_name (optional)
- **RefreshTokenIn** — refresh_token
- **LogoutIn** — refresh_token (optional: если передан → revoke одну сессию, иначе все)
- **RequestCodeOut** — request_id, expires_in (300 = 5 мин)
- **TokenPairOut** — access_token, refresh_token, expires_in (900 = 15 мин), token_type="bearer", user_id
- **AccessTokenOut** — access_token, refresh_token (rolling), expires_in, token_type
- **UserMeOut** — user_id, username, created_at
- **ErrorDetail + ErrorOut** — формат D-18: `{"error": {"code": "...", "message": "..."}}`

### server/api/errors.py
Error helpers для консистентных ответов:

| Функция | Код | HTTP |
|---------|-----|------|
| `err_user_not_allowed()` | USER_NOT_ALLOWED | 403 |
| `err_bot_not_started()` | BOT_NOT_STARTED | 400 |
| `err_telegram_send()` | TELEGRAM_ERROR | 502 |
| `err_invalid_code()` | INVALID_CODE | 400 |
| `err_code_expired()` | CODE_EXPIRED | 400 |
| `err_already_used()` | ALREADY_USED | 400 |
| `err_invalid_refresh()` | INVALID_REFRESH | 401 |
| `err_request_not_found()` | INVALID_CODE | 400 |

### server/api/auth_routes.py
APIRouter с prefix="/api/auth", 5 endpoints:

| Метод | Путь | Описание |
|-------|------|----------|
| POST | /api/auth/request-code | Запрос кода → {request_id, expires_in} |
| POST | /api/auth/verify | Верификация кода → {access_token, refresh_token, expires_in, user_id, token_type} |
| POST | /api/auth/refresh | Rolling refresh → {access_token, refresh_token, expires_in, token_type} |
| POST | /api/auth/logout | Revoke session → 204 No Content |
| GET  | /api/auth/me | Текущий пользователь → {user_id, username, created_at} |

### server/api/app.py
FastAPI app — entry point для uvicorn (`server.api.app:app`):
- `lifespan` контекст (startup log + engine.dispose on shutdown)
- `docs_url="/api/docs"`, `openapi_url="/api/openapi.json"`
- `app.include_router(auth_router)` подключён

### server/tests/test_auth_routes.py
11 integration тестов через httpx AsyncClient + реальная SQLite:

1. `test_request_code_user_not_allowed` — 403 USER_NOT_ALLOWED
2. `test_request_code_success_sends_telegram` — 200 + request_id + Telegram mock
3. `test_request_code_bot_not_started` — 400 BOT_NOT_STARTED при chat_id=NULL
4. `test_full_auth_flow_request_verify_me` — end-to-end AUTH-01 + AUTH-02
5. `test_verify_invalid_code` — 400 INVALID_CODE
6. `test_verify_malformed_code_rejected_by_pydantic` — 422 Pydantic validation
7. `test_refresh_rotates_tokens` — rolling refresh AUTH-04
8. `test_refresh_invalid_returns_401` — 401 INVALID_REFRESH
9. `test_logout_revokes_session` — AUTH-05 revoke all
10. `test_me_without_auth_returns_401` — 401 MISSING_TOKEN
11. `test_logout_with_specific_refresh_token` — revoke одной из двух сессий

## Endpoints (для Plans 07-11)

```
POST /api/auth/request-code  {username, hostname} → {request_id, expires_in}
POST /api/auth/verify        {request_id, code, device_name?} → {access_token, refresh_token, expires_in, user_id, token_type}
POST /api/auth/refresh       {refresh_token} → {access_token, refresh_token, expires_in, token_type}
POST /api/auth/logout        Bearer + optional {refresh_token} → 204
GET  /api/auth/me            Bearer → {user_id, username, created_at}
```

## Example curl (для Plan 11 deploy verification)

```bash
# Шаг 1: запросить код
curl -X POST https://planner.heyda.ru/api/auth/request-code \
  -H "Content-Type: application/json" \
  -d '{"username": "nikita", "hostname": "work-pc"}'
# → {"request_id": "uuid", "expires_in": 300}

# Шаг 2: верифицировать код из Telegram
curl -X POST https://planner.heyda.ru/api/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"request_id": "uuid", "code": "123456", "device_name": "work-pc"}'
# → {"access_token": "eyJ...", "refresh_token": "eyJ...", "expires_in": 900, "token_type": "bearer", "user_id": "uuid"}

# /me
curl https://planner.heyda.ru/api/auth/me \
  -H "Authorization: Bearer eyJ..."
# → {"user_id": "uuid", "username": "nikita", "created_at": "..."}
```

## Covered Requirements

| ID | Description | Status |
|----|-------------|--------|
| AUTH-01 | Telegram-код авторизации | ✅ /api/auth/request-code → send_auth_code |
| AUTH-02 | Ввод кода → JWT пара | ✅ /api/auth/verify → TokenPairOut |
| AUTH-04 | Rolling refresh | ✅ /api/auth/refresh + SessionService.rotate_refresh |
| AUTH-05 | Logout через tray | ✅ /api/auth/logout + revoke session |
| SRV-01 | REST API /auth/* | ✅ FastAPI router, Pydantic v2, Depends() |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Блокирующая проблема] Missing tzdata на Windows**
- **Found during:** Task 2 verification
- **Issue:** `ZoneInfo("Europe/Moscow")` бросает `ZoneInfoNotFoundError` на Windows — tzdata не установлен
- **Fix:** `pip install tzdata` + добавлен `tzdata>=2024.1` в `server/requirements.txt`
- **Files modified:** `server/requirements.txt`
- **Commit:** a824d19

### Test Count
Написано 11 тестов вместо 10 из плана: добавлен `test_logout_with_specific_refresh_token` для полного покрытия AUTH-05 (logout конкретной сессии vs logout всех).

## Self-Check: PASSED

| Item | Status |
|------|--------|
| server/api/schemas.py | FOUND |
| server/api/errors.py | FOUND |
| server/api/auth_routes.py | FOUND |
| server/api/app.py | FOUND |
| server/tests/test_auth_routes.py | FOUND |
| commit eb97d0d (schemas+errors) | FOUND |
| commit a824d19 (auth_routes+app) | FOUND |
| commit 967a4ec (tests) | FOUND |
