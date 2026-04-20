---
phase: 3
slug: overlay-system
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-16
updated: 2026-04-17
---

# Phase 3 — Validation Strategy

> Per-phase validation contract. Refined by planner with actual plan/task IDs.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + Phase 2 conftest.py + Plan 03-01 fixtures |
| **Mocking fixtures** | headless_tk, mock_pystray_icon, mock_winotify, mock_winreg, mock_ctypes_dpi (Plan 03-01) |
| **Headless Tk** | `ctk.CTk().withdraw()` в headless_tk fixture — `update()` без `mainloop()` |
| **Config file** | `client/pyproject.toml` (наследует из Phase 2) |
| **Quick run** | `python -m pytest client/tests/ui -x -q --timeout=30` |
| **Full suite** | `python -m pytest client/tests -q --timeout=60` |
| **Estimated runtime** | 15-20 секунд |

---

## Sampling Rate

- **After every task commit:** `python -m pytest client/tests/ui/<specific_test>.py -x --timeout=30`
- **After every wave merge:** Full UI suite + Phase 2 regression (`python -m pytest client/tests -x --timeout=60`)
- **Before `/gsd:verify-work`:** Full suite green + Manual checkpoint Task 3 human-verify
- **Max feedback latency:** 45 секунд на plan-level

---

## Per-Task Verification Map

| Plan | Task | Wave | Requirement | Test Type | Automated Command | Status |
|------|------|------|-------------|-----------|-------------------|--------|
| 03-01 | Расширить conftest + ui/__init__ | 0 | infra | regression | `pytest client/tests/test_storage.py -x` | ✅ |
| 03-02 | ThemeManager | 1 | infra | unit | `pytest client/tests/ui/test_themes.py -x` | ✅ |
| 03-02 | UISettings + SettingsStore | 1 | infra | unit | `pytest client/tests/ui/test_settings.py -x` | ✅ |
| 03-03 | icon_compose.render_overlay_image | 1 | infra | unit | `pytest client/tests/ui/test_icon_compose.py -x` | ✅ |
| 03-04 | OverlayManager | 2 | OVR-01..04,06 | unit | `pytest client/tests/ui/test_overlay.py -x` | ✅ |
| 03-05 | PulseAnimator | 2 | OVR-05 | unit | `pytest client/tests/ui/test_pulse.py -x` | ✅ |
| 03-06 | MainWindow shell | 3 | infra | unit | `pytest client/tests/ui/test_main_window.py -x` | ✅ |
| 03-07 | TrayManager | 3 | TRAY-01..04 | unit | `pytest client/tests/ui/test_tray.py -x` | ✅ |
| 03-08 | NotificationManager | 4 | NOTIF-01..04 | unit | `pytest client/tests/ui/test_notifications.py -x` | ✅ |
| 03-09 | autostart.py | 4 | (TRAY-03 support) | unit | `pytest client/tests/ui/test_autostart.py -x` | ✅ |
| 03-10 | WeeklyPlannerApp integration | 5 | all | integration | `pytest client/tests/ui/test_app_integration.py -x` | ✅ |
| 03-11 | E2E | 5 | all | e2e | `pytest client/tests/ui/test_e2e_phase3.py -x` | ✅ |
| 03-11 | Human verification | 5 | all | manual | (see §Manual-Only) | ⬜ |

---

## Wave 0 Requirements (Complete after Plan 03-01)

- [x] `client/tests/conftest.py` — 5 новых fixtures added: `headless_tk`, `mock_pystray_icon`, `mock_winotify`, `mock_winreg`, `mock_ctypes_dpi`
- [x] `client/tests/ui/__init__.py` — пакет-маркер
- [x] Phase 2 fixtures preserved: `tmp_appdata`, `mock_api`, `api_base`

---

## Observable vs Introspective Validation

### Observable (state-assertion — test code observes UI state)

| Requirement | Observable behavior | Test |
|-------------|---------------------|------|
| **OVR-01** | Overlay window created with overrideredirect=True + topmost=True | `test_overlay_creates_toplevel` |
| **OVR-02** | Drag → new position → reload → position restored | `test_drag_end_saves_position_via_store` + `test_set_position_updates_settings` |
| **OVR-03** | `_validate_position([-5000, -5000])` → fallback (100, 100) | `test_validate_position_fallback_for_offscreen` |
| **OVR-04** | overlay.on_click() → main_window.winfo_viewable() toggles | `test_overlay_click_toggles_main_window` (e2e) |
| **OVR-05** | Overdue task → pulse.is_active() == True | `test_overdue_task_triggers_pulse` (e2e) |
| **OVR-06** | on_top toggle → both overlay and main_window attrs set | `test_on_top_toggle_propagates` (e2e) |
| **TRAY-01** | pystray.Icon created через run_detached | `test_start_creates_icon_and_runs_detached` |
| **TRAY-02** | Меню содержит все labels из UI-SPEC §Tray Menu | `test_menu_structure_has_all_required_labels` |
| **TRAY-03** | Settings changes → settings_store.save вызван | `test_cb_theme_updates_settings_and_persists` |
| **TRAY-04** | run_detached() + все callback через root.after(0, ...) | `test_source_uses_run_detached_not_run` + grep count >= 9 |
| **NOTIF-01** | 3 режима — sound_pulse / pulse_only / silent | `test_set_mode_valid` + blocking tests |
| **NOTIF-02** | sound_pulse → winotify.Notification.show called | `test_send_toast_sound_pulse_fires` |
| **NOTIF-03** | Задача с deadline через 3 мин → detected | `test_check_deadlines_approaching_detected` |
| **NOTIF-04** | silent → winotify НЕ вызван | `test_send_toast_silent_blocks` + e2e `test_notifications_silent_blocks_toast` |

### Introspective (white-box — internal state)

| Requirement | Internal signal | Check |
|-------------|-----------------|-------|
| **OVR-05 (anim)** | `after()` cycle running at ~60fps (PULSE_INTERVAL_MS=16) | `test_pulse_interval_is_16ms_60fps` |
| **TRAY-04 threading** | grep `run_detached\|self._root.after(0` >= expected | grep markers в 03-07 acceptance |
| **PITFALL 1** | `overrideredirect(True)` called via `after(INIT_DELAY_MS=100, ...)` | `test_init_uses_after_100_delay` + grep markers |
| **PITFALL 3** | winotify.show in `threading.Thread(daemon=True)` | `test_daemon_thread_used_not_blocking_caller` + grep |
| **PITFALL 4** | `self._tk_image` instance var preserved after refresh_image | `test_refresh_image_keeps_pillow_ref` |
| **PITFALL 6** | Saved position validated before restore | `test_validate_position_fallback_for_offscreen` |
| **PITFALL 7** | winotify icon absolute path | `test_set_icon_resolves_absolute` + grep `.resolve()` |

---

## Manual-Only Verifications (Human-Verify Task 3 Plan 03-11)

Выполняется Никитой на его Windows 11 рабочей станции с 2 мониторами.

| Behavior | Requirement | Instructions |
|----------|-------------|--------------|
| Overlay визуально корректен | OVR-01 | `python main.py` → квадрат 56×56 с синим gradient + белой галочкой виден на desktop; не за другими окнами |
| Drag между мониторами | OVR-03 | Перетащить overlay с monitor 1 на monitor 2 и обратно; плавно, без лагов; позиция сохраняется |
| Click открывает окно | OVR-04 | Клик по overlay → окно показывается; второй клик → скрывается |
| Pulse при overdue | OVR-05 | Добавить задачу на вчера через подмену storage → overlay пульсирует red |
| Always-on-top работает | OVR-06 | Открыть fullscreen browser → overlay всё равно поверх (Win11 DWM limitation OK for exclusive fullscreen) |
| Tray меню open/actions | TRAY-01..03 | Right-click tray → видно меню со всеми 12+ пунктами; переключение Theme → окно мгновенно меняет фон |
| 20 rapid tray clicks | TRAY-04 | Tap tray menu 20 раз — "Открыть окно"/"Скрыть" alternating; приложение не падает, нет traceback в консоли |
| Toast appears в sound_pulse mode | NOTIF-02 | Добавить задачу с deadline через 3 мин → через 2 мин видно Windows toast |
| Не беспокоить блокирует toast | NOTIF-04 | Tray → Настройки → Уведомления → Тихо; та же задача → toast НЕ появляется |
| Autostart registry | TRAY-03 | Tray → Настройки → Автозапуск ✓; `reg query HKCU\Software\Microsoft\Windows\CurrentVersion\Run` содержит `LichnyEzhednevnik` |
| Cyrillic path OK | host | `python s:\Проекты\ежедневник\main.py` не крэшит при старте |

**Human-verify signal:** Никита отвечает либо `"approved"` либо перечисляет конкретные failures по номерам строк таблицы.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify command
- [x] Sampling continuity — Wave 0 test infra ready до tasks что от неё зависят
- [x] Wave 0 covers all MISSING references (все 5 fixtures created)
- [x] No watch-mode flags — только one-shot pytest
- [x] Feedback latency < 45s per plan
- [x] `nyquist_compliant: true` — все tasks зелёные через automated (кроме Plan 03-11 Task 3 который human-verify)

**Approval:** Pending human-verify on Plan 03-11 Task 3.
