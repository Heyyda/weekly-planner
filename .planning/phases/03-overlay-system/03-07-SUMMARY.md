# Plan 03-07 — TrayManager — SUMMARY

**Phase:** 03-overlay-system
**Plan:** 03-07
**Status:** ✅ Complete
**Completed:** 2026-04-16
**Requirements:** TRAY-01, TRAY-02, TRAY-03, TRAY-04

---

## What Was Built

`client/utils/tray.py` (341 строк, полная перезапись skeleton):

**TrayManager** — обёртка над pystray для всего tray-слоя:
- **PITFALL 2 compliance:** `pystray.Icon.run_detached()` (не `run()`) — pystray thread не блокирует Tk mainloop
- **D-27 compliance:** каждый menu-callback (`_cb_show`, `_cb_hide`, `_cb_add`, `_cb_sync`, `_cb_logout`, `_cb_quit`, `_cb_theme`, `_cb_task_style`, `_cb_notifications_mode`, `_cb_toggle_on_top`, `_cb_toggle_autostart`) проходит через `self._root.after(0, lambda: ...)` — нет прямых Tk-вызовов из pystray-потока
- Меню полностью по UI-SPEC §Tray Menu: Открыть / Скрыть / ── / Добавить / ── / Настройки (Тема → 4 опции / Вид задач → 3 / Уведомления → 3 / Поверх всех окон [✓] / Автозапуск [✓]) / ── / Обновить синхронизацию / ── / Разлогиниться / Выход
- Tray icon — `render_overlay_image(32, state, task_count, overdue_count, 0.0)` из Plan 03-03 (32×32 для HiDPI)
- Icon auto-refresh при смене task_count/overdue_count
- Settings persistence через `SettingsStore.save()` (Plan 03-02) после каждой смены опции — TRAY-03 мгновенное применение
- `on_*` hook API (11 callback slots) — Plan 03-10 позже их свяжет с OverlayManager/MainWindow/Auth/Sync

`client/tests/ui/test_tray.py` (16 тестов):
- Icon composition верен для tray-размера
- Все 11 menu items имеют корректные callbacks
- `run_detached()` вызывается, не `run()` (PITFALL 2)
- `self._root.after(0, ...)` >= 9 occurrences (source-grep verification for D-27)
- `_cb_hide` + `_cb_logout` callbacks доходят до `on_hide`/`on_logout` через полный Tk event cycle
- Toggles (on_top, autostart) сохраняются в SettingsStore
- Radio selections (тема / вид задач / режим уведомлений) обновляют settings

**Deviation (fixed by orchestrator):** Тесты `test_hide_callback_via_after` + `test_logout_callback_via_after` изначально использовали `update_idletasks()` — не обрабатывает `after(0, ...)` queued callbacks. Исправлено на `update()` (полный event cycle). Код tray.py корректен, баг только в тестах.

## Verification

- `python -m pytest client/tests/ui/test_tray.py -v` → **16/16 passed**
- grep `run_detached` client/utils/tray.py → 1 match ✓
- grep `self._root.after(0` client/utils/tray.py → 11 matches (>= 9 requirement) ✓
- grep `pystray.Icon.run(` (без `_detached`) → 0 matches ✓

## Commits

- `cd59357`: feat(03-07): TrayManager — pystray run_detached + root.after(0) callbacks + меню UI-SPEC (TRAY-01..04)

## Requirements Covered

- ✅ **TRAY-01**: pystray.Icon с полным contextual menu
- ✅ **TRAY-02**: Все 11 toggles + submenus per UI-SPEC (on_top, autostart, theme, task_style, notifications_mode, etc.)
- ✅ **TRAY-03**: SettingsStore.save на каждое изменение — мгновенное применение
- ✅ **TRAY-04**: run_detached + root.after(0) thread-safety (PITFALL 2)

## Integration Points for Plan 03-10

`WeeklyPlannerApp.__init__` свяжет:
- `tray.on_show` → `main_window.show()` + `main_window.lift()`
- `tray.on_hide` → `main_window.hide()`
- `tray.on_add` → `main_window.open_add_dialog()` (Phase 4) / placeholder в Phase 3
- `tray.on_sync` → `sync_manager.force_sync()` (Phase 2)
- `tray.on_logout` → `auth_manager.logout()` + app restart
- `tray.on_quit` → `app._shutdown()`
- `tray.on_toggle_on_top` → `overlay.set_always_on_top(bool)` + `main_window.set_always_on_top(bool)` одновременно (OVR-06)
- `tray.on_toggle_autostart` → `autostart.enable(bool)` (Plan 03-09)
- `tray.on_theme_change` → `theme_manager.set_theme(theme)` + re-render overlay icon
