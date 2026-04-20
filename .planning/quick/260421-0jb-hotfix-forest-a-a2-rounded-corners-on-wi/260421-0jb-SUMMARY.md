---
phase: 260421-0jb-hotfix-forest-a-a2
plan: 01
type: quick-hotfix
wave: 1
status: executed-pending-approval
autonomous: false
completed_tasks: [1, 2, 3]
pending_tasks: [4]  # human-verify checkpoint — owner approval required
files_modified:
  - client/ui/main_window.py
  - client/ui/themes.py
  - client/ui/week_navigation.py
  - client/tests/ui/test_themes.py  # stale assertion updated
requirements_met:
  - HOTFIX-01  # Rounded corners на Win10 (GDI SetWindowRgn) — implemented, awaiting owner verification
  - HOTFIX-02  # Шрифт Segoe UI вместо Variable — implemented, awaiting owner verification
  - HOTFIX-03  # Forest-стиль для WeekNavigation кнопок (ghost) — implemented, awaiting owner verification
commit_status: NOT COMMITTED — owner approval required per project rule
---

# Hotfix 260421-0jb: Rounded corners на Win10 + Segoe UI + Forest WeekNavigation

**One-liner:** Три точечных визуальных фикса после Phase A+A2 Forest рефакторинга: rounded corners через GDI SetWindowRgn (работает Win7+, в отличие от DWM Win11-only), замена `Segoe UI Variable` (Win11-only) на `Segoe UI` (Win7+), ghost-стиль Forest для WeekNavigation (◀ ▶ «Сегодня») + live-themeable archive-banner labels.

## Scope

Строго три таргет-файла + одна правка в тесте (устаревший assertion на старую строку шрифта).
Scope соблюдён: `git diff --stat` показывает только 4 файла.

## Changes per file

### 1. `client/ui/main_window.py`

**Добавлено:**

- Класс-константы: `WINDOW_CORNER_RADIUS = 12`, `RGN_REAPPLY_DEBOUNCE_MS = 50`
- Instance-атрибут `self._rgn_reapply_job: Optional[str]` для debounce after_cancel
- Метод `_apply_window_region_rounded(self)` — GDI `CreateRoundRectRgn` + `SetWindowRgn`, с fallback на `after_idle` если окно ещё без размеров (`w <= 1` или `h <= 1`), silent fail через `try/except + logger.debug`

**Изменено:**

- `_init_frameless_style` теперь вызывает `self._apply_window_region_rounded` вместо `self._apply_dwm_rounded_corners` (через тот же `self._window.after(DWM_CORNER_DELAY_MS, ...)`). `DWM_CORNER_DELAY_MS` и остальные DWM-константы оставлены как есть — не используются, но не мешают.
- Старый метод `_apply_dwm_rounded_corners` **заменён** на `_apply_window_region_rounded` (Win11 DWM API возвращал E_INVALIDARG на Win10 → корень бага)
- `_on_configure` теперь debouncит re-apply региона через `after_cancel` + новый `after(50ms, ...)` при resize (resize drag генерирует десятки `<Configure>` событий)

**Ключевые детали:**

- `hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())` — тот же паттерн что в `overlay.py`
- `CreateRoundRectRgn(0, 0, w+1, h+1, r, r)` — `+1` critical для exclusive coordinate quirk, без него правый/нижний край обрезается на 1px
- `SetWindowRgn(hwnd, rgn, True)` — Windows takes ownership HRGN, `DeleteObject` **не вызывается** (иначе crash / leak)

### 2. `client/ui/themes.py`

**Изменено:**

- `_FONT_FAMILY = "Segoe UI"` (было `"Segoe UI Variable"`) — одна строка правки
- Комментарий над константой обновлён — объясняет причину hotfix
- `_FONT_MONO`, FONTS dict структура, PALETTES — **не трогались** (как требовал план)

### 3. `client/ui/week_navigation.py`

**Добавлено в `__init__`:**

- `self._archive_title_label: Optional[ctk.CTkLabel] = None`
- `self._archive_return_label: Optional[ctk.CTkLabel] = None`

**Изменено в `_build`:**

- `self._prev_btn` и `self._next_btn` получили: `fg_color="transparent"`, `hover_color=bg_secondary`, `text_color=text_tertiary`, `border_width=0`, `font=FONTS["body"]`
- `self._today_btn` получил: `fg_color="transparent"`, `hover_color=bg_secondary`, `text_color=text_secondary`, `border_width=1`, `border_color=text_tertiary`, `font=FONTS["caption"]` (outlined-стиль)
- Archive-banner «📦 Архив» и «Вернуться →» labels теперь сохраняются в `self._archive_title_label` / `self._archive_return_label` с `text_color=text_secondary` (приглушённый Forest, не ярко-синий)
- Loop по `self._archive_banner.winfo_children()` для `<Button-1>` binding не менялся (покрывает оба label автоматически)

**Расширено в `_apply_theme`:**

- Re-configure на prev/next/today buttons (transparent bg + text/hover/border из новой палитры)
- Re-configure на archive-banner labels (`text_secondary` from new palette)
- Обёртка `try/except tk.TclError: pass` сохранена

### 4. `client/tests/ui/test_themes.py` (stale assertion update)

- `assert FONTS["body"][0] == "Segoe UI Variable"` → `assert FONTS["body"][0] == "Segoe UI"` с комментарием `# Hotfix 260421-0jb`. Без этой правки test падал бы на старое значение.

## Test results

**Автоматические тесты:**

```
python -m pytest client/tests/ui/test_main_window.py client/tests/ui/test_themes.py client/tests/ui/test_week_navigation.py -x --tb=short
```

**Результат:** ✅ **68 passed in 4.51s**

- `test_main_window.py`: 23/23 passed
- `test_themes.py`: 16/16 passed
- `test_week_navigation.py`: 29/29 passed

**Imports компилируются без ошибок:**

```
python -c "import client.ui.main_window, client.ui.themes, client.ui.week_navigation"
→ IMPORTS OK
```

## Grep-contract verification

Должно найтись:

| Паттерн                          | Файл                                 | Статус |
| -------------------------------- | ------------------------------------ | ------ |
| `CreateRoundRectRgn`             | `client/ui/main_window.py`           | FOUND (lines 549, 561, 562) |
| `SetWindowRgn`                   | `client/ui/main_window.py`           | FOUND (lines 60, 444, 536, 543, 548, 565, 566, 568, 572) |
| `_apply_window_region_rounded`   | `client/ui/main_window.py`           | FOUND (lines 453, 539, 542, 558) |
| `fg_color="transparent"`         | `client/ui/week_navigation.py`       | FOUND (6 occurrences: lines 159, 171, 184, 195, 306, 312) |
| `_archive_return_label`          | `client/ui/week_navigation.py`       | FOUND (6 occurrences: lines 110, 218, 225, 324, 325, 327) |

НЕ должно найтись:

| Паттерн               | Файл                    | Статус |
| --------------------- | ----------------------- | ------ |
| `Segoe UI Variable`   | `client/ui/themes.py`   | NOT FOUND (ok) |

Все 6 checkpoint'ов выполнены.

## Self-Check: PASSED

Проверено:

- [x] Все 3 таргет-файла + 1 тест-файл модифицированы согласно плану
- [x] 68 pytest тестов passed
- [x] Imports OK
- [x] Grep-контракт: находки / отсутствия как требовал план
- [x] Никакие файлы вне scope не трогались (остальные `M` в `git status` — pre-existing Phase A/A2 изменения)

## Deviations from plan

**None.** План выполнен точно как написан:

- Task 1: SetWindowRgn + after_idle-retry + debounced re-apply при resize — все паттерны из плана
- Task 2: Single-string edit `Segoe UI Variable` → `Segoe UI` + docstring-комментарий обновлён
- Task 3: Ghost-стиль + outlined Today + live-themeable archive labels + `_apply_theme` расширен — всё как в плане

**Micro-cleanup (не deviation):** убрал дословное упоминание `Segoe UI Variable` в комментарии `themes.py`, чтобы выполнить строгий grep-контракт плана (`grep "Segoe UI Variable" client/ui/themes.py` → empty). Смысл комментария сохранён.

## Task 4 (checkpoint:human-verify) — awaiting owner

**Status:** PENDING — не запущено (по правилу "не launch `python main.py`").

**Smoke-test checklist для владельца:**

Из корня worktree `S:\Проекты\ежедневник\.claude\worktrees\dazzling-allen-bd61dd` запустить:

```
python main.py
```

Затем проверить 5 чекбоксов:

- [ ] **Углы главного окна скруглены** (радиус 12px, не квадратные). Кликнуть overlay → открыть главное окно → визуально подтвердить.
- [ ] **Шрифт — Segoe UI** (не MS Sans Serif / Tahoma). Текст «Еженедельник» в title bar, «Неделя N • …» в header, названия дней — чистый модерный sans-serif.
- [ ] **Стрелки ◀ ▶ и «Сегодня» не ярко-синие.** Прозрачный фон, приглушённый текст (text_tertiary для стрелок, text_secondary для «Сегодня»), при наведении подсветка bg_secondary. У «Сегодня» тонкая рамка (1px, color=text_tertiary).
- [ ] **Смена темы перекрашивает кнопки и archive labels.** Tray → Настройки → переключить `forest_light ↔ forest_dark`. Кнопки и «📦 Архив» / «Вернуться →» должны перекраситься без рестарта.
- [ ] **Resize окна сохраняет скруглённые углы.** Потянуть окно за угол — углы остаются скруглёнными после изменения размера (debounce 50ms перепримeняет регион).

Если что-то сломано — указать какой именно из 3 фиксов не сработал и как выглядит.

## Commit command (DO NOT RUN without owner approval)

Когда владелец одобрит после smoke-теста:

```bash
cd S:/Проекты/ежедневник/.claude/worktrees/dazzling-allen-bd61dd
git add client/ui/main_window.py client/ui/themes.py client/ui/week_navigation.py client/tests/ui/test_themes.py .planning/quick/260421-0jb-hotfix-forest-a-a2-rounded-corners-on-wi/
git commit -m "fix(260421-0jb): rounded corners Win10 + Segoe UI + Forest WeekNavigation

- main_window: GDI SetWindowRgn (Win7+) вместо DWM Win11-only API, debounced re-apply при resize
- themes: _FONT_FAMILY = 'Segoe UI' (Segoe UI Variable только на Win11)
- week_navigation: ghost-стиль CTkButton + live-themeable archive labels
- tests: updated stale assertion на 'Segoe UI Variable'"
```

## Known Stubs

**None.** Все три фикса — полноценные замены, не плейсхолдеры. Метод `_apply_window_region_rounded` делает реальный SetWindowRgn с silent fail только при отсутствии ctypes.windll (не-Windows среда). Ghost-стиль использует реальные цвета из текущей палитры через `self._theme.get(...)`.

## Follow-up TODOs (не для этой таски)

- В проекте есть другие `CTkButton(...)` без явных `fg_color` — возможны аналогичные синие дефолты. Ценно прогнать `grep -n "CTkButton\\(" client/ui/*.py` в будущей фазе чистки.
- Комментарий `DWM_CORNER_DELAY_MS` и константы `DWMWA_WINDOW_CORNER_PREFERENCE` / `DWMWCP_ROUND` в `main_window.py` остались как мёртвый код — можно удалить в следующем рефакторинге, но сейчас не трогаем (вне scope hotfix, риск сломать что-то).
- `overlay.py` всё ещё пытается применить DWMWCP_ROUND — silent fail на Win10. Но overlay использует Pillow RGBA для углов, так что визуально это не проблема (явно сказано в плане: «НЕ трогать overlay.py»).
