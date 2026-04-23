---
phase: quick-260423-o8z
plan: 01
subsystem: client-ui
tags: [ui, overlay, dnd, main-window, taskbar, ux]
dependency_graph:
  requires: [260422-vvn, 260422-tx2]
  provides: [edge-drag-navigation, clean-overlay-corners, taskbar-hidden-main-window]
  affects: [client/ui/icon_compose.py, client/ui/overlay.py, client/ui/drag_controller.py, client/ui/main_window.py]
tech_stack:
  added: []
  patterns: [edge-drag-detection, wm_attributes-toolwindow, pillow-rounded-mask]
key_files:
  created: []
  modified:
    - client/ui/icon_compose.py
    - client/ui/overlay.py
    - client/ui/drag_controller.py
    - client/ui/main_window.py
    - client/tests/ui/test_icon_compose.py
    - client/tests/ui/test_drag_controller.py
    - client/tests/ui/test_main_window.py
decisions:
  - "CORNER_RADIUS_FRAC увеличен 12/56 → 16/56 для согласованности с macOS-подобным языком"
  - "Supersampling 3x → 4x в render_overlay_image (плавнее LANCZOS downsample)"
  - "DwmSetWindowAttribute(DWMWCP_ROUND) удалён полностью — rounded corners через Pillow mask"
  - "Edge-drag detection относительно self._root bounds с EDGE_JUMP_THRESHOLD_PX=60"
  - "Ghost label swap на '← Пред. неделя' / 'След. неделя →' с sage fg_color"
  - "wm_attributes('-toolwindow', True) вместо Win32 WS_EX_TOOLWINDOW (без DWM clash)"
  - "DropZone.is_prev_week / is_next_week поля сохранены для backward-compat (default=False)"
metrics:
  duration_minutes: 22
  tasks_completed: 3
  files_modified: 7
  commits: 3
  tests_added: 14
  tests_passing: 104
  completed_at: "2026-04-22T22:30:00Z"
---

# Phase quick-260423-o8z Plan 01: Overlay Render Fix + Edge-drag Cross-week + Hide Taskbar Summary

Три UX-правки v0.6.1: чистые углы overlay (4x SS + DWM off), edge-drag вместо pill-кнопок для cross-week DnD, скрытие главного окна из taskbar через `wm_attributes('-toolwindow')`.

## Commits

| # | Hash      | Message                                                                                                    |
|---|-----------|------------------------------------------------------------------------------------------------------------|
| 1 | `09d67be` | fix(ui): overlay render — 4x supersampling + CORNER_RADIUS_FRAC=16/56 + DWM off (260423-o8z task 1)        |
| 2 | `7d46e94` | feat(ui): edge-drag cross-week navigation — pill-кнопки заменены на sage edge indicators (260423-o8z task 2) |
| 3 | `14b5f49` | ui(window): скрыть главное окно из taskbar/Alt+Tab через wm_attributes('-toolwindow') (260423-o8z task 3) |

## Task 1: Overlay Render Quality

**Цель:** Убрать чёрные полоски по углам sage-иконки overlay, улучшить края.

**Изменения:**

1. **`client/ui/icon_compose.py`**:
   - `CORNER_RADIUS_FRAC = 12 / 56` → `16 / 56` (выразительнее скругление, ~21px на size=73).
   - `render_overlay_image`: supersampling `size * 3` → `size * 4` для плавнее LANCZOS downsample.
   - Комментарии обновлены с v0.6.1 референсом.

2. **`client/ui/overlay.py`**:
   - Удалены константы `DWMWA_WINDOW_CORNER_PREFERENCE = 33` и `DWMWCP_ROUND = 2`.
   - Удалён блок `ctypes.windll.dwmapi.DwmSetWindowAttribute(...)` в `_init_overlay_style`.
   - Оставлен документирующий комментарий о причине удаления (DWM-native rounded corners клашились с `-transparentcolor` canvas bg и `Pillow` rounded mask).

3. **`client/tests/ui/test_icon_compose.py`**:
   - Добавлены 3 новых теста: `test_render_4x_ss_smooth_corners`, `test_render_corner_radius_frac_constant`, `test_render_uses_4x_supersampling`.
   - Старые тесты прозрачности углов / центра / badge остались зелёными.

**Результат:** `python -m pytest client/tests/ui/test_icon_compose.py -x -q` → 15 passed.

## Task 2: Edge-drag Cross-week Navigation (TDD)

**Цель:** Заменить pill-кнопки "◀ Предыдущая неделя" / "Следующая неделя ▶" на sage vertical edge-indicator + edge-drag detection.

**Изменения `DragController`:**

- Добавлена константа `EDGE_JUMP_THRESHOLD_PX = 60`.
- `__init__` принимает новый параметр `on_edge_zone_changed: Optional[Callable[[Optional[int]], None]]`.
- Новое state `self._edge_jump_direction: Optional[int]`.
- `_on_motion`: после ghost.move() вычисляет distance_left/distance_right относительно `self._root` bounds; если < 60 → вызывает `on_edge_zone_changed(-1/+1)`; если ушли от края → `on_edge_zone_changed(None)`. Когда edge активен, `_update_zone_highlights` пропускается (визуальный приоритет).
- Новый метод `_update_ghost_for_edge(direction)`: меняет ghost label на "← Пред. неделя" / "След. неделя →" со sage fg_color, восстанавливает оригинальный текст при direction=None.
- `_on_release`: edge-jump имеет приоритет над drop zones — если `_edge_jump_direction is not None`, вызывает `on_week_jump(direction, task_id)`, скрывает indicators через callback(None), пропускает обычный drop.
- Удалены методы `_show_week_jump_zones()` и `_hide_week_jump_zones()`.
- `_start_drag` больше не вызывает `_show_week_jump_zones`.
- `_cancel_drag` вызывает `on_edge_zone_changed(None)` если indicator был показан.
- `_reset_state` сбрасывает `self._edge_jump_direction = None`.
- `_update_zone_highlights` и `_clear_all_highlights` упрощены — pill guards (is_prev_week/is_next_week) удалены.
- `DropZone.is_prev_week / is_next_week` оставлены как default=False для backward-compat тестов.

**Изменения `MainWindow`:**

- `self._prev_week_zone` / `self._next_week_zone` → `self._left_edge_indicator` / `self._right_edge_indicator` (4px sage CTkFrame).
- `_build_ui`: замена pill-создания на edge-indicators (`corner_radius=0, width=4`).
- `DragController` создаётся с `on_edge_zone_changed=self._on_edge_zone_changed`.
- Новый метод `_on_edge_zone_changed(direction)`: `direction=-1` → `left.place(relx=0, relheight=1.0)` + `right.place_forget`; `direction=+1` → правый с `anchor="ne"`; `direction=None` → оба `place_forget`.
- Удалены блоки регистрации cross-week pill-DropZone в `_rebuild_day_sections` и `_update_week`.
- `_apply_theme` обновляет `sage` цвет обоих edge-indicators.

**Pitfall solved:** CustomTkinter не принимает `width`/`height` в `place()` — они должны быть в конструкторе. Поскольку `width=4` уже задан при создании `CTkFrame`, в `place()` передаются только `relx/rely/relheight` (+ `anchor="ne"` для правого).

**Tests:**

- `test_drag_controller.py`: 9 новых тестов (edge-threshold, motion callback left/right/away, release left/right, active-skip-day-highlights, ghost-text-swap, state reset, no-pill-pack). Старые pill-specific тесты удалены/заменены.
- `test_main_window.py`: 5 новых тестов (edge_indicators_exist, on_edge_zone_changed показ левого/правого/none, no_pill_zones_attrs, adjusted test_drag_controller_has_seven_drop_zones c 7 зонами вместо 9).

**Результат:** 35 passed (test_drag_controller) + 38 passed (test_main_window).

## Task 3: Hide Main Window from Taskbar

**Цель:** Скрыть главное окно из Windows taskbar и Alt+Tab без DWM clash.

**Изменения `MainWindow.__init__`**:

```python
try:
    self._window.wm_attributes("-toolwindow", True)
    logger.debug("toolwindow attr applied — окно скрыто из taskbar")
except tk.TclError as exc:
    logger.debug("toolwindow attr failed: %s", exc)
```

Блок добавлен после `self._window.resizable(True, True)`.

**Отличие от предыдущей попытки `quick-260422-tx2`:**
- Нет `overrideredirect(True)` — native рамка сохраняется.
- Нет Win32 `SetWindowLongPtrW(WS_EX_TOOLWINDOW)` — через Tk native attr, который не клашится с DWM.
- Native title bar становится тонким (toolwindow style), но кнопки close/min/max частично сохраняются.

**Fade compatibility:** Manually verified through `test_show_fades_in_to_alpha_1` и `test_hide_fades_out_and_withdraws` — `attributes('-alpha', ...)` работает одинаково на toolwindow окне. **Rollback НЕ потребовался.**

**Test:** `test_toolwindow_attr_applied` с graceful `pytest.skip` на не-Windows платформах.

## Grep Contract Verification

| Контракт                                                    | Результат |
|-------------------------------------------------------------|-----------|
| `grep DWMWA_WINDOW_CORNER_PREFERENCE client/ui/overlay.py`  | 0 runtime matches (только комментарий) |
| `grep DwmSetWindowAttribute client/ui/overlay.py`           | 0 runtime matches (только комментарий) |
| `grep "CORNER_RADIUS_FRAC = 16 / 56" icon_compose.py`        | 1 match |
| `grep "size * 4" icon_compose.py`                           | 1 match |
| `grep EDGE_JUMP_THRESHOLD_PX drag_controller.py`            | 3 matches (const + 2 usage) |
| `grep on_edge_zone_changed drag_controller.py`              | 7+ matches |
| `grep toolwindow main_window.py`                            | 5 matches (вызов + 4 комментария/лога) |
| `grep "_prev_week_zone = ctk.CTkFrame" main_window.py`      | 0 matches |
| `grep "_next_week_zone = ctk.CTkFrame" main_window.py`      | 0 matches |
| `grep "_show_week_jump_zones\|_hide_week_jump_zones" client/ui/` | 0 matches |

## Deviations from Plan

### None — plan executed as written

Все 3 задачи выполнены без архитектурных изменений. Один минорный pitfall решён inline:

**[Rule 1 - Bug] CustomTkinter rejects width/height in place()**
- **Found during:** Task 2, первый запуск `test_on_edge_zone_changed_shows_left`
- **Issue:** `CTkFrame.place(width=4, ...)` → `ValueError: 'width' and 'height' arguments must be passed to the constructor`
- **Fix:** Убрал `width=4` из `place()` вызовов в `_on_edge_zone_changed` — `width=4` уже в `CTkFrame` конструкторе.
- **Files modified:** `client/ui/main_window.py`
- **Commit:** включено в `7d46e94`

## Authentication Gates

None — задача чисто UI/визуальная.

## Test Suite Status

**Target tests (все зелёные):**

| File | Tests | Passed |
|------|-------|--------|
| `test_icon_compose.py` | 15 | 15 |
| `test_overlay.py` | 16 | 16 |
| `test_drag_controller.py` | 35 | 35 |
| `test_main_window.py` | 38 | 38 |
| **Total** | **104** | **104** |

**Pre-existing errors** (unrelated, ignored per constraints):
- `test_e2e_phase3.py` — 10 Tcl errors (pre-existing, constraint noted).
- `test_app_integration.py::test_setup_authenticated_wires_all_components` — fails when full suite runs (test pollution from e2e_phase3 Tcl errors), **passes in isolation**.

## Known Stubs

None. Все изменения — чистая замена/удаление, новых stub-функций не создавалось.

## Manual Verification (post-commit)

До UAT проверить:
1. `python main.py` → overlay на рабочем столе: углы чисто скруглены, без чёрных полосок.
2. Главное окно не видно в `Win+T` (taskbar) и не появляется в Alt+Tab.
3. Открыть главное окно (клик по overlay) → drag задачи к левому краю (<60px): видна тонкая sage полоска слева, ghost показывает "← Пред. неделя". Drop → задача -7 дней, неделя переключается.
4. Повторить с правым краем (sage справа + "След. неделя →").
5. Pill-кнопки "◀ Предыдущая неделя" / "Следующая неделя ▶" **больше не появляются**.

## Self-Check: PASSED

**Files created/modified exist:**
- FOUND: client/ui/icon_compose.py
- FOUND: client/ui/overlay.py
- FOUND: client/ui/drag_controller.py
- FOUND: client/ui/main_window.py
- FOUND: client/tests/ui/test_icon_compose.py
- FOUND: client/tests/ui/test_drag_controller.py
- FOUND: client/tests/ui/test_main_window.py

**Commits exist in git log:**
- FOUND: 09d67be (Task 1)
- FOUND: 7d46e94 (Task 2)
- FOUND: 14b5f49 (Task 3)
