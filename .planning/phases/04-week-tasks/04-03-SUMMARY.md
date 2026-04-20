# Plan 04-03 — TaskWidget — SUMMARY

**Phase:** 04-week-tasks
**Plan:** 04-03 (Wave 1)
**Status:** ✅ Complete
**Completed:** 2026-04-18
**Requirements:** WEEK-04, WEEK-05, TASK-02

---

## What Was Built

`client/ui/task_widget.py` полностью переписан (274 строки) — старый skeleton с приоритетами/категориями удалён. TaskWidget class:

- **3 стиля** (`VALID_STYLES = {"card", "line", "minimal"}`):
  - card: corner_radius=8, bg_secondary + shadow, padding (12,10)
  - line: corner_radius=0, bottom-border, padding (10,8)
  - minimal: corner_radius=6, transparent, hover reveals bg_secondary, padding (6,6)
- **Custom Canvas checkbox 18×18** (D-11):
  - not done: border text_secondary
  - done: filled accent_done + белая галочка
  - overdue: border accent_overdue (WEEK-04)
- **Time label** (D-12): monospace, color меняется для done/overdue/default
- **Hover icons** (D-13): ✏ + 🗑 через text_color trick (invisible = bg color; visible = text_secondary)
- **Callbacks**: on_toggle(task_id, new_done), on_edit(task_id), on_delete(task_id)
- **ThemeManager.subscribe**: `_apply_theme` перекрашивает Canvas, icons, backgrounds на theme switch
- **Partial update** (PITFALL 4): `update_task(task)` не пересоздаёт frame — scroll preserved
- **`get_body_frame()`**: target для DnD mouse bindings (Plan 04-09)

`client/tests/ui/test_task_widget.py` (24 теста):
- 3 стиля + fallback для invalid
- Checkbox states (not-done / done / overdue) + Canvas size
- Time field показывается/скрывается правильно
- Callbacks (toggle, edit, delete) invoke-паттерн
- Hover enter/leave
- Update task partial (frame preserved)
- Theme switch survives
- Кириллица
- Grep markers (CHECKBOX_SIZE=18, CHECKBOX_RADIUS=3)
- get_body_frame returns body (DnD integration point)

## Verification

- `pytest client/tests/ui/test_task_widget.py -q` → **24 passed in 1.55s**
- Full suite: **332 passed** (+24 новых к 308)

## Commits

- `dbd99a9`: feat(04-03): TaskWidget — 3 стиля + Canvas checkbox + hover icons + theme-aware (WEEK-04, WEEK-05, TASK-02)

## Requirements Covered

- ✅ **WEEK-04**: Overdue task → red checkbox border
- ✅ **WEEK-05**: 3 стиля (card/line/minimal) через param
- ✅ **TASK-02**: checkbox click → on_toggle callback с оптимистичным UI update

## Ready for Wave 2

- Plan 04-04 (DaySection): импортирует TaskWidget, передаёт список задач
- Plan 04-05 (WeekNavigation): не зависит от TaskWidget
- Plan 04-07 (EditDialog): get_body_frame не нужен, работает через on_edit callback
- Plan 04-09 (DragController): использует `get_body_frame()` для mouse bindings
