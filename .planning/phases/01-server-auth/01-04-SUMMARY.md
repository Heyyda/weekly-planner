---
phase: 01-server-auth
plan: 04
subsystem: auth
tags: [jwt, pyjwt, sessions, fastapi, bearer-auth, sqlite, asyncio]

# Dependency graph
requires:
  - phase: 01-02
    provides: "SQLAlchemy ORM модели User, Session, Task, AuthCode"
  - phase: 01-03
    provides: "Settings с jwt_secret, jwt_refresh_secret, access_token_ttl_seconds, get_db"
provides:
  - "create_access_token, create_refresh_token с раздельными секретами (D-14)"
  - "decode_access_token, decode_refresh_token — возвращают None при любой ошибке (не raise)"
  - "hash_refresh_token — SHA256 hex для хранения в sessions table"
  - "SessionService: create (rolling refresh), rotate_refresh, revoke, get_by_refresh_hash"
  - "get_current_user FastAPI dependency с Bearer auth и ошибками в формате D-18"
affects: ["01-05", "01-06", "01-07"]

# Tech tracking
tech-stack:
  added: ["PyJWT (jwt.encode/decode с HS256)", "fastapi.security.HTTPBearer"]
  patterns:
    - "Раздельные JWT секреты для access и refresh (D-14)"
    - "Type-тег в payload предотвращает подмену токенов"
    - "None вместо raise при decode ошибке — единообразный API"
    - "Rolling refresh: старая session revoked при rotate, новая создана"
    - "SHA256 hash для хранения refresh в БД (не bcrypt — энтропия токена достаточна)"
    - "HTTPBearer(auto_error=False) + собственный формат ошибок D-18"

key-files:
  created:
    - "server/auth/jwt.py"
    - "server/auth/sessions.py"
    - "server/auth/dependencies.py"
    - "server/tests/test_jwt.py"
    - "server/tests/test_sessions.py"
    - "server/tests/test_dependencies.py"
  modified: []

key-decisions:
  - "PyJWT (не python-jose) — python-jose abandoned, PyJWT активно поддерживается"
  - "datetime.now(timezone.utc) вместо deprecated utcnow()"
  - "SHA256 для refresh token hash (не bcrypt) — refresh token имеет высокую энтропию, bcrypt излишен"
  - "auto_error=False в HTTPBearer — полный контроль над форматом ошибки (D-18)"
  - "rotate_refresh создаёт новую Session через SessionService.create (переиспользование кода)"

patterns-established:
  - "JWT decode: try/except PyJWTError → None (не raise)"
  - "Session create: flush() для получения id, затем encode refresh с sid=session.id"
  - "FastAPI dependency error format: HTTPException(detail={'error': {'code': ..., 'message': ...}})"

requirements-completed: ["AUTH-02", "AUTH-03", "AUTH-04", "AUTH-05"]

# Metrics
duration: 4min
completed: 2026-04-14
---

# Phase 01 Plan 04: JWT + SessionService Summary

**PyJWT access/refresh с раздельными секретами, rolling SessionService, FastAPI Bearer dependency — фундамент для auth endpoints в Plan 06**

## Performance

- **Duration:** 4 мин
- **Started:** 2026-04-14T23:27:27Z
- **Completed:** 2026-04-14T23:31:04Z
- **Tasks:** 3/3
- **Files modified:** 6 (3 impl + 3 tests)

## Accomplishments

- JWT модуль с раздельными секретами для access (JWT_SECRET) и refresh (JWT_REFRESH_SECRET) — type-confusion защита встроена в decode
- SessionService с rolling refresh (D-13): каждый rotate_refresh создаёт новую session и revokes старую; revoke() для logout (D-15)
- get_current_user FastAPI dependency: Bearer → decode → DB lookup → User или 401 в формате D-18

## Task Commits

1. **Task 1: JWT модуль** — `03a09f3` (feat)
2. **Task 2: SessionService** — `3c1d728` (feat)
3. **Task 3: get_current_user dependency** — `85010c9` (feat)

## Files Created/Modified

- `server/auth/jwt.py` — create_access_token, create_refresh_token, decode_access_token, decode_refresh_token, hash_refresh_token
- `server/auth/sessions.py` — class SessionService: create, rotate_refresh, revoke, get_by_refresh_hash
- `server/auth/dependencies.py` — security = HTTPBearer(auto_error=False), get_current_user
- `server/tests/test_jwt.py` — 8 тестов (roundtrip, type-confusion, TTL, tamper, hash)
- `server/tests/test_sessions.py` — 7 integration тестов с реальной SQLite
- `server/tests/test_dependencies.py` — 5 тестов через мини-FastAPI с dependency_overrides

## Decisions Made

- PyJWT вместо python-jose (abandoned): `import jwt as pyjwt` — ни одного `from jose`
- SHA256 для hash refresh-токена: token имеет ~256 бит энтропии (UUID + секрет), bcrypt излишен
- HTTPBearer(auto_error=False): FastAPI по умолчанию вернул бы 403 без нашего формата D-18

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] BOT_TOKEN в тестовых фикстурах исправлен**
- **Found during:** Task 2 (запуск RED фазы test_sessions.py)
- **Issue:** Фикстура `_setup_env` использовала `BOT_TOKEN = "token"` (5 символов), но config требует `min_length=10`. Тест падал на setup, не на сам модуль.
- **Fix:** Заменено на `"1234567890:ABC"` в test_sessions.py (и test_dependencies.py превентивно)
- **Files modified:** server/tests/test_sessions.py
- **Verification:** Тест прошёл setup, дошёл до `ModuleNotFoundError` (корректный RED)
- **Committed in:** `3c1d728` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — недостаточная длина тестовых credentials)
**Impact on plan:** Мелкое исправление тестовой фикстуры, не влияет на scope.

## Issues Encountered

Timezone awareness в `session.expires_at`: SQLite возвращает naive datetime, а `_utcnow()` возвращает aware. Решено через `.replace(tzinfo=timezone.utc)` при сравнении в `rotate_refresh`.

## Known Stubs

None — все функции полностью реализованы и протестированы.

## Self-Check: PASSED

All files confirmed present. All 3 task commits verified in git log.

## Next Phase Readiness

- Plan 05 (auth-code + Telegram): server/auth/codes.py и telegram.py — независимы от этого плана
- Plan 06 (auth endpoints): может использовать `create_access_token`, `SessionService`, `get_current_user` напрямую
- Plan 07 (sync endpoint): `get_current_user` dependency готова к использованию
- Старый `server/auth.py` (python-jose skeleton) намеренно оставлен до Plan 10 (deploy)

---
*Phase: 01-server-auth*
*Completed: 2026-04-14*
