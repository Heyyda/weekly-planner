---
phase: "03-overlay-system"
plan: "03"
subsystem: "client/ui"
tags: [pillow, icon, overlay, tray, pulse, badge, tdd]
dependency_graph:
  requires:
    - "01-01: базовая структура проекта, client/ui/__init__.py"
  provides:
    - "render_overlay_image() — публичный API для Plans 03-04, 03-05, 03-07"
    - "client/ui/icon_compose.py — Pillow-фабрика иконки"
  affects:
    - "03-04: OverlayManager импортирует render_overlay_image для canvas"
    - "03-05: PulseAnimator использует pulse_t параметр"
    - "03-07: TrayManager использует size=16/32 для tray icon"
tech_stack:
  added:
    - "Pillow: Image, ImageDraw.rounded_rectangle, line, ellipse"
  patterns:
    - "TDD RED→GREEN: failing import → passing 12 тестов"
    - "Pillow gradient via pixel-by-pixel + rounded_rectangle mask (Pattern 3 из RESEARCH.md)"
    - "Triangle-wave interpolation для pulse_t (D-02)"
key_files:
  created:
    - "client/ui/icon_compose.py"
    - "client/tests/ui/test_icon_compose.py"
  modified: []
decisions:
  - "Тест-координаты для badge: (44, 4) вместо центра (48, 8) — центр перекрыт текстом badge"
  - "Gradient через pixel-by-pixel fill + L-mask, а не ImageFilter.GaussianBlur (точнее)"
  - "pulse_t > 1.0 обрабатывается как периодичность: t = t - int(t)"
metrics:
  duration: "~4 минуты"
  completed_date: "2026-04-16"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 03 Plan 03: icon_compose.py — Pillow-фабрика иконки overlay/tray — Summary

## One-liner

Pillow-фабрика `render_overlay_image()` с gradient, rounded corners, checkmark/plus, pulse-интерполяцией и badge — DRY-модуль для Plans 03-04, 03-05, 03-07.

## What Was Built

`client/ui/icon_compose.py` — единственный публичный модуль:

- **`render_overlay_image(size, state, task_count, overdue_count, pulse_t)`** — фабрика, возвращающая `PIL.Image.Image` (RGBA).
- **`_draw_gradient_rounded()`** — вертикальный градиент top→bottom с clip по rounded_rectangle mask.
- **`_draw_checkmark()`** — белая галочка Things 3 стиль, chunky stroke.
- **`_draw_plus()`** — белый плюс для empty-state.
- **`_draw_badge()`** — белый ellipse в правом верхнем углу с тёмным числом.
- **`_lerp_rgb()`** — линейная интерполяция RGB per-channel.

Цветовые константы verbatim из UI-SPEC:
- `OVERLAY_BLUE_TOP = (78, 161, 255)` — #4EA1FF
- `OVERLAY_BLUE_BOTTOM = (30, 115, 232)` — #1E73E8
- `OVERLAY_RED_TOP = (232, 90, 90)` — #E85A5A
- `OVERLAY_RED_BOTTOM = (192, 53, 53)` — #C03535

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Failing tests (12 тестов) | 5268b95 | client/tests/ui/test_icon_compose.py |
| GREEN | icon_compose.py + тест-корректировки | 724294e | client/ui/icon_compose.py, client/tests/ui/test_icon_compose.py |

## Verification

```
pytest client/tests/ui/test_icon_compose.py -v
12 passed in 0.06s
```

Все 12 тестов зелёные:
1. `test_returns_pil_image_correct_size` — PIL.Image, 56×56, RGBA
2. `test_corner_pixel_transparent_rounded_clip` — угол (0,0) alpha=0
3. `test_center_pixel_not_transparent` — центр (28,28) alpha>0
4. `test_empty_state_has_plus_center_white` — плюс в центре белый
5. `test_badge_appears_when_count_positive_and_size_large` — badge белый при count>0, size>=32
6. `test_no_badge_when_count_zero` — нет badge при count=0
7. `test_no_badge_on_small_icon` — нет badge при size=16
8. `test_overdue_pulse_zero_is_blue` — pulse_t=0 → синий фон (B>R)
9. `test_overdue_pulse_half_is_red` — pulse_t=0.5 → красный фон (R>B)
10. `test_overdue_badge_shows_overdue_count` — overdue badge при overdue_count>0
11. `test_robust_against_pulse_t_out_of_range` — нет crash при pulse_t=1.5 или -0.3
12. `test_tray_size_16_solid_fill` — size=16 возвращает 16×16

## Deviations from Plan

### Adjustment — Тест-координаты для badge

**Найдено во время:** GREEN phase — первый запуск тестов.

**Проблема:** Тест проверял пиксель (48, 8) — центр badge ellipse. Но именно там рендерится текст badge (число задач), поэтому пиксель серый (~195,195,195), а не чисто белый (255,255,255).

**Исправление:** Тесты badge (Test 5, 6, 10) переключены с (48, 8) на (44, 4) — устойчиво внутри ellipse и вне зоны текста. Тест сохраняет семантику (проверяет наличие/отсутствие белого badge-региона).

**Файлы:** `client/tests/ui/test_icon_compose.py`

## Known Stubs

Нет — `icon_compose.py` не имеет stub-данных, все данные поступают через параметры.

## Decisions Made

1. **Pixel-by-pixel gradient + mask:** Используем `Image.paste()` построчно вместо более сложного ImageFilter подхода — 56×56px small enough, явный и понятный код.

2. **pulse_t > 1.0 — периодичность:** Значения > 1.0 нормализуются через `t = t - int(t)` (не ошибка, не clamp). Позволяет pulse animator использовать монотонно растущий счётчик без обёртки.

3. **badge text font:** Дефолтный Pillow bitmap font (не truetype). Избегает проблем с путями к системным шрифтам в PyInstaller frozen exe (Pitfall 7 аналог).

4. **Badge draw без `bsize-1` в ellipse bounds:** `draw.ellipse([(bx, by), (bx + bsize - 1, by + bsize - 1)])` — на 1px меньше чтобы ellipse вмещался ровно в bsize×bsize.

## Self-Check

- [x] `client/ui/icon_compose.py` exists
- [x] `client/tests/ui/test_icon_compose.py` exists
- [x] Commit 5268b95 exists (RED)
- [x] Commit 724294e exists (GREEN — feat + updated tests)
- [x] 12 тестов проходят
- [x] Все 4 UI-SPEC hex-константы в коде
