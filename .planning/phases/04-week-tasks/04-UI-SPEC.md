# Phase 4: Недельный вид и задачи — UI-SPEC

**Gathered:** 2026-04-17
**Status:** Ready for planning (approved by owner via conversational discussion)
**Source:** Conversational design session после Phase 3 approval

---

## Domain

Content-слой недельного планировщика: **quick capture** (главный speed-of-capture scenario), **task rendering** в 3 стилях (Phase 3 готовит переключатель в tray, Phase 4 реально рисует), **edit/delete UX**, **drag-and-drop** задач между днями и на следующую неделю, **архив** прошлых недель, **навигация** и **today button**.

Покрывает REQ-IDs: WEEK-01..06, TASK-01..07 (13 total).

**Extends Phase 3 UI-SPEC:** использует ту же палитру, типографику, аккордеон-structure, task-style токены. Phase 4 наполняет container-ы Phase 3 реальным контентом.

**⚠ Phase 3 patch required:** правый клик на overlay сейчас показывает mini-menu (открыть/скрыть/выход). Phase 4 переопределяет его на **Quick Capture** trigger — tray-меню и так содержит все эти действия. См. §Quick Capture §Integration.

---

## Quick Capture — главный UX-подвиг

**Core Value из PROJECT.md:** "Быстро записать задачу которая прилетела 'в моменте'". Quick capture — буквальное исполнение этого обещания. Окно не открывается. Клавиатура не покидает input'а. От правого клика до сохранённой задачи — **4 действия** (right-click, type, [parse автоматически], Enter).

### Trigger

- **Правый клик по overlay-квадрату** → появляется quick-capture input
- Подменяет Phase 3 mini-menu (tray уже имеет те же команды)
- Левый клик по-прежнему открывает/закрывает главное окно (OVR-04 не меняется)
- Hover `grab` cursor остаётся для drag

### Widget position & appearance

```
desktop
───────────────────────────────────────
                                        
    ┌──┐                                
    │✓ │ 3    ← overlay 56×56         
    └──┘                               
      │  (input появляется строго под  
      ▼   overlay, с центровкой)        
    ┌────────────────────────────────┐ 
    │ 🔹 Новая задача на сегодня...  │  ← 400×40, input
    └────────────────────────────────┘   
       • focus мгновенно на поле         
       • placeholder подсказка           
       • синяя левая полоска 3px (accent_brand)
```

- **Позиция**: под overlay по-умолчанию (гориз. центр, вертикаль +overlay_height +8px)
- **Edge-case**: если overlay у нижнего края экрана (мало места снизу) → появляется **над** overlay (та же геометрия, но Y -= input_height + 8)
- **Follow-drag**: если пользователь начал двигать overlay во время открытого input — input закрывается
- **Focus**: мгновенно на поле, курсор в конце placeholder
- **Dismiss**: Esc, клик вне input, ещё один right-click по overlay, overlay-move, потеря focus из-за другого приложения

### Smart parse (natural input)

Автоматическое извлечение дня и времени из текста. Остаток — `text`.

| Pattern | Example | Result |
|---------|---------|--------|
| `HH:MM` | "позвонить Иванову 14:00" | text="позвонить Иванову", time_deadline="14:00", day=сегодня |
| Ru день недели | "заехать на склад пт" | text="заехать на склад", day=ближайшая пятница (или сегодня если сегодня пятница) |
| "завтра", "сегодня", "послезавтра" | "встреча завтра 15:30" | text="встреча", day=завтра, time_deadline="15:30" |
| Ничего | "перезвонить Лене" | text="перезвонить Лене", day=сегодня, time=None |

**Ru день недели**: пн, вт, ср, чт, пт, сб, вс (минимум 2 буквы, case-insensitive, без остатков)
**Ближайшая дата**: если день недели уже прошёл в этой неделе — берётся следующей недели

Алгоритм: regex-based, priority → HH:MM first → relative day (сегодня/завтра/послезавтра) → weekday → remainder = text. Всегда fallback на "сегодня" если day не распознан.

### Enter behavior

- Enter → task создана через `LocalStorage.add_task(Task(...))`
- Input очищается, focus сохраняется (multi-add режим)
- Визуальный feedback: вспышка синего фона input на 150ms → faded back
- Если focus потерян (click вне / Esc) — input закрывается

### Empty enter

- Пустой text + Enter → ничего не происходит, short flash red border для error
- Whitespace-only — то же

### Error handling

- Invalid parse (редко — если regex glitch) → task сохраняется с полным text, без day/time. Пользователь редактирует через edit dialog.
- LocalStorage.save failure → Toast error "Не удалось сохранить" (edge case)

---

## Task Block — Rendering Engine

Phase 3 ThemeManager + SettingsStore готовы. Phase 4 берёт `settings.task_style` и рендерит задачу в одном из 3 стилей.

### Style A: Card with shadow (default)

```
╔═══════════════════════════════════════════╗
║ ☐   Позвонить Иванову         14:00  ✏️ 🗑️║  ← hover: иконки справа
╚═══════════════════════════════════════════╝
     8px gap

╔═══════════════════════════════════════════╗
║ ☒   Отправить заказ (done)              ║  ← ☒ галочка; text strike-through
╚═══════════════════════════════════════════╝
```

- Checkbox 16×16 squared rounded 3px слева (checkmark зелёный `accent_done` при done)
- Text основной, single-line до wrap
- Time справа (если есть), monospace, muted
- Hover: ✏️ (edit) + 🗑️ (delete) icons fade-in справа, size 14×14
- Background `bg_secondary`, shadow `shadow_card`, rounded 8px
- Padding 12h × 10v, gap 8px

### Style B: Simple line

```
☐   Позвонить Иванову                14:00  ✏️ 🗑️
─────────────────────────────────────────────────
☒   Отправить заказ
─────────────────────────────────────────────────
☐   Проверить склад                  10:30  ✏️ 🗑️
```

- То же checkbox + text + time + hover icons
- Вместо карточки — тонкая bottom-line (1px `bg_tertiary` alpha 0.15)
- Нет shadow, нет background
- Padding 10h × 8v

### Style C: Minimal (hover-reveal)

```
☐   Позвонить Иванову                14:00   ← nothing visible
☒   Отправить заказ                           ← nothing visible

при hover:
┌──────────────────────────────────────────┐
│ ☐   Позвонить Иванову     14:00  ✏️ 🗑️ │   ← soft background + icons
└──────────────────────────────────────────┘
```

- Полностью "невидимый" вид по default
- Hover: soft background `rgba(accent, 0.04)` + icons + rounded 6px padding 6px вокруг
- Самый "воздушный" Linear-style

### Task text

- **Wrap без лимита** — блок растёт по высоте (user preference). 1-2-3+ строк — читабельно.
- `word-wrap: break-word` (CustomTkinter Label with `wraplength=...`)
- Min width задачи: column-width - 24px (padding × 2)

### Time field

- Показывается если `time_deadline IS NOT NULL`
- Format: `HH:MM` (UTC→local не применяется — пользователь видит то, что ввёл в том же таймзоне)
- Color:
  - Default: `text_secondary`
  - If `time_deadline < now()` AND `not done` → `accent_overdue` (red) — reinforces pulse
  - If done: `text_tertiary` (dim)

### Checkbox states

| State | Icon | Color | Behavior |
|-------|------|-------|----------|
| ☐ not done | Empty square, rounded 3px | `text_secondary` border | Click → mark done (optimistic UI) |
| ☒ done | Filled square + checkmark | `accent_done` fill, white check | Click → unmark done |
| ☐ overdue | Empty square | `accent_overdue` border, red | Same as not done, visual warning |

---

## Edit Dialog — Full Edit Flow

Клик на ✏️ (hover icon) → modal dialog. Position: центр окна (не overlay).

```
┌─────────────────────────────────────┐
│  Задача                          ✕  │  ← close button
├─────────────────────────────────────┤
│                                     │
│  Текст                              │
│  ┌───────────────────────────────┐ │
│  │ Позвонить Иванову             │ │  ← text input, multi-line
│  └───────────────────────────────┘ │
│                                     │
│  День                               │
│  ┌───────────────────────────────┐ │
│  │ Вторник, 15 апр          ▼    │ │  ← dropdown: Сегодня / Завтра / ...
│  └───────────────────────────────┘ │
│                                     │
│  Время                              │
│  ┌─────────┐                        │
│  │ 14:00   │  [✕]                   │  ← input HH:MM, кнопка "убрать"
│  └─────────┘                        │
│                                     │
│  ☐ Выполнено                        │  ← checkbox status
│                                     │
│  ─────────────────────────────      │
│                                     │
│  [🗑 Удалить]  [Отмена]  [Сохранить]│
└─────────────────────────────────────┘
```

### Field specs

- **Текст**: multiline Text widget (not Entry), height ~3 строки, auto-expand, Enter добавляет newline, Ctrl+Enter сохраняет
- **День**: dropdown `Сегодня / Завтра / Послезавтра / + дата picker (modal calendar)` — typical values + custom
- **Время**: input HH:MM с validation regex, empty = None, кнопка ✕ clear
- **Выполнено**: checkbox синхронизирован с task.done
- **Удалить**: красная кнопка слева — immediate delete с undo-toast (см. §Delete)

### Buttons

- **Сохранить** (Enter на dialog, primary blue) — apply changes → close dialog
- **Отмена** (Esc / close X) — discard changes → close dialog
- **Удалить** — immediate delete (no confirm) → undo-toast 5 sec

### Validation

- Если текст пустой → Сохранить disabled
- Если время non-HH:MM → красный border input, Save disabled
- Если день = пустой → берётся текущий (shouldn't happen в UI)

---

## Delete — Undo-toast (Gmail style)

Click на 🗑 (hover icon) или "Удалить" в edit dialog:

1. Задача **сразу** помечается `deleted_at = now()` в LocalStorage (tombstone по SYNC-08)
2. Visual: task block fade-out 200ms
3. **Toast появляется внизу окна**: "Удалено • Отменить" на 5 секунд
4. Click на "Отменить" в пределах 5 сек → `deleted_at = None`, task возвращается, fade-in
5. Через 5 сек toast исчезает, удаление финальное (tombstone sync в Phase 5)

### Toast visual

```
 ┌────────────────────────────────────┐
 │ ⟲ Задача удалена    [Отменить]    │  ← 280×40, bottom-center
 └────────────────────────────────────┘
     5 sec countdown bar (thin blue)
```

- Background: `bg_secondary` + subtle shadow
- Text: text_primary, "Отменить" как link (accent_brand, underlined on hover)
- Countdown-bar — 1px внизу toast, shrinks from full-width to 0 за 5 sec
- Multiple deletes → queued toasts, max 3 одновременно

---

## Drag-and-Drop — Ghost + Highlight Zones

**CustomTkinter не имеет native DnD.** Реализация custom через Canvas overlay + mouse event bindings (research Phase 3 PITFALL-related; Phase 4 research-phase уточнит точный подход — Canvas vs ctypes).

### DnD initiation

- Нажатие мышью на **теле задачи** (не на checkbox, не на hover-icons) → зажать left-mouse-button
- Mouse-move с зажатой кнопкой > 5px → **drag start**
- Короткий click (без movement >5px) → no DnD, обычный click propagates

### During drag

```
┌─────────────────────────────────────┐
│ ▼ Пн 14                             │  ← target zone HIGHLIGHT (blue alpha 0.15)
│   ☐  Задача A        [ghost 0.6]    │
│                                     │
│ ▼ Вт 15                             │  ← source zone: задача удалена из
│   ☐  (empty — dragged away)         │     списка, место "пустое"
│   ☐  Задача B                       │
│                                     │
│ ▶ Ср 16                       (3)   │  ← другие дни: normal
│                                     │
│         ╔══════════════════╗        │
│         ║ ☐  Dragged task  ║        │  ← ghost (opacity 0.6, follows cursor)
│         ╚══════════════════╝        │
└─────────────────────────────────────┘
```

**Ghost widget:**
- Копия task block (текущий стиль A/B/C) с opacity 0.6
- Позиция следует за курсором (pointer offset)
- Rendered как отдельный Toplevel (`overrideredirect=True`) для free-float

**Source zone:**
- Оригинальная задача исчезает из списка дня (placeholder-оставляется на месте или collapse)

**Target zone highlights:**
- Day-section с курсором hovered: background `rgba(accent_brand, 0.15)` + border-left `accent_brand` 3px (overrides today-strip if active)
- Day-sections рядом (prev/next): subtle highlight `rgba(accent_brand, 0.05)` — показывает "можно drop"
- Next-week drop zone: виден при drag → появляется special section "📅 Следующая неделя" внизу списка с blue border

### Drop

- Mouse-release внутри target zone → task.day изменяется, DB save, UI refresh
- Mouse-release **вне любой drop-zone** → ghost fade-out, задача возвращается в source (cancelled)
- Mouse-release **на own source** (не двигал) → same

### Valid vs invalid drops

- Valid: другой день текущей или следующей недели
- Invalid (ghost shows red-tinted borders): задача с `done=true` → drop OK но никаких pulse/overdue re-eval
- Archive недели: **DnD запрещён** (dim-visual показывает read-only)

### DnD RISK (flag for research-phase)

- CustomTkinter 5.2.2 drag feedback может быть laggy на слабых ПК
- Ghost Toplevel на multi-monitor: координаты virtual desktop (ctypes patterns из Phase 3)
- Research Phase 4 обязан ответить: Canvas-based vs custom-binding vs ctypes WH_MOUSE hook

---

## Header — Navigation

```
┌─────────────────────────────────────┐
│  ◀   Неделя 16 • 14-20 апр   Сегодня ▶  │  ← fixed top
└─────────────────────────────────────┘
```

**Elements:**
- ◀ prev-week arrow (hover blue, disabled at oldest week if we ever add limit — нет лимита)
- Центр: "Неделя N • DD-DD мес" (N = ISO week number, даты по локали)
- "Сегодня" button — виден **только** когда showing не-current week. Текст синий accent_brand
- ▶ next-week arrow (no limit on future either)

**Special states:**
- Viewing past week: "• Архив" suffix + banner-bar (см. §Archive)
- Viewing current week: нет "Сегодня" button (мы уже здесь)
- Viewing future week: "Сегодня" button есть

**Keyboard shortcuts** (window focused):
- `Ctrl+Left` / `Ctrl+Right`: prev/next week
- `Ctrl+T`: Сегодня
- `Esc`: close window (skrytj)

---

## Empty Day — Placeholder "+"

Когда в раскрытом дне нет задач:

```
▼ Ср 16                              (0)

     +
     (click to add)
```

- Большой `+` по центру, size 24×24, color `text_tertiary`
- Click → разворачивает inline input для этого конкретного дня (альтернатива quick-capture при открытом окне)
- Hover: `+` становится accent_brand, cursor pointer
- После ввода → input сохраняет задачу в этот день, input остаётся для след. add (multi-add), Esc закрывает

**Note:** это второй путь добавления (помимо quick-capture). Для пользователя: quick = "на сегодня быстро", inline = "на конкретный день планомерно".

---

## Archive — Past Weeks Dimmed

Когда текущая неделя показываемая в окне — **прошлая** (week_start < current_monday):

- **Opacity 0.7** на всём week-view content
- **Banner-bar** вверху (ниже header): `"📦 Архив • неделя 14  •  Вернуться →"` с кнопкой справа
  - Banner background: `bg_tertiary` (slightly darker)
  - "Вернуться" — синий accent_brand, click = today
- **Editing disabled**: checkbox click / hover-icons hidden / DnD blocked / + button no
- **Read-only visual**: курсор `default` (не pointer) на task blocks

Переход обратно в active:
- Clicking "Сегодня" → текущая неделя, полный контент
- Click prev/next arrow → соседняя неделя (может быть тоже архив если >1 неделя назад)

### Future weeks

- Viewing неделя в будущем: **full functionality**, не dim. "Планирование" = валидный use case.

---

## Focus & Keyboard

Phase 4 добавляет клавиатурные шорткаты (не блокирующие — mouse-only тоже работает).

### Global (window focused)

- `Ctrl+Space`: открыть quick-capture (альтернатива right-click на overlay — для тех кто уже в окне)
- `Ctrl+T`: Сегодня
- `Ctrl+←` / `Ctrl+→`: prev/next week
- `Esc`: close window OR close dialog OR dismiss quick-capture

### Inside quick-capture / add input / edit dialog

- `Enter`: save + stay for next (quick-capture, inline-add) OR close (edit dialog)
- `Esc`: cancel + close
- `Tab`: next field (edit dialog)
- `Shift+Tab`: prev field

### On task block (when focused via Tab / click)

- `Space`: toggle done
- `Del`: delete (undo-toast)
- `Enter`: open edit dialog
- `Tab`: next task
- `Arrow up/down`: prev/next task in current week

---

## Settings extension

Phase 4 добавляет несколько новых settings (через `SettingsStore` Phase 3):

- `task_style` — уже есть (Phase 3), значения "A", "B", "C"
- `undo_toast_duration_ms` — default 5000, hidden preference для power users
- `week_start_day` — default "monday" (ISO week), hidden
- `quick_capture_parse_language` — default "ru", hidden (для future en-support)

---

## Success Criteria (Phase 4 verifier)

1. Правый клик на overlay → quick-capture input появляется под квадратом; Enter с текстом "позвонить завтра 14:00" создаёт задачу на завтра с time=14:00
2. Все 3 task-style переключатель в tray работает мгновенно без рестарта; задачи перерисовываются
3. Hover на задачу → ✏️ + 🗑 icons появляются; click ✏️ → edit dialog с 4 полями (text/day/time/done) + 3 buttons (Delete/Cancel/Save)
4. Click 🗑 или "Удалить" в dialog → task fade-out + undo-toast 5 сек внизу; click "Отменить" → task возвращается
5. Drag задачи → ghost следует за курсором, day-sections highlighted; drop на другой день → task.day меняется, сохраняется; drop вне zones → cancelled
6. Next-week drop zone появляется при drag; drop в неё → task.day = next-week-monday (или выбранный день next-week если делаем fine-grained)
7. Прошлая неделя: opacity 0.7, banner "Архив • Вернуться" сверху, DnD/edit/delete заблокированы
8. `Ctrl+Left` / `Ctrl+Right` / `Ctrl+T` навигация по неделям
9. Пустой день: `+` по центру, click разворачивает inline input

---

## Canonical References

- `.planning/PROJECT.md` — Core Value (speed-of-capture — quick-capture это its most direct implementation)
- `.planning/REQUIREMENTS.md` §WEEK §TASK — 13 REQ-IDs
- `.planning/phases/03-overlay-system/03-UI-SPEC.md` — палитра, типографика, аккордеон-structure, task-style токены
- `.planning/phases/03-overlay-system/03-CONTEXT.md` — Phase 3 locked decisions (подписаны для extension)
- `.planning/phases/02-client-core/02-CONTEXT.md` — LocalStorage API (add_task, update_task, delete_task, merge_from_server)
- `.planning/research/PITFALLS.md` — DnD на CustomTkinter (HIGH RISK — research Phase 4 required)
- `.planning/research/FEATURES.md` — DnD = table stakes; анти-features (приоритеты, категории, recurring) не возвращаются

---

## Out of Scope (Phase 4)

- **Global hotkey (Win+Q style) для quick-capture** — отложен per PROJECT.md out-of-scope (requires elevation, PITFALL 5). Right-click на overlay эквивалентен.
- **Recurring tasks** — ExplicitOut-of-scope в PROJECT.md, не возвращаем
- **Категории / приоритеты / теги** — out-of-scope (anti-features)
- **Multi-task select** (checkbox для bulk operations) — v2 если будет потребность
- **Поиск по задачам** — v2
- **Drag arbitrary week (не next)** — phase 4 covers next-week drop zone. Произвольная неделя через DnD — v2 (UXI-03)
- **Undo stack** deeper than single delete — v2 (UXI-04)
- **English smart-parse** — v2

---

*Phase: 04-week-tasks*
*UI-SPEC gathered: 2026-04-17*
*Approved by owner via conversational design session*
