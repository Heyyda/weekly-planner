---
phase: 03-overlay-system
plan: "01"
subsystem: testing
tags: [pytest, customtkinter, pystray, winotify, winreg, ctypes, headless-tk, fixtures]

requires:
  - phase: 02-client-core
    provides: conftest.py с fixtures tmp_appdata, mock_api, api_base (расширяем, не заменяем)

provides:
  - headless_tk fixture — CTk root в withdraw()-режиме, teardown через destroy()
  - mock_pystray_icon fixture — FakeIcon класс с трекингом run_detached_called/stopped
  - mock_winotify fixture — FakeNotification + список calls для верификации toast.show()
  - mock_winreg fixture — in-memory dict {(hkey, path, name): value} + fake open/set/query/delete
  - mock_ctypes_dpi fixture — no-op SetProcessDpiAwareness и SetProcessDPIAware
  - client/tests/ui/__init__.py — маркер пакета для UI-тестов Phase 3+

affects: [03-02, 03-03, 03-04, 03-05, 03-06, 03-07, 03-08, 03-09, 03-10, 03-11]

tech-stack:
  added: []
  patterns:
    - "headless_tk: CTk().withdraw() + update_idletasks() + destroy() в teardown"
    - "mock_pystray_icon: класс-уровень instances=[] сбрасывается в каждой fixture через FakeIcon.instances = []"
    - "mock_winotify: yield список calls — функциональный стиль без глобального состояния"
    - "mock_winreg: _FakeKeyCtx context-manager для совместимости с with winreg.OpenKey(...) as key"
    - "mock_ctypes_dpi: try/except (AttributeError, OSError) для кроссплатформенной безопасности"

key-files:
  created:
    - client/tests/ui/__init__.py
  modified:
    - client/tests/conftest.py

key-decisions:
  - "scope=function (дефолт) для headless_tk — каждый тест получает свежий CTk root во избежание state leak"
  - "mock_winreg импортирует winreg только внутри fixture — не на уровне модуля (Windows-only stdlib)"
  - "mock_ctypes_dpi с raising=False в monkeypatch.setattr — ctypes.windll атрибуты могут отсутствовать"

patterns-established:
  - "UI test isolation: headless_tk + mock_pystray_icon + mock_ctypes_dpi комбинируются для полной изоляции от реальных Windows API"
  - "Fixture as tracker: mock_winotify yield-ит список calls, не возвращает класс — удобный паттерн для assertions"

requirements-completed: []

duration: 2min
completed: "2026-04-16"
---

# Phase 03 Plan 01: UI Test Infrastructure Extensions Summary

**5 headless-pytest fixtures для Phase 3 UI-тестов: CTk без реального окна, mock pystray/winotify/winreg/ctypes DPI**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-16T06:49:50Z
- **Completed:** 2026-04-16T06:52:25Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Добавлены 5 новых pytest fixtures в `client/tests/conftest.py` (Phase 2 fixtures не тронуты)
- Создан `client/tests/ui/__init__.py` — пустой маркер пакета для UI-тестов Phase 3
- Phase 2 регрессия = 0: все 106 тестов проходят после изменений
- `client/tests/ui/` подпакет корректно собирается pytest (0 import errors при collect)

## Task Commits

1. **Task 1: Расширить conftest.py + создать ui/ подпакет** — `661243a` (feat)

**Plan metadata:** (будет добавлен в финальном docs-коммите)

## Files Created/Modified

- `client/tests/conftest.py` — добавлены 5 fixtures: headless_tk, mock_pystray_icon, mock_winotify, mock_winreg, mock_ctypes_dpi (Phase 2 fixtures tmp_appdata/mock_api/api_base сохранены)
- `client/tests/ui/__init__.py` — создан с модульным docstring; маркер пакета для UI-тестов Phase 3

## Decisions Made

- `scope=function` (дефолт) для `headless_tk` — каждый тест получает свежий CTk root чтобы избежать state leak между тестами
- `mock_winreg` импортирует `winreg` внутри fixture body, не на уровне модуля — безопасно на не-Windows где winreg не существует (хотя сама Windows-only, но паттерн явный)
- `mock_ctypes_dpi` использует `raising=False` в `monkeypatch.setattr` — `ctypes.windll.shcore` атрибут может отсутствовать при отсутствии shcore.dll

## Deviations from Plan

None — план выполнен точно как написан.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Wave 0 готова: все последующие Plans 03-02..03-11 могут использовать `headless_tk`, `mock_pystray_icon`, `mock_winotify`, `mock_winreg`, `mock_ctypes_dpi` из родительского `conftest.py` без дополнительной настройки
- Pytest fixture resolution: fixtures из `client/tests/conftest.py` автоматически доступны в `client/tests/ui/*.py` тестах
- `client/tests/ui/__init__.py` создан — pytest корректно соберёт `ui/test_*.py` файлы когда они появятся в Plans 03-04..03-11

---

## Self-Check

Checking created files and commits...

- `client/tests/ui/__init__.py`: FOUND
- `client/tests/conftest.py` (modified): FOUND
- Commit `661243a`: FOUND

## Self-Check: PASSED

---

*Phase: 03-overlay-system*
*Completed: 2026-04-16*
