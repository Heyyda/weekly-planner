---
phase: 03-overlay-system
plan: 02
subsystem: ui
tags: [customtkinter, themes, settings, dataclass, winreg]

# Dependency graph
requires:
  - phase: 02-client-core
    provides: LocalStorage.load_settings/save_settings (transport для SettingsStore)

provides:
  - ThemeManager с 3 палитрами (light/dark/beige) verbatim из UI-SPEC + subscriber/notify pattern
  - PALETTES dict с 11 токенами на тему + FONTS dict (Segoe UI Variable + Cascadia Code)
  - UISettings dataclass (9 полей) + SettingsStore обёртка над LocalStorage
  - 25 unit-тестов покрывающих темизацию и сериализацию настроек

affects: [03-overlay-system (plans 03-10)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Subscribe/notify: виджеты регистрируют callback через ThemeManager.subscribe(), получают palette dict при set_theme()"
    - "from_dict/to_dict round-trip с фильтрацией неизвестных ключей через dataclasses.fields()"
    - "validate() метод на dataclass для backward compat (невалидные значения → defaults)"

key-files:
  created:
    - client/ui/themes.py
    - client/ui/settings.py
    - client/tests/ui/test_themes.py
    - client/tests/ui/test_settings.py
  modified: []

key-decisions:
  - "PALETTES dict полностью verbatim из UI-SPEC — никакого изобретения hex-значений"
  - "shadow_card хранится как rgba() строка (не hex) — Tkinter не поддерживает alpha, но значение должно быть доступно для Pillow/CSS"
  - "SettingsStore — тонкая обёртка, вся I/O логика остаётся в LocalStorage (принцип из D-25)"
  - "ThemeManager.detect_system_theme() — staticmethod, принимает mock через monkeypatch winreg"
  - "UISettings.overlay_position как list[int] (не tuple) — JSON round-trip совместимость"

patterns-established:
  - "ThemeManager.subscribe(cb) — каждый Phase 3 виджет вызывает при создании, получает palette при set_theme"
  - "UISettings.from_dict() фильтрует unknown keys — безопасно при добавлении полей в будущих планах"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-04-16
---

# Phase 03 Plan 02: ThemeManager + SettingsStore Summary

**ThemeManager с 3 warm-палитрами verbatim из UI-SPEC (#F5EFE6/#1F1B16/#E8DDC4) + subscribe/notify + UISettings dataclass с round-trip JSON через существующий LocalStorage**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-16T06:53:55Z
- **Completed:** 2026-04-16T06:56:35Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Переписан client/ui/themes.py: PALETTES с 3 темами (11 токенов на тему) verbatim из UI-SPEC, FONTS dict (Segoe UI Variable + Cascadia Code), ThemeManager с subscribe/set_theme/get/detect_system_theme
- Создан client/ui/settings.py: UISettings dataclass (9 полей, defaults Phase 3), SettingsStore обёртка без новой I/O логики
- 25 unit-тестов зелёных (14 themes + 11 settings), Phase 2 регрессия (test_storage.py) зелёная

## Task Commits

1. **Task 1: ThemeManager — 3 палитры UI-SPEC + subscribe/notify** - `3ccbd49` (feat)
2. **Task 2: UISettings dataclass + SettingsStore обёртка** - `8e623e2` (feat)

## Files Created/Modified

- `client/ui/themes.py` — Полностью переписан: PALETTES (3 темы × 11 токенов), FONTS, ThemeManager класс
- `client/ui/settings.py` — Новый: UISettings dataclass + SettingsStore обёртка над LocalStorage
- `client/tests/ui/test_themes.py` — 14 unit-тестов (палитры verbatim, subscribe, system theme, fallback)
- `client/tests/ui/test_settings.py` — 11 unit-тестов (defaults, round-trip, validate, store load/save)

## Decisions Made

- PALETTES verbatim из UI-SPEC без изменений — hex не изобретались
- shadow_card хранится как rgba() строка, так как в UI-SPEC это значение (Tkinter не использует напрямую, но Pillow/CSS-совместимость важна)
- SettingsStore — тонкая обёртка, вся I/O логика в LocalStorage (принцип D-25 CONTEXT.md)
- overlay_position/window_position как list[int] — JSON round-trip совместимость (json.load возвращает list, не tuple)
- detect_system_theme() — staticmethod для лёгкого mockability через monkeypatch("winreg.OpenKey")

## Deviations from Plan

Небольшое дополнение к плану:

**1. [Rule 2 - Missing] Добавлен тест test_each_palette_has_11_tokens**
- **Found during:** Task 1 (написание тестов)
- **Issue:** План не включал тест что все 3 палитры имеют ровно 11 токенов — без этого теста можно случайно потерять токен
- **Fix:** Добавлен дополнительный тест (14й вместо 13ти) — итого 14 tests в test_themes.py
- **Impact:** Нулевой — extra coverage, не scope creep

В остальном план выполнен точно по спецификации.

## Issues Encountered

None — все тесты прошли с первого запуска после написания реализации.

## Known Stubs

None — все поля UISettings имеют корректные defaults, SettingsStore полностью подключён к LocalStorage.

## User Setup Required

None — нет внешних сервисов.

## Next Phase Readiness

- `from client.ui.themes import ThemeManager, PALETTES, FONTS` — готово для Plans 03-03..03-10
- `from client.ui.settings import UISettings, SettingsStore` — готово для Plans 03-03..03-10
- ThemeManager.subscribe() — вызывать в каждом Phase 3 виджете при создании
- SettingsStore.load() — вызывать в WeeklyPlannerApp._setup() до создания overlay/window

---
*Phase: 03-overlay-system*
*Completed: 2026-04-16*
