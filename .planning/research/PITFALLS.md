# Pitfalls Research

**Domain:** Windows desktop overlay app — CustomTkinter + PyInstaller + FastAPI sync + Telegram bot
**Researched:** 2026-04-14
**Confidence:** HIGH (critical pitfalls verified against official docs and GitHub issues)

---

## Critical Pitfalls

### Pitfall 1: CustomTkinter Cannot Be Packaged as --onefile Without Extra Work

**What goes wrong:**
The current `build.bat` uses `--onefile`. CustomTkinter ships `.json` theme files and `.otf` fonts as non-Python data assets. PyInstaller's analysis phase does not automatically detect them, so the built `.exe` launches, finds no theme data, and either crashes or renders with broken styling. The official CustomTkinter wiki states explicitly: "PyInstaller is not able to pack them into a single .exe file" without a `.spec` modification.

**Why it happens:**
Developers assume `--add-data` with `--onefile` is sufficient. It is not — the extraction path changes every run (`_MEIxxxxxx` temp folder), and CustomTkinter's internal path resolution looks for assets relative to the package directory, not the temp folder, unless you patch `sys._MEIPASS` into the lookup.

**How to avoid:**
Option A (recommended for v1): Switch to `--onedir` and ship as a folder. Wrap in an NSIS or InnoSetup installer if you want a single "installer" experience. Startup time drops from 5–15 s to ~1 s.

Option B (single exe): Write a `.spec` file using `collect_data_files('customtkinter')` and set `os.chdir(sys._MEIPASS)` at the top of `main.py` before any CustomTkinter imports. Add to `main.py`:
```python
import sys, os
if getattr(sys, 'frozen', False):
    os.chdir(sys._MEIPASS)
```
Then verify the built exe loads themes correctly before shipping.

**Warning signs:**
- Build completes without error but app opens with grey/unstyled widgets
- `FileNotFoundError` referencing a `.json` or `.otf` in logs on first launch
- Works in `python main.py`, fails in `.exe`

**Phase to address:** Distribution phase (PyInstaller build setup). Must be verified before any internal distribution.

---

### Pitfall 2: pystray and Tkinter Fight Over the Main Thread

**What goes wrong:**
`pystray.Icon.run()` is blocking and must own the main thread on Windows. Tkinter's `mainloop()` also must run on the main thread (Tcl/Tk is single-threaded and raises `RuntimeError: main thread is not in main loop` if called from a worker thread). Naively launching both on the main thread deadlocks the app. Launching either on a background thread causes intermittent `RuntimeError: Calling Tcl from different apartment` crashes, especially on tray icon clicks.

**Why it happens:**
Both pystray and Tkinter are documented as "must run on main thread" on Windows. Developers pick one for main thread and thread the other, which silently works until a callback crosses the thread boundary.

**How to avoid:**
Use `pystray.Icon.run_detached()` — this runs the tray icon in a background thread internally without requiring the caller to block. Then run Tkinter `mainloop()` on the main thread as normal. All tray menu callbacks that touch any Tkinter widget must route through `root.after(0, callback)` — never call `.configure()`, `.pack()`, or `.destroy()` directly from a pystray callback.

```python
# tray.py — correct pattern
icon = pystray.Icon("planner", image, menu=menu)
icon.run_detached()  # returns immediately, tray runs in background thread

# In any tray callback that touches UI:
def on_show(icon, item):
    root.after(0, lambda: root.deiconify())  # safe: schedules on main thread
```

**Warning signs:**
- App works fine until user right-clicks tray icon → then hangs or crashes
- `RuntimeError: main thread is not in main loop` in crash logs
- Works on developer machine, crashes on clean install (race-condition sensitive)

**Phase to address:** Phase 1 (app shell / tray setup). Must be correct from the first working build.

---

### Pitfall 3: Global Hotkey (keyboard library) Silently Fails Without Admin Rights

**What goes wrong:**
The `keyboard` library registers low-level keyboard hooks using `SetWindowsHookEx(WH_KEYBOARD_LL)`. On Windows 10/11 with UAC enabled, this requires either elevated privileges or that the process runs as administrator. When the app runs without elevation (the normal case for autostart), `keyboard.add_hotkey()` may return without error but the hotkey never fires, or only fires when the app window is in focus — defeating the purpose of a global hotkey.

**Why it happens:**
`keyboard` documentation does not prominently warn about this. The hook appears to register successfully (no exception), but Windows silently ignores hooks from non-elevated processes targeting elevated windows. This is Windows' "UIPI" (UI Privilege Isolation).

**How to avoid:**
Test at startup whether the hotkey actually fires. If not, detect and fall back gracefully:

```python
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# On startup:
if not is_admin():
    # Disable global hotkey, show warning in tray tooltip
    # Suggest: run as admin, or document the limitation
    pass
```

Alternative: Use `ctypes` + `RegisterHotKey` Win32 API directly — it has the same elevation requirements but fails with a clear error code (0) from `RegisterHotKey`, making detection straightforward.

Consider Win+Q as the default — Win key combinations are processed by Explorer and may have special routing. Prefer Ctrl+Alt+P or a similar safe combination.

**Warning signs:**
- Win+Q does nothing after autostart (app runs without elevation at startup)
- Hotkey works when running `python main.py` (elevated dev terminal) but not from installed `.exe`
- User reports hotkey only works "sometimes"

**Phase to address:** Phase integrating hotkeys. Add elevation detection and fallback in the same commit as hotkey registration.

---

### Pitfall 4: overrideredirect Window Disappears Behind Fullscreen Apps (DWM Z-Order)

**What goes wrong:**
`HWND_TOPMOST` keeps the overlay above normal windows, but true DirectX exclusive fullscreen apps (games, some video players) bypass DWM entirely and render directly to the display adapter. The overlay becomes invisible even with `SetWindowPos(HWND_TOPMOST)`. Additionally, when the user switches away from a fullscreen app and back to the desktop, Windows redraws the DWM stack — the overlay may flash or lose its topmost position until `SetWindowPos` is called again.

**Why it happens:**
Exclusive fullscreen is not a window — it's a hardware presentation mode. No window Z-order applies. This is a Windows design boundary, not a bug that can be worked around at the application level without using DXGI interop (far out of scope).

**How to avoid:**
This is an acceptable limitation — document it. The overlay is a work productivity tool, not a game overlay. The correct UX fix is:
- Tray icon always visible (fallback access when overlay is buried)
- Toggling "always on top" off when user wants to focus without the overlay
- Do NOT attempt DirectX injection or DXGI approaches — security software flags them

For the reappearance issue after fullscreen exit, listen for `WM_DISPLAYCHANGE` or use a `WM_WINDOWPOSCHANGED` hook to reapply topmost when focus returns.

**Warning signs:**
- Bug reports: "overlay disappears when I open [game/video player]"
- Overlay reappears after clicking desktop but is briefly behind other windows

**Phase to address:** Phase 1 (overlay shell). Document the limitation in the settings panel tooltip ("Not visible over exclusive fullscreen apps").

---

### Pitfall 5: Sync Queue Race Condition — Thread-Unsafe pending_changes

**What goes wrong:**
Already identified in CONCERNS.md: `pending_changes` list in `LocalStorage` is written by the UI thread (task creation) and read+cleared by the sync background thread simultaneously. On Windows with Python's GIL, list operations are not atomic at the application level. `list.append()` mid-iteration, or `list.clear()` while `sync.py` iterates, causes lost updates or `IndexError`.

**Why it happens:**
The GIL prevents true simultaneous bytecode execution but does not protect multi-step operations (read-modify-write on the list). `list.clear()` after `for change in pending_changes` is a classic TOCTOU race.

**How to avoid:**
```python
import threading

class LocalStorage:
    def __init__(self):
        self._lock = threading.Lock()
        self._pending_changes = []

    def add_pending_change(self, change):
        with self._lock:
            self._pending_changes.append(change)

    def drain_pending_changes(self):
        """Atomically take all pending changes and reset the queue."""
        with self._lock:
            changes = list(self._pending_changes)
            self._pending_changes.clear()
        return changes
```

The sync thread should call `drain_pending_changes()` — this is the only safe pattern.

**Warning signs:**
- Tasks created in rapid succession sometimes "disappear" (no sync, not saved)
- `IndexError` in sync logs
- Sync succeeds but server is missing items that were definitely created

**Phase to address:** Core data/storage phase. Lock must be in place before any background sync is wired up.

---

### Pitfall 6: Updating the Running .exe on Windows — File Locking

**What goes wrong:**
The auto-updater downloads a new `.exe` and tries to replace the running executable. Windows locks open executables — `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`. The auto-update silently fails or crashes.

**Why it happens:**
Windows maps executables into memory and holds a file handle open for the duration of the process. Unlike Linux (where you can unlink a running file), Windows prevents any write to a running `.exe`.

**How to avoid:**
The rename trick: You cannot overwrite the running exe, but you can rename it and write to a new name.

```python
import os, sys, subprocess

def apply_update(new_exe_path: str):
    current_exe = sys.executable  # path to the running .exe
    backup_path = current_exe + ".old"
    
    # Rename current (works even while running on Windows)
    os.rename(current_exe, backup_path)
    # Copy new exe into place
    import shutil
    shutil.copy2(new_exe_path, current_exe)
    
    # Schedule cleanup of .old on next launch
    # Then restart the process
    subprocess.Popen([current_exe])
    sys.exit(0)
```

Add cleanup at startup: `if os.path.exists(sys.executable + ".old"): os.remove(sys.executable + ".old")`.

Note: If the app is packaged as `--onefile`, `sys.executable` is the correct path. If `--onedir`, the main `.exe` path needs explicit resolution.

**Warning signs:**
- "Update downloaded successfully" message but old version keeps running
- `PermissionError` in updater logs
- `.exe.old` files accumulate in installation directory

**Phase to address:** Auto-update phase. Must be tested on the actual packaged `.exe`, not `python main.py`.

---

### Pitfall 7: keyring Fails to Find Backend in PyInstaller-Packaged Exe

**What goes wrong:**
`keyring` uses a plugin discovery system to find backends (Windows Credential Manager, Secret Service, etc.). PyInstaller's static analysis often misses the backend entry points because they're discovered via `importlib.metadata` at runtime. Result: `keyring.errors.NoKeyringError: No recommended backend was available` on the user's machine, even though it works during development.

**Why it happens:**
`keyring` backends are registered as Python package entry points. PyInstaller does not automatically collect `entry_points` metadata. The packaged `.exe` has no way to discover backends dynamically.

**How to avoid:**
Explicitly import the Windows backend in your code so PyInstaller's analysis includes it:

```python
# auth.py — force import so PyInstaller includes the backend
import keyring
from keyring.backends import Windows  # explicit import
keyring.set_keyring(Windows.WinVaultKeyring())
```

Also add to `.spec` file:
```python
hiddenimports=['keyring.backends.Windows', 'keyring.backends._win_crypto']
```

Additionally, implement a fallback to encrypted JSON file storage if keyring raises any exception — never silently swallow the error as the current `except Exception: pass` does.

**Warning signs:**
- `NoKeyringError` on first launch of `.exe` on clean machine
- Works in dev (`python main.py`) because dev Python has full package metadata
- User is prompted to log in every launch (token never persisted)

**Phase to address:** Auth phase AND distribution phase. Test on a clean Windows VM with only the `.exe`.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Silent `except Exception: pass` in keyring/auth | No crash on bad keyring | Token loss invisible to user; debugging impossible | Never — always log |
| Hardcoded `API_BASE` in 3 files | Quick to write | One URL change breaks 2 out of 3 silently | Never — centralize in `client/config.py` |
| `--onefile` without `.spec` customization | Simple build command | CustomTkinter themes missing; AV flags higher | Phase 1 OK to prototype; must fix before distribution |
| `except Exception` around Win32 calls | No crash on incompatible Windows | Silent degradation — user doesn't know overlay is broken | Acceptable only if you show a warning in tray tooltip |
| JSON file for local cache (no schema version) | Simple to implement | Schema change in v2 corrupts all existing user data | Acceptable for v1 only if you add `"version": 1` to the file now |
| In-memory `_pending_codes` for Telegram auth | No Redis dependency | Server restart mid-auth flow logs user out with no explanation | Acceptable for v1; document the behavior |
| Fixed 30s sync polling regardless of activity | Simple implementation | Wastes CPU; no sync on demand | Replace with `threading.Event` triggered on change; low effort |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Tkinter + background threads | Calling `.configure()` or `.pack()` directly from worker thread | Schedule all UI mutations via `root.after(0, fn)` — the only safe pattern |
| pystray + Tkinter | Running `icon.run()` on main thread, Tkinter on background | Use `icon.run_detached()`, keep `mainloop()` on main thread |
| keyring + PyInstaller | Assuming auto-discovery works in frozen exe | Explicitly import `keyring.backends.Windows` and set as active backend |
| SQLAlchemy + SQLite + FastAPI | Default SQLite engine without WAL or busy_timeout | `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;` on every connection |
| PyInstaller + CustomTkinter | `--onefile` with `--add-data` | Either `--onedir` or `.spec` with `collect_data_files` + `sys._MEIPASS` chdir |
| Telegram bot webhook | Sync reply processing inside the ack handler | Acknowledge first (HTTP 200), then process and send replies asynchronously |
| JWT + client clock | Using exact `exp` for refresh trigger | Refresh 60 s before expiry; add `leeway=60` in token validation |
| Windows registry autostart | Writing to `HKLM` (requires admin) | Write to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` — no elevation needed |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `--onefile` cold start | 5–15 s black screen on first launch | Switch to `--onedir`; add splash screen if staying onefile | Every cold start; users think app crashed |
| JSON `save()` on every operation | UI micro-freezes during rapid task creation | Batch writes: debounce 500 ms, flush on shutdown | At 10+ rapid keypresses |
| No `busy_timeout` on SQLite | `OperationalError: database is locked` from Telegram bot | `PRAGMA busy_timeout=5000` on connect | Whenever bot and desktop client write simultaneously |
| Full week re-render on every task change | Scroll position reset; flicker on checkbox click | Partial updates — only refresh the changed TaskWidget | At 20+ tasks per week |
| Sync thread polls every 30 s flat | Extra CPU/network when idle; no immediate sync on change | `threading.Event` cleared by `add_pending_change`, waited in sync loop | Noticeable on battery; also delays offline→online sync |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Silent exception swallow in `_save_tokens()` | Token never persisted; user re-auths repeatedly; no audit trail | Log every keyring error; add fallback encrypted file storage |
| `_pending_codes` dict in memory only | Server restart invalidates mid-flow auth code; user confused | Document limitation; plan Redis/DB migration for stability |
| No refresh token rotation on use | Stolen refresh token usable indefinitely | Server: invalidate old refresh token on each rotation; issue new pair |
| JWT secret in env without rotation plan | VPS compromise → forge tokens forever | Document rotation procedure; version secrets (`kid` claim) |
| No SHA256 verification before applying auto-update | Downgrade attack; corrupted download applied | Verify SHA256 before `os.rename()` in updater (already planned; verify it's actually implemented) |
| `verify=True` not explicit in `requests` calls | Could be monkey-patched to False by accident | Set `verify=True` explicitly on all `requests.get/post` calls |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No sync status indicator | User doesn't know if task reached server; types same task twice | Sync badge: "Synced ✓", "3 pending", "Offline", "Sync failed ✗" |
| Settings changes require restart | User changes theme, nothing changes, thinks app is broken | Apply theme immediately via widget `.configure()` loop; restart only for things that truly need it |
| overrideredirect + no drag handle | If overlay positions itself off-screen, user has no recovery path | Always show "Reset position" in tray menu; persist position to `settings.json` |
| `--onefile` cold start with no feedback | 10 s black screen after double-click → user clicks again → two instances | Add a splash image or "Loading…" window before mainloop; use mutex to prevent double-launch |
| Windows 11 tray overflow | Icon buried in "show hidden icons" chevron; user thinks app crashed | On first run, show a toast notification explaining tray location; add a visible startup message |
| Offline task created, sync fails silently | User loses work between sessions with no warning | On failed sync, show count of unsynced tasks prominently; warn before exit |

---

## "Looks Done But Isn't" Checklist

- [ ] **Overlay animation**: `expand()`/`collapse()` are stubbed — verify `_move_window()` with actual `SetWindowPos` calls produces smooth animation at target 16ms steps before calling sidebar "done"
- [ ] **Theme switching**: Changing appearance mode updates `settings.json` but verify existing widgets actually change color — CustomTkinter requires explicit widget `.configure()` loop, `set_appearance_mode()` alone is not enough for already-created widgets
- [ ] **Auto-update on packaged exe**: Updater logic tested against `python updater.py` — must test rename+replace flow on the actual frozen `.exe` where `sys.executable` is the real binary
- [ ] **keyring on clean machine**: Auth flow tested in dev environment — verify on a Windows machine that has never had Python installed (keyring backend must be explicitly imported)
- [ ] **Global hotkey without elevation**: Hotkey tested from elevated dev terminal — verify it registers and fires when the `.exe` is launched from autostart (no elevation)
- [ ] **Sync queue thread safety**: `add_pending_change` + `_sync_loop` appear to work — verify by creating 50 tasks in rapid succession offline, going online, and confirming all 50 reach the server
- [ ] **CustomTkinter data files in packaged exe**: App loads with correct theme colors in packaged `.exe` — grey/default widgets indicate missing theme data
- [ ] **Cyrillic in user's Windows username**: Test that the `.exe` launches correctly when installed in `C:\Users\Никита\` — PyInstaller temp dir may fail with encoding error
- [ ] **SQLite WAL mode**: `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` are set — verify by simulating simultaneous Telegram bot write + desktop client write without `OperationalError`
- [ ] **pystray + Tkinter threading**: Tray icon menu items that show/hide the window do not crash after 20+ toggle cycles — race condition only manifests with rapid usage

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| CustomTkinter missing theme data in .exe | LOW | Switch build to `--onedir` or write proper `.spec`; rebuild and redistribute |
| pystray + Tkinter thread crash | MEDIUM | Add `run_detached()` + `root.after(0, fn)` pattern; requires thorough retesting of all tray callbacks |
| keyring failure in packaged exe | LOW | Add explicit backend import + fallback storage; rebuild |
| Auto-update file lock | LOW | Implement rename trick in `updater.py`; 30-minute fix |
| Sync queue race condition causing data loss | HIGH | Add `threading.Lock` to `LocalStorage`; must audit all call sites; user data may already be lost |
| SQLite locked errors on VPS | MEDIUM | Add WAL pragma + busy_timeout to `db.py`; hot-reloadable without data loss |
| Cyrillic path encoding crash on packaged exe | LOW | Set `PYINSTALLER_CONFIG_DIR` env var in launcher; or test + fix encoding in build script |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| CustomTkinter onefile packaging | Distribution phase (build setup) | Clean Windows VM: double-click `.exe`, verify themed widgets appear |
| pystray + Tkinter main thread conflict | Phase 1 (app shell) | 20 rapid tray icon clicks: no crash, no freeze |
| Global hotkey silently fails without admin | Hotkey implementation phase | Launch `.exe` from autostart (no elevation), press hotkey |
| overrideredirect overlay behind fullscreen | Phase 1 (overlay shell) | Document limitation; verify tray always accessible |
| Sync queue race condition | Core storage phase | 50 rapid offline task creates → sync → verify server count |
| Auto-update file locking | Auto-update phase | Run updater against running `.exe`, confirm rename+replace succeeds |
| keyring missing backend in frozen exe | Auth phase + distribution phase | Deploy to clean Windows VM; complete auth flow from `.exe` |
| SQLite locked / no WAL | Server setup phase | Concurrent bot + desktop client writes; no `OperationalError` |
| Cyrillic path in PyInstaller temp | Distribution phase | Build and run on machine with Cyrillic username/path |
| JWT refresh race + clock skew | Auth phase | Set system clock 2 min fast; verify token refresh still works |
| Theme change requires restart | UI settings phase | Change dark→light in settings panel; verify immediate visual change |

---

## Sources

- CustomTkinter Packaging wiki (official): https://github.com/TomSchimansky/CustomTkinter/wiki/Packaging — confirmed `--onefile` limitation
- PyInstaller AV false positive issue tracker: https://github.com/pyinstaller/pyinstaller/issues/6754 — no universal fix as of 2024
- PyInstaller runtime information (official docs): https://pyinstaller.org/en/stable/runtime-information.html — `sys._MEIPASS` and `sys.frozen`
- PyInstaller slow startup issue: https://github.com/orgs/pyinstaller/discussions/9080 — `--onedir` startup 5x faster than `--onefile`
- keyring + PyInstaller issue: https://github.com/jaraco/keyring/issues/468 — "binary fails to find the keyring backend"
- keyring + PyInstaller issue: https://github.com/jaraco/keyring/issues/439 — confirmed fix: explicit backend import
- Tkinter thread safety (CPython bug tracker): https://bugs.python.org/issue11077 — canonical statement of single-thread requirement
- pystray `run_detached` issues: https://github.com/moses-palmer/pystray/issues/138 — threading model confirmed
- keyboard library (boppreh): https://github.com/boppreh/keyboard — UAC/UIPI limitations documented in issues
- SQLite WAL + busy_timeout: https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/ — `busy_timeout` most impactful single fix
- SQLAlchemy + FastAPI + SQLite: https://fastapi.tiangolo.com/tutorial/sql-databases/ — `check_same_thread=False` requirement
- JWT race condition in refresh rotation: https://medium.com/@backendwithali/race-conditions-in-jwt-refresh-token-rotation — concurrent refresh race pattern
- Cyrillic path PyInstaller: https://github.com/pyinstaller/pyinstaller/issues/1954 — `PYINSTALLER_CONFIG_DIR` workaround
- PyInstaller file lock on running exe: https://github.com/pyinstaller/pyinstaller/issues/1145 — rename trick confirmed
- CustomTkinter runtime theme switching: https://github.com/TomSchimansky/CustomTkinter/issues/898 — requires widget recreation or configure loop

---
*Pitfalls research for: CustomTkinter Windows overlay + PyInstaller + FastAPI sync + Telegram bot*
*Researched: 2026-04-14*
