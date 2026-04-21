---
phase: quick-260421-wng
plan: 01
subsystem: client-ui
tags: [ux, inline-edit, overlay-colors, custom-titlebar, theme]
requirements:
  - UX-V2-01
  - UX-V2-02
  - UX-V2-03
  - UX-V2-04
key-files:
  created:
    - client/ui/inline_edit_panel.py
  modified:
    - client/ui/main_window.py
    - client/ui/week_navigation.py
    - client/ui/icon_compose.py
    - client/tests/ui/test_icon_compose.py
decisions:
  - Sage-палитра overlay выбрана как гармония с бежевой базой темы (не зелёный-кислотный, а оливково-зелёный A8B89A→7A9B6B)
  - BADGE_SIZE_FRAC поднят с 16/56 до 22/56 (+38%) — решающий фактор читаемости на светлых обоях рабочего стола
  - Badge получил outline (60,80,50) и truetype Arial Bold вместо default bitmap font — чёткий текст на любом фоне
  - Custom title bar через overrideredirect + WS_EX_APPWINDOW (не WS_EX_TOOLWINDOW) — чтобы окно осталось в taskbar и Alt+Tab
  - InlineEditPanel через place() поверх scroll area (не Toplevel) — быстрее, органичнее, без focus-steal
  - EditDialog сохранён как deprecated (на случай будущих сценариев), не удалён
metrics:
  tasks: 4
  commits: 4
  files_changed: 5
  duration_minutes: ~35
  completed: 2026-04-21
---

# Quick Task 260421-wng: UX v2 — Inline Edit + Overlay + Title Bar Summary

**One-liner:** UX v2 — inline slide-down task editing + sage-palette overlay + theme-coloured week nav + custom borderless title bar с drag и resize-grip.

## Что реализовано

### Task 1: InlineEditPanel вместо EditDialog popup (commit `e851bab`)

Новый модуль `client/ui/inline_edit_panel.py` с классом `InlineEditPanel`:

- **Slide-down анимация** (~150мс, 8 шагов, ease-out quadratic) через `place(relx=0.5, rely=0, y=animated, anchor="n", relwidth=0.94)` поверх scroll area
- **Поля формы**: textbox задачи, Day dropdown («Сегодня»/«Завтра»/«Послезавтра»/`Пн 14 апр`...), Time (HH:MM через два CTkOptionMenu + ✕ clear), Done checkbox
- **Хоткеи**: `Esc` → отмена, `Ctrl+Enter` → сохранить (через `self._root_window.bind(..., add="+")` — не перезатирает `Ctrl+Space`)
- **Кнопки**: Удалить (accent_overdue border), Отмена, Сохранить (primary)
- **Replace-on-reopen**: клик по другой задаче уничтожает предыдущую панель (instant `destroy()`) и анимирует новую

В `main_window.py`:
- `_on_task_edit` теперь вызывает `_open_edit_panel(task)` вместо `EditDialog(...)`
- `_close_edit_panel` — callback от панели для очистки ref
- `EditDialog` импорт сохранён (deprecated), файл `edit_dialog.py` не удалён

### Task 2: Стрелки недели и «Сегодня» в цвет темы (commit `0f3d300`)

В `client/ui/week_navigation.py::_build` три кнопки пересозданы:

- **◀ / ▶ стрелки**: `fg_color="transparent"`, `text_color=text_primary`, `hover_color=bg_secondary`, `border_width=0`, `corner_radius=10`
- **«Сегодня»**: `border_width=1` с `border_color=text_tertiary` для ненавязчивого outline; остальное как у стрелок
- **`_apply_theme` обновлён**: при смене темы все три кнопки обновляют `text_color`/`hover_color`/`border_color`

Больше нет chrome-синих CTk-default кнопок.

### Task 3: Overlay sage-зелёный + увеличенный badge (commit `9d150b2`)

В `client/ui/icon_compose.py`:

- **Удалены** `OVERLAY_BLUE_TOP = (78, 161, 255)` и `OVERLAY_BLUE_BOTTOM = (30, 115, 232)`
- **Добавлены** `OVERLAY_GREEN_TOP = (168, 184, 154)` (#A8B89A) и `OVERLAY_GREEN_BOTTOM = (122, 155, 107)` (#7A9B6B)
- **OVERLAY_RED_TOP/BOTTOM** оставлены — overdue pulse работает как и раньше (sage → red → sage)
- **BADGE_SIZE_FRAC**: `16/56` → `22/56` (+38% размер)
- **BADGE_TEXT**: `(30, 30, 30)` → `(20, 40, 15)` — насыщенный тёмно-зелёный
- **Новый BADGE_OUTLINE** `(60, 80, 50)` — тонкая обводка вокруг белого disc для читаемости на светлых обоях
- **Truetype font**: `_draw_badge` теперь пытается загрузить `arialbd.ttf` → fallback на `ImageFont.load_default().font_variant(size=N)` (Pillow 12.1.1 поддерживает) → fallback на default bitmap

Тесты `test_icon_compose.py` обновлены: импорт `OVERLAY_GREEN_BOTTOM`, новая pixel-координата `(50, 8)` для проверки badge (старая `(44, 4)` попадала в antialias зону с новым outline), `test_overdue_pulse_zero_is_sage` (G>R и G>B) вместо `_is_blue`. Все 12 тестов проходят.

### Task 4: Custom title bar + drag + resize grip (commit `af41c6c`)

В `client/ui/main_window.py`:

- `__init__` теперь вызывает `self._window.after(100, self._apply_borderless)` — PITFALL 1 (Win11 DWM) соблюдён
- **`_apply_borderless`**: `overrideredirect(True)` + ctypes `SetWindowLongW` для установки `WS_EX_APPWINDOW` (окно остаётся в taskbar / Alt+Tab). Graceful try/except на случай нулевого `GetParent` hwnd
- **`_build_custom_header`**: 30px bg_secondary, «Личный Еженедельник» (caption/text_tertiary) слева, ✕ (hand2 cursor, hover=accent_overdue) справа. ✕ вызывает `self.hide()` (fade-out в tray, не destroy)
- **Drag-to-move**: `<ButtonPress-1>` + `<B1-Motion>` на header и title_lbl → `_on_header_drag_start` запоминает offset, `_on_header_drag_motion` перемещает через `geometry("+x+y")`
- **`_build_resize_grip`**: `⤡` label через `place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)` + `cursor="bottom_right_corner"`. Drag меняет `winfo_width`/`winfo_height` соблюдая MIN_SIZE=(320,320)
- **`_apply_theme` расширен**: обновляет header frame/title_lbl/close_btn/resize_grip при смене темы
- Новые instance-атрибуты: `_header_frame`, `_header_title_lbl`, `_header_close_btn`, `_resize_grip`, `_drag_offset_x/y`, `_resize_start_w/h/x/y`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test_icon_compose.py импортировал удалённый OVERLAY_BLUE_BOTTOM**

- **Found during:** Task 3 (после удаления `OVERLAY_BLUE_*` grep обнаружил существующий тест)
- **Issue:** `client/tests/ui/test_icon_compose.py:7` делал `from client.ui.icon_compose import OVERLAY_BLUE_BOTTOM` — ImportError при попытке запуска тестов
- **Fix:** Заменил на `OVERLAY_GREEN_BOTTOM`, также обновил `test_overdue_pulse_zero_is_blue` → `test_overdue_pulse_zero_is_sage` с assertion `g > r and g > b` вместо `b > r` (фон теперь зелёный)
- **Files modified:** `client/tests/ui/test_icon_compose.py`
- **Commit:** `9d150b2` (включён в Task 3 — модуль + его тесты неделимы)

**2. [Rule 3 - Blocking] Badge pixel-координата (44, 4) теперь в зоне outline**

- **Found during:** Task 3 ручной диагностикой pixel colors
- **Issue:** После увеличения badge (22/56) и добавления outline пиксель (44, 4) попадает в supersampling-antialias зону между disc и outline → значение `(252, 252, 251)` вместо строгого `(255, 255, 255)`
- **Fix:** Переключил три теста (`test_badge_appears_when_count_positive_and_size_large`, `test_no_badge_when_count_zero`, `test_overdue_badge_shows_overdue_count`) на pixel `(50, 8)` — устойчиво в центре нового badge, вне outline и вне зоны текста
- **Commit:** `9d150b2`

## Known Issues / Риски по Task 4 (требуют ручной проверки)

Следующие пункты помечены в плане как risk items; их окончательная валидация требует запуска живого приложения на Win11 машине пользователя:

1. **`attributes("-alpha", ...)` + `overrideredirect(True)`** — fade show/hide может не работать на некоторых DWM-конфигурациях. План разрешает fallback: если fade сломан, приложение всё равно работает (мгновенный показ/скрытие). Код не меняет fade-механизм — должен работать на Win10/11 с типовым DWM.

2. **`ctypes.windll.user32.GetParent(winfo_id())`** — может вернуть 0 на некоторых конфигурациях. Обёрнуто в try/except + явная проверка `if not hwnd: return` перед SetWindowLongW.

3. **Snap Win11 (drag-to-edges → auto-maximize)** — НЕ работает с `overrideredirect=True`, это accepted trade-off (пользователь знает).

4. **Кнопка минимизации** — не добавлена; `iconify()` ненадёжно работает с overrideredirect. Одна ✕ = hide в tray — приложение живёт в tray.

Если Task 4 критично ломает приложение (окно не открывается или крашится) — разрешён частичный revert: закомментировать `self._window.overrideredirect(True)` в `_apply_borderless`. Native bar вернётся, Task 1/2/3 продолжат работать.

## Commits

| # | Task | Hash | Description |
|---|------|------|-------------|
| 1 | InlineEditPanel | `e851bab` | feat(inline-edit): заменить EditDialog popup на inline slide-down панель |
| 2 | Week nav colors | `0f3d300` | style(week-nav): кнопки навигации в цвет темы (transparent + text_primary) |
| 3 | Sage overlay | `9d150b2` | feat(overlay): sage-зелёный градиент + увеличенный badge с outline |
| 4 | Custom title bar | `af41c6c` | feat(window): кастомный title-bar с drag + resize-grip вместо native Windows frame |

## Verification

**Автоматическая проверка (прошла):**
- Все 4 модуля импортируются без ошибок: `InlineEditPanel`, `MainWindow`, `WeekNavigation`, `render_overlay_image`, `OVERLAY_GREEN_TOP`
- `client/tests/ui/test_icon_compose.py` — 12/12 passed
- `client/tests/test_models.py`, `test_storage.py` и прочие не-e2e — 47/47 passed
- `render_overlay_image` корректно возвращает Image для size=73 (default/overdue) и size=16 (tiny)

**Grep-проверка по плану (пройдена):**
- `main_window.py::_open_edit_panel` содержит `InlineEditPanel(` (line 620)
- `main_window.py::_apply_borderless` содержит `overrideredirect(True)` (line 334)
- `week_navigation.py::_build` содержит `fg_color="transparent"` на трёх кнопках
- `icon_compose.py` содержит `OVERLAY_GREEN_TOP = (168, 184, 154)` и `OVERLAY_GREEN_BOTTOM`
- `OVERLAY_BLUE_*` удалены из production-кода (grep показывает только упоминания в .planning/ и старом plan 03-03)

**Ручная проверка (требуется от пользователя на живом запуске):**
- [ ] Overlay на обоях — бежево-зелёный (не синий)
- [ ] Tray icon тоже зелёная
- [ ] Клик по overlay → главное окно БЕЗ native Windows title bar, с кастомным header
- [ ] Drag по header перемещает окно
- [ ] ✕ в header — fade-out в tray (не destroy)
- [ ] Resize-grip ⤡ в правом нижнем углу работает
- [ ] Окно видно в Windows taskbar, Alt+Tab показывает окно
- [ ] Стрелки ◀/▶ и «Сегодня» — в цвет темы (НЕ синие), hover = mild bg shift
- [ ] Клик по задаче → InlineEditPanel выезжает slide-down (не popup Toplevel)
- [ ] Esc закрывает inline panel без сохранения
- [ ] Ctrl+Enter сохраняет и закрывает
- [ ] Смена темы через tray → header, навигация, grip, панель — всё обновляется

## Self-Check: PASSED

- File `client/ui/inline_edit_panel.py` exists: FOUND
- File `client/ui/main_window.py` exists and modified: FOUND
- File `client/ui/week_navigation.py` exists and modified: FOUND
- File `client/ui/icon_compose.py` exists and modified: FOUND
- File `client/tests/ui/test_icon_compose.py` updated: FOUND
- Commit e851bab exists: FOUND
- Commit 0f3d300 exists: FOUND
- Commit 9d150b2 exists: FOUND
- Commit af41c6c exists: FOUND
- 12/12 icon_compose tests pass
- All modules import cleanly
