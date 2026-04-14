# Stack Research

**Domain:** Windows desktop overlay + FastAPI sync server + Telegram bot auth/mobile entry
**Researched:** 2026-04-14
**Confidence:** MEDIUM-HIGH (pre-decided stack validated; gotchas sourced from official issues and docs)

---

## Version Snapshot (verified 2026-04-14)

| Package | Pre-decided pin | Current latest | Status |
|---------|----------------|----------------|--------|
| customtkinter | >=5.2.0 | 5.2.2 (Jan 2024) | Stale — no new PyPI release in 15+ months. Use as-is, no upgrade expected. |
| pystray | >=0.19.0 | 0.19.5 (Sep 2023) | Stale — use 0.19.5 exact. Pillow compat fix in this version, critical. |
| keyboard | >=0.13.5 | 0.13.5 | Stagnant. No active development. See replacement note below. |
| keyring | >=25.0.0 | 25.7.0 (Nov 2025) | Active. Bump pin to >=25.7.0. |
| requests | >=2.31.0 | 2.33.1 (Mar 2026) | Active. Bump pin to >=2.32.0. |
| Pillow | >=10.0.0 | 12.2.0 (Apr 2026) | Active. Pillow 12.x requires Python >=3.10 — compatible with 3.12. Bump pin to >=11.0.0. |
| PyInstaller | 6.0.0+ | 6.19.0 (Feb 2026) | Active. Use >=6.10 for improved antivirus retry loop fix. |
| FastAPI | 0.110.0+ | 0.135.3 (Apr 2026) | Active. Bump pin to >=0.115.0. |
| SQLAlchemy | 2.0.0+ | 2.0.49 (Apr 2026) | Active. Pin >=2.0.30. |
| python-jose | 3.3.0+ | **ABANDONED** (last release 2021) | Replace with PyJWT. See critical note below. |
| aiogram | (not chosen yet) | 3.27.0 (Apr 2026) | Actively released. Recommend over python-telegram-bot for this stack. |
| python-telegram-bot | (alternative) | 22.7 (Mar 2026) | Also active; heavier dependency tree. |

---

## Recommended Stack

### Core Client Technologies

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12.x | Runtime | 3.12 brings 5-15% speedup vs 3.11; full win32api support; matches VPS server version |
| CustomTkinter | ==5.2.2 | Desktop GUI | Only modern-looking Tkinter wrapper that works as single-file PyInstaller bundle without Qt; proven on E-bot; 5.2.2 is the latest and only stable release |
| ctypes + pywin32 | stdlib + pywin32>=306 | Win32 overlay APIs | Required for SetWindowPos HWND_TOPMOST, DwmSetWindowAttribute (rounded corners), WINEVENT hooks. pywin32 wraps these more safely than raw ctypes. |
| pystray | ==0.19.5 | System tray icon | Only maintained cross-platform tray library for Python; 0.19.5 fixes Pillow compat regression |
| pynput | >=1.7.7 | Global hotkeys | Replace `keyboard` library — see "What NOT to Use"; no admin rights required on Windows |
| keyring | >=25.7.0 | JWT credential storage | WinCred backend (Windows Credential Manager) auto-selected on Windows; production-proven in E-bot |
| requests | >=2.32.0 | HTTP sync client | Sufficient for non-async client; simpler than httpx for this use case |
| Pillow | >=11.0.0 | Tray icon image handling | Required by pystray for icon rendering; 11.x+ is Python 3.10+ compatible |
| PyInstaller | >=6.10.0 | Single .exe packaging | 6.10+ includes retry loop for AV-locked temp DLLs; latest bootloader has fewest AV hits |

### Core Server Technologies

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | >=0.115.0 | REST API framework | Async-native, minimal boilerplate, Pydantic v2 integrated; standard for Python APIs in 2025-2026 |
| Uvicorn | >=0.30.0 | ASGI server | Standard companion to FastAPI; supports --workers for scaling if needed later |
| SQLAlchemy | >=2.0.30 | ORM + connection management | 2.x unified API; async session support via aiosqlite; WAL mode pragmas via events |
| aiosqlite | >=0.20.0 | Async SQLite driver | Required for SQLAlchemy async engine with SQLite; thin async wrapper, production stable |
| PyJWT | >=2.9.0 | JWT encode/decode | Replacement for abandoned python-jose; FastAPI docs migrated to PyJWT (PR #11589 merged 2024) |
| passlib[bcrypt] | >=1.7.4 | Password hashing | Reserved; currently not used but keep for potential future password-based admin access |
| aiogram | >=3.15.0 | Telegram bot | Async-native; runs inside same FastAPI/asyncio loop; better than python-telegram-bot for server-embedded bots |
| python-dotenv | >=1.0.0 | Server env config | Standard .env loading for PLANNER_JWT_SECRET etc. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| PyInstaller | Build .exe | Use `--noupx` flag — disabling UPX reduces AV false positives significantly |
| pip-tools | requirements.txt management | `pip-compile` for locked reproducible builds; prevents version drift between dev and build machines |

---

## Installation

```bash
# Client dependencies
pip install customtkinter==5.2.2 pystray==0.19.5 pynput>=1.7.7 keyring>=25.7.0 requests>=2.32.0 Pillow>=11.0.0 pywin32>=306

# Build tool (Windows)
pip install pyinstaller>=6.10.0

# Server dependencies
pip install fastapi>=0.115.0 uvicorn>=0.30.0 sqlalchemy>=2.0.30 aiosqlite>=0.20.0 PyJWT>=2.9.0 passlib[bcrypt]>=1.7.4 aiogram>=3.15.0 python-dotenv>=1.0.0
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| pynput (global hotkeys) | keyboard>=0.13.5 | `keyboard` library is stagnant (no releases since 2022), has Windows UAC elevation issues on some corporate setups, and uses a raw hook approach that triggers more AV flags; pynput's GlobalHotKeys API is equivalent and maintained |
| PyJWT>=2.9.0 | python-jose[cryptography] | python-jose last released 2021, has known Python 3.10+ compatibility issues, FastAPI officially migrated docs to PyJWT in 2024; python-jose is effectively abandoned |
| aiogram>=3.15.0 | python-telegram-bot>=22.0 | Both are active (aiogram 3.27.0 Apr 2026, ptb 22.7 Mar 2026). aiogram wins here because: (1) async-native = runs inside FastAPI's own event loop without thread bridging, (2) webhook integration is first-class (SimpleRequestHandler for ASGI), (3) smaller for a send-only auth bot |
| pystray==0.19.5 | infi.systray | infi.systray is Windows-only and unmaintained; pystray works cross-platform and has Pillow integration |
| aiosqlite | sync SQLAlchemy | Server uses FastAPI with async routes; using sync SQLAlchemy forces `run_in_executor` wrappers and leaks blocking calls into the event loop; aiosqlite avoids this |
| CustomTkinter | PyQt6 / Tkinter | PyQt6 adds 30-40MB to bundled .exe and requires LGPL compliance tracking; vanilla Tkinter has no dark mode or modern widgets; CustomTkinter is the right tradeoff for this project scope |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `python-jose` | Abandoned (last release 2021). Known Python 3.10+ breakage. FastAPI officially replaced it in docs. CVE exposure risk grows over time. | `PyJWT>=2.9.0` |
| `keyboard` library | Stagnant (no releases 2022+). Intermittently requires elevation on corporate Windows. Source: multiple GitHub issues, stagnant PyPI. | `pynput>=1.7.7` with `GlobalHotKeys` |
| `UPX compression` in PyInstaller | UPX-compressed exe triggers more AV hits than uncompressed. UPX also corrupts some Windows DLLs with Control Flow Guard. Use `--noupx` flag explicitly. Source: pyinstaller/pyinstaller#6754, upx/upx#711 | `pyinstaller --noupx` (default behavior since PyInstaller 6.x is to skip UPX on non-Windows, but explicitly set for clarity) |
| Sync SQLAlchemy on server | FastAPI is async; sync DB calls block the event loop and cause cascade latency under concurrent requests | SQLAlchemy async engine + `aiosqlite` |
| `python-telegram-bot` polling loop in same process | ptb's Application.run_polling() creates its own event loop and blocks; embedding it in FastAPI requires threading bridges | aiogram with Dispatcher.feed_update() or aiogram's StartupEvent webhook registration |
| PyInstaller `--onedir` as workaround for AV | Users expect single .exe; onedir creates folder with dozens of files, breaks "copy to USB" distribution pattern | `--onefile --noupx` + submit to AV vendors if flagged |

---

## Critical Gotchas

### 1. CustomTkinter + overrideredirect on Windows 11

**Problem:** `overrideredirect(True)` called synchronously at window creation time causes the window to render behind other windows on Windows 11. The window appears but is inaccessible.

**Fix:** Delay the call with `self.after(100, lambda: self.overrideredirect(True))`. This is the documented workaround in CustomTkinter Discussion #1219 and #1302.

**Additional issue:** `overrideredirect(True)` removes DWM rounded corners. To restore them on Windows 11, call `DwmSetWindowAttribute` via ctypes after setting overrideredirect:
```python
import ctypes
DWMWA_WINDOW_CORNER_PREFERENCE = 33
ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(ctypes.c_int(2)), 4)
```
Source: CustomTkinter Discussion #1302; hPyT library (GitHub: Zingzy/hPyT) wraps this.

**Confidence:** HIGH (reproduced across multiple GitHub issues, Windows 11-specific DWM behavior documented)

---

### 2. pystray threading — must NOT run on Tkinter's main thread

**Problem:** Both Tkinter and pystray have their own blocking event loops. Running pystray on the main thread blocks Tkinter's mainloop, and vice versa. Calling Tkinter from a non-main thread causes `RuntimeError: Calling Tcl from different apartment`.

**Fix:** Run pystray in a daemon thread. All Tkinter widget updates from tray callbacks must be dispatched via `root.after(0, callback)` — never called directly from the pystray thread.
```python
import threading
tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
tray_thread.start()
```

**Source:** pystray Issue #94; multiple tkthread discussions.

**Confidence:** HIGH — this is the canonical pattern; documented in multiple sources.

---

### 3. PyInstaller --onefile Windows Defender false positives

**Problem:** PyInstaller --onefile executables are frequently flagged by Windows Defender and third-party AV because they self-extract to `%TEMP%` at runtime — a common malware pattern. The bootloader is the flagged component. PyInstaller 6.3.0 had particularly high VirusTotal hit rates (6/69 vs 2/69 for 5.13.2).

**Mitigations (in priority order):**
1. Use `--noupx` — UPX compression dramatically increases AV hit rate (upx/upx#711 confirmed)
2. Pin `pyinstaller>=6.10.0` — newer bootloaders get fewer hits before AV signature updates
3. Add application manifest with `requestedExecutionLevel=asInvoker` — reduces "suspicious elevation" heuristics
4. Add a proper `--icon` — iconless executables score higher suspicion in some AV heuristics
5. Submit to Windows Defender false positive reporting portal and major AV vendors if deploying to others' machines

**Source:** pyinstaller#6754, discuss.python.org/t/pyinstaller-false-positive/43171, pythonguis.com AV guide.

**Confidence:** HIGH — documented across multiple independent sources.

---

### 4. python-jose — do NOT use

**Problem:** python-jose last PyPI release was 2021. It has known compatibility issues with Python 3.10+ (cryptography dependency conflicts). FastAPI officially removed it from docs in PR #11589 (merged 2024). Using it risks silent JWT validation failures and unpatched CVEs.

**Fix:** Use `PyJWT>=2.9.0`. Migration is straightforward:
```python
# python-jose (old)
from jose import jwt
jwt.encode({"sub": user_id}, SECRET_KEY, algorithm="HS256")

# PyJWT (new)
import jwt
jwt.encode({"sub": str(user_id)}, SECRET_KEY, algorithm="HS256")
```
Note: PyJWT returns a string directly (not bytes) in 2.x.

**Source:** fastapi/fastapi Discussion #9587 and #11345; PR #11589.

**Confidence:** HIGH — official FastAPI documentation change.

---

### 5. SQLite concurrency with FastAPI + Telegram bot

**Problem:** Both the FastAPI server and the aiogram bot process write to the same SQLite file. SQLite allows only one writer at a time. Without WAL mode and busy_timeout, concurrent writes cause immediate "database is locked" errors.

**Fix:** Enable WAL mode and set busy_timeout via SQLAlchemy event:
```python
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("sqlite+aiosqlite:////opt/planner/weekly_planner.db")

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")  # 5 seconds
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
```

WAL mode allows simultaneous readers + one writer. busy_timeout makes writers retry instead of failing instantly.

For this project (single user, low write volume), WAL + 5s timeout is sufficient. No need for queued write serialization.

**Source:** SQLAlchemy SQLite dialect docs; tenthousandmeters.com SQLite concurrency analysis.

**Confidence:** HIGH — SQLite official docs + SQLAlchemy docs.

---

### 6. keyring on Windows — WinCred character limits

**Problem:** Windows Credential Manager has a per-entry size limit (~2500 bytes for the target name, ~512 bytes for the credential blob). JWT access tokens (HS256, 7-day) are typically 200-300 bytes — well within limits. Refresh tokens are similar. However, if the service name contains Cyrillic characters ("ЛичныйЕженедельник"), test credential roundtrip in CI since WinCred encodes names as UTF-16.

**Fix:** Use ASCII service name for keyring service identifier internally, display name can be anything:
```python
keyring.set_password("weekly-planner", username, jwt_token)
```

**Source:** keyring GitHub Windows.py backend; keyring/keyring#84 (format discussion).

**Confidence:** MEDIUM — Windows limit is documented; Cyrillic-specific behavior inferred from UTF-16 encoding, not reproduced in a reported issue.

---

### 7. CustomTkinter is in maintenance mode

**Problem:** CustomTkinter 5.2.2 was released January 2024. As of April 2026, no new PyPI release in 15+ months. The GitHub repo shows 395 open issues and 17 open PRs but no recent releases. The project is "under active development" per README but PyPI is stale.

**Impact for this project:** Low. v1 uses standard widgets (frames, labels, buttons, checkboxes) that are stable in 5.2.2. No bleeding-edge CTk features needed.

**Mitigation:** Pin `customtkinter==5.2.2` exactly (not `>=`). If a bug is discovered in CTk itself, patch locally rather than waiting for upstream release. The codebase is pure Python — patching is feasible.

**Confidence:** HIGH (PyPI dates verified directly).

---

## Version Compatibility Matrix

| Client Package | Compatible Python | Notes |
|----------------|------------------|-------|
| customtkinter==5.2.2 | 3.8-3.12 | Tested on 3.12 by community; no known breakage |
| pystray==0.19.5 | 3.6+ | Requires Pillow for icon rendering on Windows |
| Pillow>=11.0.0 | >=3.10 | Pillow 12.x drops 3.9 support; 3.12 is fine |
| pywin32>=306 | 3.8-3.12 | 306 is the stable build for Python 3.12 on Windows |
| pynput>=1.7.7 | 3.8+ | Uses ctypes under the hood on Windows; no admin required |
| PyInstaller>=6.10.0 | 3.8-3.12 | Boot loader compiled for Python 3.12; use matching Python version |

| Server Package | Compatible Python | Notes |
|----------------|------------------|-------|
| FastAPI>=0.115.0 | 3.8+ | Pydantic v2 used by default in 0.100+; V1 compat shim if needed |
| SQLAlchemy>=2.0.30 | 3.7+ | Async API requires Python 3.10+ (asyncio improvements); use 3.12 |
| aiosqlite>=0.20.0 | 3.8+ | Uses asyncio.get_event_loop() internals; stable on 3.12 |
| aiogram>=3.15.0 | 3.10+ | 3.x requires Python 3.10+; use 3.12 on VPS |
| PyJWT>=2.9.0 | 3.8+ | Pure Python; no C extension; no compatibility issues |

---

## Telegram Bot: aiogram 3.x Choice Rationale

For this project the Telegram bot does three things:
1. Send 6-digit verification code to user (auth flow)
2. Accept "add task" commands
3. Return current week view

**Why aiogram 3.x over python-telegram-bot 22.x:**

aiogram 3.x is async-native and integrates directly into FastAPI's asyncio event loop via `Dispatcher.feed_update()` or the `SimpleRequestHandler` webhook middleware. No thread bridging needed.

python-telegram-bot 22.x can also embed in FastAPI but requires more careful lifecycle management — its `Application` has its own internal asyncio runner that fights with FastAPI's.

For a simple send-only bot (auth codes) + command bot (add task, view week), aiogram's simpler coroutine-based handler pattern wins:

```python
# aiogram 3.x — registers cleanly as FastAPI startup task
dp = Dispatcher()

@dp.message(Command("add"))
async def handle_add(message: Message): ...

# In FastAPI lifespan:
await bot.set_webhook(url=f"https://heyda.ru/planner/bot")
```

**Source:** aiogram 3.27.0 docs; aiogram webhook docs; fastapi+aiogram template repos verified working.

**Confidence:** MEDIUM (integration pattern confirmed in multiple GitHub templates; no direct production test for this exact combo, but standard approach)

---

## Recommended requirements.txt Structure

```
# ── CLIENT (installed locally for dev; bundled via PyInstaller) ──────────────
customtkinter==5.2.2
pystray==0.19.5
pynput>=1.7.7
keyring>=25.7.0
Pillow>=11.0.0
requests>=2.32.0
pywin32>=306

# ── BUILD (Windows only, not included in server) ─────────────────────────────
pyinstaller>=6.10.0

# ── SERVER (deployed on VPS; not needed for client dev) ──────────────────────
# fastapi>=0.115.0
# uvicorn[standard]>=0.30.0
# sqlalchemy>=2.0.30
# aiosqlite>=0.20.0
# PyJWT>=2.9.0
# passlib[bcrypt]>=1.7.4
# aiogram>=3.15.0
# python-dotenv>=1.0.0
```

Server deps kept commented to avoid installing unnecessary packages on Windows dev machine. Maintain separate `server/requirements.txt` for VPS deployment.

---

## Sources

- [CustomTkinter PyPI](https://pypi.org/project/customtkinter/) — version 5.2.2, Jan 2024
- [CustomTkinter GitHub Discussion #1219](https://github.com/TomSchimansky/CustomTkinter/issues/1219) — CTkToplevel created behind windows (overrideredirect delay fix)
- [CustomTkinter GitHub Discussion #1302](https://github.com/TomSchimansky/CustomTkinter/discussions/1302) — rounded corners with overrideredirect on Windows 11
- [pystray PyPI](https://pypi.org/project/pystray/) — version 0.19.5, Sep 2023
- [pystray Issue #94](https://github.com/moses-palmer/pystray/issues/94) — threading model (Tkinter main thread constraint)
- [PyInstaller PyPI](https://pypi.org/project/PyInstaller/) — version 6.19.0, Feb 2026
- [pyinstaller Issue #6754](https://github.com/pyinstaller/pyinstaller/issues/6754) — AV false positives with --onefile
- [upx Issue #711](https://github.com/upx/upx/issues/711) — UPX increases AV hit rate
- [fastapi Discussion #9587](https://github.com/fastapi/fastapi/discussions/9587) — python-jose abandonment
- [fastapi Discussion #11345](https://github.com/fastapi/fastapi/discussions/11345) — migration to PyJWT
- [fastapi PR #11589](https://github.com/fastapi/fastapi/pull/11589) — official docs switch to PyJWT
- [PyJWT PyPI](https://pypi.org/project/PyJWT/) — version 2.12.1, Mar 2026
- [FastAPI PyPI](https://pypi.org/project/fastapi/) — version 0.135.3, Apr 2026
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) — version 2.0.49, Apr 2026
- [SQLAlchemy SQLite dialect docs](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html) — WAL, check_same_thread, aiosqlite
- [aiogram PyPI](https://pypi.org/project/aiogram/) — version 3.27.0, Apr 2026
- [python-telegram-bot PyPI](https://pypi.org/project/python-telegram-bot/) — version 22.7, Mar 2026
- [keyring PyPI](https://pypi.org/project/keyring/) — version 25.7.0, Nov 2025
- [requests PyPI](https://pypi.org/project/requests/) — version 2.33.1, Mar 2026
- [Pillow PyPI](https://pypi.org/project/Pillow/) — version 12.2.0, Apr 2026
- [tenthousandmeters.com — SQLite concurrent writes](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) — WAL + busy_timeout pattern
- [pythonguis.com — AV false positives guide](https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/) — mitigation strategies

---

*Stack research for: Личный Еженедельник (Windows desktop overlay + FastAPI + Telegram bot)*
*Researched: 2026-04-14*
