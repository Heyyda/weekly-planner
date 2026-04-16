---
phase: 03-overlay-system
plan: "06"
subsystem: ui
tags: [customtkinter, main-window, today-strip, theme-subscribe, persistence, accordion]

requires:
  - phase: 03-overlay-system/03-02
    provides: ThemeManager с subscribe/get API и палитрами (accent_brand, bg_primary, etc.)
  - phase: 03-overlay-system/03-03
    provides: SettingsStore + UISettings (window_size, window_position, on_top)

provides:
  - "MainWindow — CTkToplevel shell с аккордеоном 7 дней (Пн-Вс)"
  - "D-07 today-indicator: синяя полоска 3px (accent_brand) + bold заголовок"
  - "Theme-aware: _apply_theme перекрашивает today-strip при смене палитры"
  - "Persistence: window_size + window_position через SettingsStore при close/resize"
  - "OVR-06 API: set_always_on_top(bool) для toggle из OverlayManager"
  - "Overlay wire-up API: toggle() / show() / hide() / is_visible()"

affects:
  - "03-10 (wire-up overlay.on_click → main_window.toggle)"
  - "04-xx (Phase 4 заменит placeholder-секции на реальные task lists)"

tech-stack:
  added: []
  patterns:
    - "CTkToplevel withdrawn при создании, show()/hide()/toggle() для lifecycle"
    - "ThemeManager.subscribe в __init__ + немедленный вызов _apply_theme с текущей палитрой"
    - "_today_strip_map[i] для тестирования strip-присутствия по индексу дня"
    - "WM_DELETE_WINDOW → hide (не destroy), реальный exit через tray"
    - "pack_propagate(False) для фиксирования ширины 3px strip"

key-files:
  created:
    - client/ui/main_window.py
    - client/tests/ui/test_main_window.py
  modified: []

key-decisions:
  - "_today_strip_map хранит {i: strip_or_None} для тестируемости non-today секций"
  - "Persistence defer: в памяти обновляем на каждый Configure event, на диск только при close (_on_close → _save_window_state)"
  - "font override: tuple (family, size, 'bold') вместо CTkFont, совместимо с FONTS dict"

patterns-established:
  - "MainWindow.toggle() = public API для overlay.on_click wire-up"
  - "MainWindow.set_always_on_top() = public API для OVR-06 toggle propagation"

requirements-completed: []

duration: 3min
completed: 2026-04-16
---

# Phase 03 Plan 06: MainWindow Shell Summary

**CTkToplevel аккордеон 7 дней с D-07 today-indicator (синяя полоска 3px + bold заголовок), theme-aware через subscribe, persistence window_size/position через SettingsStore**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-16T07:07:20Z
- **Completed:** 2026-04-16T07:09:51Z
- **Tasks:** 1 (TDD)
- **Files modified:** 2

## Accomplishments

- MainWindow shell готов для wire-up в Plan 03-10: `overlay.on_click = main_window.toggle`
- D-07 today-indicator полностью реализован: (a) CTkFrame 3px accent_brand слева, (b) bold + "• сегодня" в заголовке
- ThemeManager.subscribe обеспечивает live-перекраску today-strip при смене темы
- SettingsStore persistence: window_size + window_position сохраняются при close/resize
- 17 тестов зелёных (test_today_section_has_blue_strip, test_today_strip_updates_on_theme_change включены)

## Task Commits

1. **Task 1: MainWindow shell + аккордеон + D-07 today-strip + persistence** - `4017c9b` (feat)

**Plan metadata:** (в процессе)

## Files Created/Modified

- `client/ui/main_window.py` — MainWindow класс: CTkToplevel, TODAY_STRIP_WIDTH=3, _today_strip, _apply_theme, _save_window_state, toggle/show/hide/is_visible/set_always_on_top/destroy
- `client/tests/ui/test_main_window.py` — 17 тестов: создание, видимость, today-strip D-07, theme-switch, persistence, set_always_on_top

## Decisions Made

- `_today_strip_map` (dict i→strip|None) добавлен сверх плана для тестируемости отсутствия strip в non-today секциях — это покрывает Test 16 плана
- Persistence defer: обновление в памяти при каждом Configure event, flush на диск только при WM_DELETE_WINDOW — предотвращает чрезмерные disk writes при resize

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Добавлен _today_strip_map для Test 16 (non-today sections)**
- **Found during:** Task 1 (написание теста test_non_today_sections_have_no_strip)
- **Issue:** Plan описывал Test 16 "секции НЕ сегодня не имеют today-strip", но без `_today_strip_map` проверить это невозможно через публичный API
- **Fix:** Добавлен `self._today_strip_map: dict[int, Optional[CTkFrame]] = {}` — заполняется в _build_ui по ходу создания секций
- **Files modified:** client/ui/main_window.py, client/tests/ui/test_main_window.py
- **Verification:** test_non_today_sections_have_no_strip проходит
- **Committed in:** 4017c9b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing testability interface)
**Impact on plan:** Минимальный — добавлен внутренний dict для тестирования, публичный API не изменён.

## Issues Encountered

Тесты test_tray.py (Plan 03-07, параллельное выполнение) показывают 10 failures — это pre-existing состояние от параллельного плана, не связанного с main_window.py. Верифицировано через git stash.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `MainWindow.toggle()` готов для `overlay.on_click = main_window.toggle` (Plan 03-10)
- `MainWindow.set_always_on_top()` готов для `overlay.on_top_changed = main_window.set_always_on_top` (Plan 03-10)
- Phase 4 заменит placeholder CTkFrame-секции на реальные task lists (strip+bold останутся)

---
*Phase: 03-overlay-system*
*Completed: 2026-04-16*
