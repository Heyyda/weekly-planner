---
phase: quick-260422-tah
plan: 01
subsystem: client-ui
tags: [ui, resize, update-banner, ux]
dependency_graph:
  requires: []
  provides:
    - "MainWindow._build_edge_resizers (8 edge-zones resize)"
    - "UpdateBanner 420x170 с accent-strip + progress bar + slide-fade"
  affects:
    - "client/ui/main_window.py"
    - "client/ui/update_banner.py"
tech_stack:
  added: []
  patterns:
    - "Invisible edge-zones + place(relwidth/relheight) — fully-custom Windows resize"
    - "ButtonPress/B1-Motion/ButtonRelease binding lambda с default-arg edge=edge_name для замыкания"
    - "CTkProgressBar + after(0, cb, arg) для thread-safe прогресс из daemon-потока"
    - "Slide-down + ease-out quadratic fade-in (200ms, 8 шагов)"
key_files:
  created: []
  modified:
    - "client/ui/main_window.py (+104 строк / -33)"
    - "client/ui/update_banner.py (+174 строк / -28)"
decisions:
  - "CTkFrame в transparent-режиме перехватывает клики — подходит для invisible edge-zones"
  - "Углы lift()ятся после сторон чтобы их cursor перекрывал cursor стороны в пересечении"
  - "width/height обязательны в конструкторе CTkFrame (не в place) — отличие от tk.Frame"
  - "Theme баннера не subscribed — читается один раз в __init__ (баннер живёт секунды)"
requirements:
  - UI-RESIZE-EDGES
  - UI-UPDATE-BANNER-REDESIGN
metrics:
  duration_minutes: 10
  completed_date: "2026-04-22"
  tasks_completed: 2
  commits: 2
---

# Quick 260422-tah: Resize edges + UpdateBanner redesign

**One-liner:** Замена одного resize-grip в углу на 8 invisible edge-zones по периметру + редизайн
UpdateBanner с 340×96 debug-плашки в 420×170 с accent-strip, круглой иконкой, CTkProgressBar и
slide+fade анимацией.

## Что сделано

### Task 1 — Resize edges по всему периметру (commit `3368198`)

Удалён `_build_resize_grip` + `_on_grip_drag_start/motion` + поле `_resize_grip` и
соответствующий блок в `_apply_theme`.

Добавлено:
- Поля `_resize_edge`, `_resize_start_win_x/y`, `_edge_zones: list` в `__init__`.
- Метод `_build_edge_resizers(parent)` создаёт 8 `CTkFrame(fg_color="transparent")` и
  размещает их через `place()`:
  - 4 стороны 6px (`"n"`, `"s"`, `"e"`, `"w"`) с курсорами `sb_v_double_arrow` / `sb_h_double_arrow`
  - 4 угла 10×10 (`"nw"`, `"ne"`, `"sw"`, `"se"`) с курсорами `size_nw_se` / `size_ne_sw`
  - Углы создаются **после** сторон — `lift()` последовательно обеспечивает корректный z-order
  - Для каждой зоны bind `<ButtonPress-1>` → `_on_edge_press`, `<B1-Motion>` → `_on_edge_drag`,
    `<ButtonRelease-1>` → `_on_edge_release`
- `_on_edge_press` запоминает начальные размеры/позицию окна и edge-строку
- `_on_edge_drag` пересчитывает geometry по наличию `"n"`, `"s"`, `"e"`, `"w"` в edge-строке:
  - `"e"` → расширяет вправо (x не меняется)
  - `"w"` → расширяет влево (меняет `new_x` одновременно)
  - `"s"` → расширяет вниз
  - `"n"` → расширяет вверх (меняет `new_y` одновременно)
  - MIN_SIZE=(320,320) соблюдается через `max(MIN, ...)`
- `_on_edge_release` вызывает `_save_window_state()` — размер + позиция сохраняются в settings.json

Интеграция в `_build_ui`: `_build_edge_resizers(self._root_frame)` после `_rebuild_day_sections`
(чтобы `lift()` работал поверх всего контента).

### Task 2 — UpdateBanner redesign (commit `c445dd3`)

Переписан UI-layout `UpdateBanner.__init__` и обновлены callbacks `_on_update_click`,
`_on_download_failed`, добавлены методы `_animate_in`, `_update_progress`.

**Публичный API `__init__(root, theme_manager, updater, new_version, download_url, sha256)`
не изменён** — `app.py` (`_show_update_banner`) продолжает работать без правок.

Структура:
```
_banner (CTkToplevel)
  └─ _frame (corner_radius=12, border 1px)
       ├─ _accent_strip (width=4, accent_brand, side=left, fill=y)
       └─ content (padx=16, pady=14)
            ├─ top_row
            │    ├─ icon_frame (48×48, corner_radius=24, accent_brand, символ ⬇ 22pt bold #FFFFFF)
            │    └─ text_col: _title (h1) + _status (body)
            ├─ _progress_row (создан, НЕ pack'нут)
            │    ├─ _progress (CTkProgressBar 280×8, progress_color=accent_brand, fg=bg_tertiary)
            │    └─ _pct_label ("0%", caption)
            └─ _btn_row
                 ├─ _dismiss_btn (Позже, transparent + border)
                 └─ _update_btn (Обновить, accent_brand)
```

Анимация: `_reposition_and_show` ставит окно в правый верхний угол с `alpha=0` и `y = final_y-20`,
затем `_animate_in` 8 шагов по 25ms (всего 200ms) — ease-out quadratic для alpha и slide-down.

Progress flow:
- `_on_update_click` отключает кнопки, pack'ит `_progress_row` перед `_btn_row` и запускает
  `_download_worker` в daemon-потоке
- `_download_worker` передаёт progress callback `lambda done,total: root.after(0, _update_progress, done/total)`
- `_update_progress(frac)` вызывает `_progress.set(frac)` и `_pct_label.configure(text=f"{int(frac*100)}%")`
- На failure — `_on_download_failed` скрывает `_progress_row`, показывает "Ошибка. Проверь интернет."
  цветом `accent_overdue`, кнопка становится "Повторить"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] CustomTkinter CTkFrame не принимает width/height в place()**

- **Found during:** Task 1 — первый запуск `test_main_window.py` упал с
  `ValueError: 'width' and 'height' arguments must be passed to the constructor of the widget,
  not the place method`
- **Issue:** План указывал `place(relx=0, rely=0, relwidth=1, height=6)` для edge-полос, но
  CTkFrame (в отличие от tk.Frame) требует `width`/`height` в конструкторе
- **Fix:** Перенёс `width`/`height` из place() в конструктор CTkFrame; `relwidth`/`relheight`
  остались в place() для растяжения по одной оси
- **Files modified:** `client/ui/main_window.py` (только Task 1 — исправление в рамках того же коммита)
- **Commit:** `3368198`
- **Impact:** MIN_SIZE, cursor'ы и поведение drag'а не затронуты — чисто конструкторский
  workaround для CTk-specific API

## Verification

### Automated

**Task 1:**
```
python -c "from client.ui.main_window import MainWindow; assert hasattr(MainWindow, '_build_edge_resizers'); assert hasattr(MainWindow, '_on_edge_press'); assert hasattr(MainWindow, '_on_edge_drag'); assert hasattr(MainWindow, '_on_edge_release'); assert not hasattr(MainWindow, '_build_resize_grip'); print('OK')"
→ OK
```

**Task 2:**
```
python -c "import ast; tree = ast.parse(open('client/ui/update_banner.py', encoding='utf-8').read()); cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'UpdateBanner'); methods = {m.name for m in cls.body if isinstance(m, ast.FunctionDef)}; required = {'__init__', '_reposition_and_show', '_animate_in', '_update_progress', '_on_update_click', '_download_worker', '_on_download_failed', '_apply_and_exit', '_dismiss'}; missing = required - methods; assert not missing, f'Missing: {missing}'; src = open('client/ui/update_banner.py', encoding='utf-8').read(); assert 'WIDTH = 420' in src and 'HEIGHT = 170' in src; assert 'CTkProgressBar' in src; assert 'accent_strip' in src or 'accent_brand' in src; print('OK')"
→ OK
```

**Regression (test_main_window.py):**
```
python -m pytest client/tests/ui/test_main_window.py --tb=short
→ 28 passed in 7.05s
```

**Smoke test UpdateBanner (signature совместимость с app.py):**
```
python -c "import customtkinter as ctk; from client.ui.themes import ThemeManager; ...
b = UpdateBanner(root, tm, um, '0.7.0', 'http://example.invalid/test.exe', '')
assert hasattr(b, '_title'), '_status', '_update_btn', '_dismiss_btn', '_progress',
                '_progress_row', '_pct_label', '_btn_row', '_accent_strip', '_downloading'
→ smoke test OK — all expected attrs present
```

### Manual UAT (deferred to owner)

Checkpoint `human-verify` пропущен по явному указанию пользователя — UAT проводится отдельно:
1. Resize — потянуть за все 8 edge-zones, проверить MIN_SIZE, сохранение размера после рестарта
2. UpdateBanner — запустить инжект-снипет из PLAN (ThemeManager('light'/'dark'/'beige'),
   кликнуть "Обновить" — progress_row появляется, затем ошибка "Проверь интернет." с
   accent_overdue цветом)

## Known Stubs

Нет. Обе правки полностью функциональны — никаких placeholder'ов или mock-данных.

## Self-Check: PASSED

- [x] `client/ui/main_window.py` — модифицирован, изменения проверены
- [x] `client/ui/update_banner.py` — модифицирован, изменения проверены
- [x] Commit `3368198` найден в `git log`
- [x] Commit `c445dd3` найден в `git log`
- [x] Все 28 тестов `test_main_window.py` зелёные
- [x] Smoke test UpdateBanner подтверждает signature совместимость
- [x] Deviation (Rule 3 — CTkFrame width/height) зафиксирована
