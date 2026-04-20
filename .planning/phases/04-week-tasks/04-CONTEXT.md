# Phase 4: Недельный вид и задачи — Context

**Gathered:** 2026-04-17
**Status:** Ready for planning
**Mode:** Conversational design discussion — все визуальные решения в UI-SPEC.md

<domain>
## Phase Boundary

Content-слой над каркасом Phase 3. Задачи теперь **живут**: их добавляют через quick-capture (правый клик на overlay), отмечают выполненными, редактируют через dialog, удаляют с undo-toast, перетаскивают мышью между днями и на следующую неделю.

Покрывает REQ-IDs: WEEK-01..06 (6), TASK-01..07 (7) — всего 13.

**Phase 3 patch required (D-01 ниже):** правый клик на overlay переопределяется с "mini-menu" на Quick Capture.

</domain>

<decisions>
## Implementation Decisions

### Quick Capture (main speed-of-capture scenario)
- **D-01:** Right-click overlay → Quick Capture input (замена mini-menu из Phase 3 UI-SPEC). Tray-меню уже покрывает action'ы mini-menu — избыточности нет.
- **D-02:** Input 400×40 **под** overlay-квадратом (gap 8px); edge-flip наверх если overlay у нижнего края экрана.
- **D-03:** Input закрывается на: Esc, focus-loss, еще один right-click на overlay, drag квадрата.
- **D-04:** Smart parse RU: `HH:MM` + {сегодня / завтра / послезавтра} + {пн / вт / ср / чт / пт / сб / вс}. Fallback day=сегодня если не распознан.
- **D-05:** Enter → save + clear input + keep focus (multi-add). Empty Enter → short red-border flash.
- **D-06:** Ближайшая дата для weekday: если день уже прошёл в текущей неделе → следующая неделя того же weekday.

### Task block rendering (3 styles — переключатель в Phase 3 tray готов)
- **D-07:** Style A (cards): bg_secondary + shadow_card + rounded 8, padding 12/10, gap 8.
- **D-08:** Style B (lines): 1px bottom-border, padding 10/8, no shadow/bg.
- **D-09:** Style C (minimal): невидимый по default, hover → `rgba(accent, 0.04)` bg + rounded 6 + padding 6.
- **D-10:** Task text — **wrap без лимита** (user preference), word-wrap break-word, `CTkLabel.configure(wraplength=width-24)`.
- **D-11:** Checkbox 18×18 rounded 3: not-done (text_secondary border), done (accent_done fill + white ✓), overdue (accent_overdue border).
- **D-12:** Time field: mono, text_secondary; red (accent_overdue) если `time_deadline < now && !done`; dim (text_tertiary) если done.
- **D-13:** Hover → ✏️ + 🗑 fade-in справа (size 14×14, opacity 0 → 1 за 150ms).

### Edit dialog (hover ✏️ click)
- **D-14:** Modal center of main window (НЕ overlay); backdrop rgba(0,0,0,0.4).
- **D-15:** Fields: Text (multiline Text widget, Ctrl+Enter = Save, Enter = newline) + Day (dropdown "Сегодня / Завтра / Послезавтра / выбрать дату→CalendarModal") + Time (HH:MM input с validation regex + ✕ clear) + Done (checkbox).
- **D-16:** Buttons: [🗑 Удалить] слева (red, immediate delete + undo-toast), [Отмена] [Сохранить] справа (Esc=Отмена, Ctrl+Enter=Сохранить).
- **D-17:** Save disabled при empty text OR invalid HH:MM regex.

### Delete (undo-toast Gmail-style)
- **D-18:** Click 🗑 или "Удалить" в dialog → task fade-out 200ms + `storage.soft_delete_task()` (tombstone из Phase 2).
- **D-19:** Toast 280×40 bottom-center main window: "⟲ Задача удалена • [Отменить]", countdown-bar shrinks 5s.
- **D-20:** Click "Отменить" < 5s → `task.deleted_at = None` (Phase 2 API), task fade-in обратно в исходное место.
- **D-21:** Multi-delete → queued toasts, max 3 одновременно (stack vertically).

### Drag-and-Drop (HIGH RISK per ROADMAP)
- **D-22:** Mouse-down на task body (не checkbox, не icons) + mouse-move >5px → drag start. Короткий click = обычный click.
- **D-23:** Ghost = **отдельный `CTkToplevel`** с `overrideredirect=True`, opacity 0.6, копия task block, следует за курсором.
- **D-24:** Source day: task opacity 0.3 (placeholder) или hidden. Target day highlighting: `rgba(accent_brand, 0.15)` bg + `accent_brand` 3px border-left. Adjacent days: `rgba(accent_brand, 0.05)`.
- **D-25:** Next-week drop-zone: появляется при drag, нижняя секция "📅 Следующая неделя" с dashed accent_brand border.
- **D-26:** Drop valid → `task.day = target_day`, DB save, ghost fade-out 100ms, UI refresh. Drop invalid (вне zones) → ghost fade-out, task возвращается в source (cancelled).
- **D-27:** **Archive weeks — DnD заблокирован** (opacity 0.7 + editing disabled).
- **D-28:** Approach уточняется в Phase 4 research: `Canvas overlay` vs `ctypes WH_MOUSE hook` vs custom mouse-binding на CTkFrame. Research-phase обязан ответить до Plan 04-DnD.

### Week navigation & archive
- **D-29:** Header: `◀ Неделя N • DD-DD мес • Сегодня ▶`. "Сегодня" button виден только для не-current week (клик = today).
- **D-30:** Keyboard shortcuts (window focused): `Ctrl+←`/`Ctrl+→` = prev/next week, `Ctrl+T` = today, `Esc` = close window/dialog/qc, `Ctrl+Space` = quick-capture.
- **D-31:** Archive (week_start < current_monday): opacity 0.7 на content + banner "📦 Архив • неделя N • Вернуться →" под header. Editing/DnD disabled.
- **D-32:** Future weeks: **full functionality** (planning use case valid).
- **D-33:** Empty day: "+" icon 24×24 по центру секции, click → inline add input в этот день (альтернатива quick-capture).

### Task keyboard controls (task focused via Tab/click)
- **D-34:** `Space` = toggle done, `Del` = delete (undo-toast), `Enter` = open edit dialog, `Arrow up/down` = prev/next task.

### Data contracts (Phase 2 integration — не изменяем)
- **D-35:** Используем `LocalStorage.add_task()`, `update_task()`, `soft_delete_task()`, `merge_from_server()`, `get_visible_tasks()` — все из Phase 2.
- **D-36:** Task model (Phase 2) неизменна: id(UUID), user_id, text, day(ISO), time_deadline(ISO|None), done, position, created_at, updated_at, deleted_at.
- **D-37:** `position` — drag-reorder внутри дня (v1 — только cross-day drag; intra-day reorder — v2 если будет нужно).

### Claude's Discretion
- Конкретная структура `client/ui/week_view.py` (split на day_section.py, task_widget.py, edit_dialog.py, quick_capture.py, drag_controller.py, undo_toast.py — планер решит)
- Точная implementation DnD (определяется в phase-research)
- Calendar picker UI (Day dropdown fallback "выбрать дату")
- Exact animation timings в рамках UI-SPEC ranges
- Error handling для parse edge cases
- Test strategy (unit/integration/e2e split)

### Folded todos
(cross_reference_todos = 0 matches)

</decisions>

<canonical_refs>
## Canonical References

### Design contract (MANDATORY)
- `.planning/phases/04-week-tasks/04-UI-SPEC.md` — полный дизайн-контракт Phase 4 (quick-capture + 3 styles + dialogs + DnD + archive + keyboard)
- `design-preview/phase-4-prototype.html` — HTML-прототип с живыми сценариями (reference implementation для визуала)

### Phase 3 inheritance
- `.planning/phases/03-overlay-system/03-UI-SPEC.md` — палитра, типографика, аккордеон-structure (Phase 4 extends)
- `.planning/phases/03-overlay-system/03-CONTEXT.md` — 30 locked decisions Phase 3 (Phase 4 dependent)
- `client/ui/themes.py` (ThemeManager subscribe — Phase 3)
- `client/ui/settings.py` (SettingsStore + UISettings — Phase 3)
- `client/ui/icon_compose.py` (render_overlay_image — Phase 3; Phase 4 не меняет)
- `client/ui/overlay.py` (OverlayManager — Phase 4 patches right-click handler)
- `client/ui/main_window.py` (MainWindow shell — Phase 4 добавляет task rendering + edit dialog + undo toast + DnD в day sections)
- `client/ui/pulse.py` (PulseAnimator — Phase 4 wires через overdue detection на основе rendered tasks)

### Phase 2 data layer
- `client/core/storage.py` — LocalStorage API (add/update/soft_delete/merge/get_visible_tasks)
- `client/core/sync.py` — SyncManager (force_sync trigger когда task changes)
- `client/core/models.py` — Task/TaskChange schema (Phase 4 не меняет)

### Research & pitfalls
- `.planning/research/PITFALLS.md` — DnD CustomTkinter HIGH RISK (Phase 4 phase-research обязан снять риск)
- `.planning/research/FEATURES.md` — DnD = table stakes для недельного планировщика
- `.planning/phases/03-overlay-system/03-RESEARCH.md` §CustomTkinter patterns (re-used для Phase 4)

### Project vision
- `.planning/PROJECT.md` — Core Value "speed-of-capture"; Phase 4 quick-capture — буквальное исполнение обещания
- `.planning/REQUIREMENTS.md` §WEEK §TASK — 13 REQ-IDs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable from Phase 3
- `MainWindow` (client/ui/main_window.py) — аккордеон-сhell, day sections, today-strip, navigation header placeholder. Phase 4 наполняет содержимым.
- `ThemeManager.subscribe` pattern — task widgets подписываются на theme changes, refresh colors on switch
- `SettingsStore.load/save` — Phase 4 читает `task_style`, persists window_size/position changes

### Reusable from Phase 2
- `LocalStorage.get_visible_tasks()` → returns list[Task] filtered deleted_at is None. Явно используется MainWindow для рендеринга.
- `LocalStorage.add_task`, `update_task`, `soft_delete_task` — всё через `threading.Lock`
- `SyncManager._wake_event.set()` срабатывает на каждое локальное изменение (optimistic UI)

### Integration points
- `OverlayManager.on_context_menu` (currently mini-menu) → replace with `on_right_click → quick_capture.show(position)`
- `MainWindow._build_day_section(day_date, is_today)` → Phase 4 extends to render task list внутри `body` frame
- `WeeklyPlannerApp._refresh_ui` (Phase 3) — callback после sync/local changes → MainWindow.refresh_tasks()
- Focus chain: overlay → quick-capture → main window → task list (Tab navigation respects это)

### Platform notes
- HiDPI handled в Phase 3 (setProcessDPIAware). Phase 4 просто использует scaled coords.
- Multi-monitor — quick-capture popup должен появляться на том же monitor где overlay
- Cyrillic text wrap: CTkLabel + wraplength работает с UTF-8 корректно

### Skeleton to rewrite
- `client/ui/week_view.py` (skeleton) — будет переписан / split на несколько файлов per planner decision
- `client/ui/day_panel.py` (skeleton) — аналогично
- `client/ui/task_widget.py` (skeleton) — задействовать как reference

</code_context>

<specifics>
## Specific Ideas

- **Quick-capture как основной путь** — реализация Core Value. Если работает плохо/медленно — теряется весь смысл продукта. Performance critical.
- **Smart parse RU** — inspire by Todoist natural language input, но упростить до 3 паттернов (HH:MM, relative day, weekday).
- **Ghost + highlight zones** — inspired by Trello/Things DnD. Tactile, visible, forgiving (можно отпустить вне zones для cancel).
- **Undo-toast 5sec** — Gmail pattern. Balance between speed и safety. 5 секунд = read-time для того кто промахнулся.
- **Archive dim** — read-only visual. "Папка с прошлым", не "функциональная неделя". Просмотр без modify.
- **Three task-styles** — user-preference. Некоторые любят визуальные cards, некоторые минимализм. Phase 3 selector готов.
- **Keyboard shortcuts не mandatory** — mouse-only flow тоже работает. Шорткаты для power users.

</specifics>

<deferred>
## Deferred Ideas

- **Global hotkey (Win+Q)** — requires admin elevation, PITFALL 5. v2.
- **Recurring tasks** — excluded per PROJECT.md.
- **Task priorities, categories, tags** — anti-features v1.
- **Multi-select + bulk ops** — v2 if needed.
- **Search по всем неделям** — v2.
- **Drag arbitrary week (не just next)** — v1 covers next; arbitrary в v2 (UXI-03).
- **Undo stack >1 level** — v1 undoes only last delete within 5s. v2 может расширить (UXI-04).
- **English smart-parse** — v2.
- **Intra-day task reorder via DnD** — v1 = cross-day only. v2 если `position` field будет активно использоваться.
- **Calendar picker** — basic dropdown "Сегодня / Завтра / Послезавтра / выбрать дату→...". Полный calendar picker — v2 polish.
- **Task colors/emoji tags** — v2 anti-feature re-entry.
- **Attachments к задаче** — scope creep, never in v1.

### Reviewed Todos (not folded)
(cross_reference_todos = 0)

</deferred>

---

*Phase: 04-week-tasks*
*Context gathered: 2026-04-17 conversational + HTML prototype approved by owner*
