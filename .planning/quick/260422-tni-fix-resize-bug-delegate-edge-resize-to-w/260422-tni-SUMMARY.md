---
phase: quick-260422-tni
plan: 01
subsystem: client/ui/main_window
tags: [bugfix, win32, resize, ctypes, overrideredirect]
requires: []
provides:
  - "Edge-resize через нативный Win32 WM_NCLBUTTONDOWN (8 направлений)"
affects:
  - "client/ui/main_window.py"
tech-stack:
  added: []
  patterns:
    - "Win32 WM_NCLBUTTONDOWN delegation: ReleaseCapture + SendMessageW(hwnd, 0x00A1, HT_*, 0)"
key-files:
  created: []
  modified:
    - "client/ui/main_window.py"
decisions:
  - "Переход с Python <B1-Motion> drag-цикла на Win32 SendMessage — надёжный паттерн для overrideredirect окон"
  - "minsize уважается через WM_GETMINMAXINFO (не требует кода на Python)"
  - "Persist window geometry работает автоматом: <Configure> → settings в памяти → flush в _on_close"
metrics:
  duration: "~10 минут"
  completed_date: "2026-04-22"
commit: 51a662d
---

# Quick 260422-tni: Fix resize bug — delegate edge-resize to Windows Summary

Баг: edge-resize главного окна через Python `<B1-Motion>` handlers был ненадёжен на `overrideredirect(True)` окне — окно увеличивалось только по y, не уменьшалось обратно, event coords drift между zones. Исправлено делегацией Win32: `ReleaseCapture() + SendMessageW(hwnd, WM_NCLBUTTONDOWN, HT_*, 0)` — Windows сам ведёт drag-цикл как для native-рамки.

## Что сделано

### `client/ui/main_window.py`

**Добавлено:**
- Класс-константы `HT_MAP` (8 hit-test кодов: HT_TOP=12, HT_BOTTOM=15, HT_LEFT=10, HT_RIGHT=11, HT_TOPLEFT=13, HT_TOPRIGHT=14, HT_BOTTOMLEFT=16, HT_BOTTOMRIGHT=17) и `_WM_NCLBUTTONDOWN=0x00A1` на уровне `MainWindow` рядом с `MIN_SIZE`.

**Переписано:**
- `_on_edge_press(event, edge)` — теперь одна Win32-делегация вместо запоминания координат:
  - `user32.GetParent(widget_hwnd)` → настоящий hwnd окна (fallback на widget_hwnd если 0)
  - `user32.ReleaseCapture()` ОБЯЗАТЕЛЕН до SendMessageW — иначе Windows не переключится в resize-mode
  - `user32.SendMessageW(hwnd, 0x00A1, HT_*, 0)` — отдаём управление OS
  - Wrapping `try/except Exception` + `logger.debug` на случай если `ctypes.windll.user32` недоступен

**Удалено:**
- Методы `_on_edge_drag` (26 строк) и `_on_edge_release` (6 строк) — больше не нужны.
- 7 атрибутов из `__init__`: `_resize_start_w`, `_resize_start_h`, `_resize_start_x`, `_resize_start_y`, `_resize_edge`, `_resize_start_win_x`, `_resize_start_win_y`.
- 2 bind-а в `_build_edge_resizers`: `<B1-Motion>` и `<ButtonRelease-1>`. Остался только `<ButtonPress-1>`.

**Сохранено без изменений:**
- `_edge_zones` список, `_build_edge_resizers` разметка 8 зон, cursor-ы, `lift()`.
- `<Configure>` bind → `_on_configure` обновляет `settings.window_size/position` в памяти при любом resize (в том числе Win32-initiated).
- `_save_window_state()` вызывается в `_on_close` — persist работает сам.
- `self._window.minsize(*MIN_SIZE)` уже в `__init__` — Windows видит через `WM_GETMINMAXINFO`.
- `logger = logging.getLogger(__name__)` уже на уровне модуля (строка 44).

### Метрика упрощения

| Было | Стало |
|------|-------|
| 3 метода (`_on_edge_press`, `_on_edge_drag`, `_on_edge_release`) | 1 метод (`_on_edge_press`) |
| 7 `_resize_*` атрибутов | 0 |
| 3 bind-а на zone (`ButtonPress`, `B1-Motion`, `ButtonRelease`) | 1 bind (`ButtonPress`) |
| net +49 / −52 строки |

## Как проверено

**Automated:**
- `python -m py_compile client/ui/main_window.py` → OK
- `grep "_on_edge_drag\|_on_edge_release\|_resize_edge\|_resize_start"` → 0 совпадений
- `grep "SendMessageW\|WM_NCLBUTTONDOWN\|HT_MAP"` → 10 совпадений (>= 3 требуется)
- `python -m pytest client/tests/ui/test_main_window.py -q` → **28 passed**

**UAT (Task 2) отложен на пользователя** — проверить вручную все 8 edge-zones:
1. `python main.py`, дождаться главного окна.
2. Правый/левый edge → тяга меняет ширину (увеличение И уменьшение).
3. Нижний/верхний edge → тяга меняет высоту.
4. 4 угла (nw/ne/sw/se) → диагональная тяга меняет оба измерения.
5. Попытка сжать меньше MIN_SIZE (320×320) → должна остановиться.
6. Закрыть/открыть → новая геометрия сохранилась.
7. Drag за title-bar всё ещё работает (не трогали этот код).

## Коммит

- `51a662d` — fix(quick-260422-tni): делегировать edge-resize Win32 через WM_NCLBUTTONDOWN

## Deviations from Plan

Нет — план выполнен ровно как написан. Task 2 (UAT checkpoint) пропущен по явной инструкции пользователя в constraints ("Human-verify checkpoint пропусти — пользователь проверит UAT вручную").

## Self-Check: PASSED

- File `client/ui/main_window.py` — modified, compiles, 28 тестов проходят.
- Commit `51a662d` — exists in `git log`.
- SUMMARY.md — создан.
