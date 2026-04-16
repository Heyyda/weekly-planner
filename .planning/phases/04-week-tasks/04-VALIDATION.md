---
phase: 4
slug: week-tasks
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-17
updated: 2026-04-18
---

# Phase 4 — Validation Strategy

> Per-phase validation contract. Wave 0 (04-01) финализирует infra; per-task map заморожен.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + Phase 3 conftest + Wave 0 Phase 4 fixtures (04-01) |
| **UI testing** | `headless_tk` (session), `mock_theme_manager`, `mock_storage`, `timestamped_task_factory` |
| **DnD testing** | `dnd_event_simulator` → MagicMock events, plus bbox-hit-test state assertions |
| **Smart parse** | Pure Python unit tests (no Tk needed) |
| **Quick run** | `python -m pytest client/tests -x --timeout=30` |
| **Full suite** | `python -m pytest client/tests -v --timeout=90` |
| **Estimated runtime** | ~60-80 seconds |

---

## Sampling Rate

- After every task commit: `pytest -x --timeout=30` (subset per plan)
- After every wave: full client suite + Phase 2/3 regression
- Before verify-work (plan 04-11): all green + manual smoke test (owner)
- Max latency: 80s

---

## Per-Task Verification Map

| Plan | Wave | Requirement | Test File | Key Tests | Status |
|------|------|-------------|-----------|-----------|--------|
| 04-01 | 0 | — | client/tests/test_infrastructure.py | test_timestamped_task_factory_*, test_mock_storage_*, test_dnd_event_simulator_* | ✅ |
| 04-02 | 1 | TASK-01 | client/tests/test_quick_parse.py | test_parse_time_with_preposition, test_parse_weekday_ru, test_parse_relative_*, test_parse_no_match_fallback_today | ⬜ |
| 04-03 | 1 | WEEK-04, WEEK-05, TASK-02 | client/tests/ui/test_task_widget.py | test_three_styles, test_overdue_checkbox_color, test_toggle_done, test_hover_shows_icons | ⬜ |
| 04-04 | 2 | WEEK-01, TASK-07 | client/tests/ui/test_day_section.py | test_day_section_renders_tasks, test_empty_day_shows_plus, test_position_sort | ⬜ |
| 04-05 | 2 | WEEK-02, WEEK-03, WEEK-06 | client/tests/ui/test_week_navigation.py | test_nav_arrows_change_week, test_today_btn_visibility, test_archive_detection, test_keyboard_nav | ⬜ |
| 04-06 | 3 | TASK-01 | client/tests/ui/test_quick_capture.py | test_popup_shows, test_enter_saves, test_empty_enter_no_save, test_edge_flip, test_overlay_right_click_triggers_popup | ⬜ |
| 04-07 | 3 | TASK-03 | client/tests/ui/test_edit_dialog.py | test_dialog_modal_grab_set, test_save_disabled_empty, test_save_disabled_invalid_time, test_keyboard_shortcuts, test_grab_release_on_exit | ⬜ |
| 04-08 | 4 | TASK-04 | client/tests/ui/test_undo_toast.py | test_delete_shows_toast, test_undo_reverses, test_max_three_toasts, test_countdown_dismisses | ⬜ |
| 04-09 | 4 | TASK-05, TASK-06 | client/tests/ui/test_drag_controller.py | test_drag_threshold, test_find_drop_zone_hit, test_cancel_on_same_source, test_archive_zone_blocks_drop, test_blend_hex, test_next_week_zone_appears | ⬜ |
| 04-10 | 5 | — (integration) | client/tests/ui/test_app_integration.py (extend) | test_quick_capture_wired_to_overlay_right_click, test_main_window_renders_tasks | ⬜ |
| 04-11 | 5 | ALL 13 | client/tests/ui/test_e2e_phase4.py | test_e2e_capture_edit_delete_undo_dragflow + human-verify checkpoint | ⬜ |

---

## Observable vs Introspective Validation

### Observable (state-assertion)

| Requirement | Observable behavior | Test |
|-------------|---------------------|------|
| **WEEK-01** | Окно рендерит 7 секций Пн-Вс из LocalStorage.get_visible_tasks() | test_day_section_renders_tasks |
| **WEEK-02** | Prev/next стрелки меняют `_week_monday`, перерисовывают секции | test_nav_arrows_change_week |
| **WEEK-03** | "Сегодня" button visible только когда _week_monday != current_week_monday | test_today_btn_visibility |
| **WEEK-04** | Overdue task: checkbox border = accent_overdue | test_overdue_checkbox_color |
| **WEEK-05** | task_style setting "card"/"line"/"minimal" меняет frame corner_radius и border | test_three_styles |
| **WEEK-06** | is_archive_week() True → dim palette + banner + editing disabled | test_archive_detection, test_archive_banner_visible |
| **TASK-01** | parse_quick_input() корректно извлекает time/day/text | test_parse_priority_order |
| **TASK-01** | QuickCapturePopup.show() + Enter → LocalStorage.add_task() called | test_enter_saves |
| **TASK-02** | TaskWidget checkbox click → on_toggle(task_id, new_done) called | test_toggle_done |
| **TASK-03** | EditDialog save → LocalStorage.update_task(task_id, **fields) called | test_edit_dialog_saves_changes |
| **TASK-04** | Delete 🗑 → soft_delete_task + UndoToast appears, countdown 5s | test_delete_shows_toast, test_countdown_dismisses |
| **TASK-04** | "Отменить" < 5s → update_task(deleted_at=None) restores task | test_undo_reverses |
| **TASK-05** | DragController._commit_drop → on_task_moved(task_id, target_day) called | test_cancel_on_same_source, test_find_drop_zone_hit |
| **TASK-06** | Next-week drop-zone появляется при drag-start, скрывается при release | test_next_week_zone_appears |
| **TASK-07** | Tasks отсортированы по position в DaySection; update_task(position=...) persist | test_position_sort, test_position_preserved_on_reload |

### Introspective (white-box)

| Check | Source | Assertion |
|-------|--------|-----------|
| overrideredirect через after(100) | client/ui/quick_capture.py | grep "after(100" >= 1 (PITFALL 1) |
| grab_release на всех exit paths EditDialog | client/ui/edit_dialog.py | grep "grab_release" >= 4 |
| toolwindow атрибут | client/ui/quick_capture.py | grep "-toolwindow" >= 1 |
| CTkTextbox.get("1.0", "end-1c") | client/ui/edit_dialog.py | grep "end-1c" >= 1 |
| DropZone.contains через bbox (НЕ winfo_containing) | client/ui/drag_controller.py | winfo_containing == 0 AND grep "winfo_rootx" >= 1 |
| Ghost pre-created (withdraw/deiconify) | client/ui/drag_controller.py | class GhostWindow с .withdraw() в __init__ |
| alpha=0.6 на ghost | client/ui/drag_controller.py | grep "-alpha" + "0.6" >= 1 |
| Archive palette через color interpolation | client/ui/week_navigation.py или main_window.py | def _blend_hex или _interpolate_palette |

---

## Manual-Only Verifications (Plan 04-11 human-verify)

| Behavior | Requirement | Instructions |
|----------|-------------|--------------|
| Quick-capture появляется под overlay на multi-monitor | TASK-01 | Drag overlay на 2nd monitor, right-click, popup на том же мониторе |
| Smart parse edge cases | TASK-01 | "позвонить в 14:00", "встреча пт", "отчёт завтра", "купить молоко 18:30" |
| DnD feels smooth на реальном Windows | TASK-05, TASK-06 | Drag задачу 10 раз между разными днями, нет stutter, ghost не отстаёт |
| Undo-toast stacking | TASK-04 | Удалить 3 задачи за 2 секунды — 3 toasts stacked |
| Archive dim effect виден | WEEK-06 | Prev-week навигация → opacity 0.7 визуально, banner сверху |
| Keyboard shortcuts | WEEK-02, WEEK-03, TASK-03 | Ctrl+←/→, Ctrl+T, Esc, Ctrl+Space, Del, Space, Enter |
| Long task text wrap | WEEK-05 | Задача с 200+ символов — wraps, не обрезается |

---

## Wave 0 Requirements (COMPLETED в Plan 04-01)

- [x] `client/tests/ui/__init__.py` — существует из Phase 3
- [x] `timestamped_task_factory` в conftest.py — фабрика Task с day_offset/time/done
- [x] `mock_storage` в conftest.py — инициализированный LocalStorage на tmp_appdata
- [x] `mock_theme_manager` в conftest.py — ThemeManager('light')
- [x] `dnd_event_simulator` в conftest.py — фабрика MagicMock events для DnD
- [x] Phase 3 фикстуры сохранены без изменений

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify
- [x] Sampling continuity defined
- [x] Wave 0 infra additions planned (Plan 04-01) — **COMPLETED**
- [x] No watch-mode flags
- [x] `nyquist_compliant: true`
- [ ] 04-11 human-verify checkpoint completed (финальный gate)

**Approval:** ready for execution.
