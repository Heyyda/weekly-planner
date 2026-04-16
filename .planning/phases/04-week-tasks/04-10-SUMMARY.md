---
plan: 04-10
status: DONE
commits: 874dcbb
tests: MainWindow 23 green / AppIntegration 21 green
---

# 04-10 SUMMARY — Integration (MainWindow + WeeklyPlannerApp)

## Delivered
- `client/ui/main_window.py` — переписан с Phase 4 компонентами (422 строк)
- `client/app.py` — расширен QuickCapture wire + D-01 overlay right-click (464 строк)
- `client/tests/ui/test_main_window.py` — перезаписан (Phase 3 lifecycle + Phase 4 integration, 23 тестов)
- `client/tests/ui/test_app_integration.py` — расширен (21 тест, +7 Phase 4)

## Integration points

### MainWindow (Phase 4 content)
- **WeekNavigation** header (Plan 04-05) — заменяет Phase 3 placeholder
- **7 DaySection** (Plan 04-04) через `_rebuild_day_sections` per week change
- **UndoToastManager** (Plan 04-08) в `_root_frame`
- **DragController** (Plan 04-09) с `DropZone` per DaySection.get_body_frame()
- **EditDialog** (Plan 04-07) при `_on_task_edit`
- **Ctrl+Space** binding → quick_capture trigger (D-30)

### WeeklyPlannerApp (Phase 4 wire)
- `QuickCapturePopup` создан после MainWindow
- `overlay.on_right_click = _on_overlay_right_click` (D-01)
- `main_window._quick_capture_trigger = _trigger_quick_capture_centered` (D-30)
- `_handle_quick_capture_save → main_window.handle_quick_capture_save → storage.add_task + force_sync`
- `_handle_task_style_changed` теперь делегирован на MainWindow
- MainWindow получает `storage=self.storage, user_id=user_id` для CRUD

### CRUD callbacks в MainWindow
- `_on_task_toggle(task_id, done)` → `storage.update_task(done=)`
- `_on_task_edit(task_id)` → открывает EditDialog
- `_on_edit_save(task)` → `storage.update_task(text/day/time/done)`
- `_on_task_delete(task_id)` → `_delete_task_with_undo`
- `_delete_task_with_undo` → `soft_delete_task` + `undo_toast.show(restore_cb)`
- `_on_inline_add(task)` → `storage.add_task`
- `_on_task_moved(task_id, new_day)` → `storage.update_task(day=)`

### Undo-restore (D-20)
`storage.update_task` whitelist не включает `deleted_at` — restore идёт напрямую под `_lock`:
очищает `deleted_at = None`, добавляет `TaskChange(op="update")` в pending_changes,
`_save_locked()`.

## Tests
- MainWindow: 23 green (Phase 3 lifecycle + Phase 4 structure + CRUD callbacks + week nav)
- AppIntegration: 21 green (Phase 3 wire + Phase 4 quick_capture + D-01 + task_style delegation)

## Known state
- `test_setup_unauthenticated_skips_main_components` иногда падает при full suite
  из-за session-scoped `headless_tk` (известная Phase 3 issue, не регрессия 04-10)
- `test_e2e_phase3` 10 pre-existing errors (session-scope pyimage state) — unchanged

## Next
- 04-11: E2E phase-4 flow tests + human-verify checkpoint
- Verify phase 4 goal → close phase 4
