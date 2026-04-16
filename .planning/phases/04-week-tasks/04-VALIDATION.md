---
phase: 4
slug: week-tasks
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-17
---

# Phase 4 — Validation Strategy

> Per-phase validation contract. Planner refines per-task map during plan generation.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + Phase 3 conftest fixtures |
| **UI testing** | `headless_tk` fixture (Phase 3) + mock LocalStorage for CRUD |
| **DnD testing** | Mock mouse events via `event_generate("<Button-1>"...)`; assert DragController state |
| **Smart parse** | Pure Python unit tests (no Tk needed) |
| **Quick run** | `python -m pytest client/tests -x --timeout=30` |
| **Full suite** | `python -m pytest client/tests -v --timeout=90` |
| **Estimated runtime** | ~40-60 seconds |

---

## Sampling Rate

- After every task commit: `pytest -x --timeout=30`
- After every wave: full client suite + Phase 2/3 regression
- Before verify-work: all green + manual smoke (owner)
- Max latency: 60s

---

## Per-Task Verification Map

*Populated by planner.*

| Task ID | Plan | Wave | Requirement | Test Type | Command | Status |
|---------|------|------|-------------|-----------|---------|--------|
| *TBD* | *planner* | *planner* | *planner* | *planner* | *planner* | ⬜ pending |

---

## Wave 0 Requirements (Test Infrastructure Additions)

- [ ] `client/tests/ui/__init__.py` — already exists from Phase 3
- [ ] Add `mock_storage` fixture for CRUD unit tests (if not already from Phase 2)
- [ ] Add `dnd_event_simulator` helper for DnD test scenarios
- [ ] Extend conftest with `timestamped_task_factory` for creating test Tasks with various day/time combos

---

## Observable vs Introspective Validation

### Observable (state-assertion)

| Requirement | Observable behavior | Test |
|-------------|---------------------|------|
| **WEEK-01** | Окно показывает 7 секций Пн-Вс аккордеоном | `test_day_sections_render_for_week` |
| **WEEK-02** | Prev/next стрелки меняют week_start | `test_nav_arrows_change_week` |
| **WEEK-03** | "Сегодня" button возвращает к current week | `test_today_btn_returns_to_current` |
| **WEEK-04** | Просроченные задачи с красной бордер checkbox | `test_overdue_task_visual_red_border` |
| **WEEK-05** | Task styles A/B/C применяются по settings | `test_task_style_applies_on_switch` |
| **WEEK-06** | Past weeks показывают dim + banner "Архив" | `test_archive_shows_banner_and_dim` |
| **TASK-01** | Quick-capture right-click → input создаёт task | `test_right_click_opens_quick_capture` + e2e |
| **TASK-02** | Click checkbox → done=true, strikethrough | `test_checkbox_click_toggles_done` |
| **TASK-03** | Edit dialog Save → LocalStorage.update_task called | `test_edit_dialog_saves_changes` |
| **TASK-04** | Delete 🗑 → soft_delete_task → undo-toast 5s | `test_delete_shows_undo_toast_5s` |
| **TASK-05** | DnD task → другой день → task.day changed | `test_dnd_between_days_updates_day` (integration) |
| **TASK-06** | DnD task → next-week zone → task.day = next_monday+offset | `test_dnd_to_next_week_drop_zone` |
| **TASK-07** | Позиция задачи в дне persistent (position field) | `test_position_preserved_on_reload` |

### Introspective (white-box)

| Requirement | Internal signal | Check |
|-------------|-----------------|-------|
| Smart parse priority | HH:MM first, weekday then, text remainder | `test_parse_priority_order` |
| DnD ghost alpha | `-alpha=0.6` set on Toplevel | grep + runtime assertion |
| Undo reverses tombstone | `update_task(deleted_at=None)` called | `test_undo_reverses_soft_delete` |
| Archive editing disabled | event handlers no-op | `test_archive_click_has_no_effect` |

---

## Manual-Only Verifications

| Behavior | Requirement | Instructions |
|----------|-------------|--------------|
| DnD feels smooth (60fps) | TASK-05/06 | Owner drags task 10 times, no stutter |
| Quick-capture appears under overlay correctly on multi-monitor | TASK-01 | Drag overlay to second monitor, right-click, verify popup on same monitor |
| Smart parse edge cases | TASK-01 | Try: "позвонить в 14:00", "встреча пт", "отчёт завтра", "купить молоко 18:30" — all create correct tasks |
| Undo-toast stacking | TASK-04 | Delete 3 tasks rapidly — 3 toasts visible, stacked |
| Keyboard shortcuts | WEEK-02/03 | Ctrl+Left/Right navigation, Ctrl+T "сегодня", Esc closes dialog |
| Long text wrap | WEEK-05 | Add task with 200+ character text — wraps without horizontal scroll |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify
- [ ] Sampling continuity
- [ ] Wave 0 infra additions done
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` after planner refines

**Approval:** pending (planner refines, gsd-plan-checker validates)
