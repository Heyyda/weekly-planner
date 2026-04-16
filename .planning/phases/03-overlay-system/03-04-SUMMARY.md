---
phase: 03-overlay-system
plan: "04"
subsystem: ui
tags: [overlay, customtkinter, ctypes, win32, multi-monitor, pillow, drag, settings]

requires:
  - phase: 03-overlay-system/03-02
    provides: ThemeManager с subscribe/notify pattern
  - phase: 03-overlay-system/03-03
    provides: UISettings + SettingsStore (overlay_position, on_top persistence)
  - phase: 03-overlay-system/03-03
    provides: icon_compose.render_overlay_image (Pillow image API)

provides:
  - OverlayManager — CTkToplevel 56x56 на рабочем столе
  - Drag + position persistence через SettingsStore
  - Multi-monitor bounds validation (pure ctypes EnumDisplayMonitors, D-19)
  - on_click, on_right_click, on_top_changed callback hooks (wire в Plan 03-10)
  - refresh_image() — hook для PulseAnimator (Plan 03-05, 60fps)
  - _validate_position PITFALL 6 + _get_virtual_desktop_bounds D-19

affects:
  - 03-05-PulseAnimator (вызывает overlay.refresh_image(state="overdue", pulse_t=t))
  - 03-10-AppWiring (wire overlay.on_click → main_window.toggle)
  - 03-07-TrayManager (set_always_on_top hook)

tech-stack:
  added: []
  patterns:
    - "PITFALL 1: overrideredirect через after(INIT_DELAY_MS=100) — Win11 DWM timing"
    - "PITFALL 4: ImageTk.PhotoImage ref в instance var self._tk_image (5 вхождений)"
    - "PITFALL 6: _validate_position против virtual desktop bounds, fallback (100,100)"
    - "D-19: pure ctypes WINFUNCTYPE(_MONITORENUMPROC) + windll.user32.EnumDisplayMonitors — без pywin32"
    - "OVR-04: drag vs click — _drag_was_motion flag, on_click при False"
    - "OVR-06: on_top_changed callback отделён от внутреннего state"

key-files:
  created:
    - client/ui/overlay.py
    - client/tests/ui/test_overlay.py
  modified: []

key-decisions:
  - "D-19 enforced: ctypes.WINFUNCTYPE + _MONITORENUMPROC вместо pywin32 (pywin32 отсутствует в requirements.txt)"
  - "PITFALL 1 marker: INIT_DELAY_MS = 100 как named constant для grep-verifiability"
  - "PITFALL 4 marker: self._tk_image — 5 вхождений в overlay.py (init None + assign + itemconfig)"
  - "OVR-04: drag/click различие через _drag_was_motion bool flag, не через event timestamp"
  - "Drag bindings на Canvas (не overlay) — необходимо для кликабельности поверх CTkToplevel"
  - "Fallback chain для _get_virtual_desktop_bounds: ctypes → Tk screenwidth → (1920,1080)"

patterns-established:
  - "Pattern PITFALL1: CTkToplevel.after(100, init_style) — всегда для overrideredirect"
  - "Pattern PITFALL4: self._tk_image хранится как instance var при любом Canvas ItemImage"
  - "Pattern PITFALL6: _validate_position при load из settings"
  - "Pattern D-19: ctypes.WINFUNCTYPE для Win32 callback без pywin32"

requirements-completed:
  - OVR-01
  - OVR-02
  - OVR-03
  - OVR-04
  - OVR-06

duration: 3min
completed: "2026-04-16"
---

# Phase 03 Plan 04: OverlayManager Summary

**OverlayManager — 56x56 CTkToplevel overlay с drag, click, multi-monitor ctypes D-19, три критических PITFALL'а встроены и grep-верифицированы**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-16T06:59:53Z
- **Completed:** 2026-04-16T07:02:39Z
- **Tasks:** 1 (TDD: RED commit + GREEN commit)
- **Files modified:** 2

## Accomplishments

- OverlayManager создан: 343 строки, все OVR-01/02/03/04/06 покрыты
- TDD: 16 тестов — RED (ModuleNotFoundError) → GREEN (16/16 pass за 1.47s)
- D-19 enforced: `ctypes.WINFUNCTYPE` + `_MONITORENUMPROC` + `windll.user32.EnumDisplayMonitors` — ни строки win32api
- Все три critical PITFALL'а встроены: INIT_DELAY_MS=100, self._tk_image ref, _validate_position fallback
- on_click / on_top_changed callback hooks готовы для wire в Plan 03-10

## Task Commits

1. **Task 1 RED: failing tests для OverlayManager** — `676491b` (test)
2. **Task 1 GREEN: OverlayManager реализация** — `ea7389b` (feat)

## Files Created/Modified

- `client/ui/overlay.py` — OverlayManager, 343 строки, OVR-01..04,06 + D-19 ctypes
- `client/tests/ui/test_overlay.py` — 16 unit-тестов, все green

## Decisions Made

- D-19 enforced: pure ctypes для multi-monitor (без pywin32 — нет в requirements.txt)
- INIT_DELAY_MS = 100 как named constant — grep-verifiable marker для PITFALL 1
- Drag bindings на Canvas (не Toplevel) для совместимости с CTkToplevel event routing
- OVR-05 (pulse animation) намеренно оставлен для Plan 03-05 (PulseAnimator)

## Deviations from Plan

None — план выполнен точно как написан. Все acceptance criteria прошли с первой попытки.

## Known Stubs

None — OverlayManager полностью реализован. Pulse animation (OVR-05) отложена на Plan 03-05 согласно плану.

## Issues Encountered

None — все тесты зелёные с первой попытки.

## Next Phase Readiness

- Plan 03-05 (PulseAnimator): вызывать `overlay.refresh_image(state="overdue", pulse_t=t)` в 60fps цикле
- Plan 03-10 (AppWiring): wire `overlay.on_click = main_window.toggle` и `overlay.on_top_changed`
- Plan 03-07 (TrayManager): использовать `overlay.set_always_on_top()` из tray callback

## Self-Check: PASSED

- `client/ui/overlay.py` — FOUND
- `client/tests/ui/test_overlay.py` — FOUND
- commit `676491b` (RED) — FOUND
- commit `ea7389b` (GREEN) — FOUND
- 16/16 tests green — VERIFIED
- grep `INIT_DELAY_MS = 100` — FOUND
- grep `windll.user32.EnumDisplayMonitors` — FOUND
- grep `win32api` — ABSENT (D-19 compliant)
- grep `_tk_image` — 5 occurrences (PITFALL 4 compliant)
- grep `_validate_position` — FOUND (PITFALL 6 compliant)
- grep `WINFUNCTYPE` + `MONITORENUMPROC` — FOUND (D-19 compliant)
- line count 343 >= 180 (min_lines) — OK

---
*Phase: 03-overlay-system*
*Completed: 2026-04-16*
