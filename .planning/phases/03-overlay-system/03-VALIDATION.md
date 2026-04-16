---
phase: 3
slug: overlay-system
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 3 — Validation Strategy

> Per-phase validation contract. Planner refines per-task map during plan generation.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-mock + existing client/tests/conftest.py |
| **Mocking** | Mock `pystray.Icon`, `winotify.Notification`, `winreg`, `ctypes.user32.SetWindowPos`, Windows DPI calls |
| **Headless Tk** | `tkinter.Tk().withdraw()` in fixture, `update()` instead of `mainloop()` — Tk supports limited headless operation on Windows |
| **Config file** | `client/pyproject.toml` (uses existing pytest config from Phase 2) |
| **Quick run command** | `python -m pytest client/tests -x --timeout=15` |
| **Full suite command** | `python -m pytest client/tests -v --timeout=60` |
| **Estimated runtime** | ~30-45 seconds (UI state assertions, no rendering) |

---

## Sampling Rate

- **After every task commit:** `python -m pytest client/tests -x --timeout=15`
- **After every plan wave:** Full client suite + sanity server (`python -m pytest server/tests -x`)
- **Before `/gsd:verify-work`:** Full suite green + manual smoke on Windows (owner approval)
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

> Populated by planner.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| *TBD* | *planner* | *planner* | *planner* | *planner* | *planner fills* | ⬜ pending |

---

## Wave 0 Requirements (Test Infrastructure Additions)

- [ ] `client/tests/conftest.py` extend with: `mock_pystray_icon`, `mock_winotify`, `mock_winreg`, `headless_tk` fixtures
- [ ] `client/tests/ui/__init__.py` — marker for UI test package
- [ ] `client/requirements-dev.txt` — add `pytest-mock` if missing (likely already added in Phase 2)
- [ ] Verify `Pillow` available for icon composition tests

---

## Observable vs Introspective Validation

### Observable (state-assertion — test code observes UI state)

| Requirement | Observable behavior | Test |
|-------------|---------------------|------|
| **OVR-01** | Overlay window created with overrideredirect=True + topmost=True | `test_overlay_created_borderless_topmost` |
| **OVR-02** | Drag → new position → restart → position restored | `test_position_persisted_round_trip` (mock settings) |
| **OVR-04** | Click overlay → main_window.winfo_viewable() toggles | `test_overlay_click_toggles_window` |
| **OVR-05** | When tasks are overdue → pulse animation active (bg color changes) | `test_overdue_triggers_pulse` (time-advance, check bg color array) |
| **OVR-06** | on_top toggle → both overlay and window topmost attr set | `test_on_top_propagates_to_both` |
| **TRAY-01** | pystray.Icon created with correct menu items | `test_tray_menu_has_all_items` |
| **TRAY-02** | Toggle menu item callbacks update settings + LocalStorage.save_settings called | `test_tray_toggles_update_settings` |
| **TRAY-03** | settings changes apply instantly (no restart needed) | `test_theme_switch_live` |
| **NOTIF-01** | Mode "Только pulse" → winotify NOT called; pulse DOES | `test_notify_mode_pulse_only` |
| **NOTIF-02** | Mode "Звук+pulse" → winotify.Notification called with title/body | `test_notify_mode_sound_and_pulse` |
| **NOTIF-04** | Mode "Тихо" → neither winotify nor pulse | `test_notify_mode_quiet` |

### Introspective (white-box — check internal state)

| Requirement | Internal signal | Check |
|-------------|-----------------|-------|
| **OVR-03** | Position (x, y, monitor_id) stored; restore validates monitor still exists | `test_monitor_unplugged_fallback_to_primary` |
| **OVR-05** (anim internals) | `after()` cycle running at ~60fps during overdue | `test_pulse_animation_interval_16ms` |
| **TRAY-04** | pystray.Icon runs via `run_detached()`; all callbacks use `root.after(0, ...)` | grep `run_detached\|root.after(0` >= expected count |
| **NOTIF-03** | Deadline approaching → notify scheduler fires callback | `test_deadline_notification_scheduled` |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|--------------|
| Overlay visually looks right on real Windows 11 | OVR-all | Visual QA — no CI pixel compare | Owner runs `python main.py`, confirms квадрат outside, click toggles окно |
| Multi-monitor drag works | OVR-03 | Requires 2-monitor hardware | Owner drags between monitors on work PC |
| 20 rapid tray-menu clicks no crash | TRAY-04 | Threading test only reliable with real pystray | Owner does 20 clicks, checks no RuntimeError traceback |
| Toast appears in Windows notification center | NOTIF-02 | Requires real Windows Action Center | Owner triggers test notification, confirms appears |
| Autostart registers in HKCU\...\Run | TRAY-03 | Touches real registry | Owner toggles autostart, reboots, confirms app starts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set after planner refines

**Approval:** pending (planner refines, gsd-plan-checker validates)
