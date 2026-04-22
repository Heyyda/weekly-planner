---
phase: quick-260422-tx1
plan: 01
subsystem: client/ui
tags: [hotfix, ctypes, win32, x64, windows-error-87]
requires: []
provides:
  - "Win32 user32 API signatures (argtypes/restype) для x64-safe вызовов"
  - "Типизированные wrappers _user32 / _get_window_long / _set_window_long"
affects:
  - "client/ui/main_window.py — восстановлен запуск главного окна"
  - "quick 260422-sue — WS_EX_TOOLWINDOW snap-in теперь реально применяется"
  - "quick 260422-tah — edge-resize через WM_NCLBUTTONDOWN теперь работает без усечения"
tech_stack:
  added: []
  patterns:
    - "ctypes.c_ssize_t (= LONG_PTR) для pointer-sized Win32 параметров"
    - "GetWindowLongPtrW/SetWindowLongPtrW с hasattr-fallback на *LongW для 32-bit Python"
key_files:
  created: []
  modified:
    - "client/ui/main_window.py"
decisions:
  - "Pointer-sized параметры через ctypes.c_ssize_t (signed LONG_PTR), т.к. это точный Python-эквивалент LONG_PTR/WPARAM/LPARAM/LRESULT на обоих bitness"
  - "GetWindowLongPtrW как предпочтительный API (Windows XP SP1+), LongW только как fallback для гипотетического 32-bit Python — в проекте это не основной таргет, но защита от регрессий без затрат"
  - "HWND через wintypes.HWND (= c_void_p) — корректный pointer-sized тип в ctypes для обеих архитектур"
metrics:
  duration_minutes: 6
  completed_date: "2026-04-22"
  files_modified: 1
  tests_passing: 28
---

# Quick 260422-tx1: HOTFIX — ctypes argtypes для x64 (ERROR_INVALID_PARAMETER) Summary

Типизированы Win32 user32 API (argtypes/restype через `ctypes.c_ssize_t`) — устранён ERROR_INVALID_PARAMETER (Windows error 87) при открытии главного окна на x64 Python.

## Что сделано

Все три шага Task 1 выполнены в `client/ui/main_window.py`:

1. **Module-level типизация user32** (после `logger = logging.getLogger(__name__)`):
   - Импорт `ctypes.wintypes as wt`.
   - `_user32 = ctypes.windll.user32` — один shared handle.
   - `GetParent`: `argtypes=[HWND]`, `restype=HWND`.
   - `GetWindowLongPtrW` / `SetWindowLongPtrW` с `c_ssize_t` для value-параметра; fallback на `GetWindowLongW` / `SetWindowLongW` с `c_long` если Ptr-вариантов нет.
   - Экспортируются `_get_window_long` / `_set_window_long` (всегда указывают на выбранный ветвью API).
   - `ReleaseCapture`: `argtypes=[]`, `restype=BOOL`.
   - `SendMessageW`: `argtypes=[HWND, UINT, c_ssize_t, c_ssize_t]`, `restype=c_ssize_t`.

2. **`_apply_borderless`** (метод в MainWindow):
   - `ctypes.windll.user32.GetParent(...)` → `_user32.GetParent(...)`.
   - `ctypes.windll.user32.GetWindowLongW(...)` → `_get_window_long(...)`.
   - `ctypes.windll.user32.SetWindowLongW(...)` → `_set_window_long(...)`.
   - Вся окружающая логика (overrideredirect, withdraw/deiconify цикл, try/except Exception) оставлена без изменений.

3. **`_on_edge_press`** (метод в MainWindow):
   - Убрано локальное `user32 = ctypes.windll.user32`.
   - `user32.GetParent`, `user32.ReleaseCapture`, `user32.SendMessageW` → `_user32.*`.
   - Fallback `parent_hwnd if parent_hwnd else widget_hwnd` сохранён.
   - `HT_MAP` + `_WM_NCLBUTTONDOWN` (0x00A1) не тронуты.

## Корневая причина

На x64 Python `ctypes` без явных `argtypes`/`restype` маршалит параметры как C `int` (32-bit), но Windows ожидает `HWND` / `WPARAM` / `LPARAM` / `LONG_PTR` pointer-size (64-bit). В результате `hwnd` усекался до нижних 32 бит, и Windows возвращал error 87 (ERROR_INVALID_PARAMETER). Диалог "параметр задан неправильно" был системным сообщением об ошибке, перехваченным default handler'ом Tk/Python после неуспешного `SetWindowLongW`.

После добавления `argtypes`/`restype` с `ctypes.c_ssize_t` (= signed `LONG_PTR`) значения передаются без усечения — Windows успешно принимает `hwnd` и EX-style.

## Verification

### Automated
- `python -c "from client.ui.main_window import MainWindow"` — **PASS** (import OK, ERROR_INVALID_PARAMETER не воспроизводится на импорте модуля).
- `python -c "from client.ui import main_window"` — **PASS**.
- `python -m pytest client/tests/ui/test_main_window.py -x -q` — **28/28 PASS**, регрессий нет.

### Manual (UAT — у пользователя)
UAT checkpoint (Task 2) пропущен по constraint — пользователь проверяет самостоятельно по сценарию в PLAN.md:
1. Запуск приложения → overlay на рабочем столе.
2. Клик по overlay → главное окно открывается без диалога "параметр задан неправильно".
3. Окно НЕ в taskbar / НЕ в Alt+Tab (WS_EX_TOOLWINDOW).
4. Resize по 8 edge-zones работает.

## Deviations from Plan

None — плaн выполнен дословно. Все три шага применены как описано, типы (`c_ssize_t`, `wt.HWND`, `wt.BOOL`, `wt.UINT`) совпадают с рекомендованными, fallback-ветка для 32-bit Python присутствует, комментарии и docstrings оставлены без изменений.

## Commits

- `58ac8ee` — fix(quick-260422-tx1): типизировать ctypes.user32 API для x64 (ERROR_INVALID_PARAMETER)

## Files Modified

- `client/ui/main_window.py` (+44/-7)

## Known Stubs

None.

## Self-Check: PASSED

- [x] `client/ui/main_window.py` содержит module-level блок `_user32` с `argtypes`/`restype`.
- [x] `_apply_borderless` использует `_user32.GetParent` / `_get_window_long` / `_set_window_long` (grep подтверждает отсутствие `ctypes.windll.user32.*` / `user32.*` прямых вызовов вне docstring'а).
- [x] `_on_edge_press` использует `_user32.GetParent` / `_user32.ReleaseCapture` / `_user32.SendMessageW`.
- [x] Commit `58ac8ee` существует (`git log --oneline | grep 58ac8ee` → найден).
- [x] pytest client/tests/ui/test_main_window.py — 28 passed.
- [x] Smoke import `from client.ui.main_window import MainWindow` — OK.
