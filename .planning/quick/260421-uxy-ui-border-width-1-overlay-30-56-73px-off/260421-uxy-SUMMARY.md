---
phase: 260421-uxy-ui-border-width-1-overlay-30-56-73px-off
plan: 01
subsystem: ui
type: quick
tags: [ui, overlay, icon, theme, resize]
requirements: [UI-ICON-01, UI-BORDER-01, UI-OVERLAY-73, UI-RESIZE-01]
requires: []
provides:
  - scripts/generate_icon.py — Pillow-генератор иконки приложения (палитра темы)
  - client/ui/themes.py::PALETTES[*].border_window — новый токен рамки окна
  - client/ui/overlay.py::OverlayManager.OVERLAY_SIZE=73 — увеличенный overlay
  - client/ui/main_window.py — явный resizable + CTkFrame с border_width=1
affects:
  - client/app.py::_on_overlay_right_click — использует OverlayManager.OVERLAY_SIZE
  - client/ui/quick_capture.py::show_at_overlay — default overlay_size=73
tech_stack:
  added: []
  patterns:
    - Supersampling 3× + LANCZOS при генерации multi-size ICO
    - Fractional size coefficients (12/56, 16/56) вместо литералов — масштабируются на любой size
    - Палитра-токен для границы окна (border_window) через ThemeManager.subscribe
key_files:
  created:
    - scripts/generate_icon.py
  modified:
    - client/assets/icon.ico
    - client/assets/icon.png
    - client/ui/themes.py
    - client/ui/main_window.py
    - client/ui/overlay.py
    - client/app.py
    - client/ui/quick_capture.py
    - client/tests/ui/test_overlay.py
    - client/tests/ui/test_quick_capture.py
    - client/tests/ui/test_themes.py
decisions:
  - Рамка окна — новый токен border_window, а не переиспользование существующих (границы окна и кнопок концептуально разные)
  - Генератор иконки — отдельный script в scripts/, не в client/ (разовый build-time artefact)
  - icon_compose.py НЕ тронут: фракции 12/56 и 16/56 корректно работают для любого size (13/64 ≈ 12/56×73/64)
metrics:
  tasks: 3
  duration: "~10 минут"
  completed_date: "2026-04-21"
---

# Quick 260421-uxy: UI border 1px + overlay 73px + новая иконка — Summary

UI-полировка: генератор иконки через Pillow (палитра темы крем+синий), видимая серая рамка 1px вокруг главного окна (новый токен `border_window` во всех 3 темах), overlay-кнопка на рабочем столе увеличена с 56 до 73px (+30%), явный `resizable(True, True)` для главного окна.

## Tasks Completed

- [x] **Task 1** — Генератор иконки `scripts/generate_icon.py` + обновлённые `client/assets/icon.ico` (6 размеров) и `client/assets/icon.png` (256×256)
  - **Commit:** `a622600`
- [x] **Task 2** — Токен `border_window` во всех 3 палитрах + `_root_frame` с `border_width=1` + `resizable(True, True)` + обновление `_apply_theme`
  - **Commit:** `063ffc9`
- [x] **Task 3** — `OVERLAY_SIZE = 73`, убран хардкод `56` в `app.py:363` и `quick_capture.py:53`, обновлены 3 теста
  - **Commit:** `4cdbafe`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Fix: `ValueError: y1 must be greater than or equal to y0` в `scripts/generate_icon.py`**
- **Found during:** Task 1 (первый запуск генератора)
- **Issue:** `draw.rectangle([(0, radius), (hi-1, header_h)])` падает если `radius >= header_h`. На малых supersampling размерах header_h становился меньше чем radius, y1<y0.
- **Fix:** Гарантирую `header_h >= radius*2 + 2` и `fill_top = min(radius, header_h - 1)` с защитой `if header_h > fill_top`.
- **Files modified:** `scripts/generate_icon.py`
- **Commit:** включено в `a622600`

**2. [Rule 1 — Bug] Fix: `test_each_palette_has_11_tokens` после добавления `border_window` (регрессия Task 2)**
- **Found during:** После Task 2 при запуске полного UI suite
- **Issue:** Тест проверяет что в палитре ровно 11 токенов. После моего добавления `border_window` их стало 12.
- **Fix:** Переименовал в `test_each_palette_has_12_tokens`, добавил `border_window` в expected_tokens, обновил сообщение assert.
- **Files modified:** `client/tests/ui/test_themes.py`
- **Commit:** включено в `4cdbafe`

## Known Stubs

None. Задача — только UI-полировка (константы, токены, размеры), новых data-paths не создавалось.

## Deferred Issues (pre-existing, out of scope)

При запуске полного `pytest client/tests/ui/` обнаружено **11 pre-existing failures/errors**, НЕ связанных с этим планом:

1. **`test_e2e_phase3.py`** — 10 тестов падают с `_tkinter.TclError: invalid command name "tcl_findLibrary"` / `image "pyimageN" doesn't exist` при запуске в полном suite. В изоляции (`pytest test_e2e_phase3.py`) проходят 30/31. Это test-ordering issue (shared Tk state между `test_app_integration.py` и `test_e2e_phase3.py`) — проявляется и БЕЗ моих изменений.
2. **`test_app_integration.py::test_setup_unauthenticated_skips_main_components`** — падает с `TclError: invalid command name "tcl_findLibrary"` в полном suite. Pre-existing.
3. **`test_e2e_phase3.py::test_overlay_click_toggles_main_window`** — падает даже в изоляции (`main_window.is_visible() is True` fails). Pre-existing — не связан с overlay size или border.

Verification: stash'ил свои изменения, запускал те же тесты — падения идентичны. В скоп этого плана не входит — фиксим при необходимости отдельной задачей.

Задача в плане подтверждена валидной: на 3 целевых тест-файлах (`test_overlay.py`, `test_quick_capture.py`, `test_themes.py`) **46/46 passed**. На `test_main_window.py` — **23/23 passed**.

## Verification Passed

- `python scripts/generate_icon.py` — успешно сгенерировал `icon.ico` (размеры 16/32/48/64/128/256) + `icon.png` (256×256 RGBA)
- `from client.ui.themes import PALETTES` — все 3 палитры содержат `border_window`: light `#8A7D6B`, dark `#4A433B`, beige `#7A6B52`
- `from client.ui.overlay import OverlayManager` — `OVERLAY_SIZE == 73`
- `grep '\b56\b' client/` — осталось только в `icon_compose.py` (фракции 12/56, 16/56 — корректны), в `overlay.py` docstring (reference-только), в `test_icon_compose.py` (рендерят размер 56 для тестов — корректно).
- `pytest test_overlay.py test_quick_capture.py test_themes.py` — **46 passed**
- `pytest test_main_window.py` — **23 passed**

## Artifacts

### Новая иконка
- Путь: `client/assets/icon.ico` (multi-size ICO 16/32/48/64/128/256)
- Путь: `client/assets/icon.png` (PNG 256×256 RGBA — для winotify fallback)
- Пересборка: `python scripts/generate_icon.py`

### Токены палитры
- `border_window` в `PALETTES["light"] = "#8A7D6B"`
- `border_window` в `PALETTES["dark"] = "#4A433B"`
- `border_window` в `PALETTES["beige"] = "#7A6B52"`

## Rollback Notes

- **Overlay размер обратно на 56:** одна строка в `client/ui/overlay.py:77`:
  ```python
  OVERLAY_SIZE = 56  # px per UI-SPEC
  ```
  (всё остальное — `app.py`, `quick_capture.py`, `_validate_position`, `_clamp_to_virtual_desktop` — автоматически пересчитается через константу)

- **Убрать рамку:** в `client/ui/main_window.py:_build_ui` убрать `border_width=1` и `border_color=...`; в `_apply_theme` убрать `border_color=border` из configure.

- **Убрать resizable:** удалить строку `self._window.resizable(True, True)` — вернётся default-поведение CTkToplevel.

- **Откатить иконку:** `git checkout HEAD~3 -- client/assets/icon.ico client/assets/icon.png` (взять из коммита до `a622600`).

## Updated Tests

- `client/tests/ui/test_overlay.py` — переименован `test_overlay_size_is_56x56` → `test_overlay_size_is_73x73`
- `client/tests/ui/test_quick_capture.py` — 3 литерала `56` → `73` (строки 34, 62, 73)
- `client/tests/ui/test_themes.py` — переименован `test_each_palette_has_11_tokens` → `test_each_palette_has_12_tokens` (добавлен `border_window`)

## Self-Check: PASSED

- [x] `scripts/generate_icon.py` FOUND
- [x] `client/assets/icon.ico` FOUND (6 sizes)
- [x] `client/assets/icon.png` FOUND (256×256 RGBA)
- [x] Commit `a622600` FOUND (Task 1)
- [x] Commit `063ffc9` FOUND (Task 2)
- [x] Commit `4cdbafe` FOUND (Task 3)
- [x] All 3 target test files green (46/46)
- [x] `test_main_window.py` green (23/23) — регрессий по рамке нет
