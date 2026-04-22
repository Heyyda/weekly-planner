---
phase: quick-260422-sue
plan: 01
subsystem: client-ui
tags: [windows, win32, taskbar, ux, bugfix]
requires: []
provides:
  - "_apply_borderless применяет WS_EX_TOOLWINDOW вместо WS_EX_APPWINDOW"
affects:
  - "client/ui/main_window.py::_apply_borderless"
tech-stack:
  added: []
  patterns:
    - "WS_EX_TOOLWINDOW — стандартный Win32-способ скрыть floating tool-window из taskbar/Alt+Tab"
key-files:
  created: []
  modified:
    - client/ui/main_window.py
decisions:
  - "EX_STYLE-маска инвертирована: снимаем WS_EX_APPWINDOW, ставим WS_EX_TOOLWINDOW — окно остаётся topmost и draggable, но невидимо в системных списках окон"
metrics:
  duration: "~2 min"
  tasks_completed: 1
  tasks_total: 2
  files_changed: 1
  lines_changed: "+3/-3"
  completed: "2026-04-22"
commits:
  - hash: "84b1f90"
    message: "fix(quick-260422-sue): скрыть главное окно из taskbar и Alt+Tab через WS_EX_TOOLWINDOW"
---

# Quick 260422-sue: Taskbar WS_EX_TOOLWINDOW Fix — Summary

**One-liner:** Инвертирована EX_STYLE-маска в `_apply_borderless`: главное окно теперь получает `WS_EX_TOOLWINDOW` вместо `WS_EX_APPWINDOW` — пропадает из Windows taskbar и Alt+Tab, оставаясь полноценным floating-окном над рабочим столом.

## Что изменено

Ровно три правки в `client/ui/main_window.py`, все в методе `_apply_borderless`:

1. **Строка 348** (bitmask):
   ```diff
   - new = (current & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
   + new = (current & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
   ```

2. **Строка 328** (docstring):
   ```diff
   - """UX v2: убрать native title bar. Сохранить taskbar через WS_EX_APPWINDOW.
   + """UX v2: убрать native title bar и скрыть из taskbar/Alt+Tab через WS_EX_TOOLWINDOW.
   ```

3. **Строка 339** (комментарий):
   ```diff
   - # WS_EX_APPWINDOW — сохранить окно в taskbar и Alt+Tab
   + # WS_EX_TOOLWINDOW — скрыть окно из taskbar и Alt+Tab (overlay+tray остаются видны)
   ```

Константы `WS_EX_APPWINDOW` и `WS_EX_TOOLWINDOW` оставлены обе (нужны для корректной bitmask-логики). Withdraw/deiconify-цикл не тронут (нужен Windows для применения нового EX_STYLE). Overlay и tray не затрагивались — они уже невидимы в taskbar через свои механизмы (`overrideredirect` для overlay, pystray для tray).

## Verification

### Автоматическая

```
python -m pytest client/tests/ui/test_main_window.py -x -q
............................                                             [100%]
28 passed in 10.19s
```

Grep-sanity:
- `~WS_EX_APPWINDOW.*|.*WS_EX_TOOLWINDOW` найден на строке 348 — корректно
- `WS_EX_APPWINDOW — сохранить` не найден — старый комментарий удалён

### UAT (ручная — ожидает владельца)

Task 2 (checkpoint:human-verify) пропущен по указанию пользователя — владелец проверит вручную после запуска приложения:
- Окно отсутствует в taskbar
- Alt+Tab не показывает окно
- Overlay и tray работают без регрессий
- Drag, resize, close через кастомный title bar — функциональны

## Deviations from Plan

None — план выполнен ровно как написано, ни одна из Rules 1-4 не сработала.

## Commits

- `84b1f90` — fix(quick-260422-sue): скрыть главное окно из taskbar и Alt+Tab через WS_EX_TOOLWINDOW

## Self-Check: PASSED

- [x] FOUND: client/ui/main_window.py (изменения применены, pytest зелёный)
- [x] FOUND: commit 84b1f90 (`git log --oneline | grep 84b1f90`)
- [x] FOUND: .planning/quick/260422-sue-taskbar-ws-ex-toolwindow-ws-ex-appwindow/260422-sue-SUMMARY.md (этот файл)
