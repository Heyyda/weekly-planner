---
phase: quick-260421-0td
plan: 01
subsystem: ui
tags: [forest, theme, ui, structural-polish]
dependency_graph:
  requires:
    - 260420-x69 (Phase A — forest palettes)
    - 260421-06u (Phase A2 — frameless window)
    - 260421-0jb (Phase A3 — Win10 hotfix)
  provides:
    - today-tint визуальное выделение через bg_tertiary
    - transparent regular day-sections (сливаются с bg_primary окна)
    - 1px bg_tertiary разделители между днями
    - palette-driven checkmark (bg_primary) и clay (accent_overdue) hover на delete
  affects:
    - client/ui/day_section.py
    - client/ui/task_widget.py
tech_stack:
  added: []
  patterns:
    - Palette-driven colors через ThemeManager.get(key) вместо хардкода
    - Принудительное style override (task_style=line) на callsite TaskWidget
key_files:
  created:
    - .planning/quick/260421-0td-phase-b-forest-structure-today-accent-ba/260421-0td-SUMMARY.md
    - .planning/quick/260421-0td-phase-b-forest-structure-today-accent-ba/deferred-items.md
  modified:
    - client/ui/day_section.py
    - client/ui/task_widget.py
    - client/tests/ui/test_day_section.py
    - client/tests/ui/test_task_widget.py
decisions:
  - Forest today-bg = bg_tertiary (E2E0D2 / 1B2620), НЕ bg_secondary (lifted surface). bg_secondary в Forest = "приподнятый элемент" (F5F0E3), не tint.
  - Checkmark color = bg_primary (cream или тёмный) вместо хардкода "white" или нового ключа accent_on_forest — семантически эквивалентно, не расширяет themes.py.
  - Последняя секция получает "лишний" bottom divider — приемлемая мелочь (~4% контраст на bg_primary), избегаем правок main_window.py.
  - TaskWidget._task_style поле зарезервировано (settings-переключатель в будущем), но в Forest игнорируется на callsite render_tasks.
metrics:
  duration_minutes: 3
  completed_date: "2026-04-20T21:43:43Z"
  tests_total: 52
  tests_new: 8
---

# Quick 260421-0td: Forest Phase B — structural polish Summary

**One-liner:** Structural Forest refactor: today-секция получает bg_tertiary tint (вместо lifted bg_secondary), regular days становятся transparent (сливаются с bg_primary), 1px bg_tertiary разделители между днями, чекмарк done-задачи цветом из палитры, hover на 🗑 меняется на clay (accent_overdue).

## Changes

### `client/ui/day_section.py`

| Зона | Было | Стало |
|------|------|-------|
| `CORNER_RADIUS` | `10` | `12` |
| `_day_bg_color()` today | `bg_secondary` | `bg_tertiary` (forest-tint) |
| `_day_bg_color()` regular | `bg_primary` | `"transparent"` (слияние с окном) |
| Divider | отсутствует | 1px `CTkFrame` на `side="bottom"`, цвет `bg_tertiary` |
| TaskWidget style | `self._task_style` из caller'а | жёстко `"line"` |
| today body padding | `padx=10, pady=(2, 6)` | `padx=14, pady=(2, 12)` (regular days остались 10×(2,6)) |
| `_apply_theme` | обновлял frame+strip+counter+plus | дополнительно: divider.fg_color, frame.fg_color из новой палитры (с учётом is_today) |

### `client/ui/task_widget.py`

| Зона | Было | Стало |
|------|------|-------|
| Checkmark fill | `fill="white"` (hardcoded) | `fill=self._theme.get("bg_primary")` — cream в forest_light, тёмный в forest_dark |
| `_icon_hover` hover color | `accent_brand` для всех иконок | `accent_overdue` (clay) если `btn is self._del_btn`, иначе `accent_brand` (forest) |

### Tests

- **test_day_section.py:** +5 новых тестов
  - `test_today_bg_is_bg_tertiary`
  - `test_regular_day_bg_is_transparent`
  - `test_divider_exists_and_uses_bg_tertiary`
  - `test_corner_radius_is_12`
  - `test_task_widgets_forced_to_line_style`

- **test_task_widget.py:** +3 новых теста
  - `test_done_checkmark_uses_bg_primary`
  - `test_delete_icon_hover_uses_accent_overdue`
  - `test_edit_icon_hover_still_uses_accent_brand`

## Verification

```bash
python -m pytest client/tests/ui/test_day_section.py client/tests/ui/test_task_widget.py -x -q
# 52 passed in 1.25s
```

Downstream check:

```bash
python -m pytest client/tests/ui/test_e2e_phase4.py -x -q -k "not requires_display"
# 16 passed in 3.54s
```

## Deviations from Plan

None — plan executed exactly как написан. Task 3 (checkpoint:human-verify) пропущен
per session-wide constraint (owner проверит визуально позже).

## Deferred Issues

Два pre-existing теста падают/errors independently of Phase B changes. Подтверждено
через `git stash` — те же ошибки на базовой ветке. Не в scope Phase B.
Детали: [deferred-items.md](./deferred-items.md).

1. `test_notifications.py::test_check_deadlines_approaching_zero_delta` (1 failure)
2. `test_e2e_phase3.py::*` (10 errors, tkinter setup issue)

## Known Stubs

None. Phase B чисто визуальный refactor — никаких placeholder-данных, всё подключено
к реальной ThemeManager и Task model.

## Next Step

- Task 3 (human-verify): owner запускает `python main.py`, визуально сверяет
  чек-лист в плане (разделы forest_light → forest_dark). При «approved» Phase B
  закрыта; при отказе — deviation и правки.

## Self-Check

- [x] `client/ui/day_section.py` — modified (CORNER_RADIUS=12, today bg=bg_tertiary, divider, forced line)
- [x] `client/ui/task_widget.py` — modified (checkmark=bg_primary, delete-hover=accent_overdue)
- [x] `client/tests/ui/test_day_section.py` — 5 new tests added
- [x] `client/tests/ui/test_task_widget.py` — 3 new tests added
- [x] All 52 scope tests green
- [x] Downstream e2e_phase4 (16 tests) green
- [x] No modifications to themes.py, main_window.py, edit_dialog.py, overlay.py, quick_capture.py
- [x] No new palette keys added

## Self-Check: PASSED
