---
plan: 04-11
status: CODE-COMPLETE (human-verify pending)
commits: effce0e
tests: test_e2e_phase4 16 green, full suite 478 green
---

# 04-11 SUMMARY — E2E + validation

## Delivered
- `client/tests/ui/test_e2e_phase4.py` — 16 integration сценариев
- `.planning/phases/04-week-tasks/04-VALIDATION.md` — Execution Report + Coverage 13/13

## E2E Scenarios (16)
Add/toggle/edit/delete/undo — 5 сценариев
Drag-and-drop (between days, next week) — 2 сценария
Week navigation (prev, today, archive enter/exit) — 4 сценария
Position sort, multi-day distribution, overdue, empty day plus, task style switch — 5

## Test run
- `python -m pytest client/tests/ui/test_e2e_phase4.py` — **16 green**
- `python -m pytest client/tests/` — **478 green, 10 pre-existing errors**

Pre-existing 10 errors в `test_e2e_phase3.py` — session-scope pyimage state (Phase 3 known issue),
проходят изолированно. Не регрессии 04-11.

## Coverage: 13/13 REQ-IDs ✓

| REQ-ID  | E2E test(s) |
|---------|-------------|
| WEEK-01 | test_e2e_tasks_distributed_to_correct_days, test_e2e_empty_day_shows_plus |
| WEEK-02 | test_e2e_navigate_prev_week |
| WEEK-03 | test_e2e_today_button_returns |
| WEEK-04 | test_e2e_overdue_task_rendered |
| WEEK-05 | test_e2e_task_style_switch_rebuilds |
| WEEK-06 | test_e2e_archive_mode_activates_on_past + deactivates_on_today |
| TASK-01 | test_e2e_add_via_quick_capture_save |
| TASK-02 | test_e2e_toggle_done_updates_storage |
| TASK-03 | test_e2e_edit_dialog_saves_changes |
| TASK-04 | test_e2e_delete_shows_undo_toast + undo_restores_task |
| TASK-05 | test_e2e_move_task_between_days |
| TASK-06 | test_e2e_move_to_next_week |
| TASK-07 | test_e2e_position_sort_preserved |

## Pending
- **Human-verify checkpoint**: Никита запускает `python main.py` на Windows и подтверждает 9 Success Criteria
  из `04-UI-SPEC §Success Criteria`:
  1. Right-click overlay → quick-capture; Enter → task создан
  2. 3 task-style переключатель в tray (card/line/minimal)
  3. Hover на задачу → ✏+🗑; click ✏ → edit dialog
  4. Delete → undo-toast 5s; "Отменить" → task восстановлен
  5. Drag задачи → ghost следует; drop → day меняется
  6. Next-week drop zone при drag → task.day = след. неделя
  7. Прошлая неделя: opacity dim, banner "Архив", read-only
  8. Ctrl+Left/Right/T/Space клавиши
  9. Пустой день: "+" по центру, click → inline input

После одобрения — обновить `04-VALIDATION.md` с `approved_by_owner: YYYY-MM-DD`.
