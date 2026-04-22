---
phase: quick-260422-vvn
plan: 01
subsystem: ui/dnd
tags: [dnd, cross-week, sage-pills, drag-controller, main-window]
completed: 2026-04-22
commit: 87f5dd6
requirements: [DND-CROSS-WEEK-01]
dependency_graph:
  requires:
    - client/ui/drag_controller.py (DropZone, DragController)
    - client/ui/main_window.py (_build_ui, _rebuild_day_sections, _update_week)
    - client/ui/week_navigation.py (set_week_monday, get_week_monday)
    - client/core/storage.py (get_task, update_task)
  provides:
    - "DropZone.is_prev_week флаг"
    - "DragController.on_week_jump callback (direction, task_id)"
    - "_show_week_jump_zones / _hide_week_jump_zones helpers"
    - "MainWindow._prev_week_zone + _next_week_zone pill-frames"
    - "MainWindow._on_week_jump (storage.update_task + week_nav.set_week_monday)"
  affects:
    - "UX переноса задачи между неделями (убран 4-шаговый цикл → 1 жест)"
tech_stack:
  added: []
  patterns:
    - "Optional callback для обратной совместимости (on_week_jump=None)"
    - "DropZone с day_date=date.min/max placeholder для cross-week зон"
    - "pack/pack_forget lifecycle для cross-week pills (показ только на drag)"
key_files:
  created: []
  modified:
    - client/ui/drag_controller.py
    - client/ui/main_window.py
    - client/tests/ui/test_drag_controller.py
    - client/tests/ui/test_main_window.py
decisions:
  - "Cross-week pills регистрируются в DragController с day_date=date.min/max — placeholder не используется в hit-test (DropZone.contains полагается на frame.winfo_rootx/y, не на day_date)"
  - "Pack/pack_forget управляется DragController (не MainWindow) — DragController уже владеет drag-lifecycle, MainWindow только создаёт frames и передаёт их"
  - "_update_zone_highlights + _clear_all_highlights исключают cross-week pills из подсветки — pills сохраняют собственный sage fg_color"
  - "Re-registration pills в _update_week обязательна — diff-rebuild не создаёт новые DropZone объекты, но clear_drop_zones() + перерегистрация 7 daily очищает и pills"
metrics:
  duration: "~25 мин"
  tasks_completed: 1
  files_touched: 4
  tests_added: 11
  tests_status: "63 passed (original 52 + new 11)"
---

# Quick 260422-vvn: Cross-week DnD — sage-pill зоны (±7 дней)

Перетаскивание задачи на предыдущую/следующую неделю через sage-pill drop-зоны, появляющиеся во время drag. Убирает 4-шаговый цикл «открой соседнюю неделю, открой edit, смени дату, закрой edit» — теперь это один жест drop'а.

## Что изменено

### client/ui/drag_controller.py

1. **DropZone dataclass**: новое поле `is_prev_week: bool = False` рядом с `is_next_week` — теперь поддерживаются оба направления cross-week jump.

2. **DragController.__init__**: добавлен параметр `on_week_jump: Optional[Callable[[int, str], None]] = None`. Обратно совместим с тестами, которые передают только `on_task_moved` (в `client/tests/ui/test_drag_controller.py::_make` используется позиционный вызов без kwarg).

3. **_on_release маршрутизация**: cross-week pills имеют приоритет над same-day drop. Порядок проверок:
   - target is None OR is_archive → cancel_drag
   - target.is_prev_week or is_next_week → on_week_jump(direction=±1, task_id) + _hide_week_jump_zones
   - target != source_zone → _commit_drop (обычный same-week перенос через on_task_moved)
   - target == source_zone → cancel_drag

4. **Переименование** `_show_next_week_zone(self, zone) → _show_week_jump_zones(self)` — показывает **обе** pill-зоны (prev packится `side="top"`, next — `side="bottom"`). Аналогично `_hide_next_week_zones → _hide_week_jump_zones`.

5. **_update_zone_highlights + _clear_all_highlights**: cross-week pills исключены из цикла подсветки — они сохраняют собственный sage fg_color вместо получения active/adjacent/normal цветов для 7 daily-zones.

### client/ui/main_window.py

1. **`__init__`**: инициализация полей `self._prev_week_zone / self._next_week_zone: Optional[ctk.CTkFrame] = None` ДО вызова `_build_ui()`.

2. **`_build_ui`**: ПОСЛЕ `self._scroll.pack(...)` и ПЕРЕД `self._undo_toast = ...` создаются две pill-рамки (sage, corner_radius=14, height=36) со внутренним `CTkLabel(text_color="#FFFFFF", font=FONTS["body_m"])`:
   - «◀  Предыдущая неделя»
   - «Следующая неделя  ▶»
   Рамки намеренно НЕ pack'ятся сразу — появляются только на drag через `DragController._show_week_jump_zones()`.
   Parent = `_root_frame` (не `_scroll`), чтобы pills всегда были видны поверх scroll-контента.

3. **`DragController.__init__`**: передан `on_week_jump=self._on_week_jump`.

4. **`_rebuild_day_sections`** и **`_update_week`**: после регистрации 7 daily-zones регистрируются cross-week pills как `DropZone(day_date=date.min, frame=_prev_week_zone, is_prev_week=True)` и аналогично для next с `date.max`. Re-registration в `_update_week` критична — иначе после переключения недели `clear_drop_zones()` выбрасывает pills.

5. **`_on_week_jump(direction, task_id)`**: получает task через `storage.get_task`, парсит `task.day` (с graceful fallback на ValueError/TypeError), вычисляет `new_day = current_day + timedelta(days=7 * direction)`, обновляет задачу через `storage.update_task(task_id, day=new_day.isoformat())`, вычисляет понедельник новой недели как `new_day - timedelta(days=new_day.weekday())` и вызывает `week_nav.set_week_monday(new_week_monday)`. Цепочка `set_week_monday → on_week_changed → _update_week → _refresh_tasks` восстанавливает UI новой недели с диф-rebuild'ом без мерцания. Дополнительный явный `_refresh_tasks()` в конце — защита от крайнего случая.

## Ключевые манёвры

### 1. `day_date=date.min/max` как placeholder для cross-week зон

`DropZone.contains()` работает исключительно через `frame.winfo_rootx/y` (bbox hit-test) — `day_date` поле вообще не читается в маршрутизации. Поэтому placeholder `date.min` для prev и `date.max` для next безопасен. `is_archive=False` по умолчанию — в `_on_release` зона принимается (не отбрасывается как archive).

### 2. Pack/pack_forget lifecycle вне MainWindow

DragController уже владеет drag-lifecycle (press/motion/release). Было бы неестественно заставлять MainWindow слушать «drag начался — покажи pills, drag закончился — скрой». Поэтому MainWindow создаёт frames **без pack'а** и регистрирует их как DropZone — DragController сам пакует их в `_start_drag` и снимает через `pack_forget` в `_commit_drop/_cancel_drag`.

Pack-опции задаются один раз в `_show_week_jump_zones` с явными `fill="x", padx=12, pady=(4,4), side="top"/"bottom"`. Повторный pack после pack_forget работает корректно в Tk — геометрия восстанавливается как при первом pack'е.

### 3. Re-registration pills в двух rebuild-путях

MainWindow имеет два пути rebuild:
- **Heavy rebuild** (`_rebuild_day_sections`): пересоздаёт 7 DaySection. Используется в первом `_build_ui`, при смене `task_style`, при отсутствующих секциях.
- **Diff-rebuild** (`_update_week`): переиспользует 7 DaySection через `set_day_date`, вызывается при навигации между неделями (UX-01).

Оба вызывают `clear_drop_zones()` перед регистрацией 7 daily-zones. Без re-registration pills в `_update_week` prev/next переставали работать после первой же смены недели. Теперь оба пути идентично регистрируют cross-week pills вслед за daily-zones.

## Pitfalls, всплывшие при реализации

**Pitfall 1 — `_update_zone_highlights` сбрасывал sage-цвет pills.** Первая версия подсвечивала активную зону (любую, включая pill) и ставила `normal` на все остальные — это перезаписывало `fg_color` pill'а на `bg_primary`. Исправлено: в блоках `active`/`adjacent`/`normal`/«clear previous hovered» добавлены проверки `not zone.is_prev_week and not zone.is_next_week`.

**Pitfall 2 — существующий тест `test_drag_controller_has_seven_drop_zones` падал.** Поведение честно изменилось: теперь зарегистрировано 9 зон (7 day + 2 cross-week). Тест обновлён — проверяется, что day-zones = 7 и total = 9.

## Тесты (всего +11)

**test_drag_controller.py** (+6):
- `test_dropzone_prev_week_flag`
- `test_week_jump_callback_optional` (сигнатура `__init__`)
- `test_both_cross_week_zones_shown_on_drag_start`
- `test_drop_on_prev_week_pill_triggers_callback` → on_week_jump(-1, task_id)
- `test_drop_on_next_week_pill_triggers_callback` → on_week_jump(+1, task_id)
- `test_cross_week_zones_hidden_on_cancel`

**test_main_window.py** (+5):
- `test_cross_week_pills_registered`
- `test_on_week_jump_prev_moves_task_and_switches_week`
- `test_on_week_jump_next_moves_task_and_switches_week`
- `test_on_week_jump_unknown_task_is_noop`
- `test_week_change_re_registers_cross_week_pills`

Обновлён `test_drag_controller_has_seven_drop_zones` — учёт 9 зон вместо 7.

## Verification

- **AST parse**: `python -c "ast.parse(drag_controller.py); ast.parse(main_window.py)"` → OK
- **grep `_show_next_week_zone|_hide_next_week_zones` в drag_controller.py** → 0 совпадений (переименовано полностью)
- **grep `is_prev_week|is_next_week` в drag_controller.py** → 13 совпадений (dataclass + _on_release + _show/_hide helpers + _update_zone_highlights)
- **grep `_prev_week_zone|_next_week_zone|_on_week_jump` в main_window.py** → 16 совпадений
- **pytest test_drag_controller.py + test_main_window.py**: 63 passed (original 52 + new 11)
- **pytest client/tests/ui/ (кроме e2e_phase3/4)**: 333 passed, 1 pre-existing Tcl ordering failure (не связано с изменениями — test_app_integration проходит индивидуально)

## Self-Check: PASSED

- File `client/ui/drag_controller.py` — FOUND (modified)
- File `client/ui/main_window.py` — FOUND (modified)
- File `client/tests/ui/test_drag_controller.py` — FOUND (modified)
- File `client/tests/ui/test_main_window.py` — FOUND (modified)
- Commit `87f5dd6` — FOUND (`feat(ui): cross-week DnD — sage-pill зоны для ±7 дней`)
- New test count = 11 — verified via pytest (63 total, +11 vs baseline 52)
- grep markers verified (see Verification section)
