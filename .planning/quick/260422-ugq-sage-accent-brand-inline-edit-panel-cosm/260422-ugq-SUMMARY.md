---
phase: quick-260422-ugq
plan: 01
subsystem: ui/themes + ui/inline-edit
tags: [ux, polish, theme, sage, inline-edit, cosmetics]
requires: [theme-manager, customtkinter]
provides: [sage-brand-accent, inline-edit-sage-cosmetics, _blend_hex]
affects: [day_section.today_strip, update_banner.icon/progress/button, task_widget accent usage]
tech-stack:
  added: []
  patterns: [subscribe/notify theme, linear-hex-blending]
key-files:
  modified:
    - client/ui/themes.py
    - client/ui/inline_edit_panel.py
    - client/tests/ui/test_themes.py
    - client/tests/test_infrastructure.py
  created: []
decisions:
  - "sage (#7A9B6B/#94B080/#6B8B5C) заменяет electric-blue как accent_brand — UX-решение владельца для консистентности с sage-overlay (9d150b2)"
  - "CTkOptionMenu дефолтные цвета синие → пришлось явно передавать fg_color/button_color/hover/dropdown_* из темы"
  - "border inline-панели через _blend(bg_secondary, text_tertiary, 0.35) — soft-tonal вместо контрастного border_window"
  - "Тесты test_themes.py и test_infrastructure.py обновлены под новые sage-значения (Rule 3 blocking fix)"
metrics:
  duration: ~10min
  completed: 2026-04-22
---

# Quick 260422-ugq: Sage accent_brand + inline-edit panel cosmetics — Summary

**One-liner:** Unification accent-бренда на sage-зелёный во всех трёх палитрах + визуальная консистентность inline-edit панели (явные sage OptionMenu/Save, soft border через hex-блендинг, top-отступ 20px).

## Objective recap

До коммита `accent_brand` был электрик-синий (`#1E73E8` / `#4EA1FF` / `#2966C4`) — диссонировал с тёплым cream/warm-dark/beige фоном и новым sage-overlay (9d150b2). Inline-edit панель рендерила дефолтные CTk-синие OptionMenu/Save вместо бренд-акцента. Плюс резкий border (`border_window`) и отступ 12px делали панель "прилипшей" к верху.

## Что сделано

### Часть A — `client/ui/themes.py`
6 hex-замен в PALETTES:

| Палитра | Ключ | Было | Стало |
|---------|------|------|-------|
| light | accent_brand | #1E73E8 | **#7A9B6B** (sage) |
| light | accent_brand_light | #4EA1FF | **#9DBC8A** (sage hover) |
| dark | accent_brand | #4EA1FF | **#94B080** (brighter sage) |
| dark | accent_brand_light | #85BFFF | **#AEC9A2** (sage hover dark) |
| beige | accent_brand | #2966C4 | **#6B8B5C** (muted sage) |
| beige | accent_brand_light | #4E86DA | **#8CA87D** (sage hover beige) |

Остальные ключи (bg_*, text_*, accent_done, accent_overdue, shadow_card, border_window) не трогались.

### Часть B — `client/ui/inline_edit_panel.py` — явные accent-цвета
Четыре виджета получили `fg_color=self._theme.get("accent_brand")` (и связанные параметры):

1. **Day CTkOptionMenu** (`_build_ui` day-column): +6 параметров (fg/button/hover/dropdown-fg/dropdown-text/text_color="#FFFFFF")
2. **HH CTkOptionMenu** (`self._hh_menu`): те же 6 параметров. Рантайм-dim через `_set_time_menus_dim()` работает (configure(text_color=...) перекрывает initial "#FFFFFF" без конфликтов)
3. **MM CTkOptionMenu** (`self._mm_menu`): аналогично HH
4. **save_btn CTkButton**: +3 параметра (fg_color/hover_color/text_color)

### Часть C — `inline_edit_panel.py` cosmetics
1. **Top-отступ:** `self._slide(target_y=12, step=0)` → `target_y=20` (на 8px ниже от верха)
2. **Soft border:** `border = self._theme.get("border_window")` → `border = self._blend_hex(bg_secondary, text_tertiary, 0.35)` — border получается в тон фона, на 35% смещённый к tertiary тексту, визуально мягкий
3. **Новый staticmethod `InlineEditPanel._blend_hex(a, b, t)`** — линейная интерполяция двух hex-цветов. Избегнута коллизия имён: blue-компонент назван `bl` (не `b`) т.к. `b` — имя параметра

### Обновлённые тесты (deviation, Rule 3 — blocking fix)
Старые тесты в `test_themes.py` и `test_infrastructure.py` пинили electric-blue hex ("verbatim из UI-SPEC"). После изменения PALETTES они падали. Обновлены assertions на новые sage-значения, с комментарием про "UX-решение post-UI-SPEC":

- `test_light_palette_exact_hex_per_ui_spec`: #1E73E8/#4EA1FF → #7A9B6B/#9DBC8A
- `test_dark_palette_exact_hex_per_ui_spec`: #4EA1FF → #94B080
- `test_beige_palette_exact_hex_per_ui_spec`: #2966C4 → #6B8B5C
- `test_get_returns_hex_from_current_palette`: #4EA1FF → #94B080 (dark)
- `test_mock_theme_manager_light`: #1E73E8 → #7A9B6B (light)

## Verification

### Automated (pytest)
```
python -m pytest client/tests/ui/ \
  --ignore=client/tests/ui/test_e2e_phase3.py \
  --ignore=client/tests/ui/test_e2e_phase4.py \
  -q
# → 323 passed in 21.04s
```
Также targeted: `test_themes.py` (17 tests), `test_main_window.py`, `test_infrastructure.py` — все зелёные.

### Grep-маркеры
- `fg_color=self._theme.get("accent_brand")` → 4 совпадения в `inline_edit_panel.py` (3 OptionMenu + save_btn) ✓
- `target_y=20` → 1 совпадение (open-анимация) ✓
- `border = self._blend_hex` → 1 совпадение ✓
- `InlineEditPanel._blend_hex("#000000", "#FFFFFF", 0.5) == "#7F7F7F"` ✓
- `PALETTES["light"]["accent_brand"] == "#7A9B6B"` ✓ (и ещё 5 sage-значений)

### Ignored (pre-existing)
- `test_e2e_phase3.py` / `test_e2e_phase4.py` — Tcl `image "pyimageNN" doesn't exist` (проблема конфликта CTk image-ресурсов между тестами, существовала до этого quick-задания)

## Side-effects (осознанные)
Через ThemeManager.subscribe новые sage-цвета автоматически применились к:
- `DaySection.today_strip` (использует accent_brand для "сегодняшней" полосы)
- `UpdateBanner.icon_frame/progress/update_btn` (accent_brand для иконки/прогрессбара/CTA)
- `TaskWidget` где акцент используется
- Любые другие виджеты, подписанные на accent_brand/accent_brand_light

Визуально они становятся **теплее и консистентнее** общей cream/sage-тематике — позитивный side-effect, ожидаемый.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Обновлены тесты test_themes.py и test_infrastructure.py**
- **Found during:** верификация pytest client/tests/ui/
- **Issue:** 4 теста в test_themes.py + 1 в test_infrastructure.py ассертили старые electric-blue hex-значения ("verbatim UI-SPEC"). После замены палитры на sage — падают.
- **Fix:** Обновил assertions на новые sage-hex'ы, добавил inline-комментарии "UX-решение post-UI-SPEC, quick 260422-ugq". Формально UI-SPEC остаётся источником правды на уровне документа — но для конкретно accent_brand зафиксировано post-решение владельца.
- **Files modified:** `client/tests/ui/test_themes.py`, `client/tests/test_infrastructure.py`
- **Commit:** 5f2a037 (один коммит с основным изменением)

## Deferred Issues
Нет. Все 323 UI теста зелёные.

## Known Stubs
Нет.

## Commits
| Hash | Message |
|------|---------|
| `5f2a037` | ui(inline-edit): sage accent_brand + явные fg_color OptionMenu/Save + soft border + top-отступ 20px |

## Self-Check: PASSED

- client/ui/themes.py — изменён, PALETTES.light/dark/beige.accent_brand — sage ✓
- client/ui/inline_edit_panel.py — _blend_hex существует, 4 fg_color marker, target_y=20 ✓
- client/tests/ui/test_themes.py — обновлён, тесты зелёные ✓
- client/tests/test_infrastructure.py — обновлён, тест зелёный ✓
- commit 5f2a037 существует в git log ✓
- 323 / 323 UI тестов passed (за исключением pre-existing e2e_phase3/4 Tcl-error) ✓
