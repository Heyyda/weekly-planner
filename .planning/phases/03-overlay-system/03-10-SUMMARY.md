---
phase: 03-overlay-system
plan: 10
subsystem: client/app
tags: [orchestrator, integration, tdd, lifecycle, phase3-complete]
dependency_graph:
  requires: [03-02, 03-04, 03-05, 03-06, 03-07, 03-08, 03-09]
  provides: [WeeklyPlannerApp — оркестратор Phase 3]
  affects: [main.py, client/app.py]
tech_stack:
  added: []
  patterns:
    - "Orchestrator pattern: ThemeManager→Storage→Auth→Sync→Overlay→MainWindow→Pulse→Notifications→Tray"
    - "TDD: RED→GREEN→COMMIT per task"
    - "Cyrillic-safe: Path.resolve() вместо os.path.abspath()"
key_files:
  created:
    - client/tests/ui/test_app_integration.py
  modified:
    - client/app.py
    - main.py
decisions:
  - "Login placeholder при auth=False: overlay+tray без main_window/sync/pulse"
  - "_handle_top_changed_from_tray напрямую меняет overlay._overlay.attributes без on_top_changed hook (избегаем рекурсии)"
  - "REFRESH_INTERVAL_MS=30000 (overlay/tray badge), DEADLINE_CHECK_INTERVAL_MS=60000 (notifications)"
metrics:
  duration: "3 min"
  completed_date: "2026-04-17"
  tasks_completed: 1
  files_changed: 3
---

# Phase 3 Plan 10: WeeklyPlannerApp Orchestrator Summary

**One-liner:** WeeklyPlannerApp оркестрирует все 6 Phase 3 компонентов через канонический 10-шаговый lifecycle с TDD-покрытием (14 тестов зелёных).

## What Was Built

Полная перезапись `client/app.py` — skeleton заменён на production-ready оркестратор.

### Компоненты и порядок инициализации (03-RESEARCH §Pattern 10)

1. **ThemeManager** — до любых CTk виджетов
2. **AppPaths + LocalStorage + SettingsStore** → load settings → apply theme
3. **AuthManager** + `load_saved_token()` → authenticated flag
   - При `False`: `_setup_unauthenticated_placeholder()` — overlay + tray без sync/main_window
   - При `True`: продолжить полную инициализацию
4. **SyncManager** — `start()` background thread
5. **OverlayManager** — draggable квадрат
6. **MainWindow** — аккордеон дней (hidden)
7. **PulseAnimator** — `on_frame` callback → `overlay.refresh_image(state="overdue", pulse_t=t)`
8. **NotificationManager** — `mode` из settings + `set_icon(path.resolve())`
9. **TrayManager** — `start()` (run_detached) — ПОСЛЕДНИМ (все callbacks готовы)
10. **Schedulers** — `root.after(30s, _scheduled_refresh)` + `root.after(60s, _scheduled_deadline_check)`

### Wire Points

| Callback | Source | Destination |
|----------|--------|-------------|
| `overlay.on_click` | OverlayManager | `main_window.toggle` (OVR-04) |
| `overlay.on_top_changed` | OverlayManager | `main_window.set_always_on_top` (OVR-06) |
| `tray.on_show/hide` | TrayManager | `main_window.show/hide` |
| `tray.on_sync` | TrayManager | `sync.force_sync()` |
| `tray.on_logout` | TrayManager | `auth.logout() + sync.stop()` |
| `tray.on_quit` | TrayManager | `pulse.stop + sync.stop + tray.stop + overlay.destroy + root.destroy` |
| `tray.on_top_changed` | TrayManager | `overlay._overlay.attributes + main_window.set_always_on_top` |
| `tray.on_notifications_mode_changed` | TrayManager | `notifications.set_mode(mode)` |
| `tray.on_autostart_changed` | TrayManager | `autostart.enable/disable_autostart()` |
| `tray.is_autostart_enabled` | TrayManager | `autostart.is_autostart_enabled()` |

### Schedulers

- `_scheduled_refresh` (30s): обновляет overlay image, tray icon, tooltip; управляет pulse start/stop
- `_scheduled_deadline_check` (60s): `notifications.fire_scheduled_toasts(storage.get_visible_tasks())`

### main.py Changes

- `Path(__file__).resolve().parent` — Cyrillic-safe sys.path insert
- `VERSION = "0.3.0"` (Phase 3)
- `logging.basicConfig()` для ранней диагностики до app._setup()

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `8313556` | test | Failing integration tests (RED phase) — 14 тестов |
| `d928e65` | feat | WeeklyPlannerApp orchestrator + main.py (GREEN) |

## Tests

Файл: `client/tests/ui/test_app_integration.py` — 14 тестов:

1. `test_app_instantiates` — CTk root создаётся, компоненты None до setup
2. `test_setup_unauthenticated_skips_main_components` — placeholder при auth=False
3. `test_setup_authenticated_wires_all_components` — все 6 компонентов при auth=True
4. `test_overlay_on_click_wires_to_main_window_toggle` — OVR-04 wire
5. `test_overlay_on_top_changed_wires_to_main_window` — OVR-06 wire
6. `test_handle_notifications_mode_changed` — notifications.mode меняется
7. `test_handle_autostart_toggle_on` — winreg запись через enable_autostart
8. `test_handle_quit_cleanup` — sync.stop вызван, _quit_requested=True
9. `test_cyrillic_path_resolution_works` — Path.resolve() работает
10. `test_refresh_ui_starts_pulse_on_overdue` — pulse.start() при overdue задаче
11. `test_refresh_ui_stops_pulse_when_no_overdue` — pulse не активен без overdue
12. `test_tray_started` — pystray.Icon.run_detached() вызван
13. `test_sync_started` — sync.start() вызван при auth=True
14. `test_handle_logout_stops_sync_and_clears_auth` — sync.stop + auth.logout

**Всего тестов в проекте: 258 (все зелёные)**

## Deviations from Plan

None — план выполнен точно. Все acceptance criteria из PLAN.md соответствуют реализации.

## Known Stubs

- `_handle_add_placeholder` → открывает main_window.show() вместо add-task dialog (Phase 4 реализует full dialog)
- Login dialog — не реализован, Phase 3 scope: overlay placeholder + log message
- `_handle_task_style_changed` — только логирует, реальный re-render — Phase 4

Эти stubs намеренны и задокументированы в PLAN.md как Phase 3 scope boundary.

## Self-Check: PASSED

- client/app.py: FOUND
- client/tests/ui/test_app_integration.py: FOUND
- main.py: FOUND
- commit d928e65 (feat): FOUND
- commit 8313556 (test): FOUND
- 258 tests: ALL PASSED
