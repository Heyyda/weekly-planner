# External Integrations

**Analysis Date:** 2026-04-14

## APIs & External Services

**Telegram:**
- **Purpose:** User authentication and verification code delivery
- **Flow:**
  1. User enters Telegram username → `client/core/auth.py:AuthManager.request_code()`
  2. Server generates 6-digit code → sends via Telegram bot
  3. User enters code → `AuthManager.verify_code()` validates and returns JWT
- **SDK/Client:** `requests>=2.31.0` for HTTP calls
- **Auth:** 
  - Server uses: `PLANNER_TG_BOT_TOKEN` env var (Telegram Bot API token)
  - Webhook: Not used - one-off messages only
- **Implementation:** `server/auth.py` handles code generation/validation
- **Webhook endpoint:** None (bot sends DM, doesn't receive callbacks)

**Update Server:**
- **Purpose:** Version checking and executable download
- **Endpoint:** `https://heyda.ru/planner/download` + `https://heyda.ru/planner/api/version`
- **SDK/Client:** `requests>=2.31.0`
- **Auth:** None (public endpoint)
- **Implementation:** `client/utils/updater.py`
  - `check()` - GET `/api/version` compares current vs available
  - `download_and_verify()` - Downloads .exe, validates SHA256
  - Fallback: If bat-script fails, link opens in browser

## Data Storage

**Databases:**
- **SQLite (Server-side):**
  - Location: `/opt/planner/weekly_planner.db` (configurable via `PLANNER_DB` env var)
  - Client: SQLAlchemy 2.0.0+
  - ORM: `server/db.py` defines models
  - Tables: `users`, `tasks`, `categories`, `day_notes`, `recurring_templates`
  - Foreign keys: User → Tasks, Categories, DayNotes, Templates

**Local Caching (Client):**
- **File Storage:** `%APPDATA%/ЛичныйЕженедельник/cache.json`
- **Purpose:** Offline-first work, optimistic UI updates
- **Managed by:** `client/core/storage.py:LocalStorage`
- **Contents:**
  - `weeks` - Cached week data (nested by week_start date)
  - `categories` - User's task categories
  - `templates` - Recurring task templates
  - `pending_changes` - Queue of unsaved operations (create/update/delete)
  - `settings` - User preferences (theme, hotkey, autostart, etc.)
- **Sync Strategy:** Background merge (server wins on conflicts)

**Credential Storage (Client):**
- **Location:** Windows Credential Manager
- **Managed by:** `keyring>=25.0.0` library
- **Service name:** `"ЛичныйЕженедельник"`
- **Stored:** JWT access token, refresh token, username
- **Accessed by:** `client/core/auth.py:AuthManager`

**File Storage (Server):**
- None currently - all data in SQLite

**Caching (Client):**
- Local JSON cache for offline work
- No Redis or Memcached integration

## Authentication & Identity

**Auth Provider:** Custom Telegram-based (hybrid custom + external)

**Implementation:**
- `client/core/auth.py` - Client-side auth manager
  - `load_saved_token()` - Retrieve JWT from keyring
  - `request_code()` - POST to `/api/auth/request`
  - `verify_code()` - POST to `/api/auth/verify` with code
  - `_validate_token()` - GET `/api/auth/me` to check validity
  - `_refresh()` - POST `/api/auth/refresh` to get new access token

**Server-side:**
- `server/auth.py` - JWT generation and validation
  - `generate_verification_code()` - Creates 6-digit code, stores in `_pending_codes` dict (10-min expiry)
  - `verify_code()` - Checks code against stored value
  - `create_access_token()` - HS256-signed JWT (7-day expiry)
  - `create_refresh_token()` - HS256-signed JWT (30-day expiry)
  - `decode_token()` - Validates JWT signature

**Token Management:**
- **Access Token:** 7 days (`JWT_ACCESS_EXPIRE_DAYS`)
- **Refresh Token:** 30 days (`JWT_REFRESH_EXPIRE_DAYS`)
- **Algorithm:** HS256 (symmetric signing)
- **Secret:** `PLANNER_JWT_SECRET` env var (MUST rotate in production)
- **Storage:** Windows Credential Manager (via keyring)

**Fallback (Offline):**
- Cached JWT considered valid if server unreachable
- Sync queues changes locally until network returns

## Monitoring & Observability

**Error Tracking:**
- None detected in codebase
- Silent failures: Network errors logged implicitly but no centralized tracking

**Logs:**
- `client/utils/updater.py` - Creates `%TEMP%/planner_update.log` during updates
- Entry example: `[2026-04-14 14:30:22] Starting update`
- Purpose: Debug failed update attempts

**Alerts:**
- None implemented yet

## CI/CD & Deployment

**Hosting:**
- **Client:** Distributed as single .exe file (self-contained)
- **Server:** VPS 109.94.211.29 (co-located with E-bot, port 8100)

**CI Pipeline:**
- None detected (no GitHub Actions, no .gitlab-ci.yml)
- Manual build: `build\build.bat` on Windows
- Manual deployment: Copy .exe to users or host on `https://heyda.ru/planner/download`

**Build Process:**
- PyInstaller (local Windows machine)
- Outputs: `dist\Личный Еженедельник.exe`
- File size: ~100MB+ (full Python + dependencies bundled)

**Update Mechanism:**
- Semantic versioning in `main.py:VERSION = "0.1.0"`
- Server stores: `version`, `download_url`, `sha256` in response
- Client downloads, validates SHA256, replaces via bat-script, restarts

## Environment Configuration

**Required env vars (Server):**
- `PLANNER_DB` - Database path (default: `/opt/planner/weekly_planner.db`)
- `PLANNER_JWT_SECRET` - **CRITICAL:** Must be strong random string in production
- `PLANNER_TG_BOT_TOKEN` - Telegram Bot API token for sending verification codes
- `PLANNER_TG_ADMIN_CHAT` - Admin chat ID for operational logs
- `PLANNER_EXE_PATH` - Path to latest .exe for version endpoint

**Secrets location:**
- Server: Environment variables (sourced from `.env` or deployment config)
- Client: Windows Credential Manager (via keyring)
- Build: PyInstaller packages Python + all deps into .exe

**No secrets in code:**
- API base URLs hardcoded: `https://heyda.ru/planner/api` (config file level)
- Tokens retrieved from secure storage at runtime

## Webhooks & Callbacks

**Incoming:**
- None - Client initiates all requests (pull-based)
- Telegram bot sends DMs (one-way message, no webhook back)

**Outgoing:**
- None currently
- Potential future: Update notifications to user via Telegram

## Data Flow Architecture

**Sync Flow (Optimistic UI):**
1. User creates/edits task in client
2. Applied to local cache immediately (optimistic)
3. Operation added to `pending_changes` queue
4. Background sync thread (30-sec interval) in `client/core/sync.py`
5. POST to `/api/sync` with all pending changes
6. Server processes, returns merged week data
7. Client updates local cache with server version (server wins on conflicts)
8. If conflict: Server version overwrites local (deterministic resolution)
9. If offline: Changes stay in queue, sync retry on reconnect

**Authentication Flow:**
1. First launch: No JWT in keyring → show login screen
2. User enters Telegram username
3. Client: POST `/api/auth/request` → bot sends code via Telegram DM
4. User enters 6-digit code in app
5. Client: POST `/api/auth/verify` {username, code} → returns {access_token, refresh_token}
6. Stored in keyring: `(jwt, refresh_token, username)`
7. All future API calls include: `Authorization: Bearer {jwt}`
8. On 401 response: Auto-refresh via POST `/api/auth/refresh`

**Update Flow:**
1. App startup: GET `/api/version`
2. Compare returned version vs `main.py:VERSION`
3. If newer: Show "Update available" banner
4. User clicks "Update"
5. Download .exe from `download_url`
6. Verify SHA256 matches
7. Create bat-script that:
   - Waits for exe to close (10 attempts × 1-sec)
   - `copy /y` new exe over old
   - Delete new file
   - Self-delete bat script
8. User manually restarts app (or scheduled restart)

## Integration Points Summary

| Service | Type | Protocol | Client Lib | Auth | Error Handling |
|---------|------|----------|------------|------|-----------------|
| Telegram Bot | Auth | HTTPS | requests | Token env var | Silent on 401, fallback to no code |
| Planner API | REST | HTTPS | requests | JWT (keyring) | Retry sync queue, offline mode |
| Update Server | Download | HTTPS | requests | None | Fallback: "Download" link in browser |
| SQLite | Database | Local | SQLAlchemy | None | N/A (server-only) |
| Win Credential Mgr | Secret Store | Windows API | keyring | User password | Fallback to no token on error |

---

*Integration audit: 2026-04-14*
