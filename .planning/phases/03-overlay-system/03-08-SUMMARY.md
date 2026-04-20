---
phase: 03-overlay-system
plan: 08
subsystem: ui
tags: [winotify, notifications, toast, threading, deadline-detection, dedup]

# Dependency graph
requires:
  - phase: 03-overlay-system
    provides: "UISettings.notifications_mode + VALID_NOTIFICATIONS (plans 01-02)"
  - phase: 02-client-core
    provides: "Task dataclass с time_deadline, done, deleted_at"
provides:
  - "NotificationManager — winotify toast wrapper с 3 режимами"
  - "check_deadlines(tasks) — approaching/overdue окна [-5min, 0]"
  - "fire_scheduled_toasts(tasks) — integrated scheduler с dedup"
  - "set_icon() с Path.resolve() абсолютный путь (PITFALL 7)"
  - "daemon thread для send_toast (PITFALL 3 — non-blocking)"
affects: [03-10, app.py integration, tray-callbacks]

# Tech tracking
tech-stack:
  added: [winotify==1.1.0]
  patterns:
    - "daemon thread для blocking winotify subprocess (PITFALL 3)"
    - "Path.resolve() для абсолютного icon path (PITFALL 7)"
    - "dedup set(tuple[task_id, kind]) для однократных уведомлений"
    - "Optional import winotify внутри _do_show_toast (lazy import)"

key-files:
  created:
    - client/utils/notifications.py
    - client/tests/ui/test_notifications.py
  modified:
    - requirements.txt (добавлен winotify==1.1.0)

key-decisions:
  - "Mode 'silent' и 'pulse_only' оба блокируют send_toast → returns False (NOTIF-01/04)"
  - "winotify импортируется лениво внутри _do_show_toast (не на уровне модуля) — graceful degradation если не установлен"
  - "APPROACHING_WINDOW_MIN=5, OVERDUE_WINDOW_MIN=1 — вынесены как модульные константы для тестирования"
  - "Dedup через set((task_id, kind)) — позволяет повторно уведомить о другом kind (approaching ≠ overdue)"

patterns-established:
  - "send_toast: threading.Thread(daemon=True) — никогда не блокировать mainloop через winotify"
  - "set_icon: Path.resolve() — абсолютный путь обязателен для PowerShell subprocess"
  - "check_deadlines: возвращает list[dict] — caller может инспектировать без отправки"
  - "fire_scheduled_toasts: check + send — удобный entry point для root.after() scheduler"

requirements-completed: [NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04]

# Metrics
duration: 15min
completed: 2026-04-16
---

# Phase 3 Plan 08: NotificationManager Summary

**winotify toast с 3 режимами (sound_pulse/pulse_only/silent) + deadline scheduler в daemon thread (PITFALL 3) + Path.resolve() icon (PITFALL 7)**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-16T08:20:00Z
- **Completed:** 2026-04-16T08:35:00Z
- **Tasks:** 1 (TDD — единственная задача плана)
- **Files modified:** 3 (notifications.py, test_notifications.py, requirements.txt)

## Accomplishments

- NotificationManager с 3 режимами per UI-SPEC §Notifications (NOTIF-01)
- winotify toast в daemon thread — неблокирующий caller (NOTIF-02, PITFALL 3)
- check_deadlines() — обнаружение approaching [0,5min] и overdue [-1min,0] (NOTIF-03)
- silent/pulse_only блокируют send_toast (NOTIF-04)
- Dedup через _sent set — повторные уведомления не дублируются
- Path.resolve() для абсолютного icon path (PITFALL 7)
- 28 тестов зелёных, все acceptance criteria подтверждены grep-проверками

## Task Commits

1. **Task 1: NotificationManager + тесты (TDD)** - `c7285cf` (feat)

## Files Created/Modified

- `client/utils/notifications.py` — NotificationManager с 3 режимами, winotify daemon thread, deadline scheduler
- `client/tests/ui/test_notifications.py` — 28 unit-тестов (NOTIF-01..04, PITFALL 3/7 структурные проверки)
- `requirements.txt` — добавлен winotify==1.1.0

## Decisions Made

- winotify импортируется лениво внутри `_do_show_toast` (не на уровне модуля) — если пакет не установлен, импорт не падает при старте, только при попытке toast в sound_pulse режиме
- Dedup ключ = `(task_id, kind)` — позволяет получить оба уведомления для одной задачи (сначала "approaching", потом "overdue")
- winotify==1.1.0 добавлен в requirements.txt (отклонение Rule 2 — критическая зависимость отсутствовала)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] winotify==1.1.0 добавлен в requirements.txt**
- **Found during:** Task 1 (запуск тестов)
- **Issue:** winotify не был в requirements.txt — тесты падали с `ModuleNotFoundError`
- **Fix:** `pip install winotify==1.1.0` + добавил в requirements.txt
- **Files modified:** requirements.txt
- **Verification:** тесты прошли после установки (28 passed)
- **Committed in:** c7285cf (часть task commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical dependency)
**Impact on plan:** Минимальный — добавление зафиксированной зависимости из RESEARCH.md (D-17, winotify==1.1.0). Scope не изменился.

## Issues Encountered

None — plan executed cleanly after winotify installation.

## User Setup Required

None — winotify устанавливается через pip (requirements.txt). Никаких ручных шагов.

## Next Phase Readiness

- NotificationManager готов к интеграции в Plan 03-10 (app wiring):
  ```python
  # tray callback
  on_notifications_mode_changed=lambda mode: notifications.set_mode(mode)

  # app scheduler (каждую минуту)
  root.after(60_000, lambda: notifications.fire_scheduled_toasts(storage.get_visible_tasks()))
  ```
- NOTIF-01..04 закрыты — Phase 3 requirements по уведомлениям выполнены

## Known Stubs

None — NotificationManager полностью функционален. Все 3 режима работают.
`fire_scheduled_toasts` ещё не вызывается из app.py — это задача Plan 03-10.

## Self-Check: PASSED

- `client/utils/notifications.py` — EXISTS
- `client/tests/ui/test_notifications.py` — EXISTS
- commit `c7285cf` — FOUND
- `daemon=True` в notifications.py — FOUND (PITFALL 3)
- `.resolve()` в notifications.py — FOUND (PITFALL 7)
- 28 tests PASSED

---
*Phase: 03-overlay-system*
*Completed: 2026-04-16*
