---
phase: quick-260422-vvn
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/drag_controller.py
  - client/ui/main_window.py
autonomous: true
requirements:
  - DND-CROSS-WEEK-01
user_setup: []

must_haves:
  truths:
    - "При drag-старте задачи поверх области scroll появляются две sage-pill зоны: «◀ Предыдущая неделя» сверху и «Следующая неделя ▶» снизу"
    - "Drop задачи на pill предыдущей недели → задача переносится на день -7 дней, UI переключается на ту неделю, задача видна в ней"
    - "Drop задачи на pill следующей недели → задача переносится на день +7 дней, UI переключается на ту неделю, задача видна в ней"
    - "После cancel-drop (вне pill) зоны скрываются без следа, текущая неделя не меняется"
    - "Bbox hit-test зон работает независимо от day_date (сторонние pill не привязаны к конкретному дню)"
  artifacts:
    - path: "client/ui/drag_controller.py"
      provides: "DropZone.is_prev_week, on_week_jump callback, _show/_hide_week_jump_zones helpers"
      contains: "is_prev_week"
    - path: "client/ui/main_window.py"
      provides: "self._prev_week_zone, self._next_week_zone pill-frames; _on_week_jump callback"
      contains: "_on_week_jump"
  key_links:
    - from: "client/ui/drag_controller.py:_on_release"
      to: "MainWindow._on_week_jump"
      via: "on_week_jump(direction, task_id) callback (direction=±1)"
      pattern: "on_week_jump"
    - from: "client/ui/drag_controller.py:_start_drag"
      to: "MainWindow._prev_week_zone + _next_week_zone"
      via: "_show_week_jump_zones() вызывает zone.frame.pack(...)"
      pattern: "_show_week_jump_zones"
    - from: "client/ui/main_window.py:_on_week_jump"
      to: "WeekNavigation.set_week_monday"
      via: "new_week_monday = new_day - timedelta(days=new_day.weekday())"
      pattern: "set_week_monday"
---

<objective>
Cross-week DnD: перетаскивание задачи на предыдущую/следующую неделю через sage-pill drop-зоны которые появляются во время drag.

Purpose: Убирает когнитивный тормоз «открой соседнюю неделю, открой edit, смени дату, закрой edit» — один жест drop'а переносит задачу на ±7 дней и переключает UI на ту неделю. Speed-of-capture принцип применён к переносу.

Output:
- 2 pill-frame'а в главном окне (skrыты по умолчанию, появляются только при drag-активности)
- DropZone dataclass расширен флагом `is_prev_week` (к уже существующему `is_next_week`)
- Универсальный callback `on_week_jump(direction, task_id)` в DragController (прежний `on_task_moved` не затрагивается)
- MainWindow._on_week_jump меняет task.day на ±7 дней + переключает WeekNavigation через set_week_monday
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

<interfaces>
<!-- Ключевые интерфейсы, извлечённые из codebase — executor использует их напрямую, без exploration. -->

From client/ui/drag_controller.py (существующий DropZone, расширяется):
```python
@dataclass
class DropZone:
    day_date: date
    frame: ctk.CTkBaseClass
    is_archive: bool = False
    is_next_week: bool = False   # УЖЕ ЕСТЬ
    # is_prev_week: bool = False  ← ДОБАВИТЬ

class DragController:
    def __init__(
        self,
        root: ctk.CTk,
        theme_manager,
        on_task_moved: Callable[[str, date], None],
        # on_week_jump: Optional[Callable[[int, str], None]] = None,  ← ДОБАВИТЬ
    ) -> None: ...

    def register_drop_zone(self, zone: DropZone) -> None: ...
    def _on_release(self, event) -> None: ...    # Маршрутизирует между on_task_moved и on_week_jump
    def _show_next_week_zone(self, zone) -> None: ... # Переименовать → _show_week_jump_zones
    def _hide_next_week_zones(self) -> None: ...     # Переименовать → _hide_week_jump_zones
```

From client/ui/week_navigation.py:
```python
class WeekNavigation:
    def get_week_monday(self) -> date: ...
    def set_week_monday(self, monday: date) -> None: ...  # jump ±7 автоматически триггерит on_week_changed

def get_week_monday(d: date) -> date: ...  # вычислить понедельник для любой date
```

From client/core/storage.py:
```python
class LocalStorage:
    def get_task(self, task_id: str) -> Optional[Task]: ...
    def update_task(self, task_id: str, **fields) -> None: ...  # принимает day=<ISO str>
```

From client/ui/themes.py (sage palette):
```python
# theme_manager.get("accent_brand") → sage-зелёный hex (light=#7A9B6B, dark=#94B080, beige=#6B8B5C)
# FONTS["body_m"] → (Segoe UI Variable, 13, bold)
```

From client/ui/main_window.py:
```python
class MainWindow:
    self._root_frame: ctk.CTkFrame       # главный контейнер (fill=both)
    self._week_nav: WeekNavigation       # packed side="top" в _root_frame
    self._scroll: ctk.CTkScrollableFrame # packed fill=both expand=True
    self._drag_controller: DragController
    self._storage: Optional[LocalStorage]

    def _on_task_moved(self, task_id, new_day) -> None: ...  # НЕ трогать
    def _refresh_tasks(self) -> None: ...
    def _rebuild_day_sections(self) -> None: ...             # регистрирует 7 daily zones
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Cross-week drop-зоны (DragController + MainWindow atomic)</name>
  <files>client/ui/drag_controller.py, client/ui/main_window.py</files>
  <action>
**A. client/ui/drag_controller.py — расширить DropZone, API, helpers.**

1. В dataclass `DropZone` (строка 20-27) добавить поле (рядом с `is_next_week`):
```python
is_prev_week: bool = False
```

2. В `DragController.__init__` (строка 117) добавить параметр `on_week_jump`:
```python
def __init__(
    self,
    root: ctk.CTk,
    theme_manager,
    on_task_moved: Callable[[str, date], None],
    on_week_jump: Optional[Callable[[int, str], None]] = None,
) -> None:
    ...
    self._on_task_moved = on_task_moved
    self._on_week_jump = on_week_jump
```

3. В `_on_release` (строка 223) изменить логику маршрутизации:
```python
def _on_release(self, event) -> None:
    if not self._dragging:
        self._reset_state()
        return

    target = self._find_drop_zone(event.x_root, event.y_root)
    if target is None or target.is_archive:
        self._cancel_drag()
        return

    # Cross-week jump имеет приоритет над same-day drop
    if target.is_prev_week or target.is_next_week:
        direction = -1 if target.is_prev_week else 1
        task_id = self._source_task_id
        self._ghost.hide()
        self._clear_all_highlights()
        self._hide_week_jump_zones()
        try:
            if task_id and self._on_week_jump:
                self._on_week_jump(direction, task_id)
        except Exception as exc:
            logger.error("on_week_jump failed: %s", exc)
        self._reset_state()
        return

    if target != self._source_zone:
        self._commit_drop(target)
    else:
        self._cancel_drag()
```

4. Заменить метод `_show_next_week_zone(self, zone)` (строка 349) на общий `_show_week_jump_zones(self)`:
```python
def _show_week_jump_zones(self) -> None:
    """Показать ОБЕ pill-зоны (prev + next) при старте drag."""
    for zone in self._drop_zones:
        if zone.is_prev_week or zone.is_next_week:
            try:
                # pack-параметры задаёт вызывающий код (MainWindow);
                # мы просто возвращаем frame в pack-менеджер. Поскольку
                # pack_forget сохраняет предыдущие опции, pack() без аргументов
                # восстановит предыдущий pack-контракт. На всякий случай
                # используем lift() для z-order.
                zone.frame.pack(fill="x", padx=12, pady=(4, 4))
                zone.frame.lift()
            except Exception:
                pass
```

5. Заменить `_hide_next_week_zones(self)` (строка 355) на `_hide_week_jump_zones(self)`:
```python
def _hide_week_jump_zones(self) -> None:
    """Скрыть обе pill-зоны после drop/cancel."""
    for zone in self._drop_zones:
        if zone.is_prev_week or zone.is_next_week:
            try:
                zone.frame.pack_forget()
            except Exception:
                pass
```

6. В `_start_drag` (строка 238) заменить блок показа next-week zone:
```python
# Было:
# for zone in self._drop_zones:
#     if zone.is_next_week:
#         self._show_next_week_zone(zone)
# Стало:
self._show_week_jump_zones()
```

7. В `_commit_drop` (строка 255) и `_cancel_drag` (строка 269) заменить `self._hide_next_week_zones()` на `self._hide_week_jump_zones()`.

8. В `_update_zone_highlights` (строка 297) проверить что highlight не применяется к prev/next-week зонам (они имеют собственный sage-стиль):
```python
# В цикле где проставляется "adjacent" исключить week-jump зоны:
for zone in self._drop_zones:
    if (
        zone is not hovered
        and zone is not self._source_zone
        and not zone.is_archive
        and not zone.is_prev_week
        and not zone.is_next_week
    ):
        self._set_zone_highlight(zone, "adjacent")
```

**B. client/ui/main_window.py — создать pill-зоны + callback + регистрация.**

9. В `_build_ui` (строка 357) ПОСЛЕ `self._scroll.pack(...)` (строка 377) и ПЕРЕД `self._undo_toast = ...` (строка 379) добавить создание двух pill-frame'ов:
```python
# Cross-week DnD pills (sage accent) — скрыты по умолчанию,
# pack/unpack управляется DragController._show/_hide_week_jump_zones().
sage = self._theme.get("accent_brand")
self._prev_week_zone = ctk.CTkFrame(
    self._root_frame,
    fg_color=sage,
    corner_radius=14,
    height=36,
)
ctk.CTkLabel(
    self._prev_week_zone,
    text="◀  Предыдущая неделя",
    text_color="#FFFFFF",
    font=FONTS["body_m"],
).pack(expand=True, fill="both")

self._next_week_zone = ctk.CTkFrame(
    self._root_frame,
    fg_color=sage,
    corner_radius=14,
    height=36,
)
ctk.CTkLabel(
    self._next_week_zone,
    text="Следующая неделя  ▶",
    text_color="#FFFFFF",
    font=FONTS["body_m"],
).pack(expand=True, fill="both")
# Намеренно НЕ pack'им — будут pack'иться только во время drag.
```

10. В инициализации `DragController` (строка 383) передать callback:
```python
self._drag_controller = DragController(
    self._root, self._theme,
    on_task_moved=self._on_task_moved,
    on_week_jump=self._on_week_jump,
)
```

11. В `_rebuild_day_sections` ПОСЛЕ цикла регистрации 7 daily drop-zones (строки 606-621, сразу после цикла) добавить регистрацию week-jump зон:
```python
if self._drag_controller:
    # Cross-week pills — day_date=date.min/max как placeholder,
    # реальный hit-test работает через frame.winfo_rootx/y.
    if self._prev_week_zone is not None:
        self._drag_controller.register_drop_zone(DropZone(
            day_date=date.min,
            frame=self._prev_week_zone,
            is_prev_week=True,
        ))
    if self._next_week_zone is not None:
        self._drag_controller.register_drop_zone(DropZone(
            day_date=date.max,
            frame=self._next_week_zone,
            is_next_week=True,
        ))
```

ВАЖНО: аналогичный блок нужен в `_update_week` (diff-rebuild, строка 657) сразу после `clear_drop_zones()` + цикла регистрации 7 daily зон. Без этого после переключения недели cross-week pills перестанут работать.

12. В `__init__` добавить поля (инициализация None перед `self._build_ui()`):
```python
self._prev_week_zone: Optional[ctk.CTkFrame] = None
self._next_week_zone: Optional[ctk.CTkFrame] = None
```

13. Добавить новый метод `_on_week_jump` рядом с `_on_task_moved` (строка 792):
```python
def _on_week_jump(self, direction: int, task_id: str) -> None:
    """Cross-week DnD: перенести задачу на ±7 дней и переключить UI на ту неделю.

    direction=-1 → предыдущая неделя, +1 → следующая.
    После update_task вызываем WeekNavigation.set_week_monday, который
    триггерит on_week_changed → _update_week (diff-rebuild без мерцания).
    """
    if self._storage is None or self._week_nav is None:
        return
    task = self._storage.get_task(task_id)
    if task is None:
        return
    try:
        current_day = date.fromisoformat(task.day)
    except (ValueError, TypeError):
        return
    new_day = current_day + timedelta(days=7 * direction)
    self._storage.update_task(task_id, day=new_day.isoformat())
    # Переключить UI на неделю с новой задачей:
    new_week_monday = new_day - timedelta(days=new_day.weekday())
    self._week_nav.set_week_monday(new_week_monday)
    # set_week_monday → on_week_changed → _update_week + _refresh_tasks
    # через существующую цепочку. Дополнительный _refresh_tasks тут
    # защитит от случая если set_week_monday не триггерит callback
    # (например, если неделя уже текущая — крайний случай ±7 == same week невозможен).
    self._refresh_tasks()
```

**Гарантии целостности:**
- `on_week_jump` в DragController — Optional (обратная совместимость с тестами, которые передают только on_task_moved).
- `_show_week_jump_zones` pack'ит с явными `padx=12, pady=(4,4)` — повторный pack после pack_forget работает корректно в Tk.
- DropZone с `day_date=date.min/max` — hit-test через `frame.winfo_rootx/y` не использует `day_date`, поэтому placeholder безопасен. `is_archive=False` по умолчанию — в `_on_release` такие зоны принимаются.
- `_update_zone_highlights` исключает week-jump зоны из adjacent-highlight — они сохраняют свой sage fg_color.

**Самопроверки перед финалом:**
- `grep -n "_show_next_week_zone\|_hide_next_week_zones" client/ui/drag_controller.py` → 0 совпадений (переименовано полностью).
- `grep -n "is_prev_week\|is_next_week" client/ui/drag_controller.py` → оба поля используются в _on_release маршрутизации.
- `grep -n "_prev_week_zone\|_next_week_zone\|_on_week_jump" client/ui/main_window.py` → минимум 3 упоминания каждого.
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('client/ui/drag_controller.py', encoding='utf-8').read()); ast.parse(open('client/ui/main_window.py', encoding='utf-8').read()); print('OK')"</automated>
    Дополнительно (manual smoke): запустить `python main.py`, открыть главное окно, начать перетаскивать любую задачу — над scroll должны появиться две sage pills; drop на верхнюю → задача переезжает на прошлую неделю и окно показывает ту неделю; drop на нижнюю → аналогично на следующую неделю; cancel (drop в пустоту) → зоны скрываются, неделя не меняется.
  </verify>
  <done>
- DropZone имеет is_prev_week: bool = False рядом с is_next_week
- DragController.__init__ принимает on_week_jump: Optional[Callable[[int, str], None]]
- _on_release распознаёт is_prev_week/is_next_week и вызывает on_week_jump(direction, task_id) вместо on_task_moved
- Переименованы _show_next_week_zone → _show_week_jump_zones; _hide_next_week_zones → _hide_week_jump_zones (оба показывают/скрывают ОБЕ pill-зоны)
- MainWindow создаёт self._prev_week_zone и self._next_week_zone (CTkFrame sage, corner_radius=14, height=36, со CTkLabel FONTS["body_m"] белым текстом)
- MainWindow передаёт on_week_jump=self._on_week_jump в DragController
- _rebuild_day_sections И _update_week регистрируют обе pill как DropZone (day_date=date.min/max, is_prev_week/is_next_week=True)
- _on_week_jump: storage.update_task(day=±7) + week_nav.set_week_monday(new_monday) + _refresh_tasks
- Файлы парсятся Python AST без ошибок
- Manual smoke (описан в verify) проходит
  </done>
</task>

</tasks>

<verification>
- Python AST parse двух изменённых файлов проходит без SyntaxError
- grep '_show_next_week_zone' и '_hide_next_week_zones' в drag_controller.py → 0 совпадений (переименования завершены)
- grep 'is_prev_week' в drag_controller.py → минимум 3 использования (dataclass field + _on_release check + _show/_hide_week_jump_zones)
- grep '_on_week_jump' в main_window.py → ≥2 (определение метода + передача callback в DragController)
- Manual smoke: cross-week drag показывает обе pill, drop на prev/next переключает неделю, задача видна в новой неделе, cancel не меняет неделю
- Регрессия: обычный same-week drag (задача → другой день той же недели) продолжает работать через on_task_moved (не on_week_jump)
</verification>

<success_criteria>
- Все критерии `done` в task 1 выполнены
- must_haves.truths (все 5) наблюдаются при manual smoke
- must_haves.key_links все подключены (on_week_jump callback, _show_week_jump_zones helper, set_week_monday цепочка)
- Существующая логика `_on_task_moved` не затронута регрессией — same-day drop'ы работают как прежде
</success_criteria>

<output>
После завершения создать `.planning/quick/260422-vvn-dnd-cross-week-prev-next-week-drop-zones/260422-vvn-SUMMARY.md` с описанием:
- Что изменено в drag_controller.py (DropZone.is_prev_week, on_week_jump, переименованные helpers, _on_release маршрутизация)
- Что изменено в main_window.py (_prev_week_zone/_next_week_zone pills, _on_week_jump callback, регистрация в _rebuild_day_sections + _update_week)
- Манёвр с day_date=date.min/max как placeholder для cross-week зон (hit-test не использует day_date)
- Манёвр с pack/pack_forget в DragController (pack-опции сохраняются между циклами forget/pack)
- Pitfalls если всплыли (pack-order, DWM при деструкции pills, etc.)
</output>
