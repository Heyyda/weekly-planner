---
phase: quick-260422-v1a
plan: 01
subsystem: ui
tags: [recurrence, inline-edit, time-picker, window-persistence, quick-capture, ux-polish]

requires:
  - phase: quick-260422-ugq
    provides: "sage accent_brand palette + inline-edit панель + hex-blend border"
  - phase: quick-260422-tah
    provides: "UpdateBanner 420×170 с accent-strip (шаблон для QuickCapture redesign)"
provides:
  - "Task.recurrence Optional[str] — локальное поле 'weekly' / None"
  - "LocalStorage клонирование weekly-задачи на day+7 при done=False→True"
  - "recurrence фильтруется из TaskChange (не попадает на сервер)"
  - "merge_from_server сохраняет локальный recurrence при server-wins"
  - "InlineEditPanel: 'Повторять каждую неделю' чекбокс вместо 'Выполнено'"
  - "TaskWidget: '🔁 ' prefix в тексте для recurrence='weekly'"
  - "Time picker '—' placeholder вместо '09:00'/'00' когда время не задано"
  - "Window size/position persist при любом способе закрытия (X/tray/Alt+Z)"
  - "QuickCapturePopup redesign 360×140 + accent strip + hint footer"
  - "QuickCapturePopup screen-clamp позиционирование (right → left → center+clamp)"
affects: [inline-edit, task-widget, storage-sync, main-window-lifecycle, quick-capture]

tech-stack:
  added: []
  patterns:
    - "Локальное поле модели, фильтруемое из wire-payload (recurrence)"
    - "Debounced persistence через tk.after + after_cancel паттерн"
    - "Screen-clamp позиционирование toplevel (right → left → center)"

key-files:
  created: []
  modified:
    - client/core/models.py
    - client/core/storage.py
    - client/ui/task_widget.py
    - client/ui/inline_edit_panel.py
    - client/ui/main_window.py
    - client/ui/quick_capture.py

key-decisions:
  - "recurrence — локальное-только поле, сервер про него не знает (cache.json only)"
  - "Клон задачи = новая Task с собственным UUID → sync отправит обычный CREATE"
  - "merge_from_server сохраняет локальный recurrence чтобы флаг не терялся при синке"
  - "Done-чекбокс убран из inline-edit (дублирование) — toggle только через TaskWidget"
  - "'—' sentinel в HH/MM OptionMenu: выбор '—' в любом dropdown выключает time_enabled"
  - "hide() синхронно сохраняет геометрию пока окно visible (winfo_* корректны)"
  - "Debounced _on_configure → after(500ms) с cancel предыдущего таймера — idle persist"
  - "QuickCapture clamp: right → left → center+clamp (приоритетный порядок размещения)"

patterns-established:
  - "Локальное поле модели: default=None, фильтруется из TaskChange wire_fields"
  - "Клонирование внутри update_task: готовим вне lock (threading.Lock не RLock)"
  - "Debounced UI-state save: after_cancel + after — idle persist без хаммеринга"

requirements-completed:
  - UX-RECURRENCE-01
  - UX-TIME-PLACEHOLDER-01
  - UX-WINDOW-PERSIST-01
  - UX-QUICKCAPTURE-REDESIGN-01

duration: ~35 min
completed: 2026-04-22
---

# Quick 260422-v1a: UX-пак (recurrence + time placeholder + window persistence + quick-capture redesign) Summary

**Четыре связанные UX-правки одной серией: weekly-повторение с автоклоном, '—' placeholder для time-picker, надёжный persist размера окна при любом закрытии, и редизайн QuickCapturePopup со screen-clamp позиционированием.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-22T19:27:00Z
- **Completed:** 2026-04-22T19:36:00Z
- **Tasks:** 4 / 4
- **Files modified:** 6

## Accomplishments

- Weekly recurrence реализован end-to-end: модель → storage → UI — при отметке done клон на следующую неделю создаётся автоматически и синхронизируется с сервером как обычная новая задача
- Time-picker больше не навязывает '09:00' для задач без времени — '—' явно сигнализирует "время не задано", ✕ и явный выбор '—' оба корректно отключают deadline
- Размер главного окна теперь надёжно сохраняется при закрытии любым путём — через debounced persist при resize + синхронный save в hide()
- QuickCapturePopup визуально согласован с UpdateBanner/InlineEditPanel (accent strip + border) и никогда не уезжает за край экрана благодаря clamp-логике

## Task Commits

1. **Task 1: Weekly recurrence — модель + storage клонирование + UI** — `69327da` (feat)
2. **Task 2: Time picker placeholder '—'** — `1049930` (feat)
3. **Task 3: Надёжная персистентность размера окна** — `65460e9` (fix)
4. **Task 4: QuickCapturePopup redesign + screen-clamp** — `9be7ea0` (feat)

## Files Created/Modified

- `client/core/models.py` — добавлено поле `Task.recurrence: Optional[str] = None`
- `client/core/storage.py` — `update_task` клонирует weekly-задачу при done=False→True; `merge_from_server` сохраняет локальный recurrence при server-wins; `allowed` расширен для recurrence; recurrence фильтруется из wire-payload
- `client/ui/task_widget.py` — `_format_text(task)` helper даёт '🔁 ' prefix для recurrence='weekly'; используется в `_build` и `update_task`
- `client/ui/inline_edit_panel.py` — Done чекбокс заменён на "Повторять каждую неделю"; `_recurrence_var` вместо `_done_var`; `HH_OPTIONS`/`MM_OPTIONS` начинаются с '—'; `_clear_time`/`_on_time_enabled_implicit`/`_save` учитывают '—' sentinel; `_set_time_menus_dim` → no-op
- `client/ui/main_window.py` — `_save_window_state_after_id` для debounced save; `_debounced_save_window_state` callback; `_on_configure` дебаунсит через `after(500, ...)` с cancel; `hide()` сохраняет геометрию ДО fade-out; `destroy()` отменяет pending таймер; `_on_edit_save` передаёт `recurrence` в `update_task`
- `client/ui/quick_capture.py` — `POPUP_WIDTH=360`/`POPUP_HEIGHT=140`; `EDGE_MARGIN=8`; `ACCENT_STRIP_WIDTH=4`; `_init_popup_style` переписан (outer frame + accent strip + caption label + entry + hint footer); `_blend_hex` helper; `show_at_overlay` screen-clamp (right → left → center+clamp); `show_centered` clamp; `_flash_empty_border` обновлён под новый border

## Automated Verification

```
$ python -c "from client.core.models import Task; t = Task.new('u', 'test', '2026-04-22'); t.recurrence = 'weekly'; d = t.to_dict(); assert d.get('recurrence') == 'weekly', d; print('OK')"
OK

$ python -c "from client.ui.inline_edit_panel import HH_OPTIONS, MM_OPTIONS; assert HH_OPTIONS[0] == '—' and MM_OPTIONS[0] == '—'; assert len(HH_OPTIONS) == 25 and len(MM_OPTIONS) == 13; print('OK')"
OK

$ python -c "import ast; src = open('client/ui/main_window.py', encoding='utf-8').read(); assert '_debounced_save_window_state' in src; assert 'self._save_window_state_after_id' in src; assert src.count('self._save_window_state()') >= 2; print('OK')"
OK (save_window_state calls: 2)

$ python -c "import ast; src = open('client/ui/quick_capture.py', encoding='utf-8').read(); assert 'POPUP_WIDTH = 360' in src; assert 'POPUP_HEIGHT = 140' in src; assert '_blend_hex' in src; assert 'winfo_screenwidth' in src; assert 'Быстрая задача' in src; assert 'Enter' in src and 'Esc' in src; print('OK')"
OK

$ python -c "import client.ui.main_window, client.ui.inline_edit_panel, client.ui.quick_capture, client.ui.task_widget, client.core.models, client.core.storage; print('ALL IMPORTS OK')"
ALL IMPORTS OK
```

### Test suite (целевые файлы)

```
$ python -m pytest client/tests/test_models.py client/tests/test_storage.py client/tests/ui/test_main_window.py client/tests/ui/test_quick_capture.py -q
79 passed in 17.34s
```

Все 79 целевых тестов зелёные до и после всех 4 задач. Pre-existing Tcl errors в `test_e2e_phase3/4` (Tcl image cleanup между тестами) остались как были — вне скоупа этой quick-задачи.

### Runtime smoke-test recurrence cloning

```
> Create weekly task → mark done → check clone:
Total tasks: 2
  daily standup day=2026-04-22 done=True recurrence=weekly
  daily standup day=2026-04-29 done=False recurrence=weekly
Pending changes: 3
  create abc day=2026-04-22 done=False
  update abc done=True             # recurrence не в wire!
  create def day=2026-04-29 done=False  # клон как обычный CREATE
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing functionality] Сохранение `recurrence` при `merge_from_server`**

- **Found during:** Task 1 (после основной реализации, при проверке сценария sync)
- **Issue:** `merge_from_server` заменяет локальный task-dict целиком на server TaskState. Поскольку сервер про recurrence не знает, ЛЮБАЯ синхронизация стирала бы флаг weekly.
- **Fix:** При server-wins перезаписи сохраняем `existing.get("recurrence")` в `local_format`, если сервер не прислал это поле (он и не умеет).
- **Files modified:** `client/core/storage.py::merge_from_server`
- **Commit:** Включено в `69327da` (Task 1)

Это не "добавляет фичу", а закрывает скрытый баг в исходном плане — без фикса recurrence жил бы только до первого успешного sync pull.

## Manual UAT Checklist

Владельцу предстоит проверить (в SUMMARY фиксируется после проверки):

1. [ ] Создать задачу → edit-panel → включить "Повторять каждую неделю" → сохранить → в списке задача с 🔁
2. [ ] Отметить weekly-задачу done → перейти на следующую неделю → копия задачи присутствует (без 🔁-done, с position+1000)
3. [ ] Создать задачу без времени → edit-panel показывает "— : —" (не "09:00")
4. [ ] Кликнуть ✕ рядом с time-picker → оба dropdown вернулись в "—"
5. [ ] Открыть main_window → ресайз → скрыть через Alt+Z (не X) → убить процесс → перезапустить → размер восстановился
6. [ ] Перетащить overlay в правый нижний угол экрана → ПКМ по overlay → QuickCapturePopup появляется СЛЕВА от overlay (не уезжает за правый край)
7. [ ] QuickCapturePopup визуально: виден accent strip слева (sage), caption "Быстрая задача" сверху, hint "Enter — сохранить · Esc — отмена" снизу

## Risks / Known Issues

- **Recurrence живёт только в cache.json** — при сбросе/коррупции локального кеша флаги weekly теряются на всех незаклонированных задачах (для уже склонированных копий это неважно). Если нужно глобально — потребуется поле в серверной схеме + миграция (вне скоупа).
- **QuickCapturePopup при работе на сетапе с двумя мониторами:** `winfo_screenwidth()` возвращает ширину primary monitor. Если overlay на вторичном справа от primary — clamp сработает, но popup не выйдет за правый край primary (может оказаться на primary вместо вторичного). Известное ограничение Tk; мультимонитор-aware позиционирование — отдельный ресёрч.
- **test_show_fades_in_to_alpha_1** flaky в full-suite run (alpha=0.984 вместо >=0.99) из-за timing-зависимости под нагрузкой — в isolation и в целевом наборе тестов всегда зелёный. Pre-existing behavior, не затронут изменениями.

## Self-Check

Verifying SUMMARY claims:

- File `client/core/models.py`: FOUND (recurrence added line ~71)
- File `client/core/storage.py`: FOUND (update_task clone + merge_from_server preserve)
- File `client/ui/task_widget.py`: FOUND (_format_text helper)
- File `client/ui/inline_edit_panel.py`: FOUND (recurrence var + '—' options)
- File `client/ui/main_window.py`: FOUND (debounced save + hide trigger)
- File `client/ui/quick_capture.py`: FOUND (redesign + clamp)
- Commit `69327da`: FOUND
- Commit `1049930`: FOUND
- Commit `65460e9`: FOUND
- Commit `9be7ea0`: FOUND

## Self-Check: PASSED
