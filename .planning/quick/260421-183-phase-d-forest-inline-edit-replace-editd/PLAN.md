---
phase: 260421-183-phase-d
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - client/ui/task_edit_card.py
  - client/ui/day_section.py
  - client/ui/main_window.py
  - client/tests/ui/test_task_edit_card.py
  - client/tests/ui/test_day_section.py
  - client/tests/ui/test_main_window.py
autonomous: true
requirements:
  - FOREST-D-01
  - FOREST-D-02
  - FOREST-D-03
  - FOREST-D-04

must_haves:
  truths:
    - "Клик ✎ на задаче разворачивает inline-карточку в той же позиции"
    - "Карточка показывает текущий текст задачи с multiline textbox, select-all at open"
    - "Day-pills показывают Сегодня/Завтра + 7 дней недели, активная pill совпадает с task.day"
    - "HH/MM entry предзаполнен текущим временем; ✕ сбрасывает time в None"
    - "Ctrl+Enter сохраняет (callback on_save); Esc отменяет (callback не вызывается)"
    - "🗑 удаляет задачу (callback on_delete)"
    - "Открытие edit-card на второй задаче автосохраняет первую"
    - "MainWindow._on_task_edit роутит в DaySection.enter_edit_mode вместо EditDialog"
  artifacts:
    - path: "client/ui/task_edit_card.py"
      provides: "TaskEditCard widget"
      contains: "class TaskEditCard"
    - path: "client/ui/day_section.py"
      provides: "enter_edit_mode/exit_edit_mode + _editing_task_id"
      contains: "enter_edit_mode"
    - path: "client/ui/main_window.py"
      provides: "Inline edit routing + on_task_update"
      contains: "enter_edit_mode"
    - path: "client/tests/ui/test_task_edit_card.py"
      provides: "10+ unit tests for TaskEditCard"
  key_links:
    - from: "client/ui/main_window.py:_on_task_edit"
      to: "client/ui/day_section.py:enter_edit_mode"
      via: "direct method call"
      pattern: "enter_edit_mode"
    - from: "client/ui/day_section.py:exit_edit_mode"
      to: "client/ui/main_window.py:_on_task_update"
      via: "on_task_update callback"
      pattern: "on_task_update"
    - from: "client/ui/task_edit_card.py"
      to: "client/ui/themes.py"
      via: "FONTS + theme_manager.get()"
      pattern: "self._theme.get"
---

<objective>
Заменить modal EditDialog на inline edit card, которая разворачивается прямо в списке задач — на месте TaskWidget при клике ✎. Сохранить EditDialog как fallback.

Purpose: Снизить cognitive friction при редактировании — контекст (другие задачи дня) остаётся видимым, нет modal-prison-mode. Это также визуально консистентно с Forest-дизайном (pills, минимализм).

Output: Новый виджет TaskEditCard; DaySection с edit-mode state; MainWindow routing; тестовое покрытие 10+ тестов для новой карточки и 4+ для DaySection edit-mode.
</objective>

<context>
@.planning/STATE.md
@CLAUDE.md
@client/core/models.py
@client/ui/themes.py
@client/ui/task_widget.py
@client/ui/day_section.py
@client/ui/main_window.py
@client/ui/edit_dialog.py

<interfaces>
<!-- Key contracts for executor -->

From client/core/models.py:
```python
@dataclass
class Task:
    id: str
    user_id: str
    text: str
    day: str                                    # ISO date: "2026-04-14"
    time_deadline: Optional[str] = None         # ISO datetime или "HH:MM" или None
    done: bool = False
    position: int = 0
    created_at: str = ""
    updated_at: str = ""
    deleted_at: Optional[str] = None
```

From client/ui/themes.py:
```python
FONTS: dict[str, tuple]  # keys: h1, h2, body, body_m, caption, small, icon, mono
class ThemeManager:
    def get(self, key: str) -> str
    def subscribe(self, callback: Callable[[dict[str, str]], None]) -> None
# Palette keys: bg_primary, bg_secondary, bg_tertiary,
# text_primary, text_secondary, text_tertiary,
# accent_brand, accent_brand_light, accent_done, accent_overdue
```

From client/ui/day_section.py:
```python
class DaySection:
    def __init__(self, parent, day_date, is_today, theme_manager, task_style,
                 user_id, on_task_toggle, on_task_edit, on_task_delete, on_inline_add)
    _task_widgets: dict[str, TaskWidget]
    _tasks: list[Task]
    _body_frame: ctk.CTkFrame  # parent for edit card
```

From client/ui/main_window.py:
```python
class MainWindow:
    _day_sections: dict[date, DaySection]
    _storage: LocalStorage
    def _on_task_edit(self, task_id: str) -> None  # existing — to be rewritten
```

From client/core/storage.py:
```python
def get_task(self, task_id: str) -> Optional[Task]
def update_task(self, task_id: str, **fields) -> bool  # fields: text, day, time_deadline, done, position
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create TaskEditCard widget with full UI</name>
  <files>client/ui/task_edit_card.py</files>
  <behavior>
    - build creates frame with forest border strip + textbox + day pills + time entries + checkbox + 3 buttons
    - day pills: 2 always-present (Сегодня, Завтра) + 7 day-of-week pills from week_monday
    - active pill matches task.day (exact ISO date)
    - time pre-populated from task.time_deadline (HH:MM extracted); None → empty dim entries
    - clear-time (✕) sets hh/mm to empty + marks time=None on save
    - Esc binding → _on_cancel (does NOT call on_save)
    - Ctrl+Enter binding → _on_save (emits updated fields dict)
    - 🗑 → _on_delete(task_id)
    - palette switch updates frame/border colors (theme.subscribe)
  </behavior>
  <action>
Create client/ui/task_edit_card.py implementing TaskEditCard class.

STRUCTURE:
```
class TaskEditCard:
    CORNER_RADIUS = 10
    LEFT_STRIP_WIDTH = 3

    def __init__(self, parent, task, week_monday, theme_manager,
                 on_save, on_cancel, on_delete):
        # store refs, create outer CTkFrame with bg_secondary + 1.5px border (не border — CTk не поддерживает border_width на CTkFrame так же как у CTkButton; используем border_width=2 + border_color=accent_brand).
        # Actually CustomTkinter CTkFrame SUPPORTS border_width + border_color — использовать.
        # Inside outer frame: left 3px accent strip (CTkFrame width=3) + content frame.
        # Content rows via pack: textbox → day-pills (2 rows) → time row → done checkbox → divider → buttons.
```

IMPLEMENTATION DETAILS:

1. Outer frame:
   - `self.frame = ctk.CTkFrame(parent, corner_radius=10, fg_color=bg_secondary, border_width=2, border_color=accent_brand)`
   - expose `pack(**kwargs)` and `destroy()`.

2. Inside, horizontal layout with LEFT strip + content column:
   - `strip = ctk.CTkFrame(self.frame, width=3, fg_color=accent_brand, corner_radius=0)` packed side="left", fill="y".
   - `content = ctk.CTkFrame(self.frame, fg_color="transparent")` packed side="left", fill="both", expand=True, padx=(9, 12), pady=10.

3. Textbox row:
   - `self._textbox = ctk.CTkTextbox(content, height=56, wrap="word", font=FONTS["body"], corner_radius=6, fg_color=bg_primary, border_width=1, border_color=bg_tertiary)`
   - packed fill="x", pady=(0, 8).
   - Insert task.text; bind `<FocusIn>` to select-all-once flag; select all in __init__ via `tag_add("sel", "1.0", "end-1c")`.

4. Day-pills: two rows (safety for narrow width).
   - Row 2a: "ДЕНЬ" label + "Сегодня"/"Завтра" pills.
   - Row 2b: 7 weekday pills from week_monday.
   - Each pill = CTkButton with:
     - Active: `fg_color=accent_brand, text_color=bg_primary, border_width=0, hover_color=accent_brand_light`
     - Inactive: `fg_color="transparent", text_color=text_secondary, border_width=1, border_color=bg_tertiary, hover_color=bg_secondary`
   - Height=26, width auto. Font=FONTS["caption"].
   - Labels: "Сегодня" (today.isoformat()), "Завтра" ((today+1).isoformat()), weekday pills "Пн 14" style using DAY_NAMES_RU_SHORT.
   - State held in `self._selected_day: str` (ISO date). `_set_day(iso)` → updates `self._selected_day` and restyles all pills.
   - Store pill widgets in `self._pills: dict[str, ctk.CTkButton]` keyed by iso date. "Сегодня" and "Завтра" pills keyed by their computed iso.

5. Time row:
   - Label "ВРЕМЯ" (FONTS["small"], text_tertiary).
   - Two CTkEntry (width=42, height=28, justify="center", font=FONTS["mono"]): `self._hh_entry`, `self._mm_entry`.
   - Pre-populate from `_extract_hhmm(task.time_deadline)` (if None → both empty).
   - Between them: CTkLabel ":" FONTS["mono"].
   - After mm: CTkLabel "✕" cursor="hand2" → `_clear_time()` clears both entries.
   - Validation: on `<FocusOut>` and `<KeyRelease>`, pad to 2 digits + clamp (00-23 / 00-59). If invalid → leave empty.

6. Done checkbox:
   - CTkCheckBox "Выполнено" bound to `self._done_var = tk.BooleanVar(value=task.done)`.

7. Divider + buttons:
   - CTkFrame height=1 bg_tertiary fill="x" pady=(8, 8).
   - Button row: CTkFrame transparent.
   - "🗑 Удалить" on left — transparent bg, text_color=accent_overdue, hover bg_secondary, border_width=0.
   - "Отмена" on right-1 — transparent bg + border text_tertiary.
   - "Сохранить" on right — fg_color=accent_brand, text_color=bg_primary, font=FONTS["body_m"].

8. Bindings:
   - `self.frame.bind_all`? NO — use `self._textbox.bind("<Escape>", ...)` AND `self.frame.bind("<Escape>", ...)` + bind on each entry.
   - Better: bind on `self.frame` via `bind_all` for `<Escape>` and `<Control-Return>` while the card is alive, then unbind on destroy. Simpler and more robust: helper `_bind_shortcuts()` that binds on textbox + entries + pills.
   - Simplest that works: bind on self._textbox and on self.frame (Frame doesn't accept key events unless focused; so also bind on the toplevel parent via `self.frame.winfo_toplevel().bind("<Escape>", self._on_cancel_event)` and clean up in destroy via saved `str` bind id. BUT bind() on toplevel returns funcid and binding persists; we need add="+" and cleanup with unbind(funcid).
   - Implementation: in __init__ do `self._toplevel = self.frame.winfo_toplevel()`; `self._esc_id = self._toplevel.bind("<Escape>", self._on_cancel_event, add="+")`; same for Ctrl-Return → `_on_save_event`.
   - In destroy: `self._toplevel.unbind("<Escape>", self._esc_id)` try/except.

9. Methods:
   - `pack(**kwargs) -> None`: self.frame.pack(**kwargs)
   - `destroy() -> None`: cleanup bindings + self.frame.destroy()
   - `focus() -> None`: self._textbox.focus_set()
   - `_on_save() / _on_save_event(event=None)`: gather state → call on_save(updated_fields dict with keys: text, day, time_deadline, done)
     - text = self._textbox.get("1.0", "end-1c").strip() — skip save if empty
     - day = self._selected_day
     - time_deadline: build "HH:MM" if both entries valid digits, else None
     - done = self._done_var.get()
   - `_on_cancel() / _on_cancel_event(event=None)`: call on_cancel()
   - `_on_delete()`: call on_delete(self._task.id)
   - `_apply_theme(palette)`: update frame fg_color, strip color, textbox colors, pill colors via restyle loop.

10. Palette subscription:
    - `theme_manager.subscribe(self._apply_theme)` in __init__.
    - Add `self._destroyed: bool = False` guard.

11. Week-monday pills iteration:
    - `for i in range(7): d = week_monday + timedelta(days=i); iso = d.isoformat(); label = f"{DAY_NAMES_RU_SHORT[i]} {d.day}"`
    - Active pill: iso == self._selected_day.
    - "Сегодня"/"Завтра" pills: key=today.isoformat() and (today+1).isoformat(). When Сегодня pill clicked, set _selected_day = today.isoformat().
    - Edge case: if task.day == today.isoformat(), both "Сегодня" and the weekday pill for today should indicate active. Safer: only one pill shows active at a time. Pref: Сегодня wins over weekday pill for today. Implementation: order pill registration so Сегодня/Завтра take priority keys, and restyle loop iterates ALL pills setting active if key matches _selected_day.
    - Dict storage: `self._pills: list[tuple[str, ctk.CTkButton]]` (list of (iso, button)) — multiple entries allowed with same iso (e.g. "Сегодня" and "Пн 14" both iso=today). Restyle sets active where iso matches.

12. Constants: `DAY_NAMES_RU_SHORT` can be imported from `client.ui.day_section` (already exists there).

CODE PATTERNS (follow existing conventions):
- Guard every tk/ctk call with try/except tk.TclError on destroy paths.
- Use `self._destroyed` flag before operations.
- No hardcoded hex — all colors via self._theme.get(key).
- Russian comments in docstrings OK.

Constants:
- CORNER_RADIUS = 10
- BORDER_WIDTH = 2
- LEFT_STRIP_WIDTH = 3
- TEXTBOX_HEIGHT = 56
- PILL_HEIGHT = 26
- TIME_ENTRY_WIDTH = 42
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && python -m pytest client/tests/ui/test_task_edit_card.py -x -q 2>&1 | tail -30</automated>
  </verify>
  <done>client/ui/task_edit_card.py exists with TaskEditCard class; all 10 TaskEditCard tests pass</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: TaskEditCard tests (10 tests)</name>
  <files>client/tests/ui/test_task_edit_card.py</files>
  <behavior>
    - test_card_builds_without_errors: construct + destroy doesn't raise
    - test_day_pills_show_7_days_from_week_monday: 7 weekday pills registered
    - test_active_day_pill_matches_task_day: selected_day == task.day
    - test_time_pre_populated_from_task: hh_entry has hour, mm_entry has minute
    - test_clear_time_button_sets_time_to_none: click ✕ → save emits time_deadline=None
    - test_escape_cancels: on_cancel called, on_save NOT called
    - test_ctrl_enter_saves: on_save called with updated fields
    - test_save_emits_on_save_with_updated_fields: edit text → save → callback receives updated text
    - test_delete_emits_on_delete: click 🗑 → on_delete(task.id)
    - test_palette_switch_updates_colors: theme.set_theme called → card updates (at minimum no crash)
  </behavior>
  <action>
Create `client/tests/ui/test_task_edit_card.py` with fixture `tec_deps` (mirror ed_deps from test_edit_dialog.py) and helper `_make()`.

Use `timestamped_task_factory` and `mock_theme_manager` fixtures.

week_monday = date.today() - timedelta(days=date.today().weekday())

For shortcut tests (Esc / Ctrl+Enter): instead of triggering actual keybindings, directly call `dlg._on_cancel_event(None)` / `dlg._on_save_event(None)` — that's what the binding does. (Mirror pattern from test_edit_dialog.py:test_cancel_closes_dialog which calls _cancel() directly.)

For test_clear_time_button:
1. Create card with task.time="14:30"
2. Call `card._clear_time()`
3. Call `card._on_save()`
4. Assert on_save kwargs/args had time_deadline=None

For test_active_day_pill: assert `card._selected_day == task.day`.

For test_palette_switch: call `card._apply_theme({"bg_secondary": "#aabbcc", ...})` with the current palette dict; assert no exception.

For test_day_pills_show_7: assert `sum(1 for iso, _ in card._pills if iso in {(week_monday+timedelta(i)).isoformat() for i in range(7)}) >= 7`.

Imports:
```python
from datetime import date, timedelta
from unittest.mock import MagicMock
import pytest
from client.ui.task_edit_card import TaskEditCard
```

Fixture skeleton:
```python
@pytest.fixture
def tec_deps(headless_tk, mock_theme_manager, timestamped_task_factory):
    return {
        "parent": headless_tk,
        "theme": mock_theme_manager,
        "factory": timestamped_task_factory,
        "on_save": MagicMock(),
        "on_cancel": MagicMock(),
        "on_delete": MagicMock(),
    }

def _make(deps, task=None, week_monday=None):
    if task is None:
        task = deps["factory"](text="my task")
    if week_monday is None:
        today = date.today()
        week_monday = today - timedelta(days=today.weekday())
    card = TaskEditCard(
        deps["parent"], task, week_monday, deps["theme"],
        on_save=deps["on_save"],
        on_cancel=deps["on_cancel"],
        on_delete=deps["on_delete"],
    )
    card.pack(fill="x")
    deps["parent"].update_idletasks()
    return card
```

Each test destroys the card at end.
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && python -m pytest client/tests/ui/test_task_edit_card.py -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>All 10 tests in test_task_edit_card.py pass</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: DaySection edit-mode (enter_edit_mode/exit_edit_mode)</name>
  <files>client/ui/day_section.py, client/tests/ui/test_day_section.py</files>
  <behavior>
    - enter_edit_mode(task_id): hides TaskWidget, inserts TaskEditCard in same position, sets _editing_task_id
    - enter_edit_mode called twice on different tasks: first auto-saves then second opens
    - exit_edit_mode(save=True): calls on_task_update(task_id, updated_fields)
    - exit_edit_mode(save=False): does NOT call on_task_update
    - on completion, TaskWidget reappears (body is re-rendered)
  </behavior>
  <action>
Modify `client/ui/day_section.py`:

1. Add to __init__ signature: `on_task_update: Optional[Callable[[str, dict], None]] = None` (keep optional for backwards compat with existing tests that don't pass it).

2. Add attributes:
   - `self._on_task_update: Optional[Callable] = on_task_update`
   - `self._editing_task_id: Optional[str] = None`
   - `self._edit_card: Optional[TaskEditCard] = None`
   - `self._week_monday: Optional[date] = None` — computed on enter_edit_mode from self._day_date.

3. Import TaskEditCard at top: `from client.ui.task_edit_card import TaskEditCard`

4. New method `enter_edit_mode(task_id: str) -> None`:
   - If `self._editing_task_id is not None`: `self.exit_edit_mode(save=True)` (auto-save)
   - Find task: `task = next((t for t in self._tasks if t.id == task_id), None)`; return if None
   - Hide TaskWidget: `widget = self._task_widgets.get(task_id); widget.frame.pack_forget() if widget`
   - Compute week_monday: `week_monday = self._day_date - timedelta(days=self._day_date.weekday())`
   - Create TaskEditCard:
     ```python
     self._edit_card = TaskEditCard(
         self._body_frame, task, week_monday, self._theme,
         on_save=lambda fields: self._handle_edit_save(task_id, fields),
         on_cancel=lambda: self.exit_edit_mode(save=False),
         on_delete=lambda: self._on_task_delete(task_id),
     )
     ```
   - Pack BEFORE the hidden widget via `before=widget.frame` (if widget exists) for exact in-place replacement. If widget None, pack at end.
     `self._edit_card.pack(fill="x", pady=(0, 3), before=widget.frame)` (try/except — `before=` requires widget alive).
   - `self._editing_task_id = task_id`
   - `self._edit_card.focus()`

5. New method `_handle_edit_save(task_id, fields) -> None`:
   - If `self._on_task_update`: `self._on_task_update(task_id, fields)`
   - `self.exit_edit_mode(save=False)` — note: save already applied, here just tear down.
   - Actually pattern: save emits callback immediately; exit_edit_mode tears down UI. Simpler: `_handle_edit_save` calls callback, then `_teardown_edit_mode()`.

6. New method `exit_edit_mode(save: bool) -> None`:
   - If `self._edit_card` is None: return
   - If save and self._editing_task_id: extract current state via `self._edit_card._collect_fields()` → call `self._on_task_update(self._editing_task_id, fields)` if callback exists
     - BUT: simpler is to treat exit_edit_mode(save=True) as "click Save button programmatically" — call `self._edit_card._on_save()` which in turn calls the on_save lambda wired above. That will fire _handle_edit_save.
     - Easier implementation: exit_edit_mode(save=True) → call `self._edit_card._on_save()` (which fires the wired callback → _handle_edit_save → tears down). exit_edit_mode(save=False) → call `self._teardown_edit_mode()` directly.
   - Alternative simpler: both branches call `_teardown_edit_mode`, and save=True additionally calls callback.
   - Use this pattern:
     ```python
     def exit_edit_mode(self, save: bool) -> None:
         if self._edit_card is None:
             return
         if save and self._on_task_update:
             fields = self._edit_card.collect_fields()  # public method
             task_id = self._editing_task_id
             if fields is not None and task_id:
                 self._on_task_update(task_id, fields)
         self._teardown_edit_mode()
     ```
   - This requires TaskEditCard to expose `collect_fields() -> Optional[dict]` (returns None if text empty — invalid).

7. Method `_teardown_edit_mode() -> None`:
   - Destroy edit_card
   - Restore TaskWidget visibility: `widget = self._task_widgets.get(self._editing_task_id); widget.frame.pack(fill="x", pady=(0, 3))` (re-pack in original position — pack order may change; caller usually re-renders via storage refresh so this is a safety net).
   - Clear state: `self._edit_card = None; self._editing_task_id = None`

8. Update _handle_edit_save:
   ```python
   def _handle_edit_save(self, task_id: str, fields: dict) -> None:
       if self._on_task_update:
           self._on_task_update(task_id, fields)
       self._teardown_edit_mode()
   ```

9. In destroy(): also tear down edit card if present.

10. MODIFY TaskEditCard: add public method `collect_fields() -> Optional[dict]` that returns the same dict `_on_save` builds, returning None if text is empty (to signal invalid save). Also modify `_on_save` to internally use `collect_fields()` and skip callback if None.

Now modify `client/tests/ui/test_day_section.py` — add 4 new tests at the end:

```python
def test_enter_edit_mode_replaces_task_widget_with_card(ds_deps, timestamped_task_factory):
    ds = _make(ds_deps)
    task = ds_deps["factory"](text="orig")
    ds.render_tasks([task])
    ds.enter_edit_mode(task.id)
    assert ds._editing_task_id == task.id
    assert ds._edit_card is not None
    # Original widget still in _task_widgets dict but frame pack_forgotten:
    widget = ds._task_widgets[task.id]
    # After pack_forget, the frame.winfo_manager() returns "" (no geometry manager)
    assert widget.frame.winfo_manager() == ""
    ds.destroy()


def test_second_edit_mode_saves_first_then_opens_new(ds_deps, timestamped_task_factory):
    ds_deps["root"].update_idletasks()
    on_task_update = MagicMock()
    ds = DaySection(
        ds_deps["root"], date.today(), False, ds_deps["theme"], "line",
        "user-1", ds_deps["on_toggle"], ds_deps["on_edit"],
        ds_deps["on_delete"], ds_deps["on_inline_add"],
        on_task_update=on_task_update,
    )
    t1 = ds_deps["factory"](text="a")
    t2 = ds_deps["factory"](text="b")
    ds.render_tasks([t1, t2])
    ds.enter_edit_mode(t1.id)
    ds.enter_edit_mode(t2.id)
    # First task auto-saved (callback called)
    on_task_update.assert_called()
    assert ds._editing_task_id == t2.id
    ds.destroy()


def test_exit_edit_mode_save_calls_on_task_update(ds_deps, timestamped_task_factory):
    on_task_update = MagicMock()
    ds = DaySection(
        ds_deps["root"], date.today(), False, ds_deps["theme"], "line",
        "user-1", ds_deps["on_toggle"], ds_deps["on_edit"],
        ds_deps["on_delete"], ds_deps["on_inline_add"],
        on_task_update=on_task_update,
    )
    task = ds_deps["factory"](text="x")
    ds.render_tasks([task])
    ds.enter_edit_mode(task.id)
    ds.exit_edit_mode(save=True)
    on_task_update.assert_called_once()
    args = on_task_update.call_args[0]
    assert args[0] == task.id
    assert isinstance(args[1], dict)
    ds.destroy()


def test_exit_edit_mode_cancel_does_not_call_on_task_update(ds_deps, timestamped_task_factory):
    on_task_update = MagicMock()
    ds = DaySection(
        ds_deps["root"], date.today(), False, ds_deps["theme"], "line",
        "user-1", ds_deps["on_toggle"], ds_deps["on_edit"],
        ds_deps["on_delete"], ds_deps["on_inline_add"],
        on_task_update=on_task_update,
    )
    task = ds_deps["factory"](text="x")
    ds.render_tasks([task])
    ds.enter_edit_mode(task.id)
    ds.exit_edit_mode(save=False)
    on_task_update.assert_not_called()
    ds.destroy()
```
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && python -m pytest client/tests/ui/test_day_section.py -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>All DaySection tests pass (old + 4 new); enter_edit_mode/exit_edit_mode implemented</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: MainWindow routing — on_task_edit → DaySection.enter_edit_mode + on_task_update</name>
  <files>client/ui/main_window.py, client/tests/ui/test_main_window.py</files>
  <behavior>
    - _on_task_edit(task_id) locates containing DaySection and calls enter_edit_mode
    - new _on_task_update(task_id, fields) applies storage.update_task + _refresh_tasks
    - DaySection is constructed with on_task_update=self._on_task_update
    - EditDialog fallback remains in code but not triggered by default
    - test: _on_task_edit calls the section's enter_edit_mode
  </behavior>
  <action>
Modify `client/ui/main_window.py`:

1. In _rebuild_day_sections, pass `on_task_update=self._on_task_update` when constructing each DaySection:
```python
ds = DaySection(
    self._scroll, d, is_today, self._theme, style, self._user_id,
    on_task_toggle=self._on_task_toggle,
    on_task_edit=self._on_task_edit,
    on_task_delete=self._on_task_delete,
    on_inline_add=self._on_inline_add,
    on_task_update=self._on_task_update,
)
```

2. Replace existing _on_task_edit body:
```python
def _on_task_edit(self, task_id: str) -> None:
    """Forest Phase D: route to inline TaskEditCard via DaySection.enter_edit_mode.
    Falls back to modal EditDialog when section not found."""
    if self._storage is None:
        return
    task = self._storage.get_task(task_id)
    if task is None:
        return
    # Locate the DaySection containing this task
    try:
        task_day = date.fromisoformat(task.day)
    except (ValueError, TypeError):
        task_day = None
    section = self._day_sections.get(task_day) if task_day else None
    if section is not None:
        section.enter_edit_mode(task_id)
        return
    # Fallback: modal EditDialog
    EditDialog(
        self._window, task, self._theme,
        on_save=self._on_edit_save,
        on_delete=self._on_task_delete,
    )
```

3. Add new method:
```python
def _on_task_update(self, task_id: str, fields: dict) -> None:
    """Forest Phase D: inline edit save → apply to storage + refresh UI."""
    if self._storage is None:
        return
    # Filter to recognised fields
    allowed = {"text", "day", "time_deadline", "done", "position"}
    payload = {k: v for k, v in fields.items() if k in allowed}
    if not payload:
        return
    self._storage.update_task(task_id, **payload)
    self._refresh_tasks()
```

4. Add test in test_main_window.py:
```python
def test_on_task_edit_calls_day_section_enter_edit_mode(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory(text="edit me")
    mw_phase4_deps["storage"].add_task(task)
    mw._refresh_tasks()
    today = date.today()
    ds = mw._day_sections.get(today)
    assert ds is not None
    ds.enter_edit_mode = MagicMock()  # spy
    mw._on_task_edit(task.id)
    ds.enter_edit_mode.assert_called_once_with(task.id)
    mw.destroy()
```

Optionally also a test for _on_task_update:
```python
def test_on_task_update_applies_to_storage(mw_phase4_deps, timestamped_task_factory):
    mw = _make_mw_p4(mw_phase4_deps)
    task = timestamped_task_factory(text="orig")
    mw_phase4_deps["storage"].add_task(task)
    mw._on_task_update(task.id, {"text": "updated", "done": True})
    updated = mw_phase4_deps["storage"].get_task(task.id)
    assert updated.text == "updated"
    assert updated.done is True
    mw.destroy()
```
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && python -m pytest client/tests/ui/test_main_window.py -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>MainWindow routes to inline edit; 2 new tests pass; fallback EditDialog code path present</done>
</task>

<task type="auto">
  <name>Task 5: Full regression — run all UI tests + edit_dialog still passes</name>
  <files></files>
  <action>
Run full client test suite to verify:
- No existing test broke
- New tests pass
- EditDialog tests still pass (fallback preserved)

```bash
cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd"
python -m pytest client/tests/ui/ -x -q 2>&1 | tail -40
```

If any failure: fix and re-run.
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && python -m pytest client/tests/ui/ -q 2>&1 | tail -5</automated>
  </verify>
  <done>All UI tests pass (TaskEditCard + DaySection + MainWindow + EditDialog)</done>
</task>

<task type="auto">
  <name>Task 6: Write SUMMARY and commit</name>
  <files>.planning/quick/260421-183-phase-d-forest-inline-edit-replace-editd/SUMMARY.md</files>
  <action>
Write SUMMARY.md documenting:
- What changed (new file, edited files, new callbacks)
- Why (user goal — replace modal with inline)
- Key design decisions (collect_fields API, toplevel-binding for Esc/Ctrl-Enter, pill restyle approach)
- Test coverage: +10 TaskEditCard, +4 DaySection, +2 MainWindow (or +1)
- Files unchanged: themes.py, task_widget.py, edit_dialog.py (kept as fallback)

Then commit with the message from task_requirements using HEREDOC.
  </action>
  <verify>
    <automated>cd "S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd" && git log -1 --oneline 2>&1</automated>
  </verify>
  <done>SUMMARY.md exists; commit created on current branch</done>
</task>

</tasks>

<verification>
Full test suite pass:
```
python -m pytest client/tests/ui/ -q
```
Manual smoke (optional): launch app, click ✎ on task, verify card appears, edit text, click Save, verify task text updated.
</verification>

<success_criteria>
- [ ] client/ui/task_edit_card.py exists with TaskEditCard class
- [ ] TaskEditCard uses only FONTS + palette keys (no hardcoded hex)
- [ ] DaySection has _editing_task_id, enter_edit_mode, exit_edit_mode, _teardown_edit_mode
- [ ] MainWindow._on_task_edit routes to DaySection.enter_edit_mode
- [ ] MainWindow._on_task_update applies storage.update_task + _refresh_tasks
- [ ] EditDialog preserved as fallback (no deletion)
- [ ] themes.py and task_widget.py NOT modified
- [ ] +10 tests in test_task_edit_card.py, +4 in test_day_section.py, +1-2 in test_main_window.py
- [ ] All UI tests pass
- [ ] SUMMARY.md + commit created autonomously
</success_criteria>
