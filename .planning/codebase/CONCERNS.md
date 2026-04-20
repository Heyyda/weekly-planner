# Codebase Concerns

**Analysis Date:** 2026-04-14

## Tech Debt

**Extensive Stub/Pass Implementation:**
- Issue: 30+ functions across client UI and app initialization are empty stubs with TODO comments. Core functionality is completely unimplemented.
- Files: 
  - `client/app.py` — `_setup()` (lines 53-65) and `destroy()` (lines 72-75) are pass-only
  - `client/ui/sidebar.py` — `setup()` (61-65), `expand()` (67-70), `collapse()` (72-75), `_move_window()` (84-87) all empty
  - `client/ui/day_panel.py` — `add_task()` (39-42), `_refresh()` (51-54) empty
  - `client/ui/task_widget.py` — 6 methods all empty (35-66)
  - `client/ui/week_view.py` — main refresh logic missing (line 76)
  - `client/ui/notes_panel.py` — save/load (33-38) empty
  - `client/ui/stats_panel.py` — refresh (27) unimplemented
  - `client/ui/settings_panel.py` — two stub methods (lines 32, 37)
  - `server/api.py` — only 2 endpoints out of 10+ are stubbed (lines 34-42)
- Impact: Application cannot run end-to-end. Core workflows (task creation, sidebar animation, data sync, server API) are incomplete.
- Fix approach: Systematically implement all stubs in priority order: (1) auth flow, (2) data models/storage, (3) server API endpoints, (4) UI rendering, (5) animations.

**Hardcoded API Endpoints (Multiple Locations):**
- Issue: API_BASE URL is hardcoded as `https://heyda.ru/planner/api` in 3 separate files with "TODO: финализировать" comments. No centralized config.
- Files: 
  - `client/core/auth.py` line 25
  - `client/core/sync.py` line 26
  - `client/utils/updater.py` line 22
- Impact: Difficult to change API endpoint (requires manual edits in 3 places). Different modules could be pointing to different endpoints if changed inconsistently.
- Fix approach: Create `client/config.py` with centralized `API_BASE` constant. Import it everywhere instead of duplicating.

**JWT Token Storage — Keyring Potential Failures Not Handled:**
- Issue: `client/core/auth.py` uses Windows keyring via `keyring` library. Generic exception handling (line 44: `except Exception: pass`) silently swallows credential storage errors.
- Files: `client/core/auth.py` lines 36-46, 121-127
- Impact: Token save failures go unnoticed. User could lose authentication token after login. Token validation errors are opaque (line 101 returns True on offline assuming validity).
- Fix approach: 
  - Log keyring errors explicitly (don't silence all exceptions)
  - Validate that `_save_tokens()` succeeds before returning True from `verify_code()`
  - Add fallback storage (encrypted JSON file) if keyring fails

**No Input Validation in Auth Flow:**
- Issue: Username and code validation happens only on server. Client doesn't validate format before sending.
- Files: `client/core/auth.py` lines 48-77
- Impact: Invalid usernames (empty, special chars) or codes (wrong length) sent to server. No early user feedback.
- Fix approach: Add regex/format validation on client before POST requests.

## Known Bugs

**Conflict Resolution in Sync Always "Server Wins" — No Merge:**
- Issue: `client/core/sync.py` line 82-84 blindly overwrites local cache with server data. If user creates task offline then server has different version, local work is lost.
- Files: `client/core/sync.py` lines 80-87
- Symptoms: User creates 5 tasks offline, goes online, sync receives server versions of same 2 tasks → 3 user-created tasks overwritten.
- Workaround: None (by design, server is source of truth, but merge logic is missing).
- Fix approach: Implement three-way merge (before_local, local_current, server_new) or last-write-wins with conflict UI.

**Race Condition: Pending Changes Queue Not Thread-Safe:**
- Issue: `client/core/storage.py` manages pending_changes list without threading.Lock. Sync thread reads/clears in `_sync_loop()` while UI thread may be writing in `add_pending_change()`.
- Files: `client/core/storage.py` (lines 74-88), `client/core/sync.py` (line 69)
- Symptoms: Lost updates during sync, partial queue cleared mid-operation, IndexError on concurrent access.
- Trigger: Rapid task creation followed immediately by forced sync.
- Fix approach: Add `threading.Lock` to LocalStorage class, acquire in all `_data` mutations.

**Sidebar Animation Uses `root.after()` But Not Bound to Geometry:**
- Issue: `client/ui/sidebar.py` references `SetWindowPos` in TODO but animation logic calls `_move_window()` which is empty. No actual window movement happens.
- Files: `client/ui/sidebar.py` lines 67-87
- Symptoms: Sidebar doesn't slide in/out. Window doesn't animate. Stays frozen at initial position.
- Fix approach: Implement `_move_window()` with ctypes.windll.user32.SetWindowPos or use tkinter `geometry()` with scheduled updates via `after()`.

**Overrideredirect Window Cannot Be Moved by User — Lock-In Risk:**
- Issue: `client/app.py` line 44 uses `overrideredirect=True)` which removes title bar. No dragging by default. If sidebar gets stuck off-screen, user cannot recover.
- Files: `client/app.py` line 44, `client/ui/sidebar.py` entire logic
- Symptoms: Window hidden behind edge, no visible dragging handle, user cannot access sidebar.
- Fix approach: Implement mouse-drag-to-move on trigger region (4px strip), or add keyboard shortcut to reset position to screen edge.

**Settings Changes Not Applied Until Restart:**
- Issue: Theme, hotkey, and "Do Not Disturb" changes are saved to `settings.json` but never re-applied to running app.
- Files: `client/ui/settings_panel.py` (stub at lines 32, 37 — no apply logic)
- Symptoms: User changes dark→light, still sees dark theme. Changes Win+Q hotkey, old hotkey still works.
- Fix approach: Emit signals/callbacks in settings changes, apply theme/hotkey/timeout immediately.

## Security Considerations

**JWT Secret in Environment Variable Without Rotation:**
- Risk: `server/config.py` line 18 reads `JWT_SECRET` from env. If VPS is compromised, attacker can forge JWT tokens indefinitely.
- Files: `server/config.py` line 18, `server/auth.py` lines 55, 71
- Current mitigation: 7-day access token expiry provides some window. Refresh token validation happens server-side.
- Recommendations:
  - Add token rotation: refresh token should rotate on each use (consume old, issue new pair)
  - Key rotation: plan for periodic secret rollover (version secrets, support multiple active keys)
  - Audit: log all token issues and validations for forensics

**Verification Codes Stored in Memory Only — Lost on Restart:**
- Risk: `server/auth.py` line 21 — `_pending_codes` dict is ephemeral. Server restart clears all pending auth codes. Users mid-login must restart auth flow.
- Files: `server/auth.py` lines 20-31
- Current mitigation: 10-minute expiry (line 29) auto-clears old codes.
- Recommendations: 
  - Move to Redis or DB (persistent across restarts, supports TTL)
  - Until then: document that server restarts during auth window require re-starting client auth

**No HTTPS Enforcement on Client API Calls:**
- Risk: `client/core/auth.py`, `sync.py`, `updater.py` all use hardcoded HTTPS URLs, but requests library doesn't validate SSL certificates by default (could be subject to MITM if CA is compromised).
- Files: All POST/GET to API_BASE (lines 51, 91, 37 in respective files)
- Current mitigation: HTTPS in URL, requests validates by default.
- Recommendations: 
  - Explicitly set `verify=True` on all requests calls (already default, but make explicit)
  - Consider certificate pinning for extra assurance

**Telegram Bot Token Not Validated on Client:**
- Risk: Server auth flow depends on TELEGRAM_BOT_TOKEN (line 24 in config.py). If token leaks, attacker can impersonate bot, send fake verification codes.
- Files: `server/config.py` line 24
- Current mitigation: Token is env var on server only, not in client code.
- Recommendations:
  - Audit Telegram API integration (not in scope of this skeleton, but implement when building auth.py routes)
  - Validate that bot replies come from correct Telegram chat ID

## Performance Bottlenecks

**Sync Thread Runs Every 30 Seconds Regardless of Activity:**
- Problem: `client/core/sync.py` line 62 sleeps 30 seconds in loop. If user is idle, wasting CPU and battery polling empty pending_changes queue.
- Files: `client/core/sync.py` lines 58-62
- Cause: Fixed interval timer, no event-driven sync.
- Improvement path:
  - Listen for pending_changes queue size changes (use threading.Event)
  - Sync only when: (1) new changes queued, (2) timer interval reached, (3) user manually forces sync

**JSON Serialization on Every Task Change:**
- Problem: `client/core/storage.py` calls `json.dump()` to disk for every single operation (add_pending_change, save_week, save_settings).
- Files: `client/core/storage.py` lines 72, 88, 100 (all call `self.save()` which writes entire file)
- Cause: No batching, every single UI action triggers I/O.
- Improvement path:
  - Batch writes: queue changes, flush to disk in background thread every N seconds or on shutdown
  - Use SQLite locally instead of JSON for faster queries

**No Pagination on Long Task Lists:**
- Problem: WeekPlan loads all tasks for week into memory. If user has 100+ tasks, rendering all TaskWidgets causes UI lag.
- Files: `client/core/models.py` (WeekPlan.total_tasks, days[].tasks list), no pagination logic anywhere
- Cause: Full load from JSON/API, no virtual scrolling.
- Improvement path:
  - Implement virtual scrolling in day panels (only render visible tasks)
  - Load tasks on-demand when day panel expands

**PyInstaller --onefile Creates Large Binary:**
- Problem: Single .exe bundle includes entire Python runtime + all dependencies (ctypes, tkinter, requests, customtkinter, pystray, PIL). Expected size: 80-120MB.
- Files: `CLAUDE.md` build command (line 48 of instructions)
- Cause: PyInstaller --onefile trades size for convenience.
- Improvement path:
  - Test actual size once built
  - If >100MB, consider: (1) multi-file build (faster startup, larger footprint), (2) UPX compression (risky), (3) lazy imports of heavy modules

## Fragile Areas

**Windows-Only Code Path (No Cross-Platform Tested):**
- Files: 
  - `client/ui/sidebar.py` lines 84-87 (ctypes.windll — Windows only)
  - `client/utils/autostart.py` (assumed Windows registry manipulation, not visible)
  - `client/utils/hotkeys.py` (keyboard library works cross-platform but hotkey syntax may be OS-specific)
  - `client/utils/notifications.py` (win10toast assumed — Windows only)
- Why fragile: Code will crash on macOS/Linux. Sidebar won't exist, hotkeys won't work.
- Safe modification: Wrap Win32 calls in try-except, provide fallback behavior (no sidebar on non-Windows). Document Windows-only for now.
- Test coverage: Gaps — no unit tests for window positioning, hotkey registration.

**Sidebar Animation Without SetWindowPos Implementation:**
- Files: `client/ui/sidebar.py` lines 67-75, 84-87
- Why fragile: Animation logic exists but underlying window move is stubbed (line 87 comment only). Any code calling `expand()`/`collapse()` does nothing.
- Safe modification: First implement `_move_window()` with actual Win32 calls or tkinter geometry updates before enabling expand/collapse buttons.
- Test coverage: Manual testing only; no unit tests for animation smoothness or edge cases (rapid toggle, cursor leaves during animation).

**AppState Global State in Memory:**
- Files: `client/app.py` line 36 (self.state = AppState())
- Why fragile: Single AppState instance shared across all modules, no validation. Changes to theme/hotkey/autostart don't propagate. No persistence check.
- Safe modification: Make AppState immutable or provide property setters that trigger callbacks. Persist every change immediately to settings file.
- Test coverage: No tests for state consistency.

**Empty Task/DayPanel Implementation Cannot Handle Real Data:**
- Files: 
  - `client/ui/task_widget.py` TaskWidget class (19 lines, all stubs)
  - `client/ui/day_panel.py` DayPanel class (20 lines, all stubs)
- Why fragile: Models (Task, DayPlan) defined in `models.py` but UI layer has no rendering code. Once real tasks are created, UI won't display them.
- Safe modification: Implement `_refresh()` methods that iterate model.tasks and create TaskWidget children. Bind model changes to UI updates.
- Test coverage: Gaps — no tests for rendering, list updates, state synchronization.

**Server-Side Async Not Used (Blocking I/O in FastAPI):**
- Files: `server/api.py` (stubbed, but anticipated endpoints will be blocking without async/await)
- Why fragile: Once real database queries are added, they'll block the event loop. No background task handling planned.
- Safe modification: Mark all route handlers as `async def` from the start. Use `await` for I/O. Use FastAPI BackgroundTasks for sync operations.

## Scaling Limits

**In-Memory Verification Codes (No Persistence):**
- Current capacity: Limited by available server RAM. Dict stores username→code pairs for 10 minutes.
- Limit: Server restart clears all codes. No cleanup of expired codes (only at lookup). Memory leak if users repeatedly fail auth.
- Scaling path: Move to Redis with TTL or dedicated auth service. Cache verification attempts to prevent brute force.

**SQLite Database on Single VPS Without Replication:**
- Current capacity: SQLite handles ~1000 concurrent connections theoretically; practical limit ~10-50 with normal queries.
- Limit: No backup, no read replicas. Single VPS failure = data loss. No horizontal scaling.
- Scaling path: 
  - Backup: Cron job to copy weekly_planner.db to external storage (AWS S3, NAS)
  - If user count > 100: migrate to PostgreSQL, set up WAL (write-ahead logging), replicate to standby

**LocalStorage JSON File Grows Unbounded:**
- Current capacity: Typical cache.json for 1 year of 5-day weeks with 5 tasks/day ≈ 500KB.
- Limit: No cleanup of old weeks. App loads entire file on startup.
- Scaling path:
  - Implement cache eviction: keep only last 12 weeks + current week locally
  - Archive older weeks to separate file or delete after sync confirmation
  - Use SQLite locally instead of JSON for faster queries

## Dependencies at Risk

**keyboard Library Requires Elevated Privileges on Windows:**
- Risk: `keyboard` library (for hotkey registration) requires admin or elevation on Windows 10+. User running app without admin cannot register Win+Q hotkey.
- Files: `client/utils/hotkeys.py` line 29 (keyboard.add_hotkey)
- Impact: Global hotkey feature will silently fail. User won't know why Win+Q doesn't work.
- Migration plan:
  - Test if app detects admin elevation at startup. If not, warn user.
  - Fallback: use `ctypes.SetWindowsHookEx` (lower-level hook, also requires elevation)
  - Or: Relax feature — register hotkey only if privilege available, disable if not

**pystray Library Fallback to No System Tray:**
- Risk: `pystray` may fail to import on some Windows versions or minimal Python environments.
- Files: `client/utils/tray.py` lines 15-20 (conditional import, HAS_PYSTRAY flag)
- Current mitigation: Check `HAS_PYSTRAY` before starting tray (line 35 returns early)
- Impact: App runs without system tray, but user has no quick show/hide access.
- Migration plan: Already has fallback (skip tray gracefully). Document this behavior. Consider alternative: `win10toast` for notifications as pystray substitute for system tray.

**customtkinter Theming Incomplete:**
- Risk: CustomTkinter theming is global (lines 39-40 in app.py), but theme switching doesn't re-apply to already-created widgets.
- Files: `client/app.py` lines 39-40, `client/ui/themes.py` line 74 (TODO comment)
- Impact: Changing theme mid-app results in partial theme application. Some widgets don't update color.
- Migration plan: Implement theme registry: emit theme-change signal, all widgets listen and update. Or: recreate all widgets when theme changes (expensive).

## Missing Critical Features

**No Offline-First UX Indicator:**
- Problem: User doesn't know if sync succeeded or failed. No visual indicator (green/red dot) for sync status. Changes disappear silently if sync fails permanently.
- Blocks: Cannot reliably use app in low-connectivity environments. No trust that data is saved to server.
- Recommendation: Add sync status badge (bottom of sidebar) showing: "Syncing...", "Synced ✓", "Offline (3 pending changes)", "Sync failed ✗".

**No Migration Path from Old Client (if needed):**
- Problem: No versioning in cache.json format. If schema changes (e.g., add new field to Task), old client cache becomes invalid.
- Blocks: Cannot deploy schema changes without invalidating existing user data.
- Recommendation: Add "version": 1 to cache.json, implement migration functions to upgrade old schemas.

## Test Coverage Gaps

**No Unit Tests at All:**
- Untested: All auth logic (`client/core/auth.py`, `server/auth.py`), sync conflict resolution, offline queue, local storage I/O.
- Files: Entire `client/`, `server/` directories
- Risk: Bugs in token refresh, pending changes loss, keyring failures go unnoticed until production.
- Priority: High — add tests for:
  - `AuthManager.load_saved_token()` success/failure cases
  - `AuthManager._refresh()` token expiry and rotation
  - `SyncManager._do_sync()` conflict resolution, network errors, offline queue
  - `LocalStorage` concurrent read/write with locks
  - `Task.is_overdue()` boundary conditions

**No Integration Tests (Client ↔ Server):**
- Untested: Full auth flow (request code → verify code → get token), week sync, task CRUD end-to-end.
- Blocks: Cannot verify API contracts, error handling between layers.
- Recommendation: Add pytest fixtures for test server and mock Telegram bot. Test workflows like: (1) new user auth, (2) offline changes then sync, (3) server conflict resolution.

**No UI Component Tests:**
- Untested: Sidebar animation timing, task widget rendering, day panel expand/collapse, theme application.
- Blocks: Regressions in UI go undetected. Animation bugs only caught by manual testing.
- Recommendation: Use pytest + pytest-tk (or similar) to render CustomTkinter widgets, assert geometry and state.

**No Win32 Integration Tests:**
- Untested: `SetWindowPos` window positioning, hotkey registration, system tray startup/shutdown.
- Blocks: Sidebar animation and hotkey features untested. Only discoverable on Windows.
- Recommendation: Add Windows-specific test suite with real (or mocked) Win32 calls.

---

*Concerns audit: 2026-04-14*
