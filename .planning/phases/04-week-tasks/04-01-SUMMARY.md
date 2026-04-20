# Plan 04-01 — Wave 0 Test Infrastructure — SUMMARY

**Phase:** 04-week-tasks
**Plan:** 04-01
**Status:** ✅ Complete
**Completed:** 2026-04-18
**Requirements:** (infrastructure — no REQ-IDs)

---

## What Was Built

**Task 1** — `client/tests/conftest.py` расширен 4 новыми Phase 4 фикстурами (Phase 3 сохранены без изменений):

- `timestamped_task_factory` — фабрика `Task` с `day_offset`, `time`, `done`, `text`, `user_id`, `position` параметрами. Создаёт UUID автоматически через `Task.new()`.
- `mock_storage` — инициализированный `LocalStorage(AppPaths())` на `tmp_appdata`. Готов к `add_task/update_task/soft_delete_task/get_visible_tasks`.
- `mock_theme_manager` — `ThemeManager('light')` без субскриберов. Отдаёт реальные hex палитры Phase 3.
- `dnd_event_simulator` — `MagicMock` events с `x_root/y_root/x/y/widget` атрибутами для DnD unit-тестов без реального `event_generate()`.

**Task 2** — `04-VALIDATION.md` финализирован:
- `nyquist_compliant: true` + `wave_0_complete: true` в frontmatter
- Per-task map: 11 планов с test-файлами и ключевыми тестами
- Observable/introspective split задокументирован
- Manual-only verifications для Plan 04-11 human-verify

## Verification

`python -m pytest client/tests -x --timeout=60` → **278 passed** (было 268 до этого плана, +10 новых infrastructure-тестов):
- `test_timestamped_task_factory_default/past_day/future_with_time/done/cyrillic` — 5 тестов
- `test_mock_storage_empty_initially/accepts_tasks` — 2 теста
- `test_mock_theme_manager_light` — 1 тест
- `test_dnd_event_simulator_with_coords/defaults` — 2 теста

Phase 2/3 regression зелёная (все 268 до-Phase-4 тесты без изменений).

## Commits

- `43c08f0`: feat(04-01): Phase 4 fixtures в conftest + 10 infrastructure тестов

## Files Created/Modified

- `client/tests/conftest.py` (+82 строки, 4 fixtures)
- `client/tests/test_infrastructure.py` (+73 строки, 10 tests)
- `.planning/phases/04-week-tasks/04-VALIDATION.md` (rewrite — refined)

## Ready for Wave 1

- Plan 04-02 (smart parse) может использовать `timestamped_task_factory` для тестовых данных
- Plan 04-03 (task widget) может использовать все 4 новых fixtures (`headless_tk` + `mock_theme_manager` + `timestamped_task_factory`)
- Plans 04-04..04-11 наследуют infra через pytest autodiscovery
