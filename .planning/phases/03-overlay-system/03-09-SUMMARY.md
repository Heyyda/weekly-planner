---
phase: 03-overlay-system
plan: 09
subsystem: ui
tags: [winreg, autostart, registry, windows, tdd]

# Dependency graph
requires:
  - phase: 01-infrastructure
    provides: project skeleton, client/utils directory structure

provides:
  - "client/utils/autostart.py: is_autostart_enabled / enable_autostart / disable_autostart / get_autostart_command"
  - "ASCII value name 'LichnyEzhednevnik' в HKCU\\...\\Run (frozen-exe safe)"
  - "Поддержка dev-режима и frozen PyInstaller exe через getattr(sys, 'frozen', False)"

affects: [03-10-wiring, 03-07-tray, phase-6-build]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ASCII registry value name вместо кириллицы (frozen-exe safety, параллельный паттерн D-25)"
    - "getattr(sys, 'frozen', False) для auto-detect PyInstaller frozen exe"
    - "FileNotFoundError graceful handling в disable — no-op если запись отсутствует"
    - "TDD: тесты с mock_winreg fixture до реализации (RED → GREEN)"

key-files:
  created:
    - client/tests/ui/test_autostart.py
  modified:
    - client/utils/autostart.py

key-decisions:
  - "APP_REG_VALUE = 'LichnyEzhednevnik' (ASCII) — кириллица в winreg SetValueEx ломается в frozen PyInstaller exe (D-30)"
  - "get_autostart_command() возвращает команду в кавычках — корректная обработка пробелов и кириллицы в пути"
  - "Frozen detection через getattr(sys, 'frozen', False) — безопасно без атрибута в dev-режиме"

patterns-established:
  - "ASCII-only registry value names для Windows frozen exe совместимости"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-04-15
---

# Phase 03 Plan 09: Autostart Summary

**Windows autostart через winreg HKCU\\...\\Run с ASCII value name 'LichnyEzhednevnik' — TDD, 9 тестов, поддержка dev и PyInstaller frozen exe**

## Performance

- **Duration:** ~2 мин
- **Started:** 2026-04-15T08:13:35Z
- **Completed:** 2026-04-15T08:14:56Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Переписан skeleton autostart.py: кириллическое `APP_NAME` заменено на ASCII `APP_REG_VALUE = "LichnyEzhednevnik"` (D-30, frozen-exe safety)
- Добавлена функция `get_autostart_command()` с поддержкой dev и frozen PyInstaller режимов
- 9 unit-тестов через `mock_winreg` fixture — все зелёные, включая roundtrip и graceful disable

## Task Commits

1. **Task 1: Переписать client/utils/autostart.py + тесты** — `85edffb` (feat)

**Plan metadata:** добавлен в финальный docs-коммит.

## Files Created/Modified

- `client/utils/autostart.py` — Переписан skeleton: ASCII value name, 4 функции, frozen detection, logging
- `client/tests/ui/test_autostart.py` — 9 TDD unit-тестов через mock_winreg fixture

## Decisions Made

- ASCII value name `"LichnyEzhednevnik"` вместо кириллицы — winreg в frozen PyInstaller exe использует CP1252 кодировку что ломает кириллические имена (D-30 + PITFALL 4 pattern)
- `get_autostart_command()` возвращает команду в кавычках — путь к python.exe и main.py может содержать пробелы и кириллицу (например `S:\Проекты\`)
- `getattr(sys, "frozen", False)` вместо прямого `sys.frozen` — AttributeError safety в dev-режиме

## Deviations from Plan

None — план выполнен точно как описано. TDD RED (import error) → GREEN (9/9 pass).

## Issues Encountered

None — skeleton содержал правильную структуру функций, только потребовалось:
1. Переименовать `APP_NAME` (кириллица) → `APP_REG_VALUE` (ASCII)
2. Добавить `get_autostart_command()` как отдельную публичную функцию
3. Добавить logging и type hints

## Next Phase Readiness

- `autostart.py` готов для wire-up в Plan 03-10 через tray callback hooks
- Plan 03-07 TrayManager уже импортирует `autostart.is_autostart_enabled` и может вызывать enable/disable
- Phase 6 (PyInstaller --onefile) может использовать те же функции без изменений — `sys.frozen = True` автоматически переключит на `sys.executable`

---
*Phase: 03-overlay-system*
*Completed: 2026-04-15*
